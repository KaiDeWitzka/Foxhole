#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netzwerkkarte.py - Scannt das lokale Netzwerk und erzeugt eine interaktive,
single-file HTML-Netzwerkkarte (netzwerkkarte.html), die z. B. in WikiJS
per <iframe> eingebettet werden kann.

Nur Python-Standardbibliothek, keine externen Pakete.

Aufruf:
  python3 netzwerkkarte.py                          # scannt lokales Subnetz -> scan.json + netzwerkkarte.html
  python3 netzwerkkarte.py --subnet 192.168.1.0/24  # anderes Subnetz scannen
  python3 netzwerkkarte.py --from scan.json         # HTML nur aus vorhandenen Scan-Daten neu erzeugen
  python3 netzwerkkarte.py --demo                   # Demodaten erzeugen (Vorschau ohne Scan)
  python3 netzwerkkarte.py --vendor-api             # Hersteller zusätzlich online nachschlagen (api.macvendors.com)

Erkannt werden u. a.: Router/Gateway, Switche/Netzwerkgeraete, Server/NAS,
Clients, Drucker und Smart-Home-/IoT-Geraete inkl. IP, MAC, Hostname,
Hersteller (OUI) und offenen Ports.
"""

import argparse
import concurrent.futures as cf
import ipaddress
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Hersteller-Datenbank (OUI, kuratierte Auswahl haeufiger Hersteller)
# Schluessel: erste 3 Oktette der MAC ohne Trennzeichen, Grossbuchstaben.
# Erweiterbar - unbekannte Prefixe liefern "Unbekannt".
# ---------------------------------------------------------------------------
OUI = {
    "00040E": "AVM (FRITZ!)",
    "001132": "Synology",
    "245EBE": "QNAP",
    "00089B": "QNAP",
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Foundation",
    "E45F01": "Raspberry Pi Foundation",
    "246F28": "Espressif (ESP8266/ESP32)",
    "30AEA4": "Espressif (ESP8266/ESP32)",
    "5CCF7F": "Espressif (ESP8266/ESP32)",
    "ECFABC": "Espressif (ESP8266/ESP32)",
    "68C63A": "Espressif (ESP8266/ESP32)",
    "A4CF12": "Espressif (ESP8266/ESP32)",
    "600194": "ITEAD (Sonoff)",
    "24A43C": "Ubiquiti",
    "0418D6": "Ubiquiti",
    "68D79A": "Ubiquiti",
    "DC9FDB": "Ubiquiti",
    "E063DA": "Ubiquiti",
    "50C7BF": "TP-Link",
    "001D0F": "TP-Link",
    "B04E26": "TP-Link",
    "00095B": "Netgear",
    "A06391": "Netgear",
    "001788": "Philips Lighting / Signify (Hue)",
    "ECB5FA": "Signify (Hue)",
    "000E58": "Sonos",
    "48A6B8": "Sonos",
    "5CAAFD": "Sonos",
    "008077": "Brother (Drucker)",
    "001E8F": "Canon (Drucker)",
    "000048": "Epson (Drucker)",
    "000BA2": "Epson (Drucker)",
    "70EE50": "Netatmo",
    "ACBC32": "Apple",
    "0017F2": "Apple",
    "001F5B": "Apple",
    "002500": "Apple",
    "001632": "Samsung",
    "001D25": "Samsung",
    "002119": "Samsung",
    "00155D": "Microsoft (Hyper-V)",
    "000D3A": "Microsoft",
    "002248": "Microsoft",
    "0002B3": "Intel",
    "6805CA": "Intel",
    "001422": "Dell",
    "00219B": "Dell",
    "001AA0": "Dell",
    "001F29": "HP / HPE",
    "001708": "HP / HPE",
    "3CD92B": "HPE / Aruba",
    "000C42": "MikroTik",
    "4C5E0C": "MikroTik",
    "D4CA6D": "MikroTik",
    "B869F4": "MikroTik",
    "000C6E": "ASUS",
    "001D60": "ASUS",
    "002215": "ASUS",
    "04D4C4": "ASUS",
    "50465D": "ASUS",
    "001349": "Zyxel",
    "0019CB": "Zyxel",
    "001B11": "D-Link",
    "000F3D": "D-Link",
    "001CF0": "D-Link",
    "1CBDD9": "D-Link",
    "0014EE": "Western Digital",
    "001882": "Huawei",
    "00259E": "Huawei",
    "00466B": "Huawei",
    "001E10": "Huawei",
    "34CE00": "Xiaomi",
    "582D34": "Xiaomi",
    "286C07": "Xiaomi",
    "6490C1": "Xiaomi",
    "F4F5E8": "Xiaomi",
    "10FEED": "Tuya (Smart-Home)",
    "44650D": "Tuya (Smart-Home)",
    "48E1E9": "Tuya (Smart-Home)",
    "5002A9": "Tuya (Smart-Home)",
    "34987A": "Allterco (Shelly)",
    "18B430": "Google (Nest)",
    "00FC8B": "Amazon (Echo)",
    "50F5DA": "Amazon (Echo)",
    "6837E9": "Amazon (Echo)",
    "000C29": "VMware",
    "005056": "VMware",
}

# Haeufig gescannte Ports -> Dienstname
PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB", 465: "SMTPS",
    587: "SMTP (Submission)", 631: "IPP (Drucker)", 993: "IMAPS", 995: "POP3S",
    1883: "MQTT", 3000: "HTTP-Alt", 3306: "MySQL", 3389: "RDP",
    5000: "UPnP / HTTP", 5353: "mDNS", 5432: "PostgreSQL", 5683: "CoAP",
    5900: "VNC", 8000: "HTTP-Alt", 8009: "Google Cast", 8080: "HTTP-Proxy",
    8443: "HTTPS-Alt", 8883: "MQTT (TLS)", 9100: "JetDirect (Drucker)",
    10000: "Webmin", 32400: "Plex",
}

# Ports, die bei der reinen "Ist der Host erreichbar?"-Sondierung probiert werden
PROBE_PORTS = (80, 443, 22, 53, 445, 8080, 3389)


def norm_mac(mac):
    return re.sub(r"[^0-9A-Fa-f]", "", mac or "").upper()[:6]


def vendor_of(mac, use_api=False):
    p = norm_mac(mac)
    if len(p) == 6 and p in OUI:
        return OUI[p]
    if use_api and len(p) == 6:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.macvendors.com/" + mac,
                headers={"User-Agent": "netzwerkkarte/1.0"})
            with urllib.request.urlopen(req, timeout=2) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
                if data.get("vendor"):
                    return data["vendor"]
        except Exception:
            pass
    return "Unbekannt" if mac else ""


# ---------------------------------------------------------------------------
# Netzwerk-Infos des eigenen Hosts
# ---------------------------------------------------------------------------
def _hex_to_ip(h):
    return socket.inet_ntoa(struct.pack("<I", int(h, 16)))


def local_net_info():
    """Liefert (local_ip, prefix, gateway, iface) - moeglichst ohne externe Tools."""
    local_ip = None
    prefix = 24
    gateway = None
    iface = None
    if shutil.which("ip"):
        try:
            out = subprocess.run(["ip", "route", "show", "default"],
                                 capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"default via (\d+\.\d+\.\d+\.\d+) dev (\S+)", out)
            if m:
                gateway, iface = m.group(1), m.group(2)
            if iface:
                out2 = subprocess.run(["ip", "-4", "addr", "show", "dev", iface],
                                      capture_output=True, text=True, timeout=5).stdout
                m2 = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", out2)
                if m2:
                    local_ip, prefix = m2.group(1), int(m2.group(2))
        except Exception:
            pass
    if local_ip is None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.0.2.1", 80))  # Verbindung wird nicht wirklich aufgebaut
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"
    if gateway is None:
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) > 2 and parts[1] == "00000000" and parts[3] == "0003":
                        gateway = _hex_to_ip(parts[2])
                        iface = iface or parts[0]
                        break
        except Exception:
            pass
    if prefix == 32:
        # /32 (z. B. Punkt-zu-Punkt): fuer den Scan das lokale /24 annehmen
        prefix = 24
    return local_ip, prefix, gateway, iface


def dns_servers():
    servers = []
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                m = re.match(r"\s*nameserver\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    servers.append(m.group(1))
    except Exception:
        pass
    return servers


def arp_table():
    """IP -> MAC aus der Kernel-ARP-Tabelle."""
    table = {}
    try:
        with open("/proc/net/arp") as f:
            next(f)
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
                    if parts[3] != "00:00:00:00:00:00":
                        table[parts[0]] = parts[3]
    except Exception:
        pass
    if not table and shutil.which("arp"):
        try:
            out = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=5).stdout
            for m in re.finditer(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]{17})", out):
                table[m.group(1)] = m.group(2)
        except Exception:
            pass
    return table


# ---------------------------------------------------------------------------
# Host-Discovery
# ---------------------------------------------------------------------------
def _checksum(data):
    if len(data) % 2:
        data += b"\x00"
    s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF


def icmp_ping(ip, timeout=1.0):
    """Reiner Python-ICMP-Ping (braucht root/CAP_NET_RAW). None = nicht moeglich."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except (PermissionError, OSError):
        return None
    pid = os.getpid() & 0xFFFF
    payload = struct.pack("!BBHHH", 8, 0, 0, pid, 1) + b"netzwerkkarte" + bytes(24)
    csum = _checksum(payload)
    packet = struct.pack("!BBHHH", 8, 0, csum, pid, 1) + payload[8:]
    s.settimeout(timeout)
    try:
        s.sendto(packet, (ip, 0))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = s.recvfrom(1024)
            except socket.timeout:
                break
            if addr[0] == ip and len(data) >= 28 and data[20] == 0:  # Echo-Reply
                return True
        return False
    except OSError:
        return False
    finally:
        s.close()


