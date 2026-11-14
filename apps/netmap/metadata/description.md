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

## In WikiJS einbetten

**WikiJS 3.x** hat keinen HTML-Editor mehr (nur noch Markdown, AsciiDoc, Visuell) — die Karte wird
daher in eine **Markdown-Seite** als raw HTML eingebettet. Dafür einmalig unter
*Administration → Rendering → HTML → Security* **„Sanitize HTML“ deaktivieren** und
**„Allow iframes“ aktivieren** (ab WikiJS 3.1.x empfohlen), dann einfügen
(Port laut Runtipi-App, hier 8399):

```html
<iframe src="http://<runtipi-host>:8399/netzwerkkarte.html" style="width:100%; height:900px; border:0; border-radius:8px;"></iframe>
```

Alternativ ohne iframe: normaler Markdown-Link auf `http://<runtipi-host>:8399/netzwerkkarte.html`.

Bei HTTPS-WikiJS muss die Karte ebenfalls per HTTPS erreichbar sein (Mixed-Content), z. B. über einen
Reverse Proxy.

## Quelle

Scanner & Karten-Generator: [KaiDeWitzka/netmap](https://github.com/KaiDeWitzka/netmap)
