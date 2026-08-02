#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows-compatible LiCSAR downloader whose output layout matches
LiCSBAS2 LiCSBAS01_get_geotiff.py.

Default layout:
  OUTPUT_PARENT/FRAME_ID/
  ├─ GEOC/
  │  ├─ YYYYMMDD_YYYYMMDD/
  │  │  ├─ YYYYMMDD_YYYYMMDD.geo.unw.tif
  │  │  └─ YYYYMMDD_YYYYMMDD.geo.cc.tif
  │  ├─ FRAME_ID.geo.E.tif
  │  ├─ FRAME_ID.geo.N.tif
  │  ├─ FRAME_ID.geo.U.tif
  │  ├─ FRAME_ID.geo.hgt.tif
  │  ├─ FRAME_ID.geo.mli.tif
  │  ├─ baselines
  │  ├─ network.png
  │  └─ metadata.txt
  └─ GACOS/                         (only with --get_gacos)
     └─ YYYYMMDD.sltd.geo.tif

The script is independent from LiCSBAS2, but follows its naming and directory
conventions so the downloaded frame directory can later be copied/mounted into
Linux and processed from LiCSBAS2 step 02 onward.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

VERSION = "1.2.4"
DEFAULT_BASE_URL = (
    "https://gws-access.jasmin.ac.uk/public/"
    "nceo_geohazards/LiCSAR_products/"
)
FRAME_RE = re.compile(r"^\d{3}[AD]_\d{5}_\d{6}$")
PAIR_RE = re.compile(r"^\d{8}_\d{8}$")
DATE_RE = re.compile(r"^\d{8}$")


@dataclass(frozen=True)
class RemoteFile:
    url: str
    local_path: Path
    category: str
    label: str


@dataclass
class Result:
    category: str
    label: str
    local_path: str
    url: str
    status: str
    bytes_local: int = 0
    message: str = ""
    bytes_transferred: int = 0


@dataclass
class Settings:
    frame: str
    start: dt.date
    end: dt.date
    output_parent: Path
    workers: int = 4
    get_gacos: bool = False
    download_mli: bool = True
    download_all_mli: bool = False
    base_url: str = DEFAULT_BASE_URL
    timeout_connect: float = 20.0
    timeout_read: float = 180.0
    retries: int = 4
    overwrite: bool = False
    dry_run: bool = False
    verify_tls: bool = True
    user_agent: str = "LiCSAR-Windows-Downloader/1.1.2"
    progress_interval: float = 10.0

    @property
    def track(self) -> str:
        return str(int(self.frame[:3]))

    @property
    def frame_dir(self) -> Path:
        # If the supplied output directory already ends with the frame ID,
        # do not create FRAME/FRAME accidentally.
        if self.output_parent.name.lower() == self.frame.lower():
            return self.output_parent
        return self.output_parent / self.frame

    @property
    def geoc_dir(self) -> Path:
        return self.frame_dir / "GEOC"

    @property
    def gacos_dir(self) -> Path:
        return self.frame_dir / "GACOS"

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.timeout_connect, self.timeout_read)


class DownloadError(RuntimeError):
    pass