def tcp_probe(ip, timeout=0.5):
    for p in PROBE_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            if s.connect_ex((ip, p)) == 0:
                return True
        except OSError:
            pass
        finally:
            s.close()
    return False


def ping_system(ip, timeout=1):
    if not shutil.which("ping"):
        return None
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", str(timeout), ip],
                           capture_output=True, timeout=timeout + 2)
        return r.returncode == 0
    except Exception:
        return None


def host_alive(ip, arp):
    if ip in arp:
        return True
    r = ping_system(ip)
    if r is True:
        return True
    if r is None:
        r = icmp_ping(ip)
        if r is True:
            return True
        if r is None:
            return tcp_probe(ip)
    return False


def resolve_hostname(ip):
    try:
        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(socket.gethostbyaddr, ip)
            return fut.result(timeout=2)[0]
    except Exception:
        return ""


def scan_port(ip, port, timeout=0.6):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        if s.connect_ex((ip, port)) == 0:
            return port
    except OSError:
        pass
    finally:
        s.close()
    return None


# ---------------------------------------------------------------------------
# Klassifikation
# ---------------------------------------------------------------------------
def _has(text, words):
    t = (text or "").lower()
    return any(w in t for w in words)


NET_VENDOR_WORDS = ("cisco", "hp", "hpe", "aruba", "dell", "netgear", "tp-link",
                    "ubiquiti", "mikrotik", "d-link", "asus", "avm", "fritz",
                    "devolo", "zyxel", "linksys", "huawei", "sophos", "fortinet")
