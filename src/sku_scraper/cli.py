from pathlib import Path

import click
import requests

from sku_scraper import scraper, writer


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
        all_groups = None
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
