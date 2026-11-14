#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mini-HTTPS-Server fuer die Netzwerkkarte (nur Standardbibliothek).

Liefert das Web-Verzeichnis per TLS auf Port 8080, sobald ein Zertifikat unter
NETZ_CERT/NETZ_KEY existiert (Default: /certs/cert.pem + /certs/key.pem).
Das Zertifikat wird beim ersten Start vom Scanner-Entrypoint als selbstsigniertes
Zertifikat erzeugt; ein eigenes Zertifikat (z. B. LAN-CA / Let's Encrypt / NPM)
kann einfach als cert.pem/key.pem nach /certs gelegt werden und wird bevorzugt.
Ohne Zertifikat (nach Wartezeit): Fallback auf HTTP.
"""
import functools
import http.server
import os
import ssl
import time

WEB_DIR = os.environ.get("NETZ_WEB_DIR", "/data/web")
CERT = os.environ.get("NETZ_CERT", "/certs/cert.pem")
KEY = os.environ.get("NETZ_KEY", "/certs/key.pem")
PORT = int(os.environ.get("NETZ_WEB_PORT", "8080"))
WAIT_CERT_S = int(os.environ.get("NETZ_WAIT_CERT", "60"))


def main():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=WEB_DIR)
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler)
    waited = 0
    while not (os.path.exists(CERT) and os.path.exists(KEY)) and waited < WAIT_CERT_S:
        time.sleep(2)
        waited += 2
    if os.path.exists(CERT) and os.path.exists(KEY):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(CERT, KEY)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        print("HTTPS aktiv: https://<host>:%d/netzwerkkarte.html (Zertifikat: %s)" % (PORT, CERT), flush=True)
    else:
        print("Kein Zertifikat gefunden (%s) - Fallback auf HTTP" % CERT, flush=True)
    print("Liefere %s auf Port %d" % (WEB_DIR, PORT), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
