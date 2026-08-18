import sys
from pathlib import Path

import click
import requests
from click.shell_completion import BashComplete, ZshComplete

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
    for slug, info in sorted(groups.items()):
        click.echo(f"{slug:<{max_slug}}  {info['url']}")


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
@click.option(
    "--single-file",
    "single_file",
    is_flag=True,
    help="Combine all scraped SKUs into combined-skus.txt and combined-where-clause.txt.",
)
def scrape(groups: tuple[str, ...], scrape_all: bool, output_dir: Path, single_file: bool) -> None:
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
        slugs_to_urls = {slug: info["url"] for slug, info in all_groups.items()}
    else:
        try:
            validated = [scraper.validate_slug(g) for g in groups]
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
        slugs_to_urls = {
            slug: f"https://cloud.google.com/skus/sku-groups/{slug}"
            for slug in validated
        }

    combined: dict[str, None] = {}  # ordered set for deduplication across groups

    for slug, url in slugs_to_urls.items():
        try:
            sku_ids = scraper.fetch_sku_ids(session, url)
        except (requests.RequestException, ValueError) as exc:
            click.echo(click.style(f"  ERROR  {slug}: {exc}", fg="red"), err=True)
            continue

        if single_file:
            for sid in sku_ids:
                combined[sid] = None
            click.echo(f"{slug}: {len(sku_ids)} SKUs")
        else:
            skus_path = writer.write_skus_file(slug, sku_ids, output_dir)
            where_path = writer.write_where_clause_file(slug, sku_ids, output_dir)
            click.echo(f"{slug}: {len(sku_ids)} SKUs → {skus_path.name}, {where_path.name}")

    if single_file:
        all_ids = list(combined.keys())
        skus_path = writer.write_skus_file("combined", all_ids, output_dir)
        where_path = writer.write_where_clause_file("combined", all_ids, output_dir)
        click.echo(f"Combined: {len(all_ids)} unique SKUs → {skus_path.name}, {where_path.name}")


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


@main.command()
@click.option("--id", "sku_id", default=None, metavar="SKU_ID", help="Search by exact SKU ID.")
@click.option("--name", "sku_name", default=None, metavar="TEXT", help="Search by SKU name (case-insensitive substring).")
@click.option("--rebuild", is_flag=True, help="Force rebuild the cache before searching.")
@click.option("--workers", default=10, show_default=True, help="Parallel fetch workers (used when building cache).")
@click.option("--ignore-deprecated", "ignore_deprecated", is_flag=True, help="Exclude deprecated SKU groups from results.")
def search(sku_id: str | None, sku_name: str | None, rebuild: bool, workers: int, ignore_deprecated: bool) -> None:
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

    group_names: dict[str, str] = index.get("group_names", {})
    if not group_names and "group_names" not in index:
        click.echo(
            click.style("Note: cache is missing group display names. Run 'build-cache --force' to add them.", fg="yellow"),
            err=True,
        )
    by_id: dict = index["by_id"]

    if sku_id:
        entry = by_id.get(sku_id)
        if entry is None:
            click.echo(f"No groups found for SKU ID {sku_id!r}.")
            return
        sorted_groups = sorted(entry["groups"], key=_group_sort_key)
        if ignore_deprecated:
            sorted_groups = [g for g in sorted_groups if "deprecat" not in g]
        if not sorted_groups:
            click.echo(f"No groups found for SKU ID {sku_id!r}.")
            return
        color_map = _group_color_map(sorted_groups)
        click.echo(f"SKU ID : {sku_id}")
        click.echo(f"Name   : {entry['name']}")
        click.echo(f"Groups :")
        if group_names:
            name_w = max(len(group_names.get(g, g)) for g in sorted_groups)
            for g in sorted_groups:
                color = color_map[g]
                click.echo(f"  {click.style(f'{group_names[g]:<{name_w}}', fg=color)}  {click.style(g, fg=color)}")
        else:
            for g in sorted_groups:
                click.echo(f"  {click.style(g, fg=color_map[g])}")
    else:
        query = sku_name.lower()
        matches = sorted(
            ((sid, e) for sid, e in by_id.items() if query in e["name"].lower()),
            key=lambda x: (x[1]["name"], x[0]),
        )
        if not matches:
            click.echo(f"No SKUs found matching name {sku_name!r}.")
            return

        # One row per (SKU, group) so name and slug each get their own column.
        # Primary sort: deprecated groups last; secondary: SKU name, then ID.
        rows = sorted(
            [
                (sid, entry["name"], g)
                for sid, entry in matches
                for g in entry["groups"]
                if not ignore_deprecated or "deprecat" not in g
            ],
            key=lambda r: (_group_sort_key(r[2]), r[1], r[0]),
        )
        if not rows:
            click.echo(f"No SKUs found matching name {sku_name!r}.")
            return
        color_map = _group_color_map({slug for _, _, slug in rows})
        id_w = max(len(r[0]) for r in rows)
        sku_name_w = max(len(r[1]) for r in rows)

        if group_names:
            gname_w = max(len(group_names.get(slug, slug)) for _, _, slug in rows)
            click.echo(f"{'SKU ID':<{id_w}}  {'SKU NAME':<{sku_name_w}}  {'GROUP NAME':<{gname_w}}  GROUP SLUG")
            click.echo("-" * (id_w + sku_name_w + gname_w + 30))
            for sku_id_val, sku_name_val, slug in rows:
                color = color_map[slug]
                gname = group_names.get(slug, slug)
                click.echo(
                    f"{sku_id_val:<{id_w}}  {sku_name_val:<{sku_name_w}}"
                    f"  {click.style(f'{gname:<{gname_w}}', fg=color)}"
                    f"  {click.style(slug, fg=color)}"
                )
        else:
            click.echo(f"{'SKU ID':<{id_w}}  {'SKU NAME':<{sku_name_w}}  GROUP SLUG")
            click.echo("-" * (id_w + sku_name_w + 30))
            for sku_id_val, sku_name_val, slug in rows:
                color = color_map[slug]
                click.echo(f"{sku_id_val:<{id_w}}  {sku_name_val:<{sku_name_w}}  {click.style(slug, fg=color)}")