IOT_VENDOR_WORDS = ("espressif", "tuya", "xiaomi", "signify", "philips", "hue",
                    "allterco", "shelly", "sonoff", "itead", "netatmo", "nest",
                    "echo", "sonos")
IOT_HOST_WORDS = ("light", "lampe", "lamp", "plug", "steckdose", "sensor",
                  "thermostat", "hue", "ikea", "tradfri", "zigbee", "mqtt",
                  "dect", "rolladen", "rollo", "switch-", "tuya", "shelly")
PRINTER_VENDOR_WORDS = ("brother", "epson", "canon", "lexmark", "xerox", "ricoh",
                        "kyocera", "okidata", "konica", "sharp")
NAS_VENDOR_WORDS = ("synology", "qnap", "western digital", "seagate", "lacie",
                    "terramaster", "asustor")
SERVER_HOST_WORDS = ("nas", "server", "proxmox", "esxi", "vmware", "backup",
                     "pi-hole", "pihole", "homeassistant", "hass", "docker")
SERVER_PORTS = {21, 22, 25, 53, 445, 3306, 3389, 5432, 5900, 10000, 32400, 5000}
PRINTER_PORTS = {9100, 631, 515}
IOT_PORTS = {1883, 8883, 5683, 8009, 5353}


def classify(dev, gateway, dns_list, local_ip):
    ports = {p for p, _ in dev["ports"]}
    vendor = dev.get("vendor") or ""
    host = dev.get("hostname") or ""
    notes = []
    if dev["ip"] == gateway:
        cat = "router"
        notes.append("Standard-Gateway dieses Netzwerks")
    elif ports & PRINTER_PORTS or _has(vendor, PRINTER_VENDOR_WORDS):
        cat = "printer"
    elif (_has(vendor, NAS_VENDOR_WORDS) or _has(host, SERVER_HOST_WORDS)
          or (ports & SERVER_PORTS and len(ports) >= 1 and not _has(vendor, IOT_VENDOR_WORDS))):
        cat = "server"
    elif (_has(vendor, IOT_VENDOR_WORDS) or _has(host, IOT_HOST_WORDS)
          or (ports & IOT_PORTS and not (ports & SERVER_PORTS))):
        cat = "smart"
    elif _has(vendor, NET_VENDOR_WORDS):
        cat = "switch"
        notes.append("verwalteter Switch / Access Point (Web-UI)")
    elif dev.get("mac") or ports:
        cat = "client"
    else:
        cat = "unknown"
    if dev["ip"] in dns_list:
        notes.append("DNS-Server")
    if dev["ip"] == local_ip:
        notes.append("Dieses Geraet (Scanner)")
    dev["category"] = cat
    dev["notes"] = notes
    return dev


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def run_scan(subnet=None, use_api=False, max_hosts=1024):
    local_ip, prefix, gateway, iface = local_net_info()
    dns_list = dns_servers()
    if subnet:
        net = ipaddress.ip_network(subnet, strict=False)
    else:
        net = ipaddress.ip_network("%s/%d" % (local_ip, min(prefix, 24)), strict=False)
    targets = set(str(h) for h in net.hosts())
    for extra in [gateway] + dns_list:
        if extra:
            targets.add(extra)
    targets.discard(local_ip)
    targets = sorted(targets, key=lambda ip: ipaddress.ip_address(ip))[:max_hosts]

    print("Scanne %d Adressen in %s (Gateway: %s, DNS: %s) ..."
          % (len(targets), net, gateway or "?", ", ".join(dns_list) or "?"))
    arp = arp_table()
    alive = []
    with cf.ThreadPoolExecutor(max_workers=64) as ex:
        futs = {ex.submit(host_alive, ip, arp): ip for ip in targets}
        for fut in cf.as_completed(futs):
            ip = futs[fut]
            try:
                if fut.result():
                    alive.append(ip)
            except Exception:
                pass
    # ARP-Tabelle nach dem Scan aktualisieren (Kernel hat MACs aufgelöst)
    arp = arp_table()
    alive = sorted(set(alive) | set(arp.keys()), key=lambda ip: ipaddress.ip_address(ip))
    print("%d aktive Geraete gefunden. Port-Scan ..." % len(alive))

    devices = []
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        host_futs = {ex.submit(resolve_hostname, ip): ip for ip in alive}
        port_futs = {}
        port_ex = cf.ThreadPoolExecutor(max_workers=128)
        for ip in alive:
            for port in PORTS:
                port_futs[port_ex.submit(scan_port, ip, port)] = (ip, port)
        open_ports = {ip: [] for ip in alive}
        for fut in cf.as_completed(port_futs):
            res = fut.result()
            if res:
                ip, port = port_futs[fut]
                open_ports[ip].append([port, PORTS[port]])
        hostnames = {}
        for fut in cf.as_completed(host_futs):
            hostnames[host_futs[fut]] = fut.result() or ""
        port_ex.shutdown(wait=False)

        vendor_ex = cf.ThreadPoolExecutor(max_workers=16)
        vendor_futs = {ex.submit(vendor_of, arp.get(ip, ""), use_api): ip for ip in alive}
        for ip in alive:
            dev = {
                "ip": ip,
                "mac": arp.get(ip, ""),
                "hostname": hostnames.get(ip, ""),
                "vendor": "",
                "ports": sorted(open_ports.get(ip, [])),
                "category": "unknown",
                "notes": [],
            }
            devices.append(classify(dev, gateway, dns_list, local_ip))
        for fut in cf.as_completed(vendor_futs):
            devices[[d["ip"] for d in devices].index(vendor_futs[fut])]["vendor"] = fut.result()
        # Klassifikation erneut mit Herstellerangabe
        for d in devices:
            classify(d, gateway, dns_list, local_ip)

    data = {
        "generated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "subnet": str(net),
        "local_ip": local_ip,
        "gateway": gateway or "",
        "dns": dns_list,
        "devices": devices,
    }
    return data


