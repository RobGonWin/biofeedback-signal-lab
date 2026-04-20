"""Download bounded WFDB-style dataset slices for LUDB and MIT-BIH."""

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
    """Parse href links from a simple directory listing page."""

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
    request = Request(url=url, method="GET")
    with urlopen(request) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def read_content_length_bytes(url: str) -> int | None:
    request = Request(url=url, method="HEAD")
    with urlopen(request) as response:  # noqa: S310
        content_length_header = response.headers.get("Content-Length")
        return int(content_length_header) if content_length_header else None


def parse_listing_links(listing_html: str) -> list[str]:
    link_parser = LinkParser()
    link_parser.feed(listing_html)
    parsed_links = [href_link for href_link in link_parser.links if not href_link.startswith("../")]
    return sorted(set(parsed_links))


def list_directory_entries(directory_url: str) -> list[str]:
    return parse_listing_links(fetch_text(directory_url))


def parse_record_index(index_text: str) -> list[str]:
    indexed_record_ids = [line.strip() for line in index_text.splitlines() if line.strip()]
    return indexed_record_ids


def select_record_ids(dataset_name: str) -> list[str]:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    configured_record_ids = pipeline_config.bounded_pull.selected_record_ids
    if configured_record_ids:
        return configured_record_ids

    if pipeline_config.bounded_pull.metadata_index_file:
        index_url = (
            f"{pipeline_config.dataset.file_listing_url}{pipeline_config.bounded_pull.metadata_index_file}"
        )
        indexed_record_ids = parse_record_index(fetch_text(index_url))
        return indexed_record_ids

    raise ValueError(f"no record selection strategy configured for {dataset_name}")


def get_required_record_files(record_id: str, dataset_name: str) -> list[tuple[str, str]]:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    required_files: list[tuple[str, str]] = []
    for file_suffix in pipeline_config.bounded_pull.required_record_suffixes:
        required_files.append((f"{record_id}{file_suffix}", "waveform"))
    for file_suffix in pipeline_config.bounded_pull.required_annotation_suffixes:
        required_files.append((f"{record_id}{file_suffix}", "annotation"))
    return required_files


def build_manifest_rows(dataset_name: str) -> list[ManifestRow]:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    discovered_at_utc = datetime.now(timezone.utc).isoformat()
    manifest_rows: list[ManifestRow] = []
    selected_record_ids = select_record_ids(dataset_name)
    available_entries = set(list_directory_entries(pipeline_config.dataset.data_listing_url))

    max_single_file_bytes = pipeline_config.bounded_pull.max_single_file_mb * 1024 * 1024
    max_total_pull_bytes = pipeline_config.bounded_pull.max_total_pull_mb * 1024 * 1024
    total_selected_bytes = 0

    for record_id in selected_record_ids:
        required_record_files = get_required_record_files(record_id, dataset_name)
        for file_name, file_role in required_record_files:
            if file_name not in available_entries:
                raise FileNotFoundError(f"missing required file for {dataset_name}: {file_name}")

            source_url = f"{pipeline_config.dataset.data_listing_url}{file_name}"
            content_length_bytes = read_content_length_bytes(source_url)
            is_within_limit = (
                content_length_bytes <= max_single_file_bytes if content_length_bytes is not None else None
            )
            if is_within_limit is False:
                raise ValueError(f"file exceeds single-file limit: {source_url}")
            if content_length_bytes is not None:
                total_selected_bytes += content_length_bytes

            download_path = resolve_repo_path(
                f"{pipeline_config.paths.raw_root_directory}/{file_name}"
            )
            manifest_rows.append(
                ManifestRow(
                    dataset_name=pipeline_config.dataset.dataset_name,
                    source_url=source_url,
                    file_name=file_name,
                    subject_id=record_id,
                    session_name="",
                    record_group_id=record_id,
                    record_id=record_id,
                    file_type=Path(file_name).suffix.lstrip(".").lower(),
                    file_role=file_role,
                    selection_group=record_id,
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
            f"selected data files exceed configured total pull limit: {total_selected_bytes} bytes"
        )

    for metadata_file_name in pipeline_config.bounded_pull.include_metadata_files:
        source_url = f"{pipeline_config.dataset.file_listing_url}{metadata_file_name}"
        content_length_bytes = read_content_length_bytes(source_url)
        is_within_limit = (
            content_length_bytes <= max_single_file_bytes if content_length_bytes is not None else None
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
                file_type=Path(metadata_file_name).suffix.lstrip(".").lower() or metadata_file_name.lower(),
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
    return sha256_hash.hexdigest()


def hash_local_file(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as input_file:
        while True:
            chunk = input_file.read(1024 * 64)
            if not chunk:
                break
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def materialize_downloads(manifest_rows: list[ManifestRow]) -> list[ManifestRow]:
    updated_manifest_rows: list[ManifestRow] = []
    for manifest_row in manifest_rows:
        if manifest_row.selected_for_download:
            download_path = resolve_data_path(manifest_row.download_path)
            can_reuse_existing_file = (
                download_path.exists()
                and manifest_row.content_length_bytes is not None
                and download_path.stat().st_size == manifest_row.content_length_bytes
            )
            manifest_row.content_sha256 = (
                hash_local_file(download_path)
                if can_reuse_existing_file
                else download_file(manifest_row.source_url, download_path)
            )
        updated_manifest_rows.append(manifest_row)
    return updated_manifest_rows


def write_manifest_rows(manifest_rows: list[ManifestRow], dataset_name: str) -> None:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    manifest_csv_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_csv)
    manifest_parquet_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_parquet)
    manifest_csv_path.parent.mkdir(parents=True, exist_ok=True)

    field_names = list(asdict(manifest_rows[0]).keys())
    with manifest_csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=field_names)
        writer.writeheader()
        writer.writerows([asdict(manifest_row) for manifest_row in manifest_rows])

    manifest_frame = pd.DataFrame([asdict(manifest_row) for manifest_row in manifest_rows])
    manifest_frame.to_parquet(manifest_parquet_path, index=False)


def ingest_wfdb_dataset(dataset_name: str) -> None:
    manifest_rows = build_manifest_rows(dataset_name)
    downloaded_manifest_rows = materialize_downloads(manifest_rows)
    write_manifest_rows(downloaded_manifest_rows, dataset_name)
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    print(
        "wrote bounded raw metadata manifest: "
        f"{resolve_repo_path(pipeline_config.paths.bronze_manifest_csv)}"
    )
