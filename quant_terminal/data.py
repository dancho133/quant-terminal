"""Validated daily CSV provider and optional checksum-verified public archive importer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import urllib.request
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from quant_terminal.models import Bar, Dataset

DATA_DIR = Path(__file__).parent / "sample_data"
SOURCE_DOCS = "https://github.com/binance/binance-public-data"
SOURCE_TERMS = SOURCE_DOCS + "/blob/master/TERMS_AND_CONDITIONS.md"


def validate_bars(bars: tuple[Bar, ...]) -> tuple[Bar, ...]:
    if not bars:
        raise ValueError("Dataset is empty.")
    for i, bar in enumerate(bars):
        if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() != timedelta(0):
            raise ValueError(f"Bar {i}: timestamps must explicitly use UTC.")
        if any(not math.isfinite(v) or v <= 0 for v in (bar.open, bar.high, bar.low, bar.close)):
            raise ValueError(f"Bar {i}: OHLC prices must be finite and positive.")
        if not math.isfinite(bar.volume) or bar.volume < 0:
            raise ValueError(f"Bar {i}: volume must be finite and nonnegative.")
        if (
            bar.low > min(bar.open, bar.close)
            or bar.high < max(bar.open, bar.close)
            or bar.low > bar.high
        ):
            raise ValueError(f"Bar {i}: impossible OHLC range.")
        if bar.timestamp.time().replace(tzinfo=None) != datetime.min.time():
            raise ValueError(f"Bar {i}: daily bars must open at 00:00 UTC.")
        if i and bar.timestamp - bars[i - 1].timestamp != timedelta(days=1):
            raise ValueError(f"Bar {i}: missing, duplicate or unordered daily timestamp.")
    return bars


def dataset_from_bars(asset: str, bars: tuple[Bar, ...], provenance: dict | None = None) -> Dataset:
    validate_bars(bars)
    canonical = [
        {
            "timestamp": b.timestamp.isoformat(),
            **{k: float(v) for k, v in asdict(b).items() if k != "timestamp"},
        }
        for b in bars
    ]
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return Dataset(
        asset,
        bars,
        digest,
        provenance or {"kind": "synthetic", "description": "Test fixture; not market evidence."},
    )


class MarketDataProvider(Protocol):
    def load(self, asset: str) -> Dataset: ...


class CSVProvider:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def load(self, asset: str) -> Dataset:
        path = self.path or DATA_DIR / f"{asset}-1d.csv"
        if not path.is_file():
            raise ValueError(f"No offline dataset for {asset}: {path}")
        raw = path.read_bytes()
        metadata_path = path.with_suffix(".json")
        provenance = (
            json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata_path.exists()
            else {
                "kind": "user_csv",
                "description": "User-supplied OHLCV; provenance not independently verified.",
            }
        )
        if not isinstance(provenance, dict):
            raise ValueError("Dataset provenance manifest must be a JSON object.")
        if provenance.get("asset", asset) != asset:
            raise ValueError("Dataset metadata asset does not match the requested asset.")
        csv_hash = hashlib.sha256(raw).hexdigest()
        if provenance.get("csv_sha256", csv_hash) != csv_hash:
            raise ValueError("CSV checksum does not match its provenance manifest.")
        try:
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if reader.fieldnames != ["timestamp", "open", "high", "low", "close", "volume"]:
                raise ValueError("CSV columns must be timestamp,open,high,low,close,volume.")
            parsed = []
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(row.get(key) in (None, "") for key in reader.fieldnames):
                    raise ValueError(f"CSV row {row_number}: expected exactly six nonempty fields.")
                parsed.append(
                    Bar(
                        datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                        *(float(row[key]) for key in ("open", "high", "low", "close", "volume")),
                    )
                )
            bars = tuple(parsed)
        except (KeyError, TypeError, UnicodeError, OverflowError, csv.Error) as exc:
            raise ValueError(f"Malformed OHLCV CSV: {exc}") from exc
        return dataset_from_bars(asset, bars, provenance | {"csv_sha256": csv_hash})


def load_dataset(asset: str = "BTCUSDT", path: Path | None = None) -> Dataset:
    return CSVProvider(path).load(asset)


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "quant-terminal-research/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError("Archive exceeds the daily-data download size limit.")
    return data


def import_archives(asset: str, start: str, end: str, output: Path) -> Path:
    """Only public daily-bar monthly archives; never accesses an account or order endpoint."""
    if not re.fullmatch(r"[A-Z0-9]{3,20}", asset):
        raise ValueError("Use an uppercase alphanumeric market symbol.")
    first = datetime.strptime(start, "%Y-%m")
    last = datetime.strptime(end, "%Y-%m")
    months = (last.year - first.year) * 12 + last.month - first.month + 1
    if not 1 <= months <= 60:
        raise ValueError("Choose between 1 and 60 chronological months.")
    output = output.resolve()
    if output.exists() or output.with_suffix(".json").exists():
        raise ValueError("Choose a new output path; existing snapshots are never overwritten.")
    rows, sources = [], []
    current = first
    for _ in range(months):
        month = current.strftime("%Y-%m")
        url = f"https://data.binance.vision/data/spot/monthly/klines/{asset}/1d/{asset}-1d-{month}.zip"
        archive = _download(url)
        checksum = _download(url + ".CHECKSUM").decode().split()[0]
        if hashlib.sha256(archive).hexdigest() != checksum:
            raise ValueError(f"Archive checksum mismatch: {month}")
        with zipfile.ZipFile(io.BytesIO(archive)) as compressed:
            if len(compressed.infolist()) != 1 or compressed.infolist()[0].file_size > 2_000_000:
                raise ValueError("Expected one small daily OHLCV CSV in the archive.")
            source_rows = csv.reader(
                io.StringIO(compressed.read(compressed.namelist()[0]).decode())
            )
            for row in source_rows:
                if row[0] == "open_time":
                    continue
                raw_ts = int(row[0])
                divisor = 1_000_000 if raw_ts >= 100_000_000_000_000 else 1_000
                timestamp = datetime.fromtimestamp(raw_ts / divisor, tz=UTC)
                rows.append([timestamp.isoformat(), *row[1:6]])
        sources.append({"url": url, "archive_sha256": checksum})
        current = current.replace(
            year=current.year + (current.month == 12), month=current.month % 12 + 1
        )
    content = io.StringIO(newline="")
    writer = csv.writer(content, lineterminator="\n")
    writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
    writer.writerows(rows)
    csv_bytes = content.getvalue().encode()
    # Validate before committing any output.
    dataset_from_bars(
        asset, tuple(Bar(datetime.fromisoformat(r[0]), *(float(v) for v in r[1:])) for r in rows)
    )
    manifest = {
        "kind": "historical_public_snapshot",
        "asset": asset,
        "interval": "1d",
        "source": "Binance Vision spot archives",
        "source_docs": SOURCE_DOCS,
        "terms_url": SOURCE_TERMS,
        "license": "CC BY-NC-SA 4.0; upstream supplemental terms apply",
        "retrieved_date": datetime.now(UTC).date().isoformat(),
        "start": rows[0][0],
        "end": rows[-1][0],
        "rows": len(rows),
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "archives": sources,
        "normalization": "Open time converted from milliseconds (before 2025) or microseconds (2025 onward) to ISO UTC. Kept first five OHLCV fields. No adjusted or synthesized bars.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(csv_bytes)
    output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import public archive data; network access is opt-in."
    )
    parser.add_argument("--asset", default="BTCUSDT")
    parser.add_argument("--start", required=True, help="YYYY-MM")
    parser.add_argument("--end", required=True, help="YYYY-MM")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(import_archives(args.asset, args.start, args.end, args.output))
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Data import failed: {exc}\n")


if __name__ == "__main__":
    main()
