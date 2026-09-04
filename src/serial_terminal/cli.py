"""Command-line entry point for the serial terminal."""

from __future__ import annotations

import argparse
from pathlib import Path

from .reader import PortSettings
from .tui import TerminalApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor and log multiple serial ports in a Textual TUI.")
    parser.add_argument("ports", nargs="+", metavar="PORT", help="Serial device paths, for example /dev/ttyACM0")
    parser.add_argument("-b", "--baudrate", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--bytesize", type=int, choices=(5, 6, 7, 8), default=8, help="Data bits (default: 8)")
    parser.add_argument("--parity", choices=("N", "E", "O", "M", "S"), type=str.upper, default="N", help="Parity (default: N)")
    parser.add_argument("--stopbits", type=float, choices=(1, 1.5, 2), default=1, help="Stop bits (default: 1)")
    parser.add_argument("--timeout", type=float, default=0.25, help="Read timeout in seconds (default: 0.25)")
    parser.add_argument("--reconnect-delay", type=float, default=1.0, help="Seconds between reconnect attempts (default: 1.0)")
    parser.add_argument("--log-dir", type=Path, default=Path("log"), help="Directory for per-port logs (default: log)")
    return parser


def parse_args(arguments: list[str] | None = None) -> tuple[list[str], PortSettings, Path]:
    args = build_parser().parse_args(arguments)
    if args.baudrate <= 0 or args.timeout <= 0 or args.reconnect_delay <= 0:
        build_parser().error("--baudrate, --timeout, and --reconnect-delay must be greater than zero")
    return args.ports, PortSettings(args.baudrate, args.bytesize, args.parity, args.stopbits, args.timeout, args.reconnect_delay), args.log_dir


def main(arguments: list[str] | None = None) -> None:
    ports, settings, log_dir = parse_args(arguments)
    TerminalApp(ports, settings, log_dir).run()