class LiCSARClient:
    def __init__(self, settings: Settings, logger: logging.Logger):
        self.s = settings
        self.log = logger
        self._local = threading.local()

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            retry = Retry(
                total=self.s.retries,
                connect=self.s.retries,
                read=self.s.retries,
                status=self.s.retries,
                backoff_factor=1.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(("HEAD", "GET")),
                raise_on_status=False,
            )
            session.mount("https://", HTTPAdapter(max_retries=retry))
            session.mount("http://", HTTPAdapter(max_retries=retry))
            session.headers.update({"User-Agent": self.s.user_agent})
            self._local.session = session
        return self._local.session

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.s.timeout)
        kwargs.setdefault("allow_redirects", True)
        kwargs.setdefault("verify", self.s.verify_tls)
        return self._session().request(method, url, **kwargs)

    @staticmethod
    def _future_variant(url: str) -> str:
        if "LiCSAR_products.future/" in url:
            return url.replace("LiCSAR_products.future/", "LiCSAR_products/")
        if "LiCSAR_products/" in url:
            return url.replace("LiCSAR_products/", "LiCSAR_products.future/")
        return url

    def get_html(self, url: str) -> tuple[str, str]:
        """Return (final_url, html), trying the current/future archive variants."""
        candidates = [url]
        alt = self._future_variant(url)
        if alt != url:
            candidates.append(alt)
        errors: list[str] = []
        for candidate in candidates:
            try:
                response = self._request("GET", candidate)
                ctype = response.headers.get("Content-Type", "").lower()
                if response.status_code == 200 and (
                    "html" in ctype or "text" in ctype or not ctype
                ):
                    response.encoding = response.apparent_encoding or response.encoding
                    return response.url, response.text
                errors.append(f"{candidate}: HTTP {response.status_code}")
            except requests.RequestException as exc:
                errors.append(f"{candidate}: {exc}")
        raise DownloadError("Cannot read directory listing; " + " | ".join(errors))

    def list_names(self, directory_url: str, pattern: re.Pattern[str]) -> list[str]:
        final_url, html = self.get_html(directory_url)
        soup = BeautifulSoup(html, "html.parser")
        names: set[str] = set()
        for tag in soup.find_all("a", href=True):
            href = str(tag.get("href", ""))
            # Use the final path component, stripping the trailing slash.
            path = urlparse(urljoin(final_url, href)).path.rstrip("/")
            name = Path(path).name
            if pattern.fullmatch(name):
                names.add(name)
        return sorted(names)

    def resolve_file_url(self, expected_url: str) -> Optional[str]:
        """Resolve both legacy direct files and the post-migration link pages.

        The current COMET LiCSBAS helper searches the raw ``href`` text for the
        requested filename.  This matters because migrated JASMIN/CEDA links may
        carry the filename in a query string or another non-basename position.
        """
        candidates: list[str] = []
        for candidate in (expected_url, self._future_variant(expected_url)):
            if candidate not in candidates:
                candidates.append(candidate)

        # Old layout: the expected URL is the data file itself.
        for candidate in candidates:
            try:
                response = self._request("HEAD", candidate)
                ctype = response.headers.get("Content-Type", "").lower()
                if response.status_code == 200 and "text/html" not in ctype:
                    return response.url
            except requests.RequestException:
                pass
            try:
                response = self._request(
                    "GET", candidate, headers={"Range": "bytes=0-0"}, stream=True
                )
                ctype = response.headers.get("Content-Type", "").lower()
                if response.status_code in (200, 206) and "text/html" not in ctype:
                    final_url = response.url
                    response.close()
                    return final_url
                response.close()
            except requests.RequestException:
                pass

        # Migrated layout (JASMIN/CEDA, 2025+): entries under
        # ``interferograms/`` and ``epochs/`` are often small *manifest files*,
        # not real directories.  For example, the valid resolver endpoint is
        # ``.../interferograms/YYYYMMDD_YYYYMMDD`` (no trailing slash), and the
        # response is commonly ``text/plain`` containing HTML <a> links to CEDA.
        # Some frames/transition states still expose a normal directory ending
        # in ``/``.  Try both forms and parse links regardless of content type.
        filename = Path(urlparse(expected_url).path).name
        href_pattern = re.compile(re.escape(filename))
        container_url = expected_url.rsplit("/", 1)[0]

        manifests: list[str] = []
        for base in (container_url, container_url + "/"):
            for candidate in (base, self._future_variant(base)):
                if candidate not in manifests:
                    manifests.append(candidate)

        for manifest_url in manifests:
            try:
                response = self._request("GET", manifest_url)
            except requests.RequestException:
                continue
            if response.status_code != 200:
                response.close()
                continue
            response.encoding = response.apparent_encoding or response.encoding
            text = response.text
            final_manifest_url = response.url
            response.close()

            if "<" in text:
                soup = BeautifulSoup(text, "html.parser")
                tag = soup.find("a", href=href_pattern)
                if tag is None:
                    tag = soup.find(href=href_pattern)
                if tag is not None:
                    href = str(tag.get("href", ""))
                    if href:
                        return urljoin(final_manifest_url, href)

            # Defensive fallback for unusual/plain-text manifests whose link is
            # not parsed as an anchor.  Extract an absolute URL containing the
            # requested filename and trim common trailing delimiters.
            absolute = re.search(
                r"https?://[^\s<>\"']*" + re.escape(filename) + r"[^\s<>\"']*",
                text,
            )
            if absolute:
                return absolute.group(0).rstrip(")],;.")
        return None

    def remote_info(self, url: str) -> tuple[Optional[int], Optional[str], str]:
        """Return content length, Last-Modified, and resolved URL."""
        resolved = self.resolve_file_url(url)
        if not resolved:
            raise DownloadError("Remote file is unavailable")
        try:
            response = self._request("HEAD", resolved)
            ctype = response.headers.get("Content-Type", "").lower()
            if response.status_code == 200 and "text/html" not in ctype:
                length = response.headers.get("Content-Length")
                return (
                    int(length) if length and length.isdigit() else None,
                    response.headers.get("Last-Modified"),
                    response.url,
                )
        except requests.RequestException:
            pass
        # Fallback to a streamed GET. Do not read the body.
        response = self._request(
            "GET", resolved, headers={"Range": "bytes=0-0"}, stream=True
        )
        if response.status_code not in (200, 206):
            response.close()
            raise DownloadError(f"HTTP {response.status_code}")
        total: Optional[int] = None
        content_range = response.headers.get("Content-Range", "")
        match = re.search(r"/(\d+)$", content_range)
        if match:
            total = int(match.group(1))
        elif response.headers.get("Content-Length", "").isdigit():
            total = int(response.headers["Content-Length"])
        modified = response.headers.get("Last-Modified")
        final_url = response.url
        response.close()
        return total, modified, final_url

    @staticmethod
    def _set_mtime(path: Path, last_modified: Optional[str]) -> None:
        if not last_modified:
            return
        try:
            parsed = email.utils.parsedate_to_datetime(last_modified)
            if parsed is not None:
                timestamp = parsed.timestamp()
                os.utime(path, (timestamp, timestamp))
        except (TypeError, ValueError, OSError, OverflowError):
            pass

    def download_one(self, item: RemoteFile) -> Result:
        path = item.local_path
        try:
            remote_size, last_modified, resolved = self.remote_info(item.url)
        except Exception as exc:
            return Result(
                item.category,
                item.label,
                str(path),
                item.url,
                "unavailable",
                path.stat().st_size if path.exists() else 0,
                str(exc),
            )

        # Create the destination only after the remote object has been resolved.
        # This avoids thousands of empty pair folders when an old resolver
        # falsely reports migrated manifest entries as unavailable.
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and not self.s.overwrite:
            local_size = path.stat().st_size
            if remote_size is None and local_size > 0:
                return Result(
                    item.category, item.label, str(path), resolved, "skipped",
                    local_size, "Existing non-empty file; remote size unavailable"
                )
            if remote_size is not None and local_size == remote_size:
                return Result(
                    item.category, item.label, str(path), resolved, "skipped",
                    local_size, "Existing file size matches remote"
                )

        if self.s.dry_run:
            return Result(
                item.category, item.label, str(path), resolved, "planned",
                path.stat().st_size if path.exists() else 0,
                f"Remote size: {remote_size if remote_size is not None else 'unknown'}"
            )

        part = path.with_name(path.name + ".part")
        if self.s.overwrite:
            part.unlink(missing_ok=True)
            path.unlink(missing_ok=True)

        # A mismatched final file is moved to .part so Range can resume it.
        if path.exists():
            if part.exists():
                part.unlink()
            path.replace(part)

        current = part.stat().st_size if part.exists() else 0
        if remote_size is not None and current > remote_size:
            part.unlink(missing_ok=True)
            current = 0

        headers = {"Range": f"bytes={current}-"} if current > 0 else {}
        mode = "ab" if current > 0 else "wb"
        try:
            total_text = (
                f"{remote_size / (1024**2):.1f} MB"
                if remote_size is not None else "size unknown"
            )
            self.log.info("[START] %s (%s)", item.label, total_text)
            response = self._request("GET", resolved, headers=headers, stream=True)
            if current > 0 and response.status_code == 200:
                # Server ignored Range; restart cleanly.
                current = 0
                mode = "wb"
            elif current > 0 and response.status_code != 206:
                response.close()
                current = 0
                mode = "wb"
                response = self._request("GET", resolved, stream=True)
            response.raise_for_status()
            ctype = response.headers.get("Content-Type", "").lower()
            if "text/html" in ctype:
                raise DownloadError("Server returned HTML instead of the data file")
            bytes_done = current
            last_progress = time.monotonic()
            with part.open(mode) as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
                        bytes_done += len(chunk)
                        now = time.monotonic()
                        if now - last_progress >= self.s.progress_interval:
                            if remote_size:
                                pct = min(100.0, bytes_done * 100.0 / remote_size)
                                self.log.info(
                                    "[DATA ] %s: %.1f/%.1f MB (%.1f%%)",
                                    item.label, bytes_done / (1024**2),
                                    remote_size / (1024**2), pct,
                                )
                            else:
                                self.log.info(
                                    "[DATA ] %s: %.1f MB received",
                                    item.label, bytes_done / (1024**2),
                                )
                            last_progress = now
            response.close()

            final_size = part.stat().st_size
            if remote_size is not None and final_size != remote_size:
                raise DownloadError(
                    f"Incomplete file: local {final_size} bytes, remote {remote_size} bytes"
                )
            part.replace(path)
            self._set_mtime(path, last_modified)
            return Result(
                item.category, item.label, str(path), resolved, "downloaded",
                path.stat().st_size, "", bytes_done - current
            )
        except Exception as exc:
            return Result(
                item.category,
                item.label,
                str(path),
                resolved,
                "failed",
                part.stat().st_size if part.exists() else 0,
                str(exc),
            )


