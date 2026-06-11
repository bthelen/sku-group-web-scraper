import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sku_scraper import cache

GROUPS = {
    "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
    "cloud-storage": {"url": "https://cloud.google.com/skus/sku-groups/cloud-storage", "name": "Cloud Storage"},
}

BIGQUERY_ENTRIES = [
    {"id": "947D-3B46-7781", "name": "Active Logical Storage"},
    {"id": "C493-D992-4C50", "name": "Active Logical Storage (asia-east1)"},
]

STORAGE_ENTRIES = [
    {"id": "AAAA-1111-BBBB", "name": "Standard Storage"},
    {"id": "947D-3B46-7781", "name": "Active Logical Storage"},  # shared SKU
]


def _side_effect(session, url):
    if "bigquery" in url:
        return BIGQUERY_ENTRIES
    return STORAGE_ENTRIES


class TestBuildIndex:
    def test_returns_index_and_empty_errors_on_success(self):
        session = MagicMock()
        with patch("sku_scraper.cache.scraper.fetch_sku_entries", side_effect=_side_effect):
            index, errors = cache.build_index(session, GROUPS, workers=2, show_progress=False)
        assert errors == {}
        assert "built_at" in index
        assert "by_id" in index

    def test_indexes_sku_id_to_groups(self):
        session = MagicMock()
        with patch("sku_scraper.cache.scraper.fetch_sku_entries", side_effect=_side_effect):
            index, _ = cache.build_index(session, GROUPS, workers=2, show_progress=False)
        by_id = index["by_id"]
        assert "bigquery" in by_id["947D-3B46-7781"]["groups"]
        assert "cloud-storage" in by_id["947D-3B46-7781"]["groups"]

    def test_sku_only_in_one_group(self):
        session = MagicMock()
        with patch("sku_scraper.cache.scraper.fetch_sku_entries", side_effect=_side_effect):
            index, _ = cache.build_index(session, GROUPS, workers=2, show_progress=False)
        by_id = index["by_id"]
        assert by_id["C493-D992-4C50"]["groups"] == ["bigquery"]
        assert by_id["AAAA-1111-BBBB"]["groups"] == ["cloud-storage"]

    def test_captures_sku_name(self):
        session = MagicMock()
        with patch("sku_scraper.cache.scraper.fetch_sku_entries", side_effect=_side_effect):
            index, _ = cache.build_index(session, GROUPS, workers=2, show_progress=False)
        assert index["by_id"]["AAAA-1111-BBBB"]["name"] == "Standard Storage"

    def test_collects_errors_per_group(self):
        session = MagicMock()

        def failing_side_effect(session, url):
            if "bigquery" in url:
                raise RuntimeError("timeout")
            return STORAGE_ENTRIES

        with patch("sku_scraper.cache.scraper.fetch_sku_entries", side_effect=failing_side_effect):
            index, errors = cache.build_index(session, GROUPS, workers=2, show_progress=False)
        assert "bigquery" in errors
        assert "cloud-storage" not in errors
        assert "AAAA-1111-BBBB" in index["by_id"]

    def test_stores_group_names_in_index(self):
        with patch("sku_scraper.cache.scraper.fetch_sku_entries", side_effect=_side_effect):
            index, _ = cache.build_index(MagicMock(), GROUPS, workers=2, show_progress=False)
        assert index["group_names"] == {"bigquery": "BigQuery", "cloud-storage": "Cloud Storage"}

    def test_no_duplicate_groups_for_shared_sku(self):
        groups = {
            "a": {"url": "https://cloud.google.com/skus/sku-groups/a", "name": "A"},
            "b": {"url": "https://cloud.google.com/skus/sku-groups/b", "name": "B"},
        }
        shared_entry = [{"id": "AAAA-1111-BBBB", "name": "Same SKU"}]

        with patch("sku_scraper.cache.scraper.fetch_sku_entries", return_value=shared_entry):
            index, _ = cache.build_index(MagicMock(), groups, workers=2, show_progress=False)
        groups_list = index["by_id"]["AAAA-1111-BBBB"]["groups"]
        assert len(groups_list) == len(set(groups_list))


class TestSaveAndLoadCache:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "index.json"
        index = {"built_at": "2026-01-01T00:00:00+00:00", "by_id": {"X": {"name": "Y", "groups": ["z"]}}}
        cache.save_cache(index, path)
        loaded = cache.load_cache(path)
        assert loaded == index

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "index.json"
        cache.save_cache({"built_at": "x", "by_id": {}}, path)
        assert path.exists()

    def test_load_returns_none_when_missing(self, tmp_path):
        assert cache.load_cache(tmp_path / "nonexistent.json") is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        assert cache.load_cache(path) is None


class TestCacheAgeSeconds:
    def test_returns_none_when_no_cache(self, tmp_path):
        assert cache.cache_age_seconds(tmp_path / "missing.json") is None

    def test_returns_positive_seconds(self, tmp_path):
        path = tmp_path / "index.json"
        index = {"built_at": "2020-01-01T00:00:00+00:00", "by_id": {}}
        cache.save_cache(index, path)
        age = cache.cache_age_seconds(path)
        assert age is not None
        assert age > 0
