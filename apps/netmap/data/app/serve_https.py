#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mini-HTTPS-Server fuer die Netzwerkkarte (nur Standardbibliothek).

Liefert das Web-Verzeichnis per TLS auf Port 8080, sobald ein Zertifikat unter
NETZ_CERT/NETZ_KEY existiert (Default: /certs/cert.pem + /certs/key.pem).
Das Zertifikat wird in der Runtipi-App beim ersten Start vom Scanner-Entrypoint
als selbstsigniertes Zertifikat erzeugt; ein eigenes Zertifikat (LAN-CA /
Let's Encrypt / NPM) kann als cert.pem/key.pem dorthin gelegt werden und wird
bevorzugt. Ohne Zertifikat (nach Wartezeit): Fallback auf HTTP.

Zusatz-API (fuer das Topologie-Menue der Karte):
  GET  /api/topology  -> {"topology": "<raw topology.json>", "lan_parent": "..."}
  POST /api/topology  <- {"topology": "...", "lan_parent": "..."}
                        validiert das JSON und schreibt /config/topology.json
                        sowie /config/settings.json (NETZ_CONFIG_DIR, Default /config).
"""
import functools
import http.server
import json
import os
import ssl
import time

WEB_DIR = os.environ.get("NETZ_WEB_DIR", "/data/web")
CERT = os.environ.get("NETZ_CERT", "/certs/cert.pem")
KEY = os.environ.get("NETZ_KEY", "/certs/key.pem")
PORT = int(os.environ.get("NETZ_WEB_PORT", "8080"))
WAIT_CERT_S = int(os.environ.get("NETZ_WAIT_CERT", "60"))
CONFIG_DIR = os.environ.get("NETZ_CONFIG_DIR", "/config")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/topology":
            topo = ""
            p = os.path.join(CONFIG_DIR, "topology.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    topo = f.read()
            lan = ""
            sp = os.path.join(CONFIG_DIR, "settings.json")
            if os.path.exists(sp):
                try:
                    with open(sp, encoding="utf-8") as f:
                        lan = json.load(f).get("lan_parent", "")
                except Exception:
                    pass
            self._send_json({"topology": topo, "lan_parent": lan})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/topology":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                topo_raw = str(body.get("topology", ""))
                mapping = json.loads(topo_raw) if topo_raw.strip() else {}
                if not isinstance(mapping, dict):
                    raise ValueError("topology.json muss ein Objekt {ip|mac: parent-ip} sein")
                os.makedirs(CONFIG_DIR, exist_ok=True)
                with open(os.path.join(CONFIG_DIR, "topology.json"), "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                with open(os.path.join(CONFIG_DIR, "settings.json"), "w", encoding="utf-8") as f:
                    json.dump({"lan_parent": str(body.get("lan_parent", ""))}, f, ensure_ascii=False, indent=2)
                self._send_json({"ok": True, "devices_mapped": len(mapping)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 400)
            return
        self.send_error(404)


def main():
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
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
    print("Liefere %s auf Port %d (Config-API: /api/topology -> %s)" % (WEB_DIR, PORT, CONFIG_DIR), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
