import re
from pathlib import Path

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_\-]")


def slug_to_filename(slug: str) -> str:
    return _UNSAFE_CHARS.sub("_", slug)


def write_skus_file(slug: str, sku_ids: list[str], output_dir: Path) -> Path:
    filename = slug_to_filename(slug) + "-skus.txt"
    path = output_dir / filename
    path.write_text("\n".join(sku_ids) + "\n", encoding="utf-8")
    return path


def write_where_clause_file(slug: str, sku_ids: list[str], output_dir: Path) -> Path:
    filename = slug_to_filename(slug) + "-where-clause.txt"
    path = output_dir / filename
    clause = ", ".join(f'"{sku_id}"' for sku_id in sku_ids)
    path.write_text(clause + "\n", encoding="utf-8")
    return path
