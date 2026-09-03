#!/usr/bin/env python3
"""Bridge the Pixhawk's MAVLink serial stream to a ground station over UDP."""

import argparse
import select
import socket
import sys
import time
from typing import Tuple

import serial

Endpoint = Tuple[str, int]


def parse_endpoint(text: str) -> Endpoint:
    host, separator, port = text.rpartition(":")
    if not separator:
        raise argparse.ArgumentTypeError(f"expected HOST:PORT, got {text!r}")
    try:
        return host, int(port)
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad port in {text!r}") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serial", default="/dev/ttyACM0", help="flight controller serial port"
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="ignored for USB CDC ports, needed for real UARTs",
    )
    parser.add_argument(
        "--gcs",
        type=parse_endpoint,
        default=("10.0.0.2", 14550),
        help="where to send telemetry (default: 10.0.0.2:14550)",
    )
    parser.add_argument(
        "--port", type=int, default=14550, help="local UDP port to bind"
    )
    parser.add_argument(
        "--stats",
        type=float,
        default=5.0,
        help="seconds between throughput lines, 0 to disable",
    )
    args = parser.parse_args()

    try:
        link = serial.Serial(args.serial, args.baud, timeout=0)
    except serial.SerialException as exc:
        print(f"Cannot open {args.serial}: {exc}", file=sys.stderr)
        return 1

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Lets --gcs point at a subnet broadcast such as 10.0.0.255.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", args.port))

    gcs: Endpoint = args.gcs
    to_gcs = to_fc = 0
    last_report = time.monotonic()
    print(
        f"Bridging {args.serial} <-> udp/{args.port}, sending to {gcs[0]}:{gcs[1]}",
        flush=True,
    )

    try:
        while True:
            readable, _, _ = select.select([link, sock], [], [], 1.0)

            if link in readable:
                data = link.read(4096)
                if data:
                    sock.sendto(data, gcs)
                    to_gcs += len(data)

            if sock in readable:
                data, sender = sock.recvfrom(4096)
                # The ground station may arrive on a different address than the
                # default, so trust whoever actually talks to us.
                if sender != gcs:
                    print(f"Ground station is {sender[0]}:{sender[1]}")
                    gcs = sender
                link.write(data)
                to_fc += len(data)

            now = time.monotonic()
            if args.stats and now - last_report >= args.stats:
                window = now - last_report
                print(
                    f"to GCS {to_gcs / window:7.0f} B/s   "
                    f"to FC {to_fc / window:7.0f} B/s",
                    flush=True,
                )
                to_gcs = to_fc = 0
                last_report = now
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        link.close()
        sock.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
