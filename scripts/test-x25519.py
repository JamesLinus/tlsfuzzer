# Author: Hubert Kario, (c) 2017
# Released under Gnu GPL v2.0, see LICENSE file for details

from __future__ import print_function
import traceback
import sys
import getopt
import re
from itertools import chain

from tlsfuzzer.runner import Runner
from tlsfuzzer.messages import Connect, ClientHelloGenerator, \
        ClientKeyExchangeGenerator, ChangeCipherSpecGenerator, \
        FinishedGenerator, ApplicationDataGenerator, AlertGenerator, \
        fuzz_message, TCPBufferingEnable, TCPBufferingFlush, \
        TCPBufferingDisable
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectApplicationData, ExpectClose, \
        ExpectServerKeyExchange

from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        ExtensionType, HashAlgorithm, SignatureAlgorithm, GroupName
from tlslite.extensions import SignatureAlgorithmsExtension, TLSExtension, \
        SupportedGroupsExtension


def natural_sort_keys(s, _nsre=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


def help_msg():
    print("Usage: <script-name> [-h hostname] [-p port] [[probe-name] ...]")
    print(" -h hostname    name of the host to run the test against")
    print("                localhost by default")
    print(" -p port        port number to use for connection, 4433 by default")
    print(" probe-name     if present, will run only the probes with given")
    print("                names and not all of them, e.g \"sanity\"")
    print(" -e probe-name  exclude the probe from the list of the ones run")
    print("                may be specified multiple times")
    print(" --help         this message")


def main():
    host = "localhost"
    port = 4433
    run_exclude = set()

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:", ["help"])
    for opt, arg in opts:
        if opt == '-h':
            host = arg
        elif opt == '-p':
            port = int(arg)
        elif opt == '-e':
            run_exclude.add(arg)
        elif opt == '--help':
            help_msg()
            sys.exit(0)
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    conversations = {}

    # check if server selects ECDHE when fully specified
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [GroupName.secp256r1,
              GroupName.secp384r1,
              GroupName.secp521r1]
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    cipher = CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
    node = node.add_child(ExpectServerHello(version=(3, 3),
                                            cipher=cipher))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["sanity"] = conversation

    # check if server selects compatible group if none is selected
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    cipher = CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
    node = node.add_child(ExpectServerHello(version=(3, 3),
                                            cipher=cipher))
    node = node.add_child(ExpectCertificate())
    groups = [GroupName.secp256r1]
    node = node.add_child(ExpectServerKeyExchange(valid_groups=groups))
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["default to P-256 when no groups specified"] = conversation

    # check if server selects compatible group and hash when none specified
    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers))
    cipher = CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
    node = node.add_child(ExpectServerHello(version=(3, 3),
                                            cipher=cipher))
    node = node.add_child(ExpectCertificate())
    groups = [GroupName.secp256r1]
    node = node.add_child(ExpectServerKeyExchange(valid_groups=groups))
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["default to P-256/sha-1 when no extensions specified"] = conversation

    # check if server will fallback to to other cipher when no groups
    # are acceptable
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [GroupName.sect163k1]
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    cipher = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
    node = node.add_child(ExpectServerHello(version=(3, 3),
                                            cipher=cipher))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["only secp163k1 group - fallback to DHE"] = conversation

    # check if server will fallback to to other cipher when no groups
    # are defined
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [11200]
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    cipher = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
    node = node.add_child(ExpectServerHello(version=(3, 3),
                                            cipher=cipher))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["only unknown group - fallback to DHE"] = conversation

    # check if server will abort if no group is acceptable and no fallback
    # is possible
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [11200]
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.handshake_failure))
    node = node.add_child(ExpectClose())
    conversations["only unknown group - no fallback to DHE"] = conversation

    # check if server will not negotiate x25519
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [29,  # ecdh_x25519
              30]  # ecdh_x448
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    # don't specify cipher, let it fail in ServerKeyExchange - it will
    # work out once x25519 is supported
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["only x25519 and x448 groups - allow for DHE fallback"] = conversation

    # check if server will abort if x25519 is not support
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [29,  # ecdh_x25519
              30]  # ecdh_x448
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["only x25519 and x448 groups - no fallback to DHE possible"] = conversation

    # check if server will negotiate X25519
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [29]  # ecdh_x25519
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["sanity - negotiate x25519"] = conversation

    # check if server will negotiate X448
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [30]  # ecdh_x448
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(ExpectClose())
    conversations["sanity - negotiate x448"] = conversation

    # check if server will reject too small x25519 share
    # (one with too few bytes in the key share)
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [29]  # ecdh_x25519
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(TCPBufferingEnable())
    node = node.add_child(ClientKeyExchangeGenerator(ecdh_Yc=bytearray([55] * 31)))
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(TCPBufferingFlush())
    node = node.add_child(TCPBufferingDisable())
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.illegal_parameter))
    node = node.add_child(ExpectClose())
    conversations["too small x25519 key share"] = conversation

    # check if server will reject too big x25519 share
    # (one with too many bytes in the key share)
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [29]  # ecdh_x25519
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(TCPBufferingEnable())
    node = node.add_child(ClientKeyExchangeGenerator(ecdh_Yc=bytearray([55] * 33)))
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(TCPBufferingFlush())
    node = node.add_child(TCPBufferingDisable())
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.illegal_parameter))
    node = node.add_child(ExpectClose())
    conversations["too big x25519 key share"] = conversation

    # check if server will reject x25519 share with high order bit set
    # per draft-ietf-tls-rfc4492bis:
    #
    # Since there are some implementation of the X25519 function that
    # impose this restriction on their input and others that don't,
    # implementations of X25519 in TLS SHOULD reject public keys when the
    # high-order bit of the final byte is set
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [29]  # ecdh_x25519
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(TCPBufferingEnable())
    node = node.add_child(ClientKeyExchangeGenerator(ecdh_Yc=bytearray([55] * 31 + [0x80])))
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(TCPBufferingFlush())
    node = node.add_child(TCPBufferingDisable())
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.illegal_parameter))
    node = node.add_child(ExpectClose())
    conversations["x25519 key share with high bit set"] = conversation

    # check if server will reject too small x448 share
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [30]  # ecdh_x448
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(TCPBufferingEnable())
    node = node.add_child(ClientKeyExchangeGenerator(ecdh_Yc=bytearray([55] * 55)))
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(TCPBufferingFlush())
    node = node.add_child(TCPBufferingDisable())
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.illegal_parameter))
    node = node.add_child(ExpectClose())
    conversations["too small x448 key share"] = conversation

    # check if server will reject too big x448 share
    conversation = Connect(host, port)
    node = conversation
    sigs = [(HashAlgorithm.sha512, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha384, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha256, SignatureAlgorithm.rsa),
            (HashAlgorithm.sha1, SignatureAlgorithm.rsa)]
    ext = {ExtensionType.signature_algorithms:
            SignatureAlgorithmsExtension().create(sigs)}
    groups = [30]  # ecdh_x448
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create(groups)
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(version=(3, 3)))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(TCPBufferingEnable())
    node = node.add_child(ClientKeyExchangeGenerator(ecdh_Yc=bytearray([55] * 57)))
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(TCPBufferingFlush())
    node = node.add_child(TCPBufferingDisable())
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.illegal_parameter))
    node = node.add_child(ExpectClose())
    conversations["too big x448 key share"] = conversation

    # run the conversation
    good = 0
    bad = 0
    failed = []

    # make sure that sanity test is run first and last
    # to verify that server was running and kept running throught
    sanity_test = ('sanity', conversations['sanity'])
    ordered_tests = chain([sanity_test],
                          filter(lambda x: x[0] != 'sanity',
                                 conversations.items()),
                          [sanity_test])

    for c_name, c_test in ordered_tests:
        if run_only and c_name not in run_only or c_name in run_exclude:
            continue
        print("{0} ...".format(c_name))

        runner = Runner(c_test)

        res = True
        try:
            runner.run()
        except:
            print("Error while processing")
            print(traceback.format_exc())
            res = False

        if res:
            good += 1
            print("OK\n")
        else:
            bad += 1
            failed.append(c_name)

    print("Basic test to verify that server selects sane ECDHE parameters and")
    print("ciphersuites when x25519 curve is an option\n")

    print("Test end")
    print("successful: {0}".format(good))
    print("failed: {0}".format(bad))
    failed_sorted = sorted(failed, key=natural_sort_keys)
    print("  {0}".format('\n  '.join(repr(i) for i in failed_sorted)))

    if bad > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
