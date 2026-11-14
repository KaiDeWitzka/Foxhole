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