# ---------------------------------------------------------------------------
# Demodaten (Vorschau ohne Scan)
# ---------------------------------------------------------------------------
def demo_data():
    def d(ip, mac, host, vendor, ports, cat, notes=None):
        return {"ip": ip, "mac": mac, "hostname": host, "vendor": vendor,
                "ports": [[p, PORTS[p]] for p in ports], "category": cat,
                "notes": notes or []}
    return {
        "generated": datetime.now().strftime("%d.%m.%Y %H:%M:%S") + " (Demo)",
        "subnet": "192.168.178.0/24",
        "local_ip": "192.168.178.31",
        "gateway": "192.168.178.1",
        "dns": ["192.168.178.1"],
        "devices": [
            d("192.168.178.1", "34:81:C4:11:22:33", "fritz.box", "AVM (FRITZ!)",
              [53, 80, 443], "router", ["Standard-Gateway dieses Netzwerks", "DNS-Server"]),
            d("192.168.178.2", "00:09:5B:AA:BB:CC", "switch-wohnzimmer", "Netgear",
              [80, 443], "switch", ["verwalteter Switch / Access Point (Web-UI)"]),
            d("192.168.178.3", "24:A4:3C:DD:EE:FF", "ap-kueche", "Ubiquiti",
              [80, 443], "switch", ["verwalteter Switch / Access Point (Web-UI)"]),
            d("192.168.178.10", "00:11:32:12:34:56", "nas", "Synology",
              [22, 80, 443, 445, 5000], "server"),
            d("192.168.178.11", "00:0C:29:65:43:21", "proxmox", "VMware",
              [22, 443, 8006 if 8006 in PORTS else 8080], "server"),
            d("192.168.178.20", "B8:27:EB:11:22:33", "raspberrypi", "Raspberry Pi Foundation",
              [22, 80], "server", ["Dieses Geraet (Scanner)"]),
            d("192.168.178.31", "AC:BC:32:44:55:66", "laptop-anna", "Apple", [22], "client"),
            d("192.168.178.32", "00:16:32:77:88:99", "desktop-pc", "Samsung", [], "client"),
            d("192.168.178.40", "00:80:77:AA:BB:CC", "drucker-hp", "Brother (Drucker)",
              [80, 443, 631, 9100], "printer"),
            d("192.168.178.50", "00:17:88:01:02:03", "hue-bridge", "Philips Lighting / Signify (Hue)",
              [80, 443], "smart"),
            d("192.168.178.51", "24:6F:28:DE:AD:BE", "steckdose-1", "Espressif (ESP8266/ESP32)",
              [80], "smart"),
            d("192.168.178.52", "60:01:94:CA:FE:00", "sonoff-sensor", "ITEAD (Sonoff)",
              [80], "smart"),
            d("192.168.178.53", "34:98:7A:11:22:33", "shelly-wohnzimmer", "Allterco (Shelly)",
              [80], "smart"),
            d("192.168.178.60", "50:C7:BF:10:20:30", "tv", "TP-Link", [8009], "smart"),
        ],
    }


