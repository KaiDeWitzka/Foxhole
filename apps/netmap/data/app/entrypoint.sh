#!/bin/sh
# Netzwerkkarte-Scanner: scannt zyklisch das LAN und schreibt die Karte nach /data/web
set -u
OUT=/data/web
mkdir -p "$OUT"
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
