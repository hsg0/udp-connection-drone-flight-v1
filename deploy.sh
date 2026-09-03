#!/usr/bin/env bash
# Copy the PiHawk scripts to the drone and optionally run one of them.
#
#   ./deploy.sh                 # copy, then take a picture
#   ./deploy.sh capture --help  # copy, then run capture.py with args
#   ./deploy.sh bridge          # copy, then start the MAVLink UDP bridge
#   ./deploy.sh stream          # copy, then start the live video stream
#   ./deploy.sh none            # copy only
set -euo pipefail

# mDNS rather than a literal address: the Pi's DHCP lease has already moved
# once (192.168.0.138 -> .132) and broke this script.
HOST="${PIHAWK_HOST:-flight-1@flight-1.local}"
REMOTE_DIR="${PIHAWK_DIR:-/home/flight-1/pihawk-camera}"

echo "==> Deploying to ${HOST}:${REMOTE_DIR}"
ssh "$HOST" "mkdir -p '$REMOTE_DIR'"
scp capture.py mavlink_bridge.py setup_ap.sh stream_video.sh "$HOST:$REMOTE_DIR/"

action="${1:-capture}"
[ $# -gt 0 ] && shift

case "$action" in
  capture)
    echo "==> Capturing"
    ssh "$HOST" "python3 '$REMOTE_DIR/capture.py' $*"
    ;;
  bridge)
    echo "==> Starting MAVLink bridge (Ctrl-C to stop)"
    ssh -t "$HOST" "python3 '$REMOTE_DIR/mavlink_bridge.py' $*"
    ;;
  stream)
    echo "==> Starting live video stream (Ctrl-C to stop)"
    ssh -t "$HOST" "'$REMOTE_DIR/stream_video.sh' $*"
    ;;
  none)
    echo "==> Copy only"
    ;;
  *)
    echo "Unknown action '$action' (expected capture, bridge, stream, or none)" >&2
    exit 2
    ;;
esac
