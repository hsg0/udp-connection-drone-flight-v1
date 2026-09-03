#!/usr/bin/env python3
"""Capture a still from the PiHawk's CSI camera and save it to the Desktop."""

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def build_output_path(directory: Path, prefix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return directory / f"{prefix}-{stamp}.jpg"


def capture_with_picamera2(dest: Path, warmup: float) -> bool:
    """Returns False if Picamera2 is not installed, so the caller can fall back."""
    try:
        from picamera2 import Picamera2
    except ImportError:
        return False

    camera = Picamera2()
    try:
        camera.configure(camera.create_still_configuration())
        camera.start()
        # Auto-exposure and auto-white-balance need a moment to converge or the
        # first frame comes out green and underexposed.
        time.sleep(warmup)
        camera.capture_file(str(dest))
    finally:
        camera.close()
    return True


def capture_with_rpicam(dest: Path, warmup: float) -> bool:
    """Returns False if neither CLI tool is present, so the caller can report."""
    executable = shutil.which("rpicam-still") or shutil.which("libcamera-still")
    if executable is None:
        return False

    subprocess.run(
        [
            executable,
            "--nopreview",
            "--timeout",
            str(max(int(warmup * 1000), 1)),
            "--output",
            str(dest),
        ],
        check=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path.home() / "Desktop",
        help="directory to save into (default: ~/Desktop)",
    )
    parser.add_argument(
        "--prefix", default="pihawk", help="filename prefix (default: pihawk)"
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=2.0,
        help="seconds to let exposure settle before the shot (default: 2.0)",
    )
    args = parser.parse_args()

    dest = build_output_path(args.dir, args.prefix)

    try:
        if not capture_with_picamera2(dest, args.warmup):
            print("Picamera2 unavailable, falling back to rpicam-still", file=sys.stderr)
            if not capture_with_rpicam(dest, args.warmup):
                print(
                    "No camera backend found. Install Picamera2 with:\n"
                    "  sudo apt install -y python3-picamera2",
                    file=sys.stderr,
                )
                return 1
    except Exception as exc:
        print(f"Capture failed: {exc}", file=sys.stderr)
        return 1

    if not dest.exists() or dest.stat().st_size == 0:
        print(f"Capture reported success but {dest} is missing or empty", file=sys.stderr)
        return 1

    print(f"Saved {dest} ({dest.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
