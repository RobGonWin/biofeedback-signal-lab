"""Normalize LUDB raw files into staged outputs."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.normalize_wfdb_dataset import normalize_wfdb_dataset


def main() -> None:
    normalize_wfdb_dataset("ludb")


if __name__ == "__main__":
    main()
