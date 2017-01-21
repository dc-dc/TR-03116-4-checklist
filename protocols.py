#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import socket, ssl
import subprocess
from tls_includes import cipher_suites
from helper import which, logger
from checklist import ca_file

protocols=[
[ssl.PROTOCOL_TLSv1, "TLSv1", False],
[ssl.PROTOCOL_TLSv1_1,"TLSv1.1", False],
[ssl.PROTOCOL_TLSv1_2,"TLSv1.2",True]]

def test_server_for_protocol(hostname,port):
    logger.info("Test die Anforderungen aus Kapitel 2.3")
    logger.info("------------------------------------------------------------------------------------")
    logger.info("Anforderung 2.3.1 Überpreufe die unterstuetzten Protokolle:")
    logger.info("------------------------------------------------------------------------------------")
    test_supported_protocols(hostname,port)

    logger.info("------------------------------------------------------------------------------------")
    logger.info("Anforderung 2.3.2/2.3.3/2.3.4 Überpreufe die unterstuetzten Cipher-Suites:")
    logger.info("------------------------------------------------------------------------------------")
    logger.info("Im Folgenden werden die vom Server unterstützten Cipher-Suites gelistet.")
    logger.info("Unerlaubte Cipher-Suites werden direkt markiert. Allerdings muss aktuelle manuell geprpft werden ")
    logger.info("ob die verpflichtenden cipher-suites umgesetzt sind. Außerdem muss die Priorität der  ")
    logger.info("Cipher Suites aktuell manuell geprüft werden.")

    test_supported_cipher_suites(hostname, port, "RSA")

    logger.info("Tests aus Kapitel 2.3 abgeschlossen.")
    logger.info("Teste die Anforderungen aus Kapitel 2.4")

    #TODO: Ephemeral Parameter
    #TODO: Einstellungen der Bibliothek prüfen

    logger.info("Teste die Anforderungen aus Kapitel 2.5")
    logger.info("------------------------------------------------------------------------------------")
    logger.info("Anforderung 2.5.1 Überpruefe Session Renegotiation")
    logger.info("------------------------------------------------------------------------------------")
    test_session_renegotiation(hostname,port)
    logger.info("------------------------------------------------------------------------------------")
    logger.info("Anforderung 2.5.2 Überpruefe TLS Kompression")
    logger.info("------------------------------------------------------------------------------------")
    test_tls_compression(hostname,port)
    logger.info("------------------------------------------------------------------------------------")
    logger.info("Anforderung 2.5.3 Überpruefe auf Heartbeat-Extension")
    logger.info("------------------------------------------------------------------------------------")
    test_heartbeat_extension(hostname,port)
    logger.info("------------------------------------------------------------------------------------")
    logger.info("Anforderung 2.5.4 Überpruefe auf truncated_hmac-Extension")
    logger.info("------------------------------------------------------------------------------------")
    test_truncated_hmac_extension(hostname,port)

def test_supported_protocols(hostname, port):
    #Kritierum 2.3.1
    for protocol in protocols:
        try:
            context = ssl.SSLContext(protocol[0])
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
            context.load_default_certs()

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_sock = context.wrap_socket(s, server_hostname=hostname)

            ssl_sock.connect((hostname, port))
            if protocol[2]:
                logger.info("Tested server does support " + protocol[1] + " This is the expected behavior")
            else:
                logger.error("Tested server does support " + protocol[1] + " This should not be the case")

        except ssl.SSLError as err:
            if "SSLV3_ALERT_HANDSHAKE_FAILURE" in err.args[1]:
                if not protocol[2]:
                    logger.info("Tested server does not support " + protocol[1] + " This is the expected behavior")
                else:
                    logger.error("Tested server does not support " + protocol[1] + " This should not be the case")


