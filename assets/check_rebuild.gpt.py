#!/usr/bin/env python3
"""Rebuild every generated image and fail on byte drift.

The build runs in a copied checkout, so this check never
rewrites the files it is judging.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = (
    "assets/demo.gif",
    "assets/demo-poster.png",
    "assets/social-preview.png",
)


def main() -> int:
    """Compare a fresh build with every shipped asset."""
    with tempfile.TemporaryDirectory() as temporary:
        copy = Path(temporary) / "replx"
        shutil.copytree(
            ROOT,
            copy,
            ignore=shutil.ignore_patterns(
                ".git",
                "__pycache__",
            ),
        )
        result = subprocess.run(
            [sys.executable, "assets/build.py"],
            cwd=copy,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            return result.returncode

        drifted = []
        for relative in GENERATED:
            shipped = (ROOT / relative).read_bytes()
            rebuilt = (copy / relative).read_bytes()
            if shipped != rebuilt:
                drifted.append(relative)

        if drifted:
            print(
                "generated assets drifted: "
                + ", ".join(drifted),
                file=sys.stderr,
            )
            return 1

    print("OK    generated assets reproduce byte for byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
