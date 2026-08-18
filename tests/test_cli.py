from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from sku_scraper.cli import main, _group_sort_key

GROUPS = {
    "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
    "cloud-storage": {"url": "https://cloud.google.com/skus/sku-groups/cloud-storage", "name": "Cloud Storage"},
}
SKU_IDS = ["947D-3B46-7781", "C493-D992-4C50"]


class TestCompletionCommand:
    def test_bash_completion_exits_ok(self, runner):
        result = runner.invoke(main, ["completion", "bash"])
        assert result.exit_code == 0

    def test_zsh_completion_exits_ok(self, runner):
        result = runner.invoke(main, ["completion", "zsh"])
        assert result.exit_code == 0

    def test_bash_completion_contains_function(self, runner):
        result = runner.invoke(main, ["completion", "bash"])
        assert "_sku_scraper_completion" in result.output

    def test_zsh_completion_contains_compdef(self, runner):
        result = runner.invoke(main, ["completion", "zsh"])
        assert "#compdef" in result.output

    def test_invalid_shell_rejected(self, runner):
        result = runner.invoke(main, ["completion", "fish"])
        assert result.exit_code != 0


class TestDiffGroupListCommand:
    def test_no_cache_reports_error(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=None):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code != 0
        assert "No local cache" in result.output

    def test_cache_missing_group_names_reports_error(self, runner):
        index = {"built_at": "2026-01-01T00:00:00+00:00", "by_id": {}}
        with patch("sku_scraper.cli.cache.load_cache", return_value=index):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code != 0
        assert "build-cache" in result.output

    def test_no_changes_detected(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "cloud-storage": "Cloud Storage"},
            "by_id": {},
        }
        live = {
            "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
            "cloud-storage": {"url": "https://cloud.google.com/skus/sku-groups/cloud-storage", "name": "Cloud Storage"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        assert "No changes" in result.output

    def test_reports_new_groups(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery"},
            "by_id": {},
        }
        live = {
            "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
            "cloud-storage": {"url": "https://cloud.google.com/skus/sku-groups/cloud-storage", "name": "Cloud Storage"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        assert "cloud-storage" in result.output
        assert "Cloud Storage" in result.output

    def test_reports_removed_groups(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "cloud-storage": "Cloud Storage"},
            "by_id": {},
        }
        live = {
            "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        assert "cloud-storage" in result.output
        assert "Cloud Storage" in result.output

    def test_reports_both_new_and_removed(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "old-group": "Old Group"},
            "by_id": {},
        }
        live = {
            "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
            "new-group": {"url": "https://cloud.google.com/skus/sku-groups/new-group", "name": "New Group"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        assert "new-group" in result.output
        assert "New Group" in result.output
        assert "old-group" in result.output
        assert "Old Group" in result.output

    def test_shows_cache_date(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery"},
            "by_id": {},
        }
        live = {"bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"}}
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert "2026-01-01" in result.output

    def test_deprecated_prefix_match_goes_to_scheduled_not_new_or_removed(self, runner):
        # Cache has 'bigquery'; live has 'deprecated-bigquery'.
        # This is a rename to deprecation, not a new+removed pair.
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "cloud-storage": "Cloud Storage"},
            "by_id": {},
        }
        live = {
            "cloud-storage": {"url": "https://cloud.google.com/skus/sku-groups/cloud-storage", "name": "Cloud Storage"},
            "deprecated-bigquery": {"url": "https://cloud.google.com/skus/sku-groups/deprecated-bigquery", "name": "Deprecated BigQuery"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        assert "Scheduled for Deprecation" in result.output
        assert "bigquery" in result.output
        assert "deprecated-bigquery" in result.output
        # bigquery must NOT appear in the new or removed sections
        lines = result.output.splitlines()
        new_section = [l for l in lines if l.strip().startswith("+")]
        removed_section = [l for l in lines if l.strip().startswith("-")]
        assert not any("bigquery" in l for l in new_section)
        assert not any("bigquery" in l for l in removed_section)

    def test_scheduled_shows_old_group_name(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery"},
            "by_id": {},
        }
        live = {
            "deprecated-bigquery": {"url": "https://cloud.google.com/skus/sku-groups/deprecated-bigquery", "name": "Deprecated BigQuery"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        scheduled_lines = [l for l in result.output.splitlines() if l.strip().startswith("~")]
        assert len(scheduled_lines) == 1
        assert "BigQuery" in scheduled_lines[0]
        assert "bigquery" in scheduled_lines[0]
        assert "deprecated-bigquery" in scheduled_lines[0]

    def test_scheduled_section_appears_after_new_groups(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery"},
            "by_id": {},
        }
        live = {
            "deprecated-bigquery": {"url": "https://cloud.google.com/skus/sku-groups/deprecated-bigquery", "name": "Deprecated BigQuery"},
            "vertex-ai": {"url": "https://cloud.google.com/skus/sku-groups/vertex-ai", "name": "Vertex AI"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        lines = result.output.splitlines()
        new_header_idx = next(i for i, l in enumerate(lines) if "New groups" in l)
        scheduled_header_idx = next(i for i, l in enumerate(lines) if "Scheduled for Deprecation" in l)
        assert new_header_idx < scheduled_header_idx, "New groups section should appear before Scheduled for Deprecation"

    def test_deprecate_prefix_variant_also_matches(self, runner):
        # 'deprecate-bigquery' (no 'd' at end) should also match 'bigquery'.
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery"},
            "by_id": {},
        }
        live = {
            "deprecate-bigquery": {"url": "https://cloud.google.com/skus/sku-groups/deprecate-bigquery", "name": "Deprecate BigQuery"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        assert "Scheduled for Deprecation" in result.output

    def test_unmatched_deprecated_prefix_still_reported_as_new(self, runner):
        # 'deprecated-vertexai' appears in live but 'vertexai' is NOT in the cache;
        # it should be treated as a plain new group, not scheduled for deprecation.
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery"},
            "by_id": {},
        }
        live = {
            "bigquery": {"url": "https://cloud.google.com/skus/sku-groups/bigquery", "name": "BigQuery"},
            "deprecated-vertexai": {"url": "https://cloud.google.com/skus/sku-groups/deprecated-vertexai", "name": "Deprecated Vertex AI"},
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=live), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(main, ["diff-group-list"])
        assert result.exit_code == 0
        lines = result.output.splitlines()
        new_section = [l for l in lines if l.strip().startswith("+")]
        assert any("deprecated-vertexai" in l for l in new_section)


class TestGroupSortKey:
    def test_non_deprecated_sorts_before_deprecated(self):
        groups = ["bigquery", "compute-engine-deprecated", "cloud-storage"]
        assert sorted(groups, key=_group_sort_key) == [
            "bigquery", "cloud-storage", "compute-engine-deprecated"
        ]

    def test_deprecated_variants_sorted_alphabetically_among_themselves(self):
        groups = ["z-deprecated", "a-deprecated", "bigquery"]
        assert sorted(groups, key=_group_sort_key) == [
            "bigquery", "a-deprecated", "z-deprecated"
        ]

    def test_non_deprecated_sorted_alphabetically(self):
        groups = ["storage", "bigquery", "compute"]
        assert sorted(groups, key=_group_sort_key) == ["bigquery", "compute", "storage"]

    def test_deprecate_substring_match(self):
        groups = ["old-deprecate-sku-group", "bigquery"]
        assert sorted(groups, key=_group_sort_key)[0] == "bigquery"


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

    def test_single_file_writes_combined_files(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(
                main,
                ["scrape", "bigquery", "cloud-storage", "--single-file", "--output-dir", str(tmp_path)],
            )
        assert result.exit_code == 0
        assert (tmp_path / "combined-skus.txt").exists()
        assert (tmp_path / "combined-where-clause.txt").exists()
        assert not (tmp_path / "bigquery-skus.txt").exists()
        assert not (tmp_path / "cloud-storage-skus.txt").exists()

    def test_single_file_deduplicates_sku_ids(self, runner, tmp_path):
        # Both groups return the same SKU IDs — combined file should have no duplicates.
        with patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            runner.invoke(
                main,
                ["scrape", "bigquery", "cloud-storage", "--single-file", "--output-dir", str(tmp_path)],
            )
        lines = (tmp_path / "combined-skus.txt").read_text(encoding="utf-8").splitlines()
        assert lines == list(dict.fromkeys(SKU_IDS))  # deduplicated, order preserved

    def test_single_file_combines_unique_ids_from_multiple_groups(self, runner, tmp_path):
        def side_effect(session, url):
            if "bigquery" in url:
                return ["AAAA-1111-0001", "BBBB-2222-0002"]
            return ["BBBB-2222-0002", "CCCC-3333-0003"]  # BBBB shared

        with patch("sku_scraper.cli.scraper.fetch_sku_ids", side_effect=side_effect), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            runner.invoke(
                main,
                ["scrape", "bigquery", "cloud-storage", "--single-file", "--output-dir", str(tmp_path)],
            )
        lines = (tmp_path / "combined-skus.txt").read_text(encoding="utf-8").splitlines()
        assert lines == ["AAAA-1111-0001", "BBBB-2222-0002", "CCCC-3333-0003"]

    def test_single_file_with_all_flag(self, runner, tmp_path):
        with patch("sku_scraper.cli.scraper.fetch_sku_groups", return_value=GROUPS), \
             patch("sku_scraper.cli.scraper.fetch_sku_ids", return_value=SKU_IDS), \
             patch("sku_scraper.cli.scraper._make_session", return_value=MagicMock()):
            result = runner.invoke(
                main, ["scrape", "--all", "--single-file", "--output-dir", str(tmp_path)]
            )
        assert result.exit_code == 0
        assert (tmp_path / "combined-skus.txt").exists()
        assert (tmp_path / "combined-where-clause.txt").exists()


SAMPLE_INDEX = {
    "built_at": "2026-01-01T00:00:00+00:00",
    "group_names": {
        "bigquery": "BigQuery",
        "cloud-storage": "Cloud Storage",
    },
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
        assert "BigQuery" in result.output
        assert "bigquery" in result.output
        assert "Cloud Storage" in result.output
        assert "cloud-storage" in result.output

    def test_search_by_id_shows_each_group_on_own_line(self, runner):
        with patch("sku_scraper.cli.cache.load_cache", return_value=SAMPLE_INDEX), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "947D-3B46-7781"])
        lines = result.output.splitlines()
        group_lines = [l for l in lines if "bigquery" in l.lower() or "cloud-storage" in l.lower()]
        assert len(group_lines) == 2

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
        assert "BigQuery" in result.output
        assert "bigquery" in result.output
        assert "GROUP NAME" in result.output
        assert "GROUP SLUG" in result.output

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

    def test_search_by_id_no_duplicate_when_group_names_missing(self, runner):
        index = {k: v for k, v in SAMPLE_INDEX.items() if k != "group_names"}
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "947D-3B46-7781"])
        assert result.exit_code == 0
        for line in result.output.splitlines():
            assert line.count("bigquery") <= 1, f"Slug duplicated on same line: {line!r}"
            assert line.count("cloud-storage") <= 1, f"Slug duplicated on same line: {line!r}"

    def test_search_by_name_no_duplicate_when_group_names_missing(self, runner):
        index = {k: v for k, v in SAMPLE_INDEX.items() if k != "group_names"}
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "active logical"])
        assert result.exit_code == 0
        for line in result.output.splitlines():
            assert line.count("bigquery") <= 1, f"Slug duplicated on same line: {line!r}"

    def test_search_by_name_deprecated_groups_sorted_last(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "deprecated-skus": "Deprecated SKUs"},
            "by_id": {
                # "Alpha SKU" sorts before "Beta SKU" alphabetically, but is only in a deprecated group
                "AAAA-0000-0001": {"name": "Alpha SKU", "groups": ["deprecated-skus"]},
                "BBBB-0000-0002": {"name": "Beta SKU", "groups": ["bigquery"]},
            },
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "sku"])
        assert result.exit_code == 0
        lines = result.output.splitlines()
        beta_idx = next(i for i, l in enumerate(lines) if "BBBB-0000-0002" in l)
        alpha_idx = next(i for i, l in enumerate(lines) if "AAAA-0000-0001" in l)
        assert beta_idx < alpha_idx, "Non-deprecated group row should appear before deprecated group row"

    def test_ignore_deprecated_filters_id_results(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "deprecated-compute": "Deprecated Compute"},
            "by_id": {
                "947D-3B46-7781": {"name": "Active Logical Storage", "groups": ["bigquery", "deprecated-compute"]},
            },
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "947D-3B46-7781", "--ignore-deprecated"])
        assert result.exit_code == 0
        assert "bigquery" in result.output
        assert "deprecated-compute" not in result.output

    def test_ignore_deprecated_shows_not_found_when_all_groups_filtered(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"deprecated-compute": "Deprecated Compute"},
            "by_id": {
                "DDDD-0000-0001": {"name": "Deprecated Only SKU", "groups": ["deprecated-compute"]},
            },
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--id", "DDDD-0000-0001", "--ignore-deprecated"])
        assert result.exit_code == 0
        assert "No groups found" in result.output

    def test_ignore_deprecated_filters_name_results(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"bigquery": "BigQuery", "deprecated-compute": "Deprecated Compute"},
            "by_id": {
                "947D-3B46-7781": {"name": "Active Logical Storage", "groups": ["bigquery", "deprecated-compute"]},
                "DDDD-0000-0001": {"name": "Deprecated Only SKU", "groups": ["deprecated-compute"]},
            },
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "storage", "--ignore-deprecated"])
        assert result.exit_code == 0
        assert "947D-3B46-7781" in result.output
        assert "bigquery" in result.output
        assert "deprecated-compute" not in result.output
        assert "DDDD-0000-0001" not in result.output

    def test_ignore_deprecated_shows_not_found_when_all_name_rows_filtered(self, runner):
        index = {
            "built_at": "2026-01-01T00:00:00+00:00",
            "group_names": {"deprecated-compute": "Deprecated Compute"},
            "by_id": {
                "DDDD-0000-0001": {"name": "Deprecated Only SKU", "groups": ["deprecated-compute"]},
            },
        }
        with patch("sku_scraper.cli.cache.load_cache", return_value=index), \
             patch("sku_scraper.cli.cache.cache_age_seconds", return_value=3600.0):
            result = runner.invoke(main, ["search", "--name", "deprecated only", "--ignore-deprecated"])
        assert result.exit_code == 0
        assert "No SKUs found" in result.output

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
