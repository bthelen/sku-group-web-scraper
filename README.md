# sku-group-web-scraper

A CLI tool that scrapes Google Cloud SKU Group pages and exports SKU ID lists as text files.

## What it does

For any SKU group listed at [cloud.google.com/skus/sku-groups](https://cloud.google.com/skus/sku-groups), the tool fetches all SKU IDs and writes two files:

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
├── cli.py       # Click CLI — list and scrape commands
├── scraper.py   # HTTP fetching and HTML parsing
└── writer.py    # Output file generation
tests/
├── conftest.py  # Shared HTML fixtures
├── test_cli.py
├── test_scraper.py
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
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `responses` | HTTP mocking in tests |

### Keeping dependencies up to date

```bash
pip install --upgrade click requests beautifulsoup4 lxml
pip install --upgrade pytest pytest-cov responses
```
