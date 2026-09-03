#!/usr/bin/env bash
# Turn the Pi's built-in radio (wlan1) into the access point for the direct
# telemetry link. Run this ON THE PI as root:
#
#   sudo ~/pihawk-camera/setup_ap.sh
#
# Only wlan1 is touched, so the LAN connection on wlan0 (and your SSH session)
# stays up.
set -euo pipefail

IFACE="${AP_IFACE:-wlan1}"
CON="${AP_CON:-pihawk-ap}"
SSID="${AP_SSID:-pihawk-link}"
PSK="${AP_PSK:-pihawk-telemetry}"
ADDR="${AP_ADDR:-10.0.0.1/24}"
CHANNEL="${AP_CHANNEL:-6}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Must run as root: sudo $0" >&2
  exit 1
fi

if ! nmcli -t -f DEVICE device status | grep -qx "$IFACE"; then
  echo "No such interface: $IFACE" >&2
  exit 1
fi

echo "==> Replacing any existing '$CON' profile"
nmcli con delete "$CON" >/dev/null 2>&1 || true

echo "==> Creating AP profile on $IFACE (SSID '$SSID', channel $CHANNEL)"
nmcli con add type wifi ifname "$IFACE" con-name "$CON" ssid "$SSID" autoconnect no
# Band bg (2.4 GHz) is mandatory: the laptop's RTL8188ETV has no 5 GHz radio.
nmcli con modify "$CON" 802-11-wireless.mode ap \
  802-11-wireless.band bg 802-11-wireless.channel "$CHANNEL"
nmcli con modify "$CON" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK"
# never-default keeps the Pi's default route on wlan0 instead of this link.
nmcli con modify "$CON" ipv4.method manual ipv4.addresses "$ADDR" \
  ipv4.never-default yes
nmcli con modify "$CON" ipv6.method disabled

echo "==> Bringing up the AP"
nmcli con up "$CON"

echo
echo "==> $IFACE address"
ip -br addr show "$IFACE"
echo "==> Default route (must still be wlan0)"
ip route | grep '^default' || echo "WARNING: no default route"
echo
echo "AP is up. Bring up the laptop side with:  nmcli con up pihawk-link"
