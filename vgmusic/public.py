# coding: utf8
"""Python API for vgmusic.com."""

import collections
import concurrent.futures as cfutures
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
            Defaults to 'index.json'.
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
        index_path: Union[pathlib.Path, str] = "index.json",
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

        _log.debug("[cache] loading existing index")

        try:
            with open(index_path) as f:
                self.data = json.load(f)
            _log.debug("[cache] loaded existing index")

        except FileNotFoundError:
            _log.info("[cache] index does not exist, creating")
            self.data = {}
            new_file = True

        except json.JSONDecodeError as e:
            _log.warning("[cache] failed to read existing index: %s", e)
            self.data = {}
            new_file = True

        else:
            new_file = False

        self._path = pathlib.Path(index_path)

        # build the index
        for section in self.soup.find_all("p", class_="menu"):
            section_name = section.find_previous_sibling(
                "p", class_="menularge"
            ).get_text(strip=True)

            for system in section.find_all("a", href=True):

                # don't overwrite any existing data
                if system.text not in self.data:
                    _log.debug("[cache] adding system %s", system.text)

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

        if check_timestamp and (self._path is not None) and not new_file:
            last_modified = datetime.fromtimestamp(
                self._path.stat().st_mtime, timezone.utc
            )
            now = datetime.now(timezone.utc)

            if last_modified.day == now.day:
                _log.debug(
                    "[cache] skipping caching, last cached today at %s", now.isoformat()
                )
                self._cached = set(self.data)

        if force_cache is not None:
            _log.info("forcing preemptive caching for system(s) %s", force_cache)
            for system in force_cache:
                self.__getitem__(system)

    def _cache(self, system: str) -> None:

        if system in self._cached:
            return

        system_info = self.data[system]

        # Caches the system requested, ignoring if it already has been cached.
        response = self.session.get(system_info["url"], stream=True)

        if response.headers["ETag"] != system_info.get("_etag"):

            # no etag (not cached yet) or there is a new index so update
            _log.debug("caching %s", system)

            try:
                songtable = utils.SongTable(response)
            except ParseError:
                self.data[system]["titles"] = {}  # a system with no songs, ignore
            else:
                self.data[system].update(songtable.parse())

            self._cached.add(system)

        else:
            _log.debug("system %s is cached already and up to date", system)

    def __getitem__(self, system):
        # To avoid downloading every page for each system,
        # this downloads the page lazily to save bandwidth.
        self._cache(system)

        return super().__getitem__(system)

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        self.close()

    @property
    def all_songs(self):
        """All songs in the index."""
        return self.search(lambda *args: True)

    def as_json(self, *args, **kwargs) -> str:
        return json.dumps(self.data, *args, **kwargs)

    def close(self) -> None:
        if self._path is not None:
            with self._path.open("w") as f:
                json.dump(self.data, f, indent=4)

        self.session.close()

    def _download_song(self, url: str, path: pathlib.Path) -> bytes:
        with self.session.get(url, stream=True) as response:
            _log.info("[download] saving %s to %s", url, path)
            with path.open("wb") as f:
                # 1Kb chunks
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)

    def download_songs(
        self, songs: List[dict], path: Optional[pathlib.Path] = None
    ) -> None:
        """Download songs to disk.

        Args:
            songs: The songs to download.
                The output of .search() and .search_by_regex() is suitable for this.
            path: Where to download the songs to.
                Defaults to "." (curdir).
        """

        if path is None:
            path = pathlib.Path()

        songs_to_download = []

        for song in songs:
            song_path = path / f"{utils.sanitize_filename(song['song_title'])}.mid"
            if song_path.is_file():
                _log.warning("[download] song at %s already exists", song_path)
            else:
                songs_to_download.append((song["song_url"], song_path))

        with cfutures.ThreadPoolExecutor() as pool:

            futures = [
                pool.submit(self._download_song, url, path)
                for url, path in songs_to_download
            ]

            for future in cfutures.as_completed(futures):
                _ = future.result()

    def force_cache_all(self) -> None:
        """Cache songs for all systems.
        If you use this, it is recommended to pass the index_path argument to __init__
        so the whole index does not need to be regenerated again.
        """
        with cfutures.ThreadPoolExecutor() as pool:
            futures = [pool.submit(self._cache, system) for system in self.data]
            for future in cfutures.as_completed(futures):
                _ = future.result()

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
        _log.debug("searched by regex: %s, %s", regexes, song_info_key)

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
