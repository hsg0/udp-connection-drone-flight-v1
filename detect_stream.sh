#!/usr/bin/env bash
# Run detect_stream.py inside the YOLO virtualenv.
#
#   ./detect_stream.sh                    # detect on the live feed
#   ./detect_stream.sh --conf 0.5
#   ./detect_stream.sh --device cuda      # once the NVIDIA driver works
#
# The venv exists because the system Python is 3.14, which PyTorch has no
# wheels for. Create it with:
#   uv venv --python 3.12 ~/.venvs/yolo
#   uv pip install --python ~/.venvs/yolo/bin/python \
#       --index-url https://download.pytorch.org/whl/cpu torch torchvision
#   uv pip install --python ~/.venvs/yolo/bin/python ultralytics
set -euo pipefail

PYTHON="${YOLO_PYTHON:-$HOME/.venvs/yolo/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "No interpreter at $PYTHON" >&2
  echo "Set YOLO_PYTHON or create the venv (see comments in this script)." >&2
  exit 1
fi

cd "$(dirname "$0")"
exec "$PYTHON" detect_stream.py "$@"
