#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mini-HTTPS-Server fuer die Netzwerkkarte (nur Standardbibliothek).

Liefert das Web-Verzeichnis per TLS auf Port 8080, sobald ein Zertifikat unter
NETZ_CERT/NETZ_KEY existiert (Default: /certs/cert.pem + /certs/key.pem).
Das Zertifikat wird in der Runtipi-App beim ersten Start vom Scanner-Entrypoint
als selbstsigniertes Zertifikat erzeugt; ein eigenes Zertifikat (LAN-CA /
Let's Encrypt / NPM) kann als cert.pem/key.pem dorthin gelegt werden und wird
bevorzugt. Ohne Zertifikat (nach Wartezeit): Fallback auf HTTP.

Zusatz-API (fuer das Menue "Einstellungen" der Karte):
  GET  /api/config -> {"topology": "<raw topology.json>", "lan_parent": "...",
                       "repeater_ips": [...], "snmp_switches": [...], "export": "..."}
  POST /api/config <- dieselben Felder; validiert das Mapping-JSON und die
                      Export-Formate und schreibt /config/topology.json sowie
                      /config/settings.json (NETZ_CONFIG_DIR, Default /config).
                      Die Werte greifen beim naechsten Scan (data/config/ ist
                      der einzige Speicher - eine Datenbank wird nicht benoetigt).
"""
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
EXPORT_FORMATS = ("pdf", "json", "csv", "md")


def _read_settings():
    p = os.path.join(CONFIG_DIR, "settings.json")
    if os.path.exists(p):
        try:
            v = json.load(open(p, encoding="utf-8"))
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    return {}


def _as_list(v):
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


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
        if self.path == "/api/config":
            topo = ""
            p = os.path.join(CONFIG_DIR, "topology.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    topo = f.read()
            st = _read_settings()
            self._send_json({
                "topology": topo,
                "lan_parent": str(st.get("lan_parent", "") or ""),
                "repeater_ips": _as_list(st.get("repeater_ips")),
                "snmp_switches": _as_list(st.get("snmp_switches")),
                "export": str(st.get("export", "") or ""),
            })
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/config":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("JSON-Objekt erwartet")
                topo_raw = str(body.get("topology", ""))
                mapping = json.loads(topo_raw) if topo_raw.strip() else {}
                if not isinstance(mapping, dict):
                    raise ValueError("topology.json muss ein Objekt {ip|mac: parent-ip} sein")
                for k in mapping:
                    if not isinstance(k, str) or not isinstance(mapping[k], str):
                        raise ValueError("topology.json: Schluessel und Werte muessen Strings sein")
                export = str(body.get("export", "")).strip().lower()
                if export:
                    if export == "all":
                        export = ",".join(EXPORT_FORMATS)
                    else:
                        parts = [f.strip() for f in export.split(",") if f.strip()]
                        bad = [f for f in parts if f not in EXPORT_FORMATS]
                        if bad:
                            raise ValueError("unbekannte Export-Formate: %s (erlaubt: %s, all)"
                                             % (",".join(bad), ",".join(EXPORT_FORMATS)))
                        export = ",".join(parts)
                settings = _read_settings()
                settings.update({
                    "lan_parent": str(body.get("lan_parent", "")).strip(),
                    "repeater_ips": _as_list(body.get("repeater_ips")),
                    "snmp_switches": _as_list(body.get("snmp_switches")),
                    "export": export,
                })
                os.makedirs(CONFIG_DIR, exist_ok=True)
                topo_path = os.path.join(CONFIG_DIR, "topology.json")
                if mapping:
                    with open(topo_path, "w", encoding="utf-8") as f:
                        json.dump(mapping, f, ensure_ascii=False, indent=2)
                elif os.path.exists(topo_path):
                    os.remove(topo_path)
                with open(os.path.join(CONFIG_DIR, "settings.json"), "w", encoding="utf-8") as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)
                self._send_json({"ok": True, "devices_mapped": len(mapping),
                                 "export": export,
                                 "repeater_ips": settings["repeater_ips"],
                                 "snmp_switches": settings["snmp_switches"]})
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
    print("Liefere %s auf Port %d (Config-API: /api/config -> %s)" % (WEB_DIR, PORT, CONFIG_DIR), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
