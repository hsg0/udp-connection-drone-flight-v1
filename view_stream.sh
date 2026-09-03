#!/usr/bin/env bash
# Display the PiHawk live video feed. Runs ON THE LAPTOP.
#
#   ./view_stream.sh              # watch the feed
#   ./view_stream.sh --stats      # overlay measured framerate
#   ./view_stream.sh --latency 200
#
# Needs the firewall to admit the stream:
#   sudo ufw allow in on wlxa0f4598bacbb to any port 5000 proto udp
set -euo pipefail

PORT=5000
LATENCY=80
STATS=no

usage() {
  cat <<'USAGE'
Usage: view_stream.sh [options]

  --port PORT       UDP port to listen on (default: 5000)
  --latency MS      jitter buffer depth; raise it to smooth a weak link
                    at the cost of delay (default: 80)
  --stats           show measured framerate on the video
  -h, --help        this message
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --port)    PORT="$2"; shift 2 ;;
    --latency) LATENCY="$2"; shift 2 ;;
    --stats)   STATS=yes; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$STATS" = yes ]; then
  sink="fpsdisplaysink video-sink=autovideosink sync=false text-overlay=true"
else
  # sync=false shows frames as they arrive instead of pacing them to a clock,
  # which is what keeps a live feed from drifting behind.
  sink="autovideosink sync=false"
fi

echo "Listening for RTP/H.264 on udp/${PORT} (jitter buffer ${LATENCY}ms)"
echo "Start the drone side with:  ./deploy.sh stream"
echo

exec gst-launch-1.0 -v \
  udpsrc port="$PORT" \
    caps="application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96" \
  ! rtpjitterbuffer latency="$LATENCY" \
  ! rtph264depay \
  ! h264parse \
  ! avdec_h264 \
  ! videoconvert \
  ! $sink
