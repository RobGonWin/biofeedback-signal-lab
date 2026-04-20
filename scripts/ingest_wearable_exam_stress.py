"""Download a bounded local slice of the Wearable Exam Stress dataset."""

from __future__ import annotations

import csv
import hashlib
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_pipeline_config, resolve_data_path, resolve_repo_path, to_repo_relative_path


@dataclass
class ManifestRow:
    dataset_name: str
    source_url: str
    file_name: str
    subject_id: str
    session_name: str
    record_group_id: str
    record_id: str
    file_type: str
    file_role: str
    selection_group: str
    discovered_at_utc: str
    content_sha256: str
    content_length_bytes: int | None
    selected_for_download: bool
    download_path: str
    is_within_limit: bool | None


class LinkParser(HTMLParser):
    """Parse href links from the PhysioNet file listing pages."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        href_value = dict(attrs).get("href")
        if href_value is not None:
            self.links.append(href_value)


def fetch_text(url: str) -> str:
    """Fetch text content via GET."""
    request = Request(url=url, method="GET")
    with urlopen(request) as response:  # noqa: S310 - trusted static URLs from config
        response_text = response.read().decode("utf-8", errors="replace")
        return response_text


def read_content_length_bytes(url: str) -> int | None:
    """Send a HEAD request and return content length when present."""
    request = Request(url=url, method="HEAD")
    with urlopen(request) as response:  # noqa: S310 - trusted static URLs from config
        content_length_header = response.headers.get("Content-Length")
        content_length_bytes = int(content_length_header) if content_length_header else None
        return content_length_bytes


def parse_listing_links(listing_html: str) -> list[str]:
    """Extract file or directory names from a simple listing page."""
    link_parser = LinkParser()
    link_parser.feed(listing_html)

    parsed_links: list[str] = []
    for href_link in link_parser.links:
        is_parent_link = href_link.startswith("../")
        if is_parent_link:
            continue
        parsed_links.append(href_link)

    unique_links = sorted(set(parsed_links))
    return unique_links


def list_directory_entries(directory_url: str) -> list[str]:
    """List entries under a directory-style PhysioNet HTML page."""
    listing_html = fetch_text(directory_url)
    listing_entries = parse_listing_links(listing_html)
    return listing_entries


def list_selected_subjects(data_listing_url: str, selected_subject_ids: list[str]) -> list[str]:
    """Filter remote subject directories to the configured bounded slice."""
    available_subject_entries = list_directory_entries(data_listing_url)
    available_subject_ids = {
        entry.rstrip("/")
        for entry in available_subject_entries
        if entry.endswith("/") and entry.rstrip("/").startswith("S")
    }
    missing_subject_ids = sorted(set(selected_subject_ids) - available_subject_ids)
    if missing_subject_ids:
        raise FileNotFoundError(f"missing subject directories: {missing_subject_ids}")

    bounded_subject_ids = [subject_id for subject_id in selected_subject_ids if subject_id in available_subject_ids]
    return bounded_subject_ids


def list_selected_session_files(
    data_listing_url: str,
    subject_id: str,
    session_name: str,
    required_signal_files: list[str],
) -> list[str]:
    """Verify and return the configured required files for one subject session."""
    session_url = f"{data_listing_url}{subject_id}/{session_name}/"
    available_session_entries = list_directory_entries(session_url)
    available_file_names = {entry for entry in available_session_entries if not entry.endswith("/")}
    missing_signal_files = sorted(set(required_signal_files) - available_file_names)
    if missing_signal_files:
        raise FileNotFoundError(
            f"missing required files for {subject_id}/{session_name}: {missing_signal_files}"
        )

    ordered_file_names = [
        file_name for file_name in required_signal_files if file_name in available_file_names
    ]
    return ordered_file_names


def build_manifest_rows() -> list[ManifestRow]:
    """Build manifest rows for configured data files and metadata-only artifacts."""
    pipeline_config = load_pipeline_config(dataset_name="wearable_exam_stress")
    discovered_at_utc = datetime.now(timezone.utc).isoformat()
    manifest_rows: list[ManifestRow] = []

    selected_subject_ids = list_selected_subjects(
        pipeline_config.dataset.data_listing_url,
        pipeline_config.bounded_pull.selected_subject_ids,
    )

    total_selected_bytes = 0
    max_single_file_bytes = pipeline_config.bounded_pull.max_single_file_mb * 1024 * 1024
    max_total_pull_bytes = pipeline_config.bounded_pull.max_total_pull_mb * 1024 * 1024

    for subject_id in selected_subject_ids:
        for session_name in pipeline_config.bounded_pull.selected_session_names:
            selected_file_names = list_selected_session_files(
                pipeline_config.dataset.data_listing_url,
                subject_id,
                session_name,
                pipeline_config.bounded_pull.required_signal_files,
            )

            for file_name in selected_file_names:
                source_url = (
                    f"{pipeline_config.dataset.data_listing_url}{subject_id}/{session_name}/{file_name}"
                )
                content_length_bytes = read_content_length_bytes(source_url)
                is_within_limit = (
                    content_length_bytes <= max_single_file_bytes
                    if content_length_bytes is not None
                    else None
                )
                if is_within_limit is False:
                    raise ValueError(f"file exceeds single-file limit: {source_url}")

                if content_length_bytes is not None:
                    total_selected_bytes += content_length_bytes

                file_type = Path(file_name).stem.lower()
                download_path = resolve_repo_path(
                    f"{pipeline_config.paths.raw_root_directory}/{subject_id}/{session_name}/{file_name}"
                )
                manifest_rows.append(
                    ManifestRow(
                        dataset_name=pipeline_config.dataset.dataset_name,
                        source_url=source_url,
                        file_name=file_name,
                        subject_id=subject_id,
                        session_name=session_name,
                        record_group_id=f"{subject_id}_{session_name}",
                        record_id=f"{subject_id}_{session_name}_{file_name}",
                        file_type=file_type,
                        file_role="signal" if file_name.endswith(".csv") else "metadata",
                        selection_group=f"{subject_id}_{session_name}",
                        discovered_at_utc=discovered_at_utc,
                        content_sha256=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
                        content_length_bytes=content_length_bytes,
                        selected_for_download=True,
                        download_path=to_repo_relative_path(download_path),
                        is_within_limit=is_within_limit,
                    )
                )

    if total_selected_bytes > max_total_pull_bytes:
        raise ValueError(
            "selected data files exceed configured total pull limit: "
            f"{total_selected_bytes} bytes"
        )

    for metadata_file_name in pipeline_config.bounded_pull.include_metadata_files:
        source_url = f"{pipeline_config.dataset.file_listing_url}{metadata_file_name}"
        content_length_bytes = read_content_length_bytes(source_url)
        is_within_limit = (
            content_length_bytes <= max_single_file_bytes
            if content_length_bytes is not None
            else None
        )
        manifest_rows.append(
            ManifestRow(
                dataset_name=pipeline_config.dataset.dataset_name,
                source_url=source_url,
                file_name=metadata_file_name,
                subject_id="",
                session_name="",
                record_group_id="",
                record_id="",
                file_type=Path(metadata_file_name).stem.lower(),
                file_role="metadata",
                selection_group="metadata",
                discovered_at_utc=discovered_at_utc,
                content_sha256=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
                content_length_bytes=content_length_bytes,
                selected_for_download=False,
                download_path="",
                is_within_limit=is_within_limit,
            )
        )

    return manifest_rows


def download_file(source_url: str, output_path: Path) -> str:
    """Download a file and return its content hash."""
    request = Request(url=source_url, method="GET")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sha256_hash = hashlib.sha256()
    with urlopen(request) as response, output_path.open("wb") as output_file:  # noqa: S310
        while True:
            chunk = response.read(1024 * 64)
            if not chunk:
                break
            sha256_hash.update(chunk)
            output_file.write(chunk)

    content_sha256 = sha256_hash.hexdigest()
    return content_sha256


def hash_local_file(file_path: Path) -> str:
    """Hash an existing local file so ingest can resume safely."""
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as input_file:
        while True:
            chunk = input_file.read(1024 * 64)
            if not chunk:
                break
            sha256_hash.update(chunk)
    file_sha256 = sha256_hash.hexdigest()
    return file_sha256


def materialize_downloads(manifest_rows: list[ManifestRow]) -> list[ManifestRow]:
    """Download selected manifest rows and replace URL hashes with content hashes."""
    updated_manifest_rows: list[ManifestRow] = []
    for manifest_row in manifest_rows:
        if manifest_row.selected_for_download:
            download_path = resolve_data_path(manifest_row.download_path)
            can_reuse_existing_file = (
                download_path.exists()
                and manifest_row.content_length_bytes is not None
                and download_path.stat().st_size == manifest_row.content_length_bytes
            )
            if can_reuse_existing_file:
                content_sha256 = hash_local_file(download_path)
            else:
                content_sha256 = download_file(manifest_row.source_url, download_path)
            manifest_row.content_sha256 = content_sha256

        updated_manifest_rows.append(manifest_row)

    return updated_manifest_rows


def write_manifest_csv(manifest_rows: list[ManifestRow], output_path: Path) -> None:
    """Write the bronze manifest as CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    field_names = list(asdict(manifest_rows[0]).keys())
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=field_names)
        writer.writeheader()
        writer.writerows([asdict(manifest_row) for manifest_row in manifest_rows])


def write_manifest_parquet(manifest_rows: list[ManifestRow], output_path: Path) -> None:
    """Write the bronze manifest as Parquet."""
    manifest_frame = pd.DataFrame([asdict(manifest_row) for manifest_row in manifest_rows])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_frame.to_parquet(output_path, index=False)


def main() -> None:
    pipeline_config = load_pipeline_config(dataset_name="wearable_exam_stress")
    manifest_rows = build_manifest_rows()
    downloaded_manifest_rows = materialize_downloads(manifest_rows)

    manifest_csv_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_csv)
    manifest_parquet_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_parquet)
    write_manifest_csv(downloaded_manifest_rows, manifest_csv_path)
    write_manifest_parquet(downloaded_manifest_rows, manifest_parquet_path)

    print(f"wrote bounded raw metadata manifest: {manifest_csv_path}")


if __name__ == "__main__":
    main()
