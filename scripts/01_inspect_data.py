"""Inventory datasets under data/raw, including CSV files inside ZIP archives."""

from __future__ import annotations

import csv
import json
import logging
import sys
import zipfile
from pathlib import Path
from typing import TextIO


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
LOG = logging.getLogger("inspect_data")


def classify(path: Path, columns: list[str] | None = None) -> str:
    """Infer a broad data type from its location, format, and column names."""
    parts = [part.lower() for part in path.parts]
    text = " ".join((*parts, *(column.lower() for column in columns or [])))
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".dcm"} or any(
        term in text for term in ("image", "xray", "dicom")
    ):
        return "صور/تصوير طبي"
    if "ddxplus_data" in parts:
        return "بيانات أعراض وتشخيص تفريقي"
    if "symptoms" in parts:
        return "تصنيف أمراض/أعراض"
    if "diabetes" in parts:
        return "تصنيف السكري"
    if "heart" in parts:
        return "تصنيف أمراض القلب"
    if "kidney" in parts:
        return "تصنيف أمراض الكلى"
    if "ddxplus" in parts:
        return "مصدر برمجي/توثيق DDXPlus"
    if any(term in text for term in ("evidence", "pathology")):
        return "بيانات أعراض وتشخيص تفريقي"
    if any(term in text for term in ("symptom", "prognosis", "disease")):
        return "تصنيف أمراض/أعراض"
    if "diabetes" in text or "glucose" in text:
        return "تصنيف السكري"
    if "heart" in text or "cardio" in text:
        return "تصنيف أمراض القلب"
    if "kidney" in text or "renal" in text:
        return "تصنيف أمراض الكلى"
    if path.suffix.lower() in {".csv", ".tsv", ".zip"}:
        return "جدولي (التصنيف غير محسوم)"
    if path.suffix.lower() == ".json":
        return "بيانات وصفية/إعدادات"
    return "ملف غير جدولي/مصدر برمجي"


def count_csv_rows(stream: TextIO) -> tuple[int, list[str]]:
    """Count parsed CSV records (excluding the header) without loading the file."""
    reader = csv.reader(stream)
    header = next(reader, [])
    return sum(1 for _ in reader), header


def inspect_csv(path: Path) -> tuple[int, list[str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        return count_csv_rows(stream)


def inspect_zip(path: Path) -> list[str]:
    details: list[str] = []
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        for member in members:
            suffix = Path(member.filename).suffix.lower()
            with archive.open(member) as probe:
                sample = probe.read(4096)
            if suffix not in {".csv", ".tsv"} and (
                b"\x00" in sample or b"," not in sample or b"\n" not in sample
            ):
                details.append(f"{member.filename} ({member.file_size:,} bytes)")
                continue
            with archive.open(member) as binary_stream:
                import io

                text_stream = io.TextIOWrapper(
                    binary_stream, encoding="utf-8-sig", errors="replace", newline=""
                )
                row_count, columns = count_csv_rows(text_stream)
            details.append(
                f"{member.filename}: {row_count:,} rows, "
                f"{len(columns)} columns [{', '.join(columns)}]"
            )
    return details


def inspect_file(path: Path) -> None:
    size = path.stat().st_size
    row_count: str = "n/a"
    columns: list[str] | None = None
    extra: list[str] = []
    try:
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            row_num, columns = inspect_csv(path)
            row_count = f"{row_num:,}"
        elif suffix == ".zip":
            extra = inspect_zip(path)
            csv_rows = [
                item.split(": ", 1)[1].split(" rows,", 1)[0]
                for item in extra
                if ": " in item and " rows," in item
            ]
            row_count = "; ".join(csv_rows) if csv_rows else "لا يحتوي CSV"
        elif suffix == ".json":
            with path.open("r", encoding="utf-8-sig") as stream:
                value = json.load(stream)
            if isinstance(value, (list, dict)):
                row_count = f"{len(value):,} عناصر من المستوى الأعلى"
                columns = list(value[0]) if isinstance(value, list) and value and isinstance(value[0], dict) else (
                    list(value) if isinstance(value, dict) else None
                )
        kind = classify(path, columns)
        print(
            f"{path.relative_to(DATA_DIR)} | {size:,} bytes | "
            f"{row_count} | {kind} | "
            f"الأعمدة: {', '.join(columns) if columns else 'n/a'}"
        )
        for item in extra:
            print(f"  داخل الأرشيف: {item}")
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        LOG.exception("فشل فحص %s", path)
        print(f"{path.relative_to(DATA_DIR)} | {size:,} bytes | ERROR: {exc}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not DATA_DIR.is_dir():
        raise FileNotFoundError(f"مجلد البيانات غير موجود: {DATA_DIR}")
    files = sorted(path for path in DATA_DIR.rglob("*") if path.is_file() and ".git" not in path.parts)
    print(f"فحص {len(files):,} ملف ضمن {DATA_DIR}")
    for path in files:
        inspect_file(path)


if __name__ == "__main__":
    main()
