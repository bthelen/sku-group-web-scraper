import pytest

INDEX_HTML = """
<html><body>
<a href="/skus/sku-groups/bigquery">BigQuery</a>
<a href="/skus/sku-groups/cloud-storage">Cloud Storage</a>
<a href="/skus/sku-groups/compute-engine">Compute Engine</a>
<a href="/other/page">Unrelated Link</a>
</body></html>
"""

GROUP_HTML = """
<html><body>
<table>
  <tr>
    <td>BigQuery</td>
    <td>Active Logical Storage</td>
    <td><a href="/skus/?filter=947D-3B46-7781">947D-3B46-7781</a></td>
    <td>May 15, 2020</td>
  </tr>
  <tr>
    <td>BigQuery</td>
    <td>Active Logical Storage (asia-east1)</td>
    <td><a href="/skus/?filter=C493-D992-4C50">C493-D992-4C50</a></td>
    <td>May 15, 2020</td>
  </tr>
  <tr>
    <td>BigQuery</td>
    <td>Analysis</td>
    <td><a href="/skus/?filter=1234-ABCD-5678">1234-ABCD-5678</a></td>
    <td>May 15, 2020</td>
  </tr>
</table>
</body></html>
"""

EXPECTED_SKU_IDS = ["947D-3B46-7781", "C493-D992-4C50", "1234-ABCD-5678"]

EXPECTED_SKU_ENTRIES = [
    {"id": "947D-3B46-7781", "name": "Active Logical Storage"},
    {"id": "C493-D992-4C50", "name": "Active Logical Storage (asia-east1)"},
    {"id": "1234-ABCD-5678", "name": "Analysis"},
]


@pytest.fixture
def index_html() -> str:
    return INDEX_HTML


@pytest.fixture
def group_html() -> str:
    return GROUP_HTML


@pytest.fixture
def expected_sku_ids() -> list[str]:
    return EXPECTED_SKU_IDS


@pytest.fixture
def expected_sku_entries() -> list[dict[str, str]]:
    return EXPECTED_SKU_ENTRIES
