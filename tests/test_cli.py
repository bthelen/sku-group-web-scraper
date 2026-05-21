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
