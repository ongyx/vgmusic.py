# coding: utf8

import functools
import json
import logging
import pathlib

import click

from .vgmusic import API

_log = logging.getLogger("vgmusic")

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.DEBUG)

click.option = functools.partial(click.option, show_default=True)  # type:ignore


@click.command()
@click.argument("search_query", nargs=-1)
@click.option(
    "-c",
    "--cache-file",
    help="cache file to use",
    default="cache.json",
    type=pathlib.Path,
)
@click.option(
    "-d",
    "--download-to",
    help="where to download midi files to",
    default=".",
    type=pathlib.Path,
)
@click.option(
    "-n",
    "--no_download",
    help="only parse VGMusic's webpages and save to cache file (ignores search_query and download-to)",
    is_flag=True,
)
def cli(search_query, cache_file, download_to, no_download):
    """Download MIDI files from VGMusic by a search query.

    The search query is multiple queries of the form '<field>=<regex>'.
    'regex' is used to match the 'field' of the song.
    i.e 'title=[Bb]attle' matches songs with either 'Battle' or 'battle' in their name.

    'regex' _must_ be anchored (using ^ and $) if an exact match is needed. Otherwise, 'regex' may match a substring.

    Field can be any of the following:

    \b
    url: The direct url to the song download.
    title: The song name.
    size: The size of the song (in number of bytes).
    author: The name of the author.
    md5: The md5 hash of the song download.
    system: The system name (i.e NES, SNES, etc.)
    game: The game name.

    Example:

    \b
    # download any songs whose name starts with 'Magus' or 'magus',
    # under the game 'Chrono Trigger' and system 'SNES'.
    vgmusic "system=^SNES$" "game=^Chrono Trigger$" "title=^[Mm]agus"
    """

    try:
        with cache_file.open() as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = None

    api = API(cache=cache)
    api.force_cache()

    if not no_download:

        if search_query:
            regexes = {}

            for query in search_query:
                field, _, regex = query.partition("=")
                regexes[field] = regex

            songs = api.search_by_regex(**regexes)

        else:
            if click.confirm(
                "WARNING: You are about to download ALL of VGMusic's MIDI files. Are you sure?",
                abort=True,
            ):
                songs = api.search(lambda s, g, sg: True)

        _log.info("downloading %s songs", len(songs))

        api.download(songs, download_to)

    with cache_file.open("w") as f:
        json.dump(api.cache(), f, indent=2)

    api.close()
