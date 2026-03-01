#!/usr/bin/env python3
"""OpenClaw local skill runner for V2T.

Features:
- Accept online video URL(s)
- Download audio and transcribe via existing V2T pipeline
- Default output: ~/Downloads/v2t-output
- Model tiers: tiny/small/base/medium/large (large -> large-v3)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

V2T_REPO = Path("/Users/yang/Documents/GitHub/V2T")
V2T_ENTRY = V2T_REPO / "v2t.py"
DEFAULT_OUTPUT = Path.home() / "Downloads" / "v2t-output"

MODEL_MAP = {
    "tiny": "tiny",
    "small": "small",
    "base": "base",
    "medium": "medium",
    "large": "large-v3",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="V2T OpenClaw local skill runner (URL -> txt)"
    )
    parser.add_argument("urls", nargs="+", help="One or more online video URLs")
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "small", "base", "medium", "large"],
        help="Whisper model tier (default: small)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Optional language code (e.g. zh, en). Default auto-detect.",
    )
    parser.add_argument(
        "--cookies",
        default=None,
        help="Optional cookies file path for restricted videos.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep downloaded audio files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not V2T_ENTRY.exists():
        print(f"[ERROR] v2t.py not found: {V2T_ENTRY}", file=sys.stderr)
        return 2

    output_dir = Path(args.output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    mapped_model = MODEL_MAP[args.model]

    venv_python = V2T_REPO / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [
        python_bin,
        str(V2T_ENTRY),
        *args.urls,
        "--engine",
        "whisper",
        "--model",
        mapped_model,
        "--format",
        "txt",
        "--output",
        str(output_dir),
    ]

    if args.language:
        cmd.extend(["--language", args.language])
    if args.cookies:
        cmd.extend(["--cookies", str(Path(args.cookies).expanduser())])
    if args.keep_audio:
        cmd.append("--keep-audio")

    print("[v2t-local] Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(V2T_REPO))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
