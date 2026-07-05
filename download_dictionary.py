"""Download the kaikki.org German dictionary dump (~1 GB).

This is the source data for build_index.py. It is not committed to the repo
because of its size — run this once after cloning, then run build_index.py.

    uv run download_dictionary.py
    uv run build_index.py

Re-running resumes a partial download; delete the file to start over.
"""

import sys
import urllib.request
from pathlib import Path

URL = "https://kaikki.org/dictionary/German/words/kaikki.org-dictionary-German-words.jsonl"
DEST = Path(__file__).parent / "kaikki.org-dictionary-German-words.jsonl"


def _report(done: int, total: int) -> None:
    mb = done / (1024 * 1024)
    if total > 0:
        pct = done / total * 100
        bar = "#" * int(pct // 4)
        print(f"\r  {bar:<25} {pct:5.1f}%  ({mb:,.0f} MB)", end="", file=sys.stderr)
    else:
        print(f"\r  {mb:,.0f} MB", end="", file=sys.stderr)


def download() -> None:
    have = DEST.stat().st_size if DEST.exists() else 0

    req = urllib.request.Request(URL)
    if have:
        req.add_header("Range", f"bytes={have}-")
        print(f"Resuming from {have / (1024 * 1024):,.0f} MB…", file=sys.stderr)

    with urllib.request.urlopen(req) as resp:
        # 206 = server honored our Range; 200 = full body (start fresh).
        resuming = resp.status == 206
        remaining = int(resp.headers.get("Content-Length", 0))
        total = (have + remaining) if resuming else remaining
        mode = "ab" if resuming else "wb"
        done = have if resuming else 0

        with DEST.open(mode) as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                _report(done, total)

    print(f"\nDone. Saved to {DEST}", file=sys.stderr)


if __name__ == "__main__":
    download()
