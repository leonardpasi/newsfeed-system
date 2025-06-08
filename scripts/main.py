from pathlib import Path

import click
import yaml

from src.aggregator.sources.rss_source import RSSSource


@click.command(context_settings={"show_default": True})
@click.option("--src", "source_name", type=str, required=True)
def main(source_name: str):
    configs_dir = Path(__file__).parents[1] / "configs/"

    with open(configs_dir / "sources_urls.yaml") as sources_urls:
        sources_urls_dict = yaml.safe_load(sources_urls)

    if source_name not in sources_urls_dict:
        raise ValueError(
            "Source name is invalid. See /configs/sources_urls.yaml for valid source names"
        )

    url = sources_urls_dict[source_name]

    source = RSSSource(url, source_name)
    _ = source.fetch_articles()
    pass


if __name__ == "__main__":
    main()
