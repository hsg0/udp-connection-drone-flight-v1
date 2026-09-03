#!/usr/bin/env bash
# Stream live H.264 video from the PiHawk camera to the ground station as
# RTP over UDP. Runs ON THE PI.
#
#   ./stream_video.sh                          # 720p30 to 10.0.0.2:5000
#   ./stream_video.sh --quality high
#   ./stream_video.sh --quality low --dest 10.0.0.5
#   ./stream_video.sh --width 800 --height 600 --bitrate 2000000
set -euo pipefail

DEST=10.0.0.2
PORT=5000
QUALITY=medium
WIDTH=""
HEIGHT=""
FPS=""
BITRATE=""

usage() {
  cat <<'USAGE'
Usage: stream_video.sh [options]

  --quality low|medium|high   preset (default: medium)
                                low    640x480  @30  1.5 Mbit/s
                                medium 1280x720 @30  4 Mbit/s
                                high   1920x1080@30  6 Mbit/s
  --dest ADDR                 ground station address (default: 10.0.0.2)
  --port PORT                 destination UDP port (default: 5000)
  --width / --height N        override preset resolution
  --framerate N               override preset framerate
  --bitrate BITS_PER_SEC      override preset bitrate
  -h, --help                  this message
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --quality)   QUALITY="$2"; shift 2 ;;
    --dest)      DEST="$2"; shift 2 ;;
    --port)      PORT="$2"; shift 2 ;;
    --width)     WIDTH="$2"; shift 2 ;;
    --height)    HEIGHT="$2"; shift 2 ;;
    --framerate) FPS="$2"; shift 2 ;;
    --bitrate)   BITRATE="$2"; shift 2 ;;
    -h|--help)   usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$QUALITY" in
  low)    p_w=640;  p_h=480;  p_f=30; p_b=1500000 ;;
  medium) p_w=1280; p_h=720;  p_f=30; p_b=4000000 ;;
  high)   p_w=1920; p_h=1080; p_f=30; p_b=6000000 ;;
  *) echo "Unknown quality '$QUALITY' (expected low, medium, or high)" >&2; exit 2 ;;
esac

WIDTH="${WIDTH:-$p_w}"
HEIGHT="${HEIGHT:-$p_h}"
FPS="${FPS:-$p_f}"
BITRATE="${BITRATE:-$p_b}"

if pgrep -x rpicam-vid >/dev/null 2>&1; then
  echo "rpicam-vid is already running; stop it first" >&2
  exit 1
fi

echo "Streaming ${WIDTH}x${HEIGHT} @ ${FPS}fps, $((BITRATE / 1000)) kbit/s"
echo "  -> rtp://${DEST}:${PORT}   (Ctrl-C to stop)"
echo "On the ground station run:  ./view_stream.sh --port ${PORT}"
echo

# rpicam-vid drives the Pi 4's hardware H.264 encoder, so ffmpeg only re-muxes
# into RTP (-c copy) and never re-encodes. --inline repeats SPS/PPS on every
# I-frame so a viewer that joins late can still start decoding.
rpicam-vid \
    -t 0 \
    --nopreview \
    --inline \
    --codec h264 \
    --width "$WIDTH" \
    --height "$HEIGHT" \
    --framerate "$FPS" \
    --bitrate "$BITRATE" \
    -o - \
  | ffmpeg \
      -hide_banner -loglevel warning \
      -fflags nobuffer -flags low_delay \
      -f h264 -i - \
      -c copy -f rtp -flush_packets 1 \
      "udp://${DEST}:${PORT}"
