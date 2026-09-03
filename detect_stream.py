#!/usr/bin/env python3
"""Run object detection on the PiHawk live video feed. Runs ON THE LAPTOP.

Decoding is handed to GStreamer, which writes raw BGR frames to a pipe. That
avoids depending on OpenCV being built with GStreamer support, which the pip
wheels are not.
"""

import argparse
import shutil
import subprocess
import sys
import threading
import time
from typing import List, Optional

RTP_CAPS = (
    "application/x-rtp,media=(string)video,clock-rate=(int)90000,"
    "encoding-name=(string)H264,payload=(int)96"
)


def gst_command(port: int, latency: int, width: int, height: int) -> List[str]:
    # videoscale lets any sender resolution work: whatever --quality the drone
    # streams gets scaled to the size we run inference on.
    return [
        "gst-launch-1.0", "-q",
        "udpsrc", f"port={port}", f"caps={RTP_CAPS}",
        "!", "rtpjitterbuffer", f"latency={latency}",
        "!", "rtph264depay",
        "!", "h264parse",
        "!", "avdec_h264",
        "!", "videoconvert",
        "!", "videoscale",
        "!", f"video/x-raw,format=BGR,width={width},height={height}",
        "!", "fdsink", "fd=1",
    ]


class LatestFrame:
    """Holds only the newest frame, so slow inference never watches stale video."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[bytes] = None
        self.produced = 0
        self.consumed = 0

    def put(self, frame: bytes) -> None:
        with self._lock:
            self._frame = frame
            self.produced += 1

    def take(self) -> Optional[bytes]:
        with self._lock:
            frame, self._frame = self._frame, None
            if frame is not None:
                self.consumed += 1
            return frame

    @property
    def dropped(self) -> int:
        return self.produced - self.consumed


def read_exact(stream, count: int) -> Optional[bytes]:
    """A pipe hands back at most one pipe-buffer per read, so loop until full."""
    chunks = []
    remaining = count
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def reader(stream, frame_bytes: int, slot: LatestFrame, stop: threading.Event) -> None:
    while not stop.is_set():
        buf = read_exact(stream, frame_bytes)
        if buf is None:
            break
        slot.put(buf)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5000, help="UDP port to listen on")
    parser.add_argument("--latency", type=int, default=80, help="jitter buffer ms")
    parser.add_argument("--width", type=int, default=1280, help="inference width")
    parser.add_argument("--height", type=int, default=720, help="inference height")
    parser.add_argument("--model", default="yolov8n.pt", help="ultralytics weights")
    parser.add_argument("--conf", type=float, default=0.35, help="confidence threshold")
    parser.add_argument(
        "--device", default="cpu", help="cpu, or cuda once the driver works"
    )
    parser.add_argument(
        "--frames", type=int, default=0, help="stop after N frames (0 = forever)"
    )
    parser.add_argument("--no-display", action="store_true", help="skip the window")
    parser.add_argument("--save", help="write the last annotated frame here")
    args = parser.parse_args()

    if shutil.which("gst-launch-1.0") is None:
        print("gst-launch-1.0 not found", file=sys.stderr)
        return 1

    try:
        import cv2
        import numpy as np
        from ultralytics import YOLO
    except ImportError as exc:
        print(
            f"{exc}\nRun through the venv, e.g. ./detect_stream.sh",
            file=sys.stderr,
        )
        return 1

    print(f"Loading {args.model} on {args.device}", flush=True)
    model = YOLO(args.model)

    frame_bytes = args.width * args.height * 3
    pipeline = subprocess.Popen(
        gst_command(args.port, args.latency, args.width, args.height),
        stdout=subprocess.PIPE,
        # Inherit stderr: -q keeps GStreamer quiet unless something is wrong,
        # and hiding it masks the common "port already in use" failure.
        bufsize=0,
    )
    assert pipeline.stdout is not None

    slot = LatestFrame()
    stop = threading.Event()
    pump = threading.Thread(
        target=reader, args=(pipeline.stdout, frame_bytes, slot, stop), daemon=True
    )
    pump.start()

    print(f"Waiting for video on udp/{args.port} ...", flush=True)
    processed = 0
    annotated = None
    last_report = time.monotonic()
    window_frames = 0
    started = None

    try:
        while True:
            raw = slot.take()
            if raw is None:
                if pipeline.poll() is not None:
                    print("GStreamer exited; is the drone streaming?", file=sys.stderr)
                    break
                time.sleep(0.002)
                continue

            if started is None:
                started = time.monotonic()
                print("Video is flowing, running detection", flush=True)

            frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                (args.height, args.width, 3)
            )
            results = model.predict(
                frame, conf=args.conf, device=args.device, verbose=False
            )[0]
            annotated = results.plot()
            processed += 1
            window_frames += 1

            if not args.no_display:
                cv2.imshow("PiHawk detection", annotated)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break

            now = time.monotonic()
            if now - last_report >= 5.0:
                names = results.names
                found = [names[int(c)] for c in results.boxes.cls.tolist()]
                summary = ", ".join(sorted(set(found))) if found else "nothing"
                print(
                    f"{window_frames / (now - last_report):5.1f} fps  "
                    f"dropped {slot.dropped:<6} detected: {summary}",
                    flush=True,
                )
                window_frames = 0
                last_report = now

            if args.frames and processed >= args.frames:
                break
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        stop.set()
        pipeline.terminate()
        try:
            pipeline.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pipeline.kill()
        if not args.no_display:
            cv2.destroyAllWindows()

    if args.save and annotated is not None:
        cv2.imwrite(args.save, annotated)
        print(f"Saved {args.save}")

    if started and processed:
        print(f"{processed} frames in {time.monotonic() - started:.1f}s")
    return 0 if processed else 1


if __name__ == "__main__":
    sys.exit(main())