def parse_yyyymmdd(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(str(value), "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYYMMDD, e.g. 20200101."
        ) from exc


def validate_frame(value: str) -> str:
    value = value.strip()
    if not FRAME_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "Frame ID must look like 021D_04972_131213."
        )
    return value


def infer_frame_from_path(path: Path) -> Optional[str]:
    matches = re.findall(r"\d{3}[AD]_\d{5}_\d{6}", str(path))
    return matches[0] if matches else None


def load_config(path: Optional[Path]) -> dict:
    if path is None:
        return {}
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Config JSON must contain one object.")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download LiCSAR GeoTIFF products on Windows using the same file "
            "layout as LiCSBAS2 LiCSBAS01_get_geotiff.py."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("-f", "--frame", type=validate_frame, help="LiCSAR frame ID")
    parser.add_argument("-s", "--start", type=parse_yyyymmdd, help="Start date YYYYMMDD")
    parser.add_argument("-e", "--end", type=parse_yyyymmdd, help="End date YYYYMMDD")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Parent output directory; a FRAME_ID subfolder is created"
    )
    parser.add_argument(
        "--get_gacos", "--get-gacos", dest="get_gacos", action="store_true",
        help="Download available GACOS slant-delay GeoTIFFs"
    )
    parser.add_argument(
        "--no-gacos", dest="get_gacos", action="store_false",
        help="Do not download GACOS"
    )
    parser.set_defaults(get_gacos=None)
    parser.add_argument(
        "--n_para", "--workers", dest="workers", type=int,
        help="Number of parallel download threads"
    )
    parser.add_argument(
        "--no-mli", action="store_true",
        help="Skip the representative MLI file (not recommended for parity)"
    )
    parser.add_argument(
        "--get_mli", "--get-mli", dest="download_all_mli",
        action="store_true",
        help=(
            "Also download every available epoch MLI to GEOC.MLI, matching "
            "the current COMET LiCSBAS --get_mli option"
        ),
    )
    parser.add_argument(
        "--base-url", help="Advanced: LiCSAR archive root URL"
    )
    parser.add_argument("--retries", type=int, help="HTTP retry count")
    parser.add_argument("--timeout-connect", type=float, help="Connect timeout seconds")
    parser.add_argument("--timeout-read", type=float, help="Read timeout seconds")
    parser.add_argument(
        "--progress-interval", type=float,
        help="Seconds between progress messages for a file still downloading",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Redownload files even when sizes already match"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report planned files without downloading"
    )
    parser.add_argument(
        "--no-verify-tls", action="store_true",
        help="Disable TLS certificate verification (only for diagnosed certificate issues)"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def coalesce(cli_value, config: dict, key: str, default):
    return cli_value if cli_value is not None else config.get(key, default)


def settings_from_args(argv: Optional[Sequence[str]] = None) -> Settings:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)

    frame = coalesce(args.frame, config, "frame", None)
    if not frame:
        frame = infer_frame_from_path(Path.cwd())
    if not frame:
        parser.error("Frame ID is required. Use -f FRAME_ID or run inside a frame-named folder.")
    try:
        frame = validate_frame(str(frame))
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    start_raw = coalesce(args.start, config, "start", "20141001")
    end_raw = coalesce(args.end, config, "end", dt.date.today().strftime("%Y%m%d"))
    start = start_raw if isinstance(start_raw, dt.date) else parse_yyyymmdd(str(start_raw))
    end = end_raw if isinstance(end_raw, dt.date) else parse_yyyymmdd(str(end_raw))
    if start > end:
        parser.error("Start date must not be later than end date.")

    output_raw = coalesce(args.output, config, "output", str(Path.cwd()))
    output_parent = Path(os.path.expandvars(os.path.expanduser(str(output_raw)))).resolve()

    workers = int(coalesce(args.workers, config, "workers", 4))
    if workers < 1 or workers > 32:
        parser.error("workers/--n_para must be between 1 and 32.")

    get_gacos = bool(coalesce(args.get_gacos, config, "get_gacos", False))
    download_mli = not args.no_mli and bool(config.get("download_mli", True))
    download_all_mli = bool(args.download_all_mli or config.get("get_mli", False) or config.get("download_all_mli", False))
    base_url = str(coalesce(args.base_url, config, "base_url", DEFAULT_BASE_URL)).rstrip("/") + "/"
    retries = int(coalesce(args.retries, config, "retries", 4))
    timeout_connect = float(coalesce(args.timeout_connect, config, "timeout_connect", 20.0))
    timeout_read = float(coalesce(args.timeout_read, config, "timeout_read", 180.0))
    progress_interval = float(coalesce(args.progress_interval, config, "progress_interval", 10.0))
    if progress_interval < 1:
        parser.error("progress_interval/--progress-interval must be at least 1 second.")
    overwrite = bool(args.overwrite or config.get("overwrite", False))
    dry_run = bool(args.dry_run or config.get("dry_run", False))
    verify_tls = not bool(args.no_verify_tls or config.get("no_verify_tls", False))

    return Settings(
        frame=frame,
        start=start,
        end=end,
        output_parent=output_parent,
        workers=workers,
        get_gacos=get_gacos,
        download_mli=download_mli,
        download_all_mli=download_all_mli,
        base_url=base_url,
        timeout_connect=timeout_connect,
        timeout_read=timeout_read,
        retries=retries,
        overwrite=overwrite,
        dry_run=dry_run,
        verify_tls=verify_tls,
        progress_interval=progress_interval,
    )