# ---------------------------------------------------------------------------
# HTML-Generierung (single file, keine externenAbhaengigkeiten)
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Netzwerkkarte</title>
<style>
  :root { --bg:#0f1620; --panel:#182230; --panel2:#1f2c3f; --line:#2c3a4f;
          --text:#e8eef6; --muted:#93a4b8; --accent:#4da3ff; }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--text);
              font:14px/1.45 "Segoe UI", system-ui, sans-serif; }
  header { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
           padding:10px 16px; background:var(--panel); border-bottom:1px solid var(--line); }
  .title { font-size:18px; font-weight:600; }
  .title span { font-size:12px; color:var(--muted); font-weight:400; margin-left:10px; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-left:auto; }
  input[type=search] { background:var(--panel2); border:1px solid var(--line); color:var(--text);
                       border-radius:6px; padding:6px 10px; width:230px; }
  #chips { display:flex; flex-wrap:wrap; gap:6px; }
  .chip { border:1px solid var(--line); background:var(--panel2); color:var(--text);
          border-radius:999px; padding:3px 10px; cursor:pointer; font-size:12px; user-select:none; }
  .chip .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; }
  .chip.off { opacity:.35; text-decoration:line-through; }
  .views button, #btnReset { background:var(--panel2); border:1px solid var(--line); color:var(--text);
          border-radius:6px; padding:6px 12px; cursor:pointer; }
  .views button.active { background:var(--accent); border-color:var(--accent); color:#06121f; font-weight:600; }
  main { position:relative; height:calc(100% - 96px); }
  #mapWrap, #tableWrap { position:absolute; inset:0; }
  .hidden { display:none !important; }
  svg { width:100%; height:100%; display:block; cursor:grab; touch-action:none; }
  svg.panning { cursor:grabbing; }
  .edge { stroke:#3a4c63; stroke-width:1.5; }
  .edge.off { display:none; }
  .node { cursor:pointer; }
  .node circle { stroke:#0f1620; stroke-width:2; }
  .node text.icon { font-size:20px; text-anchor:middle; dominant-baseline:central; pointer-events:none; }
  .node text.lbl { font-size:11px; fill:var(--muted); text-anchor:middle; pointer-events:none; }
  .node:hover circle { stroke:#fff; stroke-width:3; }
  .node.dim { opacity:.15; }
  .node.off { display:none; }
  .node.selected circle { stroke:#fff; stroke-width:3.5; }
  #panel { position:absolute; top:12px; right:12px; width:300px; max-height:calc(100% - 24px);
           overflow:auto; background:var(--panel); border:1px solid var(--line);
           border-radius:10px; padding:14px; box-shadow:0 8px 30px rgba(0,0,0,.5); z-index:5; }
  #panel h2 { margin:0 0 2px; font-size:16px; }
  #panel .cat { display:inline-block; font-size:11px; padding:2px 8px; border-radius:999px;
                color:#06121f; font-weight:600; margin:4px 0 10px; }
  #panel table { width:100%; border-collapse:collapse; font-size:13px; }
  #panel td { padding:4px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
  #panel td:first-child { color:var(--muted); width:38%; }
  #panel .ports span { display:inline-block; background:var(--panel2); border:1px solid var(--line);
                       border-radius:5px; padding:1px 7px; margin:2px 2px 0 0; font-size:12px; }
  #panel .note { color:var(--accent); font-size:12px; }
  #panel .close { float:right; background:none; border:none; color:var(--muted);
                  font-size:18px; cursor:pointer; }
  #hint { position:absolute; left:12px; bottom:10px; color:var(--muted); font-size:12px;
          background:rgba(15,22,32,.75); padding:4px 10px; border-radius:6px; pointer-events:none; }
  #tableWrap { overflow:auto; background:var(--bg); }
  #tbl { border-collapse:collapse; width:100%; font-size:13px; }
  #tbl th { position:sticky; top:0; background:var(--panel); text-align:left; padding:8px 10px;
            border-bottom:2px solid var(--line); cursor:pointer; user-select:none; white-space:nowrap; }
  #tbl td { padding:6px 10px; border-bottom:1px solid var(--line); }
  #tbl tr:hover td { background:var(--panel2); }
  .badge { display:inline-block; padding:1px 9px; border-radius:999px; color:#06121f;
           font-size:11px; font-weight:600; }
  footer { padding:6px 16px; color:var(--muted); font-size:11px; background:var(--panel);
           border-top:1px solid var(--line); }
</style>
</head>
<body>
<header>
  <div class="title">Netzwerkkarte <span id="meta"></span></div>
  <div class="controls">
    <input id="search" type="search" placeholder="Suchen: IP, Name, Hersteller ...">
    <div id="chips"></div>
    <div class="views">
      <button id="btnMap" class="active">Karte</button>
      <button id="btnTable">Tabelle</button>
      <button id="btnReset" title="Ansicht zuruecksetzen">Ansicht</button>
    </div>
  </div>
</header>
<main>
  <div id="mapWrap">
    <svg id="svg"><g id="world"><g id="edges"></g><g id="nodes"></g></g></svg>
    <div id="panel" class="hidden"></div>
    <div id="hint">Ziehen = Knoten verschieben &middot; Hintergrund ziehen = verschieben &middot; Mausrad = Zoom &middot; Klick = Details</div>
  </div>
  <div id="tableWrap" class="hidden">
    <table id="tbl">
      <thead><tr>
        <th data-k="ip">IP</th><th data-k="hostname">Hostname</th><th data-k="mac">MAC</th>
        <th data-k="vendor">Hersteller</th><th data-k="category">Kategorie</th>
        <th data-k="ports">Offene Ports</th><th data-k="notes">Notizen</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
