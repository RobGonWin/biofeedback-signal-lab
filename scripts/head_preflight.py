"""HEAD preflight utility for configured Wearable Exam Stress endpoints."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_pipeline_config, resolve_repo_path


@dataclass
class PreflightResult:
    url: str
    status_code: int
    content_type: str | None
    content_length_bytes: int | None
    content_length_mb: float | None
    is_within_single_file_limit: bool | None


def read_headers(url: str) -> PreflightResult:
    """Send a HEAD request and summarize response headers."""
    request = Request(url=url, method="HEAD")
    with urlopen(request) as response:  # noqa: S310 - trusted static URL from config
        response_headers = response.headers
        content_length_header = response_headers.get("Content-Length")
        content_length_bytes = int(content_length_header) if content_length_header else None
        content_length_mb = (
            round(content_length_bytes / (1024 * 1024), 3)
            if content_length_bytes is not None
            else None
        )

        preflight_result = PreflightResult(
            url=url,
            status_code=response.status,
            content_type=response_headers.get("Content-Type"),
            content_length_bytes=content_length_bytes,
            content_length_mb=content_length_mb,
            is_within_single_file_limit=None,
        )
        return preflight_result


def evaluate_single_file_limit(
    preflight_result: PreflightResult,
    max_single_file_mb: int,
) -> PreflightResult:
    """Attach the configured single-file limit check to a result."""
    if preflight_result.content_length_mb is None:
        preflight_result.is_within_single_file_limit = None
        return preflight_result

    preflight_result.is_within_single_file_limit = (
        preflight_result.content_length_mb <= max_single_file_mb
    )
    return preflight_result


def write_manifest(results: list[PreflightResult], output_path: Path) -> Path:
    """Persist preflight results as JSON for reproducibility."""
    manifest_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "results": [asdict(result) for result in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    pipeline_config = load_pipeline_config()
    preflight_urls = [
        pipeline_config.dataset.dataset_page_url,
        pipeline_config.dataset.file_listing_url,
        pipeline_config.dataset.data_listing_url,
        pipeline_config.dataset.zip_url,
    ]

    preflight_results: list[PreflightResult] = []
    for preflight_url in preflight_urls:
        preflight_result = read_headers(preflight_url)
        evaluated_result = evaluate_single_file_limit(
            preflight_result,
            pipeline_config.bounded_pull.max_single_file_mb,
        )
        preflight_results.append(evaluated_result)

    manifest_path = write_manifest(
        preflight_results,
        resolve_repo_path(pipeline_config.paths.preflight_manifest_json),
    )
    print(f"wrote preflight manifest: {manifest_path}")


if __name__ == "__main__":
    main()
