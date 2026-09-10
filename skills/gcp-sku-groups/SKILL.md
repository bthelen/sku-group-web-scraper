# gcp-sku-groups

A skill for answering questions about Google Cloud SKU Groups using the `sku-scraper` CLI.

## What this skill covers

- Looking up which SKU groups contain a specific SKU (by ID or name)
- Listing all available SKU groups
- Exporting SKU ID lists to files for use in SQL queries
- Detecting changes in the live SKU group list since the last cache build

## Setup

Install the CLI from the repo root before using this skill:

```bash
pip install -e .
```

## The cache

`search` and `diff-group-list` work from a local index cache. The cache is built
automatically the first time `search` runs, but it is faster and more reliable to
build it explicitly:

```bash
sku-scraper build-cache
```

The cache lives in the OS user cache directory (`~/Library/Caches/sku-scraper/index.json`
on macOS). It is flagged stale after 7 days. Force a rebuild any time with `--force`.

If a command fails with a cache error, run `sku-scraper build-cache --force` and retry.

---

## Command reference

### List all SKU groups

**Natural language:** "what SKU groups are available", "show me all groups", "list sku groups"

```bash
sku-scraper list --json
```

Returns a sorted array of every group:

```json
[
  {"slug": "bigquery", "name": "BigQuery", "url": "https://..."},
  ...
]
```

---

### Search by SKU ID

**Natural language:** "what groups is SKU 8ADF-0E5E-853F in?", "which group contains this SKU ID",
"look up SKU 947D-3B46-7781"

```bash
sku-scraper search --id <SKU_ID> --json
```

Returns the SKU's display name and every group it belongs to:

```json
{
  "sku_id": "8ADF-0E5E-853F",
  "name": "Network Egress",
  "groups": [
    {"slug": "compute-engine", "name": "Compute Engine"},
    {"slug": "cloud-storage", "name": "Cloud Storage"}
  ]
}
```

Exits non-zero if the SKU is not found. Add `--ignore-deprecated` to exclude groups
whose slugs contain "deprecat".

---

### Search by SKU name

**Natural language:** "find SKUs named 'network egress'", "which SKUs contain 'storage' in the name",
"search for active logical storage"

```bash
sku-scraper search --name "<query>" --json
```

Case-insensitive substring match. Returns an array, one entry per matching SKU:

```json
[
  {
    "sku_id": "947D-3B46-7781",
    "name": "Active Logical Storage",
    "groups": [
      {"slug": "bigquery", "name": "BigQuery"}
    ]
  },
  ...
]
```

Exits non-zero if nothing matches. Add `--ignore-deprecated` to suppress deprecated groups.

---

### Diff the live group list against the local cache

**Natural language:** "have any SKU groups been added or removed?", "what's changed since my
last cache build?", "are any groups scheduled for deprecation?", "show me new or removed groups"

```bash
sku-scraper diff-group-list --json
```

Fetches the current live group index and compares it to the local cache. Always returns
all three categories (empty lists when nothing changed):

```json
{
  "cache_built_at": "2026-01-01T00:00:00+00:00",
  "new": [
    {"slug": "vertex-ai", "name": "Vertex AI"}
  ],
  "scheduled_for_deprecation": [
    {"old_slug": "bigquery", "new_slug": "deprecated-bigquery", "name": "BigQuery"}
  ],
  "removed": [
    {"slug": "old-compute", "name": "Old Compute Group"}
  ]
}
```

A group in `scheduled_for_deprecation` means the live list now has the same slug with
a `deprecated-` (or similar) prefix. It is not counted in `new` or `removed`.

Requires a cache with group names. If it fails, run `sku-scraper build-cache --force`.

---

### Export SKU IDs to files

**Natural language:** "export bigquery SKU IDs", "scrape the cloud-storage group",
"download all SKU groups to files", "create a where clause for compute-engine"

```bash
# One group
sku-scraper scrape bigquery

# Multiple groups
sku-scraper scrape bigquery cloud-storage compute-engine

# All groups
sku-scraper scrape --all

# All groups combined into one file pair, written to a specific directory
sku-scraper scrape --all --single-file --output-dir ~/sku-exports
```

Writes two files per group (or one pair with `--single-file`):
- `<group>-skus.txt` — one SKU ID per line
- `<group>-where-clause.txt` — SKU IDs quoted and comma-separated for SQL `WHERE` clauses

Duplicate SKU IDs are deduplicated automatically.

---

### Build or refresh the cache

**Natural language:** "build the cache", "refresh the index", "rebuild the SKU cache",
"the cache is stale, update it"

```bash
# Build if not present
sku-scraper build-cache

# Force rebuild even if cache is fresh
sku-scraper build-cache --force

# Faster parallel fetch (default: 10 workers)
sku-scraper build-cache --workers 20
```

---

## Error handling

| Symptom | Likely cause | Fix |
|---|---|---|
| `No local cache found` | Cache has never been built | `sku-scraper build-cache` |
| `Cache is missing group names` | Cache was built with an old version | `sku-scraper build-cache --force` |
| `No groups found for SKU ID` | SKU not in cache, or wrong ID | Verify the ID; rebuild cache if it might be stale |
| `Failed to fetch SKU group index` | Network error | Check connectivity and retry |
| `scrape` WARNING lines in output | One group page failed to load | Retry that group individually |