</main>
<footer id="foot"></footer>
<script>
"use strict";
const DATA = __DATA_JSON__;
const CATS = {
  internet:{label:"Internet",color:"#7f8c8d",icon:"\u{1F310}"},
  router:{label:"Router / Gateway",color:"#e74c3c",icon:"\u{1F4E1}"},
  switch:{label:"Switch / Netzwerkgeraet",color:"#9b59b6",icon:"\u{1F500}"},
  server:{label:"Server / NAS",color:"#2980b9",icon:"\u{1F5A5}\uFE0F"},
  client:{label:"Client",color:"#27ae60",icon:"\u{1F4BB}"},
  smart:{label:"Smart-Home / IoT",color:"#f39c12",icon:"\u{1F3E0}"},
  printer:{label:"Drucker",color:"#16a085",icon:"\u{1F5A8}\uFE0F"},
  unknown:{label:"Unbekannt",color:"#95a5a6",icon:"\u2753"}
};
const svg=document.getElementById("svg"), world=document.getElementById("world"),
      edgesG=document.getElementById("edges"), nodesG=document.getElementById("nodes"),
      panel=document.getElementById("panel"), search=document.getElementById("search"),
      chipsEl=document.getElementById("chips");
const view={x:20,y:20,k:1};
let nodes=[], edges=[], byId={}, dragging=null, panning=null, moved=false, raf=null;
const NS="http://www.w3.org/2000/svg";

function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function labelOf(n){ if(n.id==="internet") return "Internet";
  const d=n.dev||{}; return d.hostname || d.ip; }

function buildGraph(){
  nodes=[]; edges=[]; byId={};
  const W=svg.clientWidth||1000, H=svg.clientHeight||600, cx=W/2, cy=H/2;
  if(DATA.gateway){
    const inet={id:"internet",category:"internet",x:cx-340,y:cy,vx:0,vy:0,grav:0.004};
    nodes.push(inet); byId["internet"]=inet;
  }
  const devs=DATA.devices||[];
  const hubId=DATA.gateway||"internet";
  devs.forEach((d,i)=>{
    const a=(i/Math.max(1,devs.length))*Math.PI*2;
    const n={id:d.ip,dev:d,category:d.category,x:cx+Math.cos(a)*280+(Math.random()*60-30),
             y:cy+Math.sin(a)*220+(Math.random()*60-30),vx:0,vy:0,
             grav:(d.ip===DATA.gateway?0.02:0.003)};
    nodes.push(n); byId[n.id]=n;
  });
  if(DATA.gateway) edges.push({a:"internet",b:DATA.gateway});
  devs.forEach(d=>{ if(d.ip!==DATA.gateway) edges.push({a:hubId,b:d.ip}); });
  edges.forEach(e=>{
    const l=document.createElementNS(NS,"line");
    l.setAttribute("class","edge"); edgesG.appendChild(l); e.el=l;
  });
  nodes.forEach(n=>{
    const c=CATS[n.category]||CATS.unknown;
    const g=document.createElementNS(NS,"g");
    g.setAttribute("class","node"); g.dataset.id=n.id;
    const cir=document.createElementNS(NS,"circle");
    cir.setAttribute("r","21"); cir.setAttribute("fill",c.color);
    const ic=document.createElementNS(NS,"text");
    ic.setAttribute("class","icon"); ic.textContent=c.icon;
    const lb=document.createElementNS(NS,"text");
    lb.setAttribute("class","lbl"); lb.setAttribute("y","36"); lb.textContent=labelOf(n);
    g.appendChild(cir); g.appendChild(ic); g.appendChild(lb);
    g.addEventListener("pointerdown",ev=>{
      ev.stopPropagation(); moved=false; dragging=n; n.fixed=true;
      svg.setPointerCapture(ev.pointerId); svg.classList.add("panning"); heat();
    });
    nodesG.appendChild(g); n.el=g;
  });
  buildChips();
}

function buildChips(){
  chipsEl.innerHTML="";
  const counts={};
  nodes.forEach(n=>{counts[n.category]=(counts[n.category]||0)+1;});
  Object.keys(counts).forEach(cat=>{
    const c=CATS[cat]||CATS.unknown;
    const el=document.createElement("span");
    el.className="chip"; el.dataset.cat=cat;
    el.innerHTML='<span class="dot" style="background:'+c.color+'"></span>'+esc(c.label)+" ("+counts[cat]+")";
    el.addEventListener("click",()=>{ el.classList.toggle("off");
      hiddenCats.has(cat)?hiddenCats.delete(cat):hiddenCats.add(cat); applyFilters(); });
    chipsEl.appendChild(el);
  });
}

let query="", hiddenCats=new Set();
function applyFilters(){
  nodes.forEach(n=>{
    const d=n.dev||{};
    const text=(n.id+" "+(d.hostname||"")+" "+(d.vendor||"")+" "+(CATS[n.category]?CATS[n.category].label:"")).toLowerCase();
    n.el.classList.toggle("dim", !!query && !text.includes(query));
    n.el.classList.toggle("off", hiddenCats.has(n.category));
  });
  edges.forEach(e=>{
    const a=byId[e.a], b=byId[e.b];
    e.el.classList.toggle("off", (a&&a.el.classList.contains("off"))||(b&&b.el.classList.contains("off")));
  });
}
search.addEventListener("input",()=>{ query=search.value.trim().toLowerCase(); applyFilters(); });

