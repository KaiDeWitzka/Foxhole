#!/bin/sh
# Netzwerkkarte-Scanner: scannt zyklisch das LAN und schreibt die Karte nach /data/web
set -u
OUT=/data/web
mkdir -p "$OUT"
# TLS-Zertifikat fuer die Web-UI: eigenes cert.pem/key.pem wird bevorzugt,
# sonst selbstsigniertes Zertifikat erzeugen (SAN enthaelt die Host-IP)
CERT_DIR=/data/certs
if [ ! -s "$CERT_DIR/cert.pem" ] || [ ! -s "$CERT_DIR/key.pem" ]; then
  command -v openssl >/dev/null 2>&1 || apk add --no-cache openssl >/dev/null 2>&1
  if command -v openssl >/dev/null 2>&1; then
    mkdir -p "$CERT_DIR"
    HOST_IP=$(hostname -i 2>/dev/null | awk '{print $1}')
    SAN="DNS:localhost,DNS:netmap.local,IP:127.0.0.1"
    [ -n "${HOST_IP:-}" ] && SAN="$SAN,IP:$HOST_IP"
    if openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
        -subj "/CN=netmap.local" -addext "subjectAltName=$SAN" 2>/dev/null; then
      echo "TLS-Zertifikat erzeugt: $CERT_DIR/cert.pem (Web-UI per HTTPS)"
    else
      echo "Zertifikat konnte nicht erzeugt werden - Web-UI bleibt HTTP"
    fi
  else
    echo "openssl nicht verfuegbar - Web-UI bleibt HTTP"
  fi
fi
INTERVAL="${NETZ_SCAN_INTERVAL:-900}"
SUBNET_ARG=""
if [ -n "${NETZ_SUBNET:-}" ]; then
  SUBNET_ARG="--subnet ${NETZ_SUBNET}"
fi
echo "Starte Netzwerkkarte-Scanner (Intervall: ${INTERVAL}s, Subnetz: ${NETZ_SUBNET:-auto})"
while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Scanne Netzwerk ..."
  # shellcheck disable=SC2086
  python3 /opt/netzwerkkarte/netzwerkkarte.py ${SUBNET_ARG} --out-dir "$OUT" || echo "Scan fehlgeschlagen - naechster Versuch in ${INTERVAL}s"
  sleep "$INTERVAL"
done
