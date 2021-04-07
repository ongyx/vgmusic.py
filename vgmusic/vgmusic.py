# coding: utf8
"""Unofficial Python API for vgmusic.com."""

import collections
import collections.abc as c_abc
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import bs4
import requests

__version__ = "1.0.0"

_log = logging.getLogger("vgmusic")
logging.basicConfig(level=logging.DEBUG)

# html.parser has problems with vgmusic's table cells.
BS4_PARSER = "html5lib"
VGMUSIC_URL = "https://vgmusic.com"

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
        cache: The previously parsed system page.
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
        cache: Optional[dict] = None,
    ):

        self.url = url

        if session is None:
            session = requests.Session()

        self.session = session

        self.games: Dict[str, List[Song]] = collections.defaultdict(list)

        if cache:

            self.url = cache["url"]
            self.version = cache["version"]
            for game, songs in cache["games"].items():
                self.games[game] = [Song(**song) for song in songs]

        else:
            _log.info("parsing %s", self.url)

            resp = self.session.get(self.url)
            soup = _resp2soup(resp)

            self.version = soup.address.text.strip().split()[-1].rstrip(".")

            self._parse(soup.table)
            _log.info("ok (total %s games, %s songs)", *self.total())

    def cache(self) -> dict:
        """Serialise all songs to a dictionary format that can be saved on disk and subsequently loaded.

        Returns:
            The serialised songs.
        """

        cache: Dict[str, Any] = {"url": self.url, "version": self.version, "games": {}}

        for game, songs in self.games.items():
            serialised = [song.__dict__.copy() for song in songs]
            cache["games"][game] = serialised

        return cache

    def total(self) -> Tuple[int, int]:
        """Return the total number of games/songs as a two-tuple (games, songs)."""
        n_games = 0
        n_songs = 0

        for _, songs in self.games.items():
            n_games += 1
            n_songs += len(songs)

        return n_games, n_songs

    def __getitem__(self, game):
        return self.games[game]

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

        url = urljoin(self.url, _title.a["href"])
        title = _title.text.strip()
        size = int(_size.text.split()[0])
        author = _author.text.strip()
        md5 = RE_INFO_URL.findall(_info.a["href"])[0]

        return Song(url, title, size, author, md5)


class API(c_abc.Mapping):
    """
    Public api to VGMusic.

    Args:
        cache: The previously parsed index page.
            If not specified, the index page will be downloaded and parsed.
    """

    def __init__(self, cache: Optional[dict] = None):
        self.session = requests.Session()
        self.systems: Dict[str, System] = {}

        self._urls = {}

        if cache:
            self._urls = cache["urls"]
            for name, system_info in cache["systems"].items():
                self.systems[name] = System("", cache=system_info, session=self.session)

        else:
            soup = _resp2soup(self.session.get(VGMUSIC_URL))
            sections = soup.find_all("p", class_="menu")[1:]

            for section in sections:
                for system in section.find_all("a"):

                    url = urljoin(VGMUSIC_URL, system["href"])
                    name = system.text

                    _log.info("adding %s (%s)", name, url)
                    self._urls[name] = url

    def search(self, criteria: c_abc.Callable[[str, str, Song], bool]) -> List[Song]:
        """Search for songs using criteria.

        Args:
            criteria: A function that accepts three arguments (system_name, game_name, song) and returns True or False.

        Returns:
            Songs that match the criteria.
        """

        songs = []

        for system_name, system in self.systems.items():
            for game_name, game in system.games.items():
                for song in game:
                    if criteria(system_name, game_name, song):
                        songs.append(song)

        return songs

    def search_by_regex(self, **regexes) -> List[Song]:
        """Search for songs using regex as criteria.

        NOTE: re.search is used, not re.match.
        To anchor regexes, use '^' and '$'.

        Args:
            regexes: The regexes to use as criteria.
            'system' and 'game' match the system name and game name; anything else matches to fields in the song.

        Returns:
            Songs matching the regexes.
        """

        re_system = re.compile(regexes.pop("system", None) or "")
        re_game = re.compile(regexes.pop("game", None) or "")

        def criteria(system, game, song):
            nonlocal re_system
            nonlocal re_game

            field_matches = [
                re.search(regex, str(song.__dict__[field]))
                for field, regex in regexes.items()
            ]

            return all([re_system.search(system), re_game.search(game), *field_matches])

        return self.search(criteria)

    def cache(self) -> dict:
        """Serialise all systems to a dictionary format that can be saved on disk and subsequently loaded.

        Returns:
            The serialised systems.
        """
        return {
            "urls": self._urls,
            "systems": {name: system.cache() for name, system in self.systems.items()},
        }

    def __getitem__(self, system):
        if system not in self.systems:
            _log.info("downloading page for %s", system)
            self._download(system)

        return self.systems[system]

    def __len__(self):
        return len(self.systems)

    def __iter__(self):
        return iter(self.systems)

    def _download(self, system):
        self.systems[system] = System(self._urls[system], session=self.session)
