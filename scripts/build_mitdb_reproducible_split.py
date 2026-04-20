"""Build deterministic split metadata for MIT-BIH."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reproducible_split_dataset import build_reproducible_split_dataset


def main() -> None:
    build_reproducible_split_dataset("mitdb")


if __name__ == "__main__":
    main()