@main.command(name="diff-group-list")
def diff_group_list() -> None:
    """Compare cached SKU groups against the current live list.

    Reports which groups have been added or removed since the cache was built.
    Requires an existing local cache — run 'build-cache' first if you have none.
    """
    index = cache.load_cache()
    if index is None:
        raise click.ClickException(
            "No local cache found. Run 'build-cache' first."
        )
    if "group_names" not in index:
        raise click.ClickException(
            "Cache is missing group names. Run 'build-cache --force' to rebuild."
        )

    cached_groups: dict[str, str] = index["group_names"]
    built_at = index.get("built_at", "unknown")
    click.echo(f"Cache built: {built_at}")

    session = scraper._make_session()
    try:
        live_groups = scraper.fetch_sku_groups(session)
    except requests.RequestException as exc:
        raise click.ClickException(f"Failed to fetch SKU group index: {exc}") from exc

    cached_slugs = set(cached_groups.keys())
    live_slugs = set(live_groups.keys())

    new_slugs = sorted(live_slugs - cached_slugs)
    removed_slugs = sorted(cached_slugs - live_slugs)

    if not new_slugs and not removed_slugs:
        click.echo("No changes detected.")
        return

    if new_slugs:
        click.echo(click.style(f"\nNew groups ({len(new_slugs)}):", fg="green"))
        name_w = max(len(live_groups[s]["name"]) for s in new_slugs)
        for slug in new_slugs:
            name = live_groups[slug]["name"]
            click.echo(f"  {click.style('+', fg='green')} {name:<{name_w}}  {slug}")

    if removed_slugs:
        click.echo(click.style(f"\nRemoved groups ({len(removed_slugs)}):", fg="red"))
        name_w = max(len(cached_groups[s]) for s in removed_slugs)
        for slug in removed_slugs:
            name = cached_groups[slug]
            click.echo(f"  {click.style('-', fg='red')} {name:<{name_w}}  {slug}")


_COMPLETION_CLASSES = {"bash": BashComplete, "zsh": ZshComplete}


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh"], case_sensitive=False))
def completion(shell: str) -> None:
    """Print the shell completion script for SHELL (bash or zsh).

    To enable completions, add one of the following to your shell startup file:

    \b
    # ~/.bashrc
    eval "$(sku-scraper completion bash)"

    \b
    # ~/.zshrc
    eval "$(sku-scraper completion zsh)"

    Or save to a file and source it from there:

    \b
    sku-scraper completion bash > ~/.bash_completions/sku-scraper.bash
    source ~/.bash_completions/sku-scraper.bash
    """
    complete_cls = _COMPLETION_CLASSES[shell.lower()]
    complete = complete_cls(main, {}, "sku-scraper", "_SKU_SCRAPER_COMPLETE")
    click.echo(complete.source(), nl=False)
