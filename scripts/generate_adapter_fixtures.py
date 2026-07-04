#!/usr/bin/env python3
"""Compatibility wrapper for adapter fixture generation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if sys.path[0] != ROOT:
    try:
        sys.path.remove(ROOT)
    except ValueError:
        pass
    sys.path.insert(0, ROOT)

from delegation_bot.adapter_fixtures import main


if __name__ == "__main__":
    raise SystemExit(main())
