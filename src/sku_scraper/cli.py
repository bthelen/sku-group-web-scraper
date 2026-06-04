import sys
from pathlib import Path

import click
import requests

from sku_scraper import cache, scraper, writer


@click.group()
def main() -> None:
    """Scrape Google Cloud SKU Group pages and export SKU ID lists."""


@main.command(name="list")
def list_groups() -> None:
    """List all available SKU group names and their slugs."""
    session = scraper._make_session()
    try:
        groups = scraper.fetch_sku_groups(session)
    except requests.RequestException as exc:
        raise click.ClickException(f"Failed to fetch SKU group index: {exc}") from exc

    if not groups:
        click.echo("No SKU groups found.")
        return

    max_slug = max(len(s) for s in groups)
    click.echo(f"{'SLUG':<{max_slug}}  URL")
    click.echo("-" * (max_slug + 50))
    for slug, url in sorted(groups.items()):
        click.echo(f"{slug:<{max_slug}}  {url}")


@main.command()
@click.argument("groups", nargs=-1, metavar="[GROUP]...")
@click.option("--all", "scrape_all", is_flag=True, help="Scrape every SKU group.")
@click.option(
    "--output-dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    help="Directory to write output files into.",
)
def scrape(groups: tuple[str, ...], scrape_all: bool, output_dir: Path) -> None:
    """Scrape one or more SKU groups and write output files.

    Pass GROUP slugs as arguments (e.g. 'bigquery cloud-storage'), or use
    --all to scrape every group.
    """
    if not groups and not scrape_all:
        raise click.UsageError("Provide at least one GROUP argument or use --all.")
    if groups and scrape_all:
        raise click.UsageError("Cannot combine GROUP arguments with --all.")

    output_dir.mkdir(parents=True, exist_ok=True)
    session = scraper._make_session()

    if scrape_all:
        try:
            all_groups = scraper.fetch_sku_groups(session)
        except requests.RequestException as exc:
            raise click.ClickException(f"Failed to fetch SKU group index: {exc}") from exc
        slugs_to_urls = all_groups
    else:
        try:
            validated = [scraper.validate_slug(g) for g in groups]
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
        slugs_to_urls = {
            slug: f"https://cloud.google.com/skus/sku-groups/{slug}"
            for slug in validated
        }

    for slug, url in slugs_to_urls.items():
        try:
            sku_ids = scraper.fetch_sku_ids(session, url)
        except (requests.RequestException, ValueError) as exc:
            click.echo(click.style(f"  ERROR  {slug}: {exc}", fg="red"), err=True)
            continue

        skus_path = writer.write_skus_file(slug, sku_ids, output_dir)
        where_path = writer.write_where_clause_file(slug, sku_ids, output_dir)
        click.echo(
            f"{slug}: {len(sku_ids)} SKUs → {skus_path.name}, {where_path.name}"
        )


@main.command(name="build-cache")
@click.option("--workers", default=10, show_default=True, help="Parallel fetch workers.")
@click.option("--force", is_flag=True, help="Rebuild even if cache already exists.")
def build_cache_cmd(workers: int, force: bool) -> None:
    """Build (or rebuild) the local SKU group index cache.

    The cache is stored in the OS user cache directory and is used by the
    'search' command to look up SKU IDs and names without re-fetching all pages.
    """
    if not force:
        age = cache.cache_age_seconds()
        if age is not None:
            days = age / 86400
            click.echo(f"Cache already exists (built {days:.1f} days ago). Use --force to rebuild.")
            return

    session = scraper._make_session()
    try:
        groups = scraper.fetch_sku_groups(session)
    except requests.RequestException as exc:
        raise click.ClickException(f"Failed to fetch SKU group index: {exc}") from exc

    click.echo(f"Building index for {len(groups)} groups with {workers} workers...")
    index, errors = cache.build_index(
        session, groups, workers=workers, show_progress=sys.stderr.isatty()
    )
    cache.save_cache(index)

    sku_count = len(index["by_id"])
    click.echo(f"Cached {sku_count} SKUs across {len(groups) - len(errors)} groups → {cache.CACHE_FILE}")

    for slug, err in sorted(errors.items()):
        click.echo(click.style(f"  WARNING  {slug}: {err}", fg="yellow"), err=True)


