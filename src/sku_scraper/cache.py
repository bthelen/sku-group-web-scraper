import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_cache_dir
from tqdm import tqdm

from sku_scraper import scraper

CACHE_DIR = Path(user_cache_dir("sku-scraper"))
CACHE_FILE = CACHE_DIR / "index.json"

STALE_AFTER_DAYS = 7


def build_index(
    session,
    groups: dict[str, str],
    workers: int = 10,
    show_progress: bool = True,
) -> tuple[dict, dict[str, str]]:
    """Fetch all groups in parallel and build an inverted SKU ID index.

    Returns (index_dict, errors) where errors is {slug: error_message}.
    """
    by_id: dict[str, dict] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(scraper.fetch_sku_entries, session, url): slug
            for slug, url in groups.items()
        }
        progress = tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Fetching groups",
            unit="group",
            disable=not show_progress,
            file=sys.stderr,
        )
        with progress:
            for future in progress:
                slug = futures[future]
                try:
                    entries = future.result()
                except Exception as exc:
                    errors[slug] = str(exc)
                    continue
                for entry in entries:
                    sku_id = entry["id"]
                    if sku_id not in by_id:
                        by_id[sku_id] = {"name": entry["name"], "groups": []}
                    if slug not in by_id[sku_id]["groups"]:
                        by_id[sku_id]["groups"].append(slug)

    index = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "by_id": by_id,
    }
    return index, errors


def save_cache(index: dict, path: Path = CACHE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2), encoding="utf-8")


def load_cache(path: Path = CACHE_FILE) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def cache_age_seconds(path: Path = CACHE_FILE) -> float | None:
    index = load_cache(path)
    if index is None or "built_at" not in index:
        return None
    built_at = datetime.fromisoformat(index["built_at"])
    return (datetime.now(timezone.utc) - built_at).total_seconds()