def setup_logging(frame_dir: Path) -> logging.Logger:
    frame_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("licsar_downloader")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    file_handler = logging.FileHandler(frame_dir / "download.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def in_date_range(name: str, start: dt.date, end: dt.date) -> bool:
    date = parse_yyyymmdd(name)
    return start <= date <= end


def pair_in_range(pair: str, start: dt.date, end: dt.date) -> bool:
    first = parse_yyyymmdd(pair[:8])
    second = parse_yyyymmdd(pair[9:])
    return first >= start and second <= end


def base_frame_url(s: Settings) -> str:
    return urljoin(s.base_url, f"{s.track}/{s.frame}/")


def expected_url(s: Settings, *parts: str) -> str:
    url = base_frame_url(s)
    for part in parts:
        url = urljoin(url.rstrip("/") + "/", part)
    return url


def _find_latest_representative_mli(
    client: LiCSARClient,
    s: Settings,
    epochs: Sequence[str],
    logger: logging.Logger,
) -> Optional[RemoteFile]:
    """Find the newest available epoch MLI with visible, parallel progress.

    Version 1.0.0 checked epochs one by one and printed nothing, which could
    look frozen for long date ranges. This version checks newest-first in
    small parallel batches and stops as soon as a batch contains an MLI.
    """
    if not epochs:
        return None

    ordered = list(reversed(epochs))
    batch_size = max(8, min(32, s.workers * 4))
    logger.info(
        "[2/4] Searching latest representative MLI (%d epochs, %d threads)...",
        len(ordered), min(s.workers, 8),
    )
    checked = 0
    with tqdm(
        total=len(ordered), desc="MLI scan", unit="epoch", dynamic_ncols=True,
        leave=True,
    ) as bar:
        for offset in range(0, len(ordered), batch_size):
            batch = ordered[offset: offset + batch_size]
            resolved: dict[str, Optional[str]] = {}
            with ThreadPoolExecutor(
                max_workers=min(max(1, s.workers), 8, len(batch)),
                thread_name_prefix="mli-scan",
            ) as pool:
                future_map = {}
                for epoch in batch:
                    source = expected_url(s, "epochs", epoch, f"{epoch}.geo.mli.tif")
                    future_map[pool.submit(client.resolve_file_url, source)] = (epoch, source)
                for future in as_completed(future_map):
                    epoch, source = future_map[future]
                    try:
                        resolved[epoch] = future.result()
                    except Exception:
                        resolved[epoch] = None
                    checked += 1
                    bar.update(1)
                    bar.set_postfix_str(f"checked={checked}")

            # batch is newest-first; select the newest successful epoch.
            for epoch in batch:
                if resolved.get(epoch):
                    source = resolved[epoch] or expected_url(
                        s, "epochs", epoch, f"{epoch}.geo.mli.tif"
                    )
                    bar.set_postfix_str(f"found={epoch}")
                    logger.info(
                        "Representative MLI found: %s.geo.mli.tif -> %s.geo.mli.tif",
                        epoch, s.frame,
                    )
                    return RemoteFile(
                        source,
                        s.geoc_dir / f"{s.frame}.geo.mli.tif",
                        "mli",
                        f"{epoch}.geo.mli.tif -> {s.frame}.geo.mli.tif",
                    )
    logger.warning("No representative MLI found in the selected date range.")
    return None


def _discover_optional_epoch_products(
    client: LiCSARClient,
    s: Settings,
    epochs: Sequence[str],
    filename_template: str,
    destination_dir: Path,
    category: str,
    label: str,
    report_name: str,
    logger: logging.Logger,
) -> list[RemoteFile]:
    """Resolve optional epoch products first and queue only available files.

    This mirrors the current COMET LiCSBAS workflow: unavailable optional files
    are counted during an availability scan instead of being emitted as a long
    series of download failures.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    if not epochs:
        logger.info("%s availability: no epochs in the selected range", label)
        return []

    logger.info(
        "%s availability scan: %d epochs (%d threads)...",
        label, len(epochs), min(max(1, s.workers), 8),
    )
    rows: list[dict[str, str]] = []
    available: dict[str, str] = {}
    with ThreadPoolExecutor(
        max_workers=min(max(1, s.workers), 8, len(epochs)),
        thread_name_prefix=f"{category}-scan",
    ) as pool:
        future_map = {}
        for epoch in epochs:
            filename = filename_template.format(epoch=epoch)
            source = expected_url(s, "epochs", epoch, filename)
            future_map[pool.submit(client.resolve_file_url, source)] = (
                epoch, filename, source
            )
        with tqdm(
            total=len(epochs), desc=f"{label} scan", unit="epoch",
            dynamic_ncols=True, leave=True,
        ) as bar:
            for future in as_completed(future_map):
                epoch, filename, source = future_map[future]
                try:
                    resolved = future.result()
                except Exception:
                    resolved = None
                if resolved:
                    available[epoch] = resolved
                    status = "available"
                else:
                    status = "unavailable"
                rows.append({
                    "epoch": epoch,
                    "filename": filename,
                    "status": status,
                    "expected_url": source,
                    "resolved_url": resolved or "",
                })
                bar.update(1)
                bar.set_postfix(available=len(available), unavailable=len(rows)-len(available))

    report_path = s.frame_dir / report_name
    with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "epoch", "filename", "status", "expected_url", "resolved_url"
            ),
        )
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["epoch"]))

    unavailable_count = len(epochs) - len(available)
    logger.info(
        "%s availability: %d available, %d unavailable; details: %s",
        label, len(available), unavailable_count, report_path,
    )
    items: list[RemoteFile] = []
    for epoch in epochs:
        resolved = available.get(epoch)
        if not resolved:
            continue
        filename = filename_template.format(epoch=epoch)
        items.append(RemoteFile(
            resolved,
            destination_dir / filename,
            category,
            filename,
        ))
    return items


def discover_items(client: LiCSARClient, s: Settings, logger: logging.Logger) -> list[RemoteFile]:
    items: list[RemoteFile] = []
    s.geoc_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[1/4] Preparing metadata and reading LiCSAR directory listings...")

    # Metadata and geometry exactly as LiCSBAS01_get_geotiff.py.
    for component in ("E", "N", "U", "hgt"):
        filename = f"{s.frame}.geo.{component}.tif"
        items.append(RemoteFile(
            expected_url(s, "metadata", filename),
            s.geoc_dir / filename,
            "metadata",
            filename,
        ))
    for filename in ("baselines", "network.png", "metadata.txt"):
        items.append(RemoteFile(
            expected_url(s, "metadata", filename),
            s.geoc_dir / filename,
            "metadata",
            filename,
        ))

    epochs_url = expected_url(s, "epochs", "")
    epochs: list[str] = []
    try:
        epochs = [
            value for value in client.list_names(epochs_url, DATE_RE)
            if in_date_range(value, s.start, s.end)
        ]
        logger.info(
            "Epochs in range %s-%s: %d",
            s.start.strftime("%Y%m%d"), s.end.strftime("%Y%m%d"), len(epochs),
        )
    except Exception as exc:
        logger.warning("Could not list epochs: %s", exc)

    if s.download_mli and epochs:
        representative = _find_latest_representative_mli(client, s, epochs, logger)
        if representative is not None:
            items.append(representative)
    elif not s.download_mli:
        logger.info("[2/4] Representative MLI disabled by configuration.")
    else:
        logger.warning("[2/4] Representative MLI search skipped: no epochs found.")

    # Current COMET LiCSBAS --get_mli first checks which epoch MLIs exist.
    if s.download_all_mli:
        mlidir = s.frame_dir / "GEOC.MLI"
        items.extend(_discover_optional_epoch_products(
            client=client,
            s=s,
            epochs=epochs,
            filename_template="{epoch}.geo.mli.tif",
            destination_dir=mlidir,
            category="mli_all",
            label="All-epoch MLI",
            report_name="mli_availability.csv",
            logger=logger,
        ))

    if s.get_gacos:
        items.extend(_discover_optional_epoch_products(
            client=client,
            s=s,
            epochs=epochs,
            filename_template="{epoch}.sltd.geo.tif",
            destination_dir=s.gacos_dir,
            category="gacos",
            label="GACOS",
            report_name="gacos_availability.csv",
            logger=logger,
        ))

    logger.info("[3/4] Reading interferogram list...")
    ifg_url = expected_url(s, "interferograms", "")
    pairs = [
        value for value in client.list_names(ifg_url, PAIR_RE)
        if pair_in_range(value, s.start, s.end)
    ]
    logger.info(
        "Interferogram pairs in range %s-%s: %d",
        s.start.strftime("%Y%m%d"), s.end.strftime("%Y%m%d"), len(pairs),
    )
    for pair in pairs:
        pair_dir = s.geoc_dir / pair
        for suffix, category in (("unw", "unw"), ("cc", "cc")):
            filename = f"{pair}.geo.{suffix}.tif"
            items.append(RemoteFile(
                expected_url(s, "interferograms", pair, filename),
                pair_dir / filename,
                category,
                filename,
            ))
    logger.info("[4/4] Discovery complete. Starting file checks/downloads.")
    return items


def run_parallel(
    client: LiCSARClient,
    items: Iterable[RemoteFile],
    workers: int,
    logger: logging.Logger,
) -> list[Result]:
    items = list(items)
    total = len(items)
    if total == 0:
        return []
    results: list[Result] = []
    counters = {"downloaded": 0, "skipped": 0, "planned": 0, "unavailable": 0, "failed": 0}
    logger.info("Files to check/download: %d; parallel threads: %d", total, workers)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="licsar") as pool:
        futures = {pool.submit(client.download_one, item): item for item in items}
        with tqdm(
            total=total, desc="Overall", unit="file", dynamic_ncols=True, leave=True,
        ) as bar:
            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # defensive
                    result = Result(
                        item.category, item.label, str(item.local_path), item.url,
                        "failed", 0, f"Unhandled worker error: {exc}",
                    )
                results.append(result)
                counters[result.status] = counters.get(result.status, 0) + 1
                marker = {
                    "downloaded": "OK",
                    "skipped": "EXISTS",
                    "planned": "PLAN",
                    "unavailable": "MISS",
                    "failed": "FAIL",
                }.get(result.status, result.status.upper())
                size_text = f"{result.bytes_local / (1024**2):.1f} MB" if result.bytes_local else ""
                detail = f" - {result.message}" if result.message else ""
                tqdm.write(f"[{marker:6}] {result.label} {size_text}{detail}")
                bar.update(1)
                bar.set_postfix(
                    ok=counters.get("downloaded", 0),
                    exists=counters.get("skipped", 0),
                    miss=counters.get("unavailable", 0),
                    fail=counters.get("failed", 0),
                )
    return results


def write_report(path: Path, results: Sequence[Result]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "category", "label", "local_path", "url", "status",
                "bytes_local", "message", "bytes_transferred"
            ),
        )
        writer.writeheader()
        for result in sorted(results, key=lambda r: (r.category, r.label)):
            writer.writerow(result.__dict__)


def verify_structure(s: Settings, results: Sequence[Result]) -> tuple[list[str], list[str]]:
    """Return (critical_issues, auxiliary_warnings).

    LiCSBAS02 can proceed when valid pair folders contain both unw and cc.
    Geometry, MLI, baseline, metadata, and preview files are useful but are
    treated as auxiliary because LiCSBAS2 itself documents several as optional.
    """
    critical: list[str] = []
    warnings: list[str] = []
    geoc = s.geoc_dir
    if not geoc.is_dir():
        critical.append("GEOC directory is missing")
        return critical, warnings

    auxiliary = [
        geoc / f"{s.frame}.geo.E.tif",
        geoc / f"{s.frame}.geo.N.tif",
        geoc / f"{s.frame}.geo.U.tif",
        geoc / f"{s.frame}.geo.hgt.tif",
        geoc / "baselines",
        geoc / "metadata.txt",
        geoc / "network.png",
    ]
    if s.download_mli:
        auxiliary.append(geoc / f"{s.frame}.geo.mli.tif")
    for path in auxiliary:
        if not path.is_file() or path.stat().st_size == 0:
            warnings.append(f"Missing or empty auxiliary file: {path.name}")

    pair_dirs = [p for p in geoc.iterdir() if p.is_dir() and PAIR_RE.fullmatch(p.name)]
    if not pair_dirs:
        critical.append("No YYYYMMDD_YYYYMMDD interferogram directories found")
    for pair_dir in pair_dirs:
        for suffix in ("unw", "cc"):
            tif = pair_dir / f"{pair_dir.name}.geo.{suffix}.tif"
            if not tif.is_file() or tif.stat().st_size == 0:
                critical.append(f"Missing or empty: {pair_dir.name}/{tif.name}")

    required_bad = [
        result for result in results
        if result.category in {"unw", "cc"}
        and result.status in {"unavailable", "failed"}
    ]
    for result in required_bad:
        critical.append(
            f"Required product {result.status}: {result.label} ({result.message})"
        )

    failed = [r for r in results if r.status == "failed"]
    if failed:
        warnings.append(f"{len(failed)} download(s) failed; see download_report.csv")
    return critical, warnings


def print_summary(
    s: Settings, results: Sequence[Result], critical: Sequence[str],
    warnings: Sequence[str], logger: logging.Logger
) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    required = [r for r in results if r.category in {"unw", "cc"}]
    required_ok = [r for r in required if r.status in {"downloaded", "skipped", "planned"}]
    required_bad = [r for r in required if r.status in {"failed", "unavailable"}]

    logger.info("")
    logger.info("=" * 72)
    if s.dry_run:
        headline = "DRY RUN COMPLETED - NO DATA FILES WERE DOWNLOADED"
    elif critical or required_bad or any(r.status == "failed" for r in results):
        headline = "DOWNLOAD INCOMPLETE - CHECK THE ITEMS MARKED FAIL/MISS"
    else:
        headline = "DOWNLOAD COMPLETED SUCCESSFULLY"
    logger.info(headline)
    logger.info("=" * 72)
    logger.info(
        "Downloaded: %d | Already complete: %d | Planned: %d | Missing: %d | Failed: %d",
        counts.get("downloaded", 0), counts.get("skipped", 0),
        counts.get("planned", 0), counts.get("unavailable", 0),
        counts.get("failed", 0),
    )
    logger.info(
        "Required IFG files complete/planned: %d/%d; problematic: %d",
        len(required_ok), len(required), len(required_bad),
    )
    logger.info("Frame directory: %s", s.frame_dir)
    logger.info("LiCSBAS-compatible GEOC directory: %s", s.geoc_dir)
    logger.info("Detailed report: %s", s.frame_dir / "download_report.csv")
    logger.info("Log file: %s", s.frame_dir / "download.log")
    if s.get_gacos:
        logger.info("GACOS directory: %s", s.gacos_dir)
    if s.download_all_mli:
        logger.info("All-epoch MLI directory: %s", s.frame_dir / "GEOC.MLI")
    if critical:
        logger.error("Structure verification FAILED with %d critical issue(s):", len(critical))
        for issue in critical:
            logger.error("  - %s", issue)
    else:
        logger.info("Structure verification: PASSED for LiCSBAS pair inputs")
    if warnings:
        logger.warning("Auxiliary warnings (%d):", len(warnings))
        for warning in warnings:
            logger.warning("  - %s", warning)
    logger.info("=" * 72)
    return headline


def main(argv: Optional[Sequence[str]] = None) -> int:
    start_time = time.time()
    try:
        settings = settings_from_args(argv)
    except argparse.ArgumentTypeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    logger = setup_logging(settings.frame_dir)
    logger.info("LiCSAR Windows Downloader %s", VERSION)
    logger.info("Frame: %s (track %s)", settings.frame, settings.track)
    logger.info(
        "Date range: %s to %s",
        settings.start.strftime("%Y%m%d"), settings.end.strftime("%Y%m%d")
    )
    logger.info("Output parent: %s", settings.output_parent)
    logger.info("GACOS: %s | representative MLI: %s | all-epoch MLI: %s | dry-run: %s", settings.get_gacos, settings.download_mli, settings.download_all_mli, settings.dry_run)

    client = LiCSARClient(settings, logger)
    try:
        items = discover_items(client, settings, logger)
    except Exception as exc:
        logger.error("Discovery failed: %s", exc)
        return 3

    # De-duplicate by destination path; this chiefly protects the renamed MLI.
    unique: dict[str, RemoteFile] = {}
    for item in items:
        unique[str(item.local_path).lower()] = item
    results = run_parallel(client, unique.values(), settings.workers, logger)
    write_report(settings.frame_dir / "download_report.csv", results)

    critical, warnings = ([], []) if settings.dry_run else verify_structure(settings, results)
    headline = print_summary(settings, results, critical, warnings, logger)
    summary_path = settings.frame_dir / "download_summary.txt"
    counts = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary_path.write_text(
        "\n".join([
            headline,
            f"Frame: {settings.frame}",
            f"Date range: {settings.start:%Y%m%d}-{settings.end:%Y%m%d}",
            f"Downloaded: {counts.get('downloaded', 0)}",
            f"Already complete: {counts.get('skipped', 0)}",
            f"Missing: {counts.get('unavailable', 0)}",
            f"Failed: {counts.get('failed', 0)}",
            f"GEOC: {settings.geoc_dir}",
            f"Report: {settings.frame_dir / 'download_report.csv'}",
        ]) + "\n",
        encoding="utf-8",
    )
    logger.info("One-page status summary: %s", summary_path)
    elapsed = int(time.time() - start_time)
    logger.info("Elapsed: %02dh %02dm %02ds", elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60)

    if any(r.status == "failed" for r in results):
        return 4
    # Unavailable optional products are not fatal. Missing required products are.
    if critical:
        return 5
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled by user. Partial downloads remain as *.part and can be resumed.")
        sys.exit(130)
