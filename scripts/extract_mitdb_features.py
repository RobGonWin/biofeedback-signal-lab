"""Extract curated MIT-BIH features."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract_dataset_features import extract_dataset_features


def main() -> None:
    extract_dataset_features("mitdb")


if __name__ == "__main__":
    main()
