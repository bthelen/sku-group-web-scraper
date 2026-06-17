# sku-group-web-scraper

A CLI tool that scrapes Google Cloud SKU Group pages and exports SKU ID lists as text files.

## What it does

For any SKU group listed at [cloud.google.com/skus/sku-groups](https://cloud.google.com/skus/sku-groups), the tool can:

- **Scrape** a group and export its SKU IDs as text files ready for use in SQL queries
- **Search** across all groups by SKU ID or SKU name to find which groups contain a given SKU

Scrape output files:

- `<group>-skus.txt` — one SKU ID per line
- `<group>-where-clause.txt` — SKU IDs quoted and comma-separated, ready to paste into a SQL `WHERE` clause

## Installation

Requires Python 3.11+.

```bash
pip install -e .
```

## Usage

### List all available SKU groups

```bash
sku-scraper list
```

Prints every group slug and its URL. Use the slug as the argument to `scrape`.

### Scrape one group

```bash
sku-scraper scrape bigquery
```

Writes `bigquery-skus.txt` and `bigquery-where-clause.txt` in the current directory.

### Scrape multiple groups

```bash
sku-scraper scrape bigquery cloud-storage compute-engine
```

### Scrape all groups

```bash
sku-scraper scrape --all
```

### Write files to a specific directory

```bash
sku-scraper scrape bigquery --output-dir ~/sku-exports
```

The directory is created if it does not exist.

### Combine all results into a single pair of files

By default each group gets its own pair of output files. Use `--single-file` to merge all scraped groups into `combined-skus.txt` and `combined-where-clause.txt` instead. SKU IDs that appear in more than one group are deduplicated.

```bash
sku-scraper scrape bigquery cloud-storage --single-file
sku-scraper scrape --all --single-file --output-dir ~/sku-exports
```

---

## Searching for SKU groups by ID or name

The `search` command lets you look up which SKU groups contain a given SKU ID or name. It works from a local cache so it doesn't need to re-fetch every group page each time you search.

### Search by exact SKU ID

```bash
sku-scraper search --id 947D-3B46-7781
```

Example output:
```
SKU ID : 947D-3B46-7781
Name   : Active Logical Storage
Groups : bigquery, cloud-storage
```

### Search by SKU name

Matches any SKU whose name contains the search text (case-insensitive).

```bash
sku-scraper search --name "active logical storage"
```

Example output:
```
SKU ID          SKU NAME                              GROUPS
----------------------------------------------------------------------
947D-3B46-7781  Active Logical Storage                bigquery, cloud-storage
C493-D992-4C50  Active Logical Storage (asia-east1)   bigquery
...
```

### How the cache works

The first time you run `search`, the tool automatically fetches all SKU group pages in parallel and saves an index to your OS cache directory (`~/Library/Caches/sku-scraper/index.json` on macOS). Subsequent searches are instant.

The cache is flagged as stale after 7 days. To rebuild it manually:

```bash
sku-scraper build-cache
```

To force a rebuild even if the cache is fresh:

```bash
sku-scraper build-cache --force
```

To control how many pages are fetched in parallel (default: 10):

```bash
sku-scraper build-cache --workers 20
```

To force a rebuild as part of a search in one step:

```bash
sku-scraper search --name "storage" --rebuild
```

### Filtering out deprecated groups

Some SKU groups have slugs containing "deprecat" (e.g. `compute-engine-deprecatedskus`). By default these appear at the end of search results. To exclude them entirely:

```bash
sku-scraper search --id 947D-3B46-7781 --ignore-deprecated
sku-scraper search --name "storage" --ignore-deprecated
```

If a SKU exists only in deprecated groups, `--ignore-deprecated` will report it as not found.

---

### Output file format

**`bigquery-skus.txt`**
```
947D-3B46-7781
0752-7FDA-AF5E
C493-D992-4C50
...
```

**`bigquery-where-clause.txt`**
```
"947D-3B46-7781", "0752-7FDA-AF5E", "C493-D992-4C50", ...
```

---

## Developer guide

### Set up a development environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Project layout

```
src/sku_scraper/
├── cli.py       # Click CLI — list, scrape, search, build-cache commands
├── scraper.py   # HTTP fetching and HTML parsing
├── cache.py     # Index building (parallel), cache save/load
└── writer.py    # Output file generation
tests/
├── conftest.py  # Shared HTML fixtures
├── test_cli.py
├── test_scraper.py
├── test_cache.py
└── test_writer.py
pyproject.toml   # Package metadata, dependencies, tool config
```

### Run the tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=sku_scraper --cov-report=term-missing
```

### Dependencies

| Package | Purpose |
|---|---|
| `click` | CLI framework |
| `requests` | HTTP client |
| `beautifulsoup4` | HTML parsing |
| `lxml` | Fast HTML parser backend |
| `platformdirs` | OS-appropriate cache directory |
| `tqdm` | Progress bar for cache builds |
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `responses` | HTTP mocking in tests |

### Keeping dependencies up to date

```bash
pip install --upgrade click requests beautifulsoup4 lxml platformdirs tqdm
pip install --upgrade pytest pytest-cov responses
```
