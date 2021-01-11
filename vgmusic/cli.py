# coding: utf8

import functools
import logging
import pathlib

import click
from vgmusic.public import API
from vgmusic.utils import _setup_logging

click.option = functools.partial(click.option, show_default=True)
_log = logging.getLogger("vgmusic.py")

LEVELS = [
    logging.CRITICAL,
    logging.ERROR,
    logging.WARNING,
    logging.INFO,
    logging.DEBUG,
]

INDEX_FILENAME = "index.json"


@click.command()
@click.option("-v", "--verbose", count=True, default=4, help="set verbosity (0-4)")
@click.option(
    "-n", "--no-download", is_flag=True, help="pretend to download files (dry run)"
)
@click.option(
    "-s",
    "--search",
    default="",
    help=(
        "filter specific songs using regex in the format "
        "'system_regex[::game_regex[::song_info_regex]]' "
    ),
)
@click.option(
    "-k", "--key", default="song_title", help="key to use to filter for song_info_regex"
)
@click.option(
    "-d",
    "--directory",
    default=".",
    help="where to download the midi files and the index.json file (song info) to",
)
def cli(verbose, no_download, search, key, directory):
    _setup_logging(level=LEVELS[verbose])
    directory = pathlib.Path(directory)
    index = directory / INDEX_FILENAME

    _log.info("[download] starting")
    with API(index_path=index) as api:
        api.force_cache_all()

        if not no_download:
            api.download_songs(
                api.search_by_regex(*search.split("::"), song_info_key=key), directory
            )


if __name__ == "__main__":
    cli()