function applyView(){ world.setAttribute("transform","translate("+view.x+" "+view.y+") scale("+view.k+")"); }
function toWorld(ev){ const r=svg.getBoundingClientRect();
  return {x:(ev.clientX-r.left-view.x)/view.k, y:(ev.clientY-r.top-view.y)/view.k}; }

svg.addEventListener("wheel",ev=>{
  ev.preventDefault();
  const r=svg.getBoundingClientRect(), mx=ev.clientX-r.left, my=ev.clientY-r.top;
  const f=Math.exp(-ev.deltaY*0.0012), nk=Math.min(4,Math.max(0.15,view.k*f));
  const wx=(mx-view.x)/view.k, wy=(my-view.y)/view.k;
  view.k=nk; view.x=mx-wx*nk; view.y=my-wy*nk; applyView();
},{passive:false});
svg.addEventListener("pointerdown",ev=>{
  if(ev.target.closest(".node")) return;
  panning={x:ev.clientX,y:ev.clientY,vx:view.x,vy:view.y};
  svg.setPointerCapture(ev.pointerId); svg.classList.add("panning");
});
svg.addEventListener("pointermove",ev=>{
  if(dragging){ const p=toWorld(ev); dragging.x=p.x; dragging.y=p.y; dragging.vx=0; dragging.vy=0; moved=true; render(); }
  else if(panning){ view.x=panning.vx+(ev.clientX-panning.x); view.y=panning.vy+(ev.clientY-panning.y); applyView(); }
});
svg.addEventListener("pointerup",ev=>{
  if(dragging){ dragging.fixed=false; if(!moved) select(dragging); dragging=null; }
  panning=null; svg.classList.remove("panning");
});
document.getElementById("btnReset").addEventListener("click",()=>{
  view.x=20; view.y=20; view.k=1; applyView();
});

function tick(){
  const W=svg.clientWidth||1000, H=svg.clientHeight||600, cx=W/2, cy=H/2;
  for(let i=0;i<nodes.length;i++){ const a=nodes[i];
    for(let j=i+1;j<nodes.length;j++){ const b=nodes[j];
      let dx=a.x-b.x, dy=a.y-b.y, d2=dx*dx+dy*dy+0.01;
      if(d2>300000) continue;
      const d=Math.sqrt(d2), f=9000/d2; dx/=d; dy/=d;
      a.vx+=dx*f; a.vy+=dy*f; b.vx-=dx*f; b.vy-=dy*f;
    }
  }
  edges.forEach(e=>{ const a=byId[e.a], b=byId[e.b]; if(!a||!b) return;
    let dx=b.x-a.x, dy=b.y-a.y; const d=Math.sqrt(dx*dx+dy*dy)||0.01;
    const L=(e.a==="internet")?170:210, f=(d-L)*0.02; dx/=d; dy/=d;
    a.vx+=dx*f; a.vy+=dy*f; b.vx-=dx*f; b.vy-=dy*f;
  });
  let energy=0;
  nodes.forEach(n=>{ if(n.fixed){energy+=Math.abs(n.vx)+Math.abs(n.vy);return;}
    n.vx+=(cx-n.x)*(n.grav||0.003); n.vy+=(cy-n.y)*(n.grav||0.003);
    n.vx*=0.85; n.vy*=0.85; n.x+=n.vx; n.y+=n.vy;
    energy+=Math.abs(n.vx)+Math.abs(n.vy);
  });
  render();
  if(energy>0.6 || dragging){ raf=requestAnimationFrame(tick); } else { raf=null; }
}
function heat(){ if(!raf) raf=requestAnimationFrame(tick); }
function render(){
  edges.forEach(e=>{ const a=byId[e.a], b=byId[e.b]; if(!a||!b) return;
    e.el.setAttribute("x1",a.x); e.el.setAttribute("y1",a.y);
    e.el.setAttribute("x2",b.x); e.el.setAttribute("y2",b.y); });
  nodes.forEach(n=>{ n.el.setAttribute("transform","translate("+n.x+" "+n.y+")"); });
}

function select(n){
  const d=n.dev;
  if(!d){ panel.classList.add("hidden"); return; }
  const c=CATS[d.category]||CATS.unknown;
  const ports=(d.ports||[]).map(p=>"<span>"+esc(p[0])+" "+esc(p[1])+"</span>").join("")||"<span class='note'>keine</span>";
  const notes=(d.notes||[]).map(x=>"<div class='note'>"+esc(x)+"</div>").join("");
  panel.innerHTML="<button class='close' onclick='document.getElementById(\"panel\").classList.add(\"hidden\")'>&times;</button>"
    +"<h2>"+esc(labelOf(n))+"</h2>"
    +"<div class='cat' style='background:"+c.color+"'>"+c.icon+" "+esc(c.label)+"</div>"
    +"<table>"
    +"<tr><td>IP-Adresse</td><td>"+esc(d.ip)+"</td></tr>"
    +"<tr><td>MAC-Adresse</td><td>"+esc(d.mac||"-")+"</td></tr>"
    +"<tr><td>Hostname</td><td>"+esc(d.hostname||"-")+"</td></tr>"
    +"<tr><td>Hersteller</td><td>"+esc(d.vendor||"-")+"</td></tr>"
    +"<tr><td>Offene Ports</td><td class='ports'>"+ports+"</td></tr>"
    +(notes?"<tr><td>Notizen</td><td>"+notes+"</td></tr>":"")
    +"</table>";
  panel.classList.remove("hidden");
  nodes.forEach(x=>x.el.classList.toggle("selected", x===n));
}

