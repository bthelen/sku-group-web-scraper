from pathlib import Path

import pytest

from sku_scraper.writer import slug_to_filename, write_skus_file, write_where_clause_file


SKU_IDS = ["947D-3B46-7781", "C493-D992-4C50", "1234-ABCD-5678"]


class TestSlugToFilename:
    def test_passes_safe_slug(self):
        assert slug_to_filename("bigquery") == "bigquery"

    def test_preserves_hyphens(self):
        assert slug_to_filename("cloud-storage") == "cloud-storage"

    def test_replaces_unsafe_chars(self):
        result = slug_to_filename("foo/bar")
        assert "/" not in result

    def test_replaces_dots(self):
        result = slug_to_filename("foo.bar")
        assert "." not in result


class TestWriteSkusFile:
    def test_creates_file(self, tmp_path):
        path = write_skus_file("bigquery", SKU_IDS, tmp_path)
        assert path.exists()

    def test_filename(self, tmp_path):
        path = write_skus_file("bigquery", SKU_IDS, tmp_path)
        assert path.name == "bigquery-skus.txt"

    def test_one_id_per_line(self, tmp_path):
        path = write_skus_file("bigquery", SKU_IDS, tmp_path)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines == SKU_IDS

    def test_empty_list(self, tmp_path):
        path = write_skus_file("bigquery", [], tmp_path)
        assert path.read_text(encoding="utf-8") == "\n"

    def test_slug_with_hyphen(self, tmp_path):
        path = write_skus_file("cloud-storage", SKU_IDS, tmp_path)
        assert path.name == "cloud-storage-skus.txt"


class TestWriteWhereClauseFile:
    def test_creates_file(self, tmp_path):
        path = write_where_clause_file("bigquery", SKU_IDS, tmp_path)
        assert path.exists()

    def test_filename(self, tmp_path):
        path = write_where_clause_file("bigquery", SKU_IDS, tmp_path)
        assert path.name == "bigquery-where-clause.txt"

    def test_quoted_comma_separated(self, tmp_path):
        path = write_where_clause_file("bigquery", SKU_IDS, tmp_path)
        content = path.read_text(encoding="utf-8").strip()
        assert content == '"947D-3B46-7781", "C493-D992-4C50", "1234-ABCD-5678"'

    def test_single_id(self, tmp_path):
        path = write_where_clause_file("bigquery", ["947D-3B46-7781"], tmp_path)
        content = path.read_text(encoding="utf-8").strip()
        assert content == '"947D-3B46-7781"'

    def test_empty_list(self, tmp_path):
        path = write_where_clause_file("bigquery", [], tmp_path)
        content = path.read_text(encoding="utf-8").strip()
        assert content == ""
