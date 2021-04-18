# coding: utf8

import collections
import collections.abc as c_abc
import concurrent.futures as c_futures
import hashlib
import logging
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urljoin

import bs4
import requests

__version__ = "1.0.0"

_log = logging.getLogger("vgmusic")

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


def _escape_filename(name):
    # space is the only whitespace allowed in filenames
    return "".join(c for c in name if c.isalnum() or c == " ")


def _md5_from_url(url):
    return RE_INFO_URL.findall(url)[0]


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

    def cache(self) -> dict:
        """Serialise all fields in this song to a dictionary representation."""
        return self.__dict__

    def download(
        self, session: Optional[requests.Session] = None, verify: bool = False
    ) -> bytes:
        """Download this song's midi file.

        Args:
            session: The session to use to download.
                If not specified, requests.get will be used instead.
            verify: Whether or not to check if the size and md5 checksum matches the midi file.
                If not specified, defaults to False.

        Returns:
            The bytes of the midi file.

        Raises:
            ValueError, if verify=True and the check failed.
        """

        _log.info("downloading %s", self.url)

        if session is None:
            resp = requests.get(self.url)
        else:
            resp = session.get(self.url)

        data = resp.content

        if verify:
            size = len(data)
            md5 = hashlib.md5(data).hexdigest()

            if not ((size == self.size) and (md5 == self.md5)):
                raise ValueError(
                    f"check failed (expected checksum {self.md5}, {self.size} bytes, "
                    "got checksum {md5}, {size} bytes)"
                )

        return data


class System(c_abc.Mapping):
    """A collection of songs associated with game titles in a (video game) system.

    Args:
        url: The absolute url to the system page.
        session: The session used to download the page.
            If not specified, defaults to None (a new session is created).
        cache: The previously serialised dict from .cache().
            If not specified, defaults to None.

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
            _log.info("ok (total %s games, %s songs)", len(self), self.total_songs())

    def cache(self) -> dict:
        """Serialise all songs to a dictionary format that can be saved on disk and subsequently loaded.

        Returns:
            The serialised songs.
        """

        cache: Dict[str, Any] = {"url": self.url, "version": self.version, "games": {}}

        for game, songs in self.games.items():
            serialised = [song.cache() for song in songs]
            cache["games"][game] = serialised

        return cache

    def total_songs(self) -> int:
        """Return the total number of songs."""

        return sum(len(game) for game in self)

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
        md5 = _md5_from_url(_info.a["href"])

        return Song(url, title, size, author, md5)


class API(c_abc.Mapping):
    """
    Public api to VGMusic.

    Args:
        cache: The previously serialised dict from .cache().
            If not specified, defaults to None.

    Attributes:
        session: The requests session used to download pages/songs.
        systems: A map of system names to System objects.
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

    def search(self, criteria: Callable[[str, str, Song], bool]) -> List[Song]:
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

            fields = song.cache()

            field_matches = [
                re.search(regex, str(fields[field])) for field, regex in regexes.items()
            ]

            return all([re_system.search(system), re_game.search(game), *field_matches])

        return self.search(criteria)

    def download(
        self, songs: List[Song], to: Union[str, pathlib.Path], max_requests: int = 5
    ):
        """Download songs to path.
        Any illegal characters in the song's title are escaped/converted before being used as the filename.

        To download individual songs, use 'Song.download()' instead.

        Args:
            songs: The list of Song objects to download.
            to: The directory to download to.
            max_requests: How many concurrent downloads can happen at the same time.
                To avoid pinging VGMusic servers too much, it is recommended to set this at 10 or below.
                If not specified, defaults to 5.
        """

        to = pathlib.Path(to)

        with c_futures.ThreadPoolExecutor(max_workers=max_requests) as pool:

            futures = {}

            for song in songs:

                future = pool.submit(song.download, session=self.session)
                filename = f"{_escape_filename(song.title)}.mid"

                futures[future] = filename

            for future in c_futures.as_completed(futures):

                filename = futures[future]

                with (to / filename).open("wb") as f:
                    f.write(future.result())

    def cache(self) -> dict:
        """Serialise all systems to a dictionary format that can be saved on disk and subsequently loaded.

        Returns:
            The serialised systems.
        """
        return {
            "urls": self._urls,
            "systems": {name: system.cache() for name, system in self.systems.items()},
        }

    def force_cache(self):
        """Pre-emptively cache all system pages (no further lazy caching is done)."""
        for system in self._urls:
            self[system]

    def close(self):
        self.session.close()

    def __getitem__(self, system):
        if system not in self.systems:
            _log.info("downloading page for %s", system)
            self._force_cache(system)

        return self.systems[system]

    def __len__(self):
        return len(self.systems)

    def __iter__(self):
        return iter(self.systems)

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        self.close()

    def _force_cache(self, system):
        self.systems[system] = System(self._urls[system], session=self.session)
