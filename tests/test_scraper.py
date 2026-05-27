import pytest
import responses as resp_mock

from sku_scraper.scraper import (
    INDEX_URL,
    fetch_sku_entries,
    fetch_sku_groups,
    fetch_sku_ids,
    validate_slug,
    _make_session,
)


class TestValidateSlug:
    def test_valid_simple(self):
        assert validate_slug("bigquery") == "bigquery"

    def test_valid_with_hyphens(self):
        assert validate_slug("cloud-storage") == "cloud-storage"

    def test_valid_with_numbers(self):
        assert validate_slug("a2-80gb-vms-1-year-cud") == "a2-80gb-vms-1-year-cud"

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid SKU group slug"):
            validate_slug("../etc/passwd")

    def test_rejects_slash(self):
        with pytest.raises(ValueError):
            validate_slug("foo/bar")

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError):
            validate_slug("BigQuery")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_slug("")

    def test_rejects_leading_hyphen(self):
        with pytest.raises(ValueError):
            validate_slug("-bigquery")

    def test_rejects_shell_metacharacter(self):
        with pytest.raises(ValueError):
            validate_slug("big;query")


class TestFetchSkuGroups:
    @resp_mock.activate
    def test_parses_group_links(self, index_html):
        resp_mock.add(resp_mock.GET, INDEX_URL, body=index_html, status=200)
        session = _make_session()
        groups = fetch_sku_groups(session)

        assert "bigquery" in groups
        assert "cloud-storage" in groups
        assert "compute-engine" in groups
        assert groups["bigquery"] == "https://cloud.google.com/skus/sku-groups/bigquery"

    @resp_mock.activate
    def test_ignores_unrelated_links(self, index_html):
        resp_mock.add(resp_mock.GET, INDEX_URL, body=index_html, status=200)
        session = _make_session()
        groups = fetch_sku_groups(session)
        assert all(k.startswith("") for k in groups)
        assert len(groups) == 3

    @resp_mock.activate
    def test_raises_on_http_error(self):
        resp_mock.add(resp_mock.GET, INDEX_URL, status=503)
        session = _make_session()
        import requests
        with pytest.raises(requests.HTTPError):
            fetch_sku_groups(session)


class TestFetchSkuEntries:
    GROUP_URL = "https://cloud.google.com/skus/sku-groups/bigquery"

    @resp_mock.activate
    def test_extracts_id_and_name(self, group_html, expected_sku_entries):
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=group_html, status=200)
        session = _make_session()
        entries = fetch_sku_entries(session, self.GROUP_URL)
        assert entries == expected_sku_entries

    @resp_mock.activate
    def test_deduplicates_by_id(self):
        html = """<html><body><table>
          <tr><td>Svc</td><td>Name A</td><td><a href="#">947D-3B46-7781</a></td><td></td></tr>
          <tr><td>Svc</td><td>Name B</td><td><a href="#">947D-3B46-7781</a></td><td></td></tr>
          <tr><td>Svc</td><td>Name C</td><td><a href="#">C493-D992-4C50</a></td><td></td></tr>
        </table></body></html>"""
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=html, status=200)
        session = _make_session()
        entries = fetch_sku_entries(session, self.GROUP_URL)
        ids = [e["id"] for e in entries]
        assert ids == ["947D-3B46-7781", "C493-D992-4C50"]

    @resp_mock.activate
    def test_name_empty_when_not_in_table_row(self):
        html = """<html><body>
          <a href="#">947D-3B46-7781</a>
        </body></html>"""
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=html, status=200)
        session = _make_session()
        entries = fetch_sku_entries(session, self.GROUP_URL)
        assert entries[0]["name"] == ""

    def test_rejects_invalid_url(self):
        session = _make_session()
        with pytest.raises(ValueError, match="not an allowed SKU group URL"):
            fetch_sku_entries(session, "https://evil.example.com/skus/sku-groups/bigquery")

    @resp_mock.activate
    def test_returns_empty_list_when_no_skus(self):
        html = "<html><body><p>No SKUs here.</p></body></html>"
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=html, status=200)
        session = _make_session()
        assert fetch_sku_entries(session, self.GROUP_URL) == []


class TestFetchSkuIds:
    GROUP_URL = "https://cloud.google.com/skus/sku-groups/bigquery"

    @resp_mock.activate
    def test_extracts_sku_ids(self, group_html, expected_sku_ids):
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=group_html, status=200)
        session = _make_session()
        sku_ids = fetch_sku_ids(session, self.GROUP_URL)
        assert sku_ids == expected_sku_ids

    @resp_mock.activate
    def test_deduplicates_ids(self):
        html = """<html><body>
        <a href="/skus/?filter=947D-3B46-7781">947D-3B46-7781</a>
        <a href="/skus/?filter=947D-3B46-7781">947D-3B46-7781</a>
        <a href="/skus/?filter=C493-D992-4C50">C493-D992-4C50</a>
        </body></html>"""
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=html, status=200)
        session = _make_session()
        sku_ids = fetch_sku_ids(session, self.GROUP_URL)
        assert sku_ids == ["947D-3B46-7781", "C493-D992-4C50"]

    def test_rejects_invalid_url(self):
        session = _make_session()
        with pytest.raises(ValueError, match="not an allowed SKU group URL"):
            fetch_sku_ids(session, "https://evil.example.com/skus/sku-groups/bigquery")

    def test_rejects_url_without_trailing_slug(self):
        session = _make_session()
        with pytest.raises(ValueError):
            fetch_sku_ids(session, "https://cloud.google.com/skus/sku-groups")

    @resp_mock.activate
    def test_raises_on_http_error(self):
        resp_mock.add(resp_mock.GET, self.GROUP_URL, status=404)
        session = _make_session()
        import requests
        with pytest.raises(requests.HTTPError):
            fetch_sku_ids(session, self.GROUP_URL)

    @resp_mock.activate
    def test_returns_empty_list_when_no_skus(self):
        html = "<html><body><p>No SKUs here.</p></body></html>"
        resp_mock.add(resp_mock.GET, self.GROUP_URL, body=html, status=200)
        session = _make_session()
        assert fetch_sku_ids(session, self.GROUP_URL) == []
