from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from sku_scraper.cli import main

GROUPS = {
    "bigquery": "https://cloud.google.com/skus/sku-groups/bigquery",
    "cloud-storage": "https://cloud.google.com/skus/sku-groups/cloud-storage",
}
SKU_IDS = ["947D-3B46-7781", "C493-D992-4C50"]


@pytest.fixture
def runner():
    return CliRunner()


class TestListCommand:
    def test_lists_groups(self, runner):
        with patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "bigquery" in result.output
        assert "cloud-storage" in result.output

    def test_handles_empty_groups(self, runner):
        with patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value={}), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "No SKU groups found" in result.output

    def test_handles_request_error(self, runner):
        import requests
        with patch("sku_scraper.cli.scraper.fetch_sku_groups",
                   side_effect=requests.RequestException("timeout")), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["list"])
        assert result.exit_code != 0
        assert "Failed to fetch" in result.output


class TestScrapeCommand:
    def test_scrapes_single_group(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["scrape", "bigquery", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "bigquery" in result.output
        assert (tmp_path / "bigquery-skus.txt").exists()
        assert (tmp_path / "bigquery-where-clause.txt").exists()

    def test_scrapes_multiple_groups(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(
                main,
                ["scrape", "bigquery", "cloud-storage", "--output-dir", str(tmp_path)],
            )
        assert result.exit_code == 0
        assert (tmp_path / "bigquery-skus.txt").exists()
        assert (tmp_path / "cloud-storage-skus.txt").exists()

    def test_scrape_all(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["scrape", "--all", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "bigquery-skus.txt").exists()
        assert (tmp_path / "cloud-storage-skus.txt").exists()

    def test_error_with_no_args(self, runner):
        result = runner.invoke(main, ["scrape"])
        assert result.exit_code != 0
        assert "at least one GROUP" in result.output

    def test_error_combining_groups_and_all(self, runner, tmp_path):
        result = runner.invoke(main, ["scrape", "bigquery", "--all"])
        assert result.exit_code != 0
        assert "Cannot combine" in result.output

    def test_invalid_slug_rejected(self, runner, tmp_path):
        result = runner.invoke(main, ["scrape", "../etc/passwd", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0

    def test_skus_file_content(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            runner.invoke(main, ["scrape", "bigquery", "--output-dir", str(tmp_path)])
        lines = (tmp_path / "bigquery-skus.txt").read_text(encoding="utf-8").splitlines()
        assert lines == SKU_IDS

    def test_where_clause_file_content(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            runner.invoke(main, ["scrape", "bigquery", "--output-dir", str(tmp_path)])
        content = (tmp_path / "bigquery-where-clause.txt").read_text(encoding="utf-8").strip()
        assert content == '"947D-3B46-7781", "C493-D992-4C50"'

    def test_continues_after_group_fetch_error(self, runner, tmp_path):
        import requests
        def side_effect(session, url):
            if "bigquery" in url:
                raise requests.RequestException("timeout")
            return SKU_IDS

        with patch("sku_scraper.cli.scraper.fetch_sku_ids", side_effect=side_effect), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(
                main,
                ["scrape", "bigquery", "cloud-storage", "--output-dir", str(tmp_path)],
            )
        assert result.exit_code == 0
        assert not (tmp_path / "bigquery-skus.txt").exists()
        assert (tmp_path / "cloud-storage-skus.txt").exists()

    def test_creates_output_dir_if_missing(self, runner, tmp_path):
        new_dir = tmp_path / "new" / "nested"
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["scrape", "bigquery", "--output-dir", str(new_dir)])
        assert result.exit_code == 0
        assert new_dir.exists()


SAMPLE_INDEX = {
    "built_at": "2026-01-01T00:00:00+00:00",
    "by_id": {
        "947D-3B46-7781": {"name": "Active Logical Storage", "groups": ["bigquery", "cloud-storage"]},
        "C493-D992-4C50": {"name": "Active Logical Storage (asia-east1)", "groups": ["bigquery"]},
        "AAAA-1111-BBBB": {"name": "Standard Storage", "groups": ["cloud-storage"]},
    },
}


class TestBuildCacheCommand:
    def test_builds_and_reports(self, runner):
        with patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.cache.build_index", return_value=(SAMPLE_INDEX, {})), \
             patch("sku_scraper.cli.cache.save_cache"), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=None):
            result = runner.invoke(main, ["build-cache"])
        assert result.exit_code == 0
        assert "3 SKUs" in result.output

    def test_skips_if_cache_exists_without_force(self, runner):
        with patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["build-cache"])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_force_rebuilds_existing_cache(self, runner):
        with patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.cache.build_index", return_value=(SAMPLE_INDEX, {})), \
             patch("sku_scraper.cli.cache.save_cache"), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["build-cache", "--force"])
        assert result.exit_code == 0
        assert "3 SKUs" in result.output

    def test_prints_warnings_for_failed_groups(self, runner):
        errors = {"compute-engine": "timeout"}
        with patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.cache.build_index", return_value=(SAMPLE_INDEX, errors)), \
             patch("sku_scraper.cli.cache.save_cache"), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=None):
            result = runner.invoke(main, ["build-cache"])
        assert "compute-engine" in result.output


class TestSearchCommand:
    def test_search_by_id_found(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "947D-3B46-7781"])
        assert result.exit_code == 0
        assert "947D-3B46-7781" in result.output
        assert "Active Logical Storage" in result.output
        assert "bigquery" in result.output
        assert "cloud-storage" in result.output

    def test_search_by_id_not_found(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "ZZZZ-9999-ZZZZ"])
        assert result.exit_code == 0
        assert "No groups found" in result.output

    def test_search_by_name_found(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "active logical"])
        assert result.exit_code == 0
        assert "947D-3B46-7781" in result.output
        assert "C493-D992-4C50" in result.output

    def test_search_by_name_case_insensitive(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "STANDARD STORAGE"])
        assert result.exit_code == 0
        assert "AAAA-1111-BBBB" in result.output

    def test_search_by_name_not_found(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "nonexistent sku name"])
        assert result.exit_code == 0
        assert "No SKUs found" in result.output

    def test_error_with_no_args(self, runner):
        result = runner.invoke(main, ["search"])
        assert result.exit_code != 0
        assert "--id or --name" in result.output

    def test_error_combining_id_and_name(self, runner):
        result = runner.invoke(main, ["search", "--id", "947D-3B46-7781", "--name", "foo"])
        assert result.exit_code != 0
        assert "Cannot combine" in result.output

    def test_auto_builds_cache_when_missing(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=None), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.cache.build_index", return_value=(SAMPLE_INDEX, {})), \
             patch("sku_scraper.cli.cache.save_cache"):
            result = runner.invoke(main, ["search", "--id", "947D-3B46-7781"])
        assert result.exit_code == 0
        assert "947D-3B46-7781" in result.output

    def test_rebuild_flag_ignores_existing_cache(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX) as mock_load, \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.cache.build_index", return_value=(SAMPLE_INDEX, {})), \
             patch("sku_scraper.cli.cache.save_cache"), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "947D-3B46-7781", "--rebuild"])
        mock_load.assert_not_called()
        assert result.exit_code == 0
