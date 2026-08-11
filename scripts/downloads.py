"""Shared download helpers: byte-accurate progress across a batch of files."""

import urllib.request
from pathlib import Path

CHUNK = 1 << 16


def file_size(url: str) -> int:
    """Returns the remote size via HEAD, or 0 if unknown/unavailable."""
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(resp.headers.get("Content-Length", 0))
    except Exception:
        return 0


def download_file(dest: Path, url: str, report=None) -> None:
    """Downloads one file to dest; calls report(done_bytes) per chunk."""
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        with open(dest, "wb") as f:
            while chunk := resp.read(CHUNK):
                f.write(chunk)
                if report:
                    report(len(chunk))


def batch(files, report=None):
    """Downloads a list of (dest: Path, url: str) with cumulative progress.

    report(done_bytes, total_bytes) is called per chunk. The total comes from
    a quick HEAD pre-scan; files without Content-Length count as 0. Skips
    files that already exist.
    """
    pending = [(dest, url) for dest, url in files if not dest.exists()]
    total = sum(file_size(url) for _, url in pending)
    done = 0

    def on_chunk(n: int) -> None:
        nonlocal done
        done += n
        report(done, total)

    for dest, url in pending:
        download_file(dest, url, on_chunk if report else None)
    if report:
        report(done, total)  # final flush (reaches 100%)