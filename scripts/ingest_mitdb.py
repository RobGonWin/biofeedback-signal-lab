"""Download a bounded MIT-BIH slice for optional local analysis."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ingest_wfdb_dataset import ingest_wfdb_dataset


def main() -> None:
    ingest_wfdb_dataset("mitdb")


if __name__ == "__main__":
    main()