_GROUP_COLORS = ["cyan", "green", "yellow", "magenta", "bright_blue", "bright_red"]


def _group_color_map(groups: list[str] | set[str]) -> dict[str, str]:
    """Assign a stable color to each group slug (sorted alphabetically)."""
    return {
        slug: _GROUP_COLORS[i % len(_GROUP_COLORS)]
        for i, slug in enumerate(sorted(groups))
    }


def _group_sort_key(slug: str) -> tuple[int, str]:
    return (1 if "deprecat" in slug else 0, slug)


def _colorize_groups(groups: list[str], color_map: dict[str, str]) -> str:
    return ", ".join(
        click.style(g, fg=color_map.get(g, "white"))
        for g in sorted(groups, key=_group_sort_key)
    )


@main.command()
@click.option("--id", "sku_id", default=None, metavar="SKU_ID", help="Search by exact SKU ID.")
@click.option("--name", "sku_name", default=None, metavar="TEXT", help="Search by SKU name (case-insensitive substring).")
@click.option("--rebuild", is_flag=True, help="Force rebuild the cache before searching.")
@click.option("--workers", default=10, show_default=True, help="Parallel fetch workers (used when building cache).")
def search(sku_id: str | None, sku_name: str | None, rebuild: bool, workers: int) -> None:
    """Search for which SKU groups contain a given SKU ID or name.

    Examples:

      sku-scraper search --id 947D-3B46-7781

      sku-scraper search --name "Active Logical Storage"
    """
    if not sku_id and not sku_name:
        raise click.UsageError("Provide --id or --name.")
    if sku_id and sku_name:
        raise click.UsageError("Cannot combine --id and --name.")

    index = None if rebuild else cache.load_cache()

    if index is None:
        click.echo("Building index (this may take a minute)...", err=True)
        session = scraper._make_session()
        try:
            groups = scraper.fetch_sku_groups(session)
        except requests.RequestException as exc:
            raise click.ClickException(f"Failed to fetch SKU group index: {exc}") from exc

        index, errors = cache.build_index(
            session, groups, workers=workers, show_progress=sys.stderr.isatty()
        )
        cache.save_cache(index)
        for slug, err in sorted(errors.items()):
            click.echo(click.style(f"  WARNING  {slug}: {err}", fg="yellow"), err=True)
    else:
        age = cache.cache_age_seconds()
        if age is not None and age > cache.STALE_AFTER_DAYS * 86400:
            days = age / 86400
            click.echo(
                click.style(f"Note: cache is {days:.0f} days old. Run 'build-cache --force' to refresh.", fg="yellow"),
                err=True,
            )

    built_at = index.get("built_at", "unknown")
    click.echo(f"Cache built: {built_at}", err=True)

    by_id: dict = index["by_id"]

    if sku_id:
        entry = by_id.get(sku_id)
        if entry is None:
            click.echo(f"No groups found for SKU ID {sku_id!r}.")
            return
        color_map = _group_color_map(entry["groups"])
        click.echo(f"SKU ID : {sku_id}")
        click.echo(f"Name   : {entry['name']}")
        click.echo(f"Groups : {_colorize_groups(entry['groups'], color_map)}")
    else:
        query = sku_name.lower()
        matches = sorted(
            ((sid, e) for sid, e in by_id.items() if query in e["name"].lower()),
            key=lambda x: (x[1]["name"], x[0]),
        )
        if not matches:
            click.echo(f"No SKUs found matching name {sku_name!r}.")
            return
        all_groups = {g for _, e in matches for g in e["groups"]}
        color_map = _group_color_map(all_groups)
        id_w = max(len(sid) for sid, _ in matches)
        name_w = max(len(e["name"]) for _, e in matches)
        click.echo(f"{'SKU ID':<{id_w}}  {'SKU NAME':<{name_w}}  GROUPS")
        click.echo("-" * (id_w + name_w + 30))
        for sid, entry in matches:
            groups_str = _colorize_groups(entry["groups"], color_map)
            click.echo(f"{sid:<{id_w}}  {entry['name']:<{name_w}}  {groups_str}")