let sortKey="ip", sortAsc=true;
function ipNum(ip){ return ip.split(".").reduce((a,p)=>a*256+ +p,0); }
function renderTable(){
  const tb=document.querySelector("#tbl tbody"); tb.innerHTML="";
  const rows=(DATA.devices||[]).slice();
  rows.sort((a,b)=>{
    let va, vb;
    if(sortKey==="ip"){ va=ipNum(a.ip); vb=ipNum(b.ip); }
    else if(sortKey==="ports"){ va=(a.ports||[]).length; vb=(b.ports||[]).length; }
    else if(sortKey==="category"){ va=(CATS[a.category]?CATS[a.category].label:a.category); vb=(CATS[b.category]?CATS[b.category].label:b.category); }
    else { va=String(a[sortKey]||""); vb=String(b[sortKey]||""); }
    return (va<vb?-1:va>vb?1:0)*(sortAsc?1:-1);
  });
  rows.forEach(d=>{
    const c=CATS[d.category]||CATS.unknown;
    const tr=document.createElement("tr");
    tr.innerHTML="<td>"+esc(d.ip)+"</td><td>"+esc(d.hostname||"-")+"</td><td>"+esc(d.mac||"-")+"</td>"
      +"<td>"+esc(d.vendor||"-")+"</td>"
      +"<td><span class='badge' style='background:"+c.color+"'>"+esc(c.label)+"</span></td>"
      +"<td>"+(d.ports||[]).map(p=>esc(p[0])+" "+esc(p[1])).join(", ")+"</td>"
      +"<td>"+esc((d.notes||[]).join("; "))+"</td>";
    tb.appendChild(tr);
  });
}
document.querySelectorAll("#tbl th").forEach(th=>{
  th.addEventListener("click",()=>{
    const k=th.dataset.k;
    if(sortKey===k) sortAsc=!sortAsc; else { sortKey=k; sortAsc=true; }
    renderTable();
  });
});
const btnMap=document.getElementById("btnMap"), btnTable=document.getElementById("btnTable");
btnMap.addEventListener("click",()=>{ btnMap.classList.add("active"); btnTable.classList.remove("active");
  document.getElementById("mapWrap").classList.remove("hidden");
  document.getElementById("tableWrap").classList.add("hidden"); });
btnTable.addEventListener("click",()=>{ btnTable.classList.add("active"); btnMap.classList.remove("active");
  document.getElementById("tableWrap").classList.remove("hidden");
  document.getElementById("mapWrap").classList.add("hidden"); renderTable(); });

document.getElementById("meta").textContent=
  (DATA.devices||[]).length+" Geraete \u00B7 Subnetz "+DATA.subnet+" \u00B7 Scan: "+DATA.generated;
document.getElementById("foot").textContent=
  "Erzeugt von netzwerkkarte.py am "+DATA.generated+" \u00B7 Gateway: "+(DATA.gateway||"nicht gefunden")+
  " \u00B7 Hinweis: Unmanaged Switche/Hubs ohne eigene IP-Adresse sind im Netzwerk nicht sichtbar.";
buildGraph(); applyView(); applyFilters(); heat();
</script>
</body>
</html>
"""


def render_html(data):
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA_JSON__", payload)


def main():
    ap = argparse.ArgumentParser(description="Netzwerk-Scan -> interaktive HTML-Netzwerkkarte")
    ap.add_argument("--subnet", help="z.B. 192.168.1.0/24 (Standard: lokales Subnetz)")
    ap.add_argument("--from", dest="from_file", help="HTML aus vorhandener scan.json erzeugen")
    ap.add_argument("--demo", action="store_true", help="Demodaten statt Scan verwenden")
    ap.add_argument("--vendor-api", action="store_true", help="Hersteller online nachschlagen")
    ap.add_argument("--out-dir", default=".", help="Ausgabeverzeichnis (Standard: aktuelles Verzeichnis)")
    ap.add_argument("--json", default="scan.json", help="Dateiname der JSON-Ergebnisse")
    ap.add_argument("--html", default="netzwerkkarte.html", help="Dateiname der HTML-Karte")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            data = json.load(f)
    elif args.demo:
        data = demo_data()
        with open(os.path.join(args.out_dir, args.json), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        data = run_scan(subnet=args.subnet, use_api=args.vendor_api)
        with open(os.path.join(args.out_dir, args.json), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    html_path = os.path.join(args.out_dir, args.html)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(data))

    print("\nErgebnis:")
    print("  JSON : %s" % os.path.join(args.out_dir, args.json))
    print("  HTML : %s" % html_path)
    print("  %d Geraete: %s" % (
        len(data["devices"]),
        ", ".join("%s (%s)" % (d["ip"], d["category"]) for d in data["devices"]) or "keine"))
    print("\nIn WikiJS einbinden (siehe README.md): Datei z. B. per 'python3 -m http.server 8080' hosten")
    print("und in einer WikiJS-Seite (HTML-Editor) einfuegen:")
    print('  <iframe src="http://<server>:8080/%s" style="width:100%%;height:900px;border:0;"></iframe>' % args.html)


if __name__ == "__main__":
    main()