def test_supported_cipher_suites(hostname, port, crypto_type):
#Anforderung 2.3.2/2.3.3/2.3.4

    openssl_cmd_getcert="openssl ciphers"
    proc = subprocess.Popen([openssl_cmd_getcert], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()

    out = out.replace('\n', '').replace('\r', '')
    all_ciphers=out.split(":")
    all_ciphers = filter(None, all_ciphers)
    all_ciphers = filter(None, all_ciphers)

    for cipher in all_ciphers:
        try:
            cipher_list = [x for x in cipher_suites if x[1] == cipher and x[2]==crypto_type ]
            allowed=should=must=optional=False

            if len(cipher_list)==0:
                allowed=False
            elif cipher_list[0][3]=="MUST":
                must=True
                allowed=True
            elif cipher_list[0][3]=="SHOULD":
                should=True
                allowed=True
            elif cipher_list[0][3]=="OPTIONAL":
                optional=True
                allowed=True

            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.set_ciphers(cipher)
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
            context.load_default_certs()

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_sock = context.wrap_socket(s, server_hostname=hostname)
            ssl_sock.connect((hostname, port))
            priority= ssl_sock.cipher()[2]

            if not allowed:
                logger.error("Tested server does support unallowed " + cipher + " with priority " + str(priority) +  " This should not be the case")

            elif must or should or optional:
                logger.info(cipher + " supported with priority " + str(priority) + ". Please check with checklist whether this is appropiate for the current system.")


        except ssl.SSLError as err:
            if "SSLV3_ALERT_HANDSHAKE_FAILURE" in err.args[1] or "NO_CIPHERS_AVAILABLE" in err.args[1]:
                if must:
                    logger.error(cipher + " not supported but required by checklist")
                else:
                    logger.info(cipher + " not supported")



def test_session_renegotiation(hostname, port):
#Anforderung 2.5.1

    openssl_cmd_getcert="sslyze --regular "  + hostname +":"+str(port)

    proc = subprocess.Popen([openssl_cmd_getcert], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()

    if "Client-initiated Renegotiation:    OK - Rejected" in out:
        logger.error("Server supports insecure renegotiation. This shold not be the case")
    else:
        logger.info("Server does not support insecure renegotiation. This is the expected behavior")

    if "Secure Renegotiation:              OK - Supported" in out:
        logger.error("Server supports insecure renegotiation. This shold not be the case")
    else:
        logger.info("Server does not support secure renegotiation based on an extension. This is the expected behavior")


def test_tls_compression(hostname,port):
#Anforderung 2.5.2

    openssl_cmd_getcert=" echo "R" | openssl s_client -CAfile "+ca_file+" -connect "+ hostname +":"+str(port)
    proc = subprocess.Popen([openssl_cmd_getcert], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()

    if "Compression: NONE" in out:
        logger.info("Server does not support compression. This is the expected behavior")
    else:
        logger.error("Server supports compression. This shold not be the case")


def test_heartbeat_extension(hostname,port):
    #Anforderung 2.5.3
    #Thanks to  https://www.feistyduck.com/library/openssl-cookbook/online/ch-testing-with-openssl.html

    openssl_cmd_getcert=" echo Q | openssl s_client -CAfile "+ ca_file + " -connect "+ hostname +":"+str(port)+" -tlsextdebug"
    proc = subprocess.Popen([openssl_cmd_getcert], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()

    if "heartbeat" in out:
        logger.error("Server supports the heartbeat extension. This shold not be the case")
    else:
        logger.info("Server does not support the heartbeat extension. This is the intended behavior")

def test_truncated_hmac_extension(hostname, port):
#Anforderung 2.5.4
    openssl_cmd_getcert=" echo Q | openssl s_client -CAfile "+ ca_file +" -connect "+ hostname +":"+str(port)+" -tlsextdebug"
    proc = subprocess.Popen([openssl_cmd_getcert], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()


    #TODO: wir brauchen mal einen Server mit einer truncated_hmac extension um zu sehen, ob das hier funktioniert.
    if "truncated_hmac" in out:
        logger.error("Server supports the truncated_hmac extension. This shold not be the case")
    else:
        logger.info("Server does not support the truncated_hmac extension. This is the intended behavior")
