# Netmap – Netzwerkkarte deines Netzwerks

Scannt dein lokales Netzwerk und zeigt eine **interaktive Karte** aller gefundenen Geräte als Webseite:

- **Netzkomponenten**: Router/Gateway, verwaltete Switche & Access Points
- **Server/NAS und Clients** (anhand typischer Ports und Hersteller erkannt)
- **Smart-Home/IoT-Geräte** (Espressif, Tuya, Philips Hue, Shelly, Sonoff …) und **Drucker**
- Pro Gerät: **IP-Adresse, MAC-Adresse, Hostname, Hersteller (OUI), offene Ports, Kategorie**
  sowie **„Verbunden mit“** (an welchem Router/Switch das Gerät hängt)

Die Karte (eine einzige HTML-Datei, ohne externe Abhängigkeiten) wird **zyklisch neu gescannt** und ist
interaktiv: Zoom/Pan, Klick auf ein Gerät für Details (bei Router/Switch inkl. Liste der
**angeschlossenen Geräte**, in der Karte hervorgehoben), Suche, Kategoriefilter und Tabellenansicht.

## Hinweise

- Der Scanner-Container läuft im **Host-Netzwerkmodus** (`NET_RAW`/`NET_ADMIN`), damit MAC-Adressen
  per ARP aufgelöst werden können. Ohne eigene IP sind unmanaged Switche/Hubs nicht sichtbar.
- **Subnetz** und **Scan-Intervall** sind in den App-Einstellungen von Runtipi konfigurierbar
  (`NETZ_SUBNET`, z. B. `192.168.178.0/24`; `NETZ_SCAN_INTERVAL` in Sekunden, Standard 900).
- Die Ergebnisse liegen unter `data/web/` (`netzwerkkarte.html` + `scan.json`).
- Scanner-Skript und Entrypoint liegen unter `data/app/` im App-Repo und werden bei der Installation
  nach `${APP_DATA_DIR}/data/app` kopiert (dokumentierter Runtipi-Mechanismus). Nach einem App-Update
  am besten kurz neu installieren, damit die neueste Version des Skripts aktiv wird.

## Exporte (PDF, CSV, Markdown, JSON)

Über die App-Einstellung **`NETZ_EXPORT`** (z. B. `all` oder `pdf,csv,md`) werden bei jedem Scan
zusätzliche Exporte nach `data/web/` geschrieben und in der Karte oben rechts als Download-Buttons
angezeigt: `netzwerkkarte.pdf` (A4 quer, reine Standardbibliothek), `netzwerkkarte.csv`,
`netzwerkkarte.md` sowie `scan.json` (JSON, immer vorhanden). Erreichbar z. B. über
`https://<runtipi-host>:8399/netzwerkkarte.pdf`.

## Topologie: wer hängt an welchem Gerät?

Über die App-Einstellungen (Env-Variablen) lässt sich die Zuordnung verbessern — in der Karte
zeigt dann jeder Router/Switch/Repeater seine **angeschlossenen Geräte** (Klick hebt sie hervor;
Panel und Tabelle zeigen „Verbunden mit“):

- **FRITZ!Box / FRITZ!Repeater per TR-064:** `NETZ_FRITZ_URL`, `NETZ_FRITZ_USER`, `NETZ_FRITZ_PASS`
  (TR-064 in der Box aktivieren: *Heimnetz → Netzwerk → Netzwerkeinstellungen → „Anwendungen im
  Heimnetz erlauben (TR-064)“*) + `NETZ_REPEATER_IPS` (kommagetrennte Repeater-IPs aus der
  Mesh-Übersicht). WLAN-Clients werden dem jeweiligen Repeater zugeordnet, WLAN-Clients direkt
  an der Box dem Gateway.
- **Kabelgebundene Clients:** `NETZ_LAN_PARENT` = IP des vorgeschalteten Switches
  (z. B. `192.168.178.2` für einen TL-SG108E; leer = Gateway).
- **Manuelles Mapping:** `NETZ_TOPOLOGY=/data/topology.json` mit
  `{"192.168.178.40": "192.168.178.2"}` (IP oder MAC → Parent-IP). Sinnvoll für Switche ohne
  SNMP/LLDP (z. B. TP-Link TL-SG108E — Stock-Firmware bietet keine MAC-Tabellen-API).
- **SNMPv2c (CAM-Tabelle):** `NETZ_SNMP_COMMUNITY` (Standard: `public`) und optional
  `NETZ_SNMP_SWITCHES` (kommagetrennte IPs; leer = alle als Switch erkannten Geräte). Liest die
  MAC→Port-Tabelle (`dot1dTpFdbTable`) — funktioniert nur bei SNMP-fähigen verwalteten Switchen
  (z. B. TL-SG3xxx, Netgear GSxxxE, MikroTik, UniFi), **nicht** beim TL-SG108E. Ergebnis in der
  Karte: „Switch <IP> Port <N> (SNMP)“. Reihenfolge: TR-064 → SNMP → `topology.json` (manuell gewinnt).

## In WikiJS einbetten

**WikiJS 3.x** hat keinen HTML-Editor mehr (nur noch Markdown, AsciiDoc, Visuell) — die Karte wird
daher in eine **Markdown-Seite** als raw HTML eingebettet. Dafür einmalig unter
*Administration → Rendering → HTML → Security* **„Sanitize HTML“ deaktivieren** und
**„Allow iframes“ aktivieren** (ab WikiJS 3.1.x empfohlen), dann einfügen
(Port laut Runtipi-App, hier 8399):

```html
<iframe src="https://<runtipi-host>:8399/netzwerkkarte.html" style="width:100%; height:900px; border:0; border-radius:8px;"></iframe>
```

Alternativ ohne iframe: normaler Markdown-Link auf `https://<runtipi-host>:8399/netzwerkkarte.html`.

## HTTPS / SSL

Die Web-UI liefert die Karte **per HTTPS** auf dem App-Port (8399) aus:

- Beim ersten Start erzeugt der Scanner ein **selbstsigniertes Zertifikat** in
  `${APP_DATA_DIR}/data/certs/` (SAN enthält die Host-IP des Servers). Im Browser erscheint
  daher eine Zertifikatswarnung — einmal "trotzdem laden" bzw. das Zertifikat im System
  vertrauen (Runtipi ≥ 1.5 bietet dafür ein eigenes Zertifikat an, das man im Runtipi-Dashboard
  unter Einstellungen herunterladen und ins Trust-Store legen kann).
- **Eigenes Zertifikat** (z. B. von LAN-CA, Let's Encrypt oder Nginx Proxy Manager): einfach
  `cert.pem` + `key.pem` nach `${APP_DATA_DIR}/data/certs/` legen — vorhandene Dateien werden
  nicht überschrieben und bevorzugt verwendet.
- Ohne Zertifikat (z. B. kein `openssl` verfügbar): automatischer Fallback auf HTTP.

Damit ist die Karte auch aus einem **HTTPS-WikiJS** per iframe einbettbar (kein Mixed-Content mehr).

## Quelle

Scanner & Karten-Generator: [KaiDeWitzka/netmap](https://github.com/KaiDeWitzka/netmap)
