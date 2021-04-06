# coding: utf8
"""Unofficial Python API for vgmusic.com."""

import collections
import collections.abc as c_abc
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin

import bs4
import requests

__version__ = "1.0.0"

# html.parser has problems with vgmusic's table cells.
BS4_PARSER = "html5lib"

RE_INFO_URL = re.compile(r"/file/(.*)\.html")


def _is_empty(tag):
    return (not tag.text) or tag.text.isspace()


def _is_header(tag):
    try:
        class_name = tag["class"][0]
    except (KeyError, IndexError):
        class_name = ""

    return class_name == "header"


def _resp2soup(resp):
    return bs4.BeautifulSoup(resp.text, BS4_PARSER)


@dataclass
class Song:
    """A song in a game's soundtrack as midi.

    Args:
        url: The absolute direct url to the midi file.
        title: The name of the song.
        size: The size of the song (number of bytes).
        author: The name of the person who sequenced the song to midi.
        md5: The MD5sum of the midi file.

    Attributes:
        See args.
    """

    url: str
    title: str
    size: int
    author: str
    md5: str


class System(c_abc.Mapping):
    """A collection of songs associated with game titles in a (video game) system.

    Args:
        url: The absolute url to the system page.
        session: The session used to download the page.
            If not specified, a new session is created.
        cached: The previously parsed system page.
            If not specified, the system page will be downloaded and parsed.

    Attributes:
        url (str): See args.
        session (requests.Session): See args.
        games (Dict[str, List[Songs]]): A map of video game titles to a list of songs.
        version (str): The version of the VGMusic indexer used to create the system page.
    """

    def __init__(
        self,
        url: str,
        session: Optional[requests.Session] = None,
        cached: Optional[dict] = None,
    ):

        if session is None:
            session = requests.Session()

        self.session = session
        self.url = url
        self.games: Dict[str, List[Song]] = collections.defaultdict(list)

        if cached is not None:

            self.version = cached["version"]
            for game, songs in cached["games"].items():
                self.games[game] = [Song(**song) for song in songs]

        else:

            resp = self.session.get(self.url)
            soup = _resp2soup(resp)

            self.version = soup.address.text.strip().split()[-1].rstrip(".")

            self._parse(soup.table)

    def cache(self) -> dict:
        """Serialise all songs to a dictionary format that can be saved on disk and subsequently loaded.

        Returns:
            The serialised songs.
        """

        cache = {"version": self.version, "games": {}}

        for game, songs in self.games.items():
            serialised = [song.__dict__.copy() for song in songs]
            cache["games"][game] = serialised

        return cache

    def __getitem__(self, key):
        return self.games[key]

    def __len__(self):
        return len(self.games)

    def __iter__(self):
        return iter(self.games)

    def _parse(self, table):

        rows = table.find_all("tr")

        # first two rows are header info, ignore
        rows = rows[2:]

        game_title = None

        for row in rows:

            if _is_header(row):
                # new title
                game_title = row.text.strip()
                continue

            elif _is_empty(row):
                # visual padding, ignore
                continue

            song = self._parse_row(row)
            self.games[game_title].append(song)

    def _parse_row(self, row):

        _title, _size, _author, _info = row.find_all("td")
        print(_title, _author)

        url = urljoin(self.url, _title.a["href"])
        title = _title.text.strip()
        size = int(_size.text.split()[0])
        author = _author.text.strip()
        md5 = RE_INFO_URL.findall(_info.a["href"])[0]

        return Song(url, title, size, author, md5)
