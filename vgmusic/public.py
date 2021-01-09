# coding: utf8
"""Python API for vgmusic.com."""

import collections
import json
import logging
import pathlib
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Callable, List, Optional, Pattern, Union

import requests
from vgmusic import utils
from vgmusic.exceptions import ParseError

__version__ = "0.1.1a2"
_log = logging.getLogger("vgmusic.py")

VGMUSIC_URL = "https://vgmusic.com"


# NOTE: 'system' refers to the game system (NES, SNES, etc.)
# 'section' refers to the company that made the system (Atari, etc.)
class API(collections.UserDict):
    """VGMusic API.

    Args:
        index_path: A file path to read the index from
            (and to write back changes).
            Defaults to None.
        force_cache: A list of systems to pre-cache (normally loaded lazily).
            Defaults to None.
        check_timestamp: Whether or not to skip re-caching if the index was updated
            in the same day and accessed again.
            Does not apply if no index_path is passed.
            Defaults to True.

    Attributes:
        session (requests.Session): The session used to retrieve the listings.
        soup (bs4.BeautifulSoup): The main index page.
        data (dict): A map of system names to their info.
    """

    def __init__(
        self,
        index_path: Optional[Union[pathlib.Path, str]] = None,
        force_cache: Optional[List[str]] = None,
        check_timestamp: bool = True,
    ):
        super().__init__()

        _log.debug("initalising api")

        self.session = requests.Session()

        # This is used to keep track of which system index needs to be updated.
        # On the first __getitem__ call for a system, we get the response headers of the
        # system's index. If the Etag does not match, we update the index.
        # This is to avoid repeatedly pinging VGMusic every time __getitem__ is used.
        self._cached = set()

        # retrieve the index
        self.soup = utils.soup_from_response(self.session.get(VGMUSIC_URL))

        # the first menu element is infomation about VGMusic itself.
        # We don't need it (for now).
        self.soup.find("p", class_="menu").decompose()

        if index_path is not None:
            _log.debug("loading existing index")

            with open(index_path) as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError as e:
                    if f.read(1) != "":  # blank file
                        _log.warning("failed to read existing index: %s", e)
                    self.data = {}

            self._path = pathlib.Path(index_path)
        else:
            self._path = None

        # build the index
        for section in self.soup.find_all("p", class_="menu"):
            section_name = section.find_previous_sibling(
                "p", class_="menularge"
            ).get_text(strip=True)

            for system in section.find_all("a", href=True):

                # don't overwrite any existing data
                if system.text not in self.data:
                    _log.debug("adding system %s", system.text)

                    self.data[system.text] = {
                        # url is relative to root
                        "url": urllib.parse.urljoin(VGMUSIC_URL, system["href"]),
                        # The company which made the system/general catagory.
                        "section": section_name,
                        # a map of game titles to their songs
                        # we use None as a sentinel to avoid re-caching systems with no
                        # songs yet.
                        "titles": None,
                    }

        if check_timestamp:
            last_modified = datetime.fromtimestamp(
                self._path.stat().st_mtime, timezone.utc
            )
            now = datetime.now(timezone.utc)

            if last_modified.day == now.day:
                _log.debug("skipping caching, already recently cached")
                self._cached = set(self.data)

        if force_cache is not None:
            _log.info("forcing preemptive caching for system(s) %s", force_cache)
            for system in force_cache:
                self.__getitem__(system)

    def _is_outdated(self, system: str, response: str) -> bool:
        return self.data[system].get("_etag") != response.headers["ETag"]

    def _is_cached(self, system: str) -> bool:
        return system in self._cached and self.data[system]["titles"] is not None

    def _cache(self, system: str) -> None:
        # Caches the system requested, ignoring if it already has been cached.
        response = self.session.get(self.data[system]["url"], stream=True)

        if self._is_outdated(system, response):

            # no etag (not cached yet) or there is a new index so update
            _log.debug("caching %s", system)

            try:
                songtable = utils.SongTable(response)
            except ParseError:
                pass  # a system with no songs, ignore
            else:
                self.data[system].update(songtable.parse())

            self._cached.add(system)

        else:
            _log.debug("system %s is cached already and up to date", system)

    def __getitem__(self, system):
        # To avoid downloading every page for each system,
        # this downloads the page lazily to save bandwidth.
        if not self._is_cached(system):
            self._cache(system)

        return super().__getitem__(system)

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        self.close()

    def as_json(self, *args, **kwargs) -> str:
        return json.dumps(self.data, *args, **kwargs)

    def close(self) -> None:
        if self._path is not None:
            with self._path.open("w") as f:
                json.dump(self.data, f, indent=4)

        self.session.close()

    def force_cache_all(self) -> None:
        """Cache songs for all systems.
        If you use this, it is recommended to pass the index_path argument to __init__
        so the whole index does not need to be regenerated again.
        """
        for system in self.data:
            _ = self.__getitem__(system)

    def search(self, search_func: Callable[[str, str, dict], bool]) -> List[dict]:
        """Filter out songs using a function.

        Args:
            search_func: The function to search with.
                This function must accept three positional arguments
                (system: str, game: str, song_info: dict), and return True if
                the song passes the search, False otherwise.

                Example:

                def a_search(system, game, song):
                    return game == "Persona 5" and song["sequenced_by"] == "fakt13"

        Returns:
            A list of songs that passed the search.
        """

        searched = []

        for system, titles in self.data.items():
            if titles["titles"] is not None:
                for title, songs in titles["titles"].items():
                    for song in songs:
                        if search_func(system, title, song):
                            searched.append(song)

        return searched

    def search_by_regex(
        self,
        *regexes: Union[str, Pattern],
        song_info_key: str = "song_title",
    ) -> List[dict]:
        """Search songs from the index by regex.

        Args:
            regexes: The regex patterns to use (up to three).
                If less than three patterns are passed, the rest are filled with "".
                (matches any)
                May be compiled or un-compiled (as raw strings).
                The patterns are matched to (system, game, song_info).
            song_info_key: The key to use to match for song_info.
                Defaults to 'song_title'.

        Returns:
            The songs that match the regex(es).

        Raises:
            ValueError, if there are too many regexes.
        """
        regexes = list(regexes)

        if len(regexes) > 3:
            raise ValueError("too many regexes passed (max: 3)")

        while len(regexes) < 3:
            regexes.append("")

        def _search_by_regex(*args):
            nonlocal regexes

            # use the key's value instead
            args = list(args)
            args[2] = args[2][song_info_key]
            return all(
                bool(re.search(regex, value)) for regex, value in zip(regexes, args)
            )

        return self.search(_search_by_regex)
