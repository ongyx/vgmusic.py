# coding: utf8
"""Python API for vgmusic.com."""

import collections
import json
import logging
import re
import urllib.parse
from email.utils import parsedate_to_datetime
from typing import Callable, IO, List, Optional, Pattern, Union

import bs4
import requests

try:
    import flask
except ImportError:
    flask = None

__version__ = "0.1.1a2"

VGMUSIC_URL = "https://vgmusic.com"
BS4_PARSER = "html5lib"
# parse the indexer version.
RE_INDEX_VER = re.compile(r"([\d\.]{3,}[^\.])")

logging.basicConfig(level=logging.DEBUG, format=" %(levelname)-8s :: %(message)s")
_log = logging.getLogger(__name__)


def _clean_header(name: str) -> str:
    return name.lower().replace(" ", "_")


def _soup_from_response(response: requests.models.Response) -> bs4.BeautifulSoup:
    return bs4.BeautifulSoup(response.text, BS4_PARSER)


def _parse_song(system_url: str, headers: List[str], row: bs4.Tag) -> dict:
    song_info = {}
    for header_name, tag in zip(headers, row.find_all("td")):

        # Currently, the following headers are used on VGMusic.com.
        # song_title: Self-explainatory.
        # file_size: Size in bytes.
        # sequenced_by: Who created the midi.
        # comments: How many comments (does not work when getting HTML)

        # vgmusic.py adds these headers:
        # song_url: Direct URL to the midi file.
        # comments_url: Direct URL to the comments page.

        if header_name in ("song_title", "comments"):
            # so we won't end up with 'song_title_url'
            normalized = header_name.split("_")[0]

            song_info[f"{normalized}_url"] = urllib.parse.urljoin(
                system_url, tag.a["href"]
            )
            header_value = tag.get_text(strip=True)

        elif header_name == "file_size":
            header_value = int(tag.text.split()[0])

        else:
            header_value = tag.get_text(strip=True)

        song_info[header_name] = header_value

    del song_info["comments"]
    return song_info


def _parse_song_table(system_info: dict, response: requests.models.Response) -> dict:
    soup = _soup_from_response(response)
    table = soup.tbody

    system_info["last_updated"] = parsedate_to_datetime(
        response.headers["Last-Modified"]
    ).timestamp()

    # we use etag to check for changes (last updated is for client-side)
    system_info["_etag"] = response.headers["ETag"]

    # indexer version
    # idk who would actually need this, but still...
    system_info["indexer_version"] = RE_INDEX_VER.findall(
        soup.address.get_text(strip=True)
    )[0]

    # This header specifies the info on each song.
    # We just map it to the 'table row' tags below each title header onwards.
    header_names = [
        _clean_header(h.text) for h in table.tr.find_all("th", class_="header")
    ]

    # The first two table rows specify the header, we don't need them anymore.
    for _ in range(2):
        table.tr.decompose()

    title = None
    for row in table.find_all("tr"):

        if row.get("class", [""])[0] == "header":
            # there is no song info, skip
            title = row.td.a.text
            continue

        if not row.get_text(strip=True):
            # a blank row?
            continue

        system_info["titles"][title].append(
            _parse_song(response.url, header_names, row)
        )

    return system_info


# NOTE: 'system' refers to the game system (NES, SNES, etc.)
# 'section' refers to the company that made the system (Atari, etc.)
class API(collections.UserDict):
    """VGMusic API.

    Args:
        data_file: A file-like object to read the index from
            (and to write back changes).
            Must be opened in read-write mode ('rw').
            Defaults to None.
        force_cache: A list of systems to pre-cache (normally loaded lazily).
            Defaults to None.

    Attributes:
        session (requests.Session): The session used to retrieve the listings.
        soup (bs4.BeautifulSoup): The main index page.
        data (dict): A map of system names to their info.
    """

    def __init__(
        self,
        data_file: Optional[IO] = None,
        force_cache: Optional[List[str]] = None,
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
        self.soup = _soup_from_response(self.session.get(VGMUSIC_URL))

        # the first menu element is infomation about VGMusic itself.
        # We don't need it (for now).
        self.soup.find("p", class_="menu").decompose()

        if data_file is not None:
            _log.debug("loading existing index")
            try:
                self.data = json.load(data_file)
            except json.JSONDecodeError as e:
                if data_file.read(1) != "":  # blank file
                    _log.warning("failed to read existing index: %s", e)

            self._file = data_file
        else:
            self._file = None

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
                        "titles": collections.defaultdict(list),
                    }

        if force_cache is not None:
            _log.info("forcing preemptive caching for system(s) %s", force_cache)
            for system in force_cache:
                self.__getitem__(system)

    def filter(self, filter_func: Callable[[str, str, dict], bool]) -> List[dict]:
        """Filter out songs using a function.

        Args:
            filter_func: The function to filter with.
                This function must accept three positional arguments
                (system: str, game: str, song_info: dict), and return True if
                the song passes the filter, False otherwise.

                Example:

                def a_filter(system, game, song):
                    # shoutout :3
                    return game == "Persona 5" and song["sequenced_by"] == "fakt13"

        Returns:
            A list of songs that passed the filter.
        """

        filtered = []

        for system, titles in self.data.items():
            for title, songs in titles["titles"].items():
                for song in songs:
                    if filter_func(system, title, song):
                        filtered.append(song)

        return filtered

    def filter_by_regex(
        self,
        *regexes: Union[str, Pattern],
        song_info_key: str = "song_title",
    ) -> List[dict]:
        """Filter songs from the index by regex.

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

        def _filter_by_regex(*args):
            nonlocal regexes

            # use the key's value instead
            args = list(args)
            print(args)
            args[2] = args[2][song_info_key]
            print(args)
            return all(
                bool(re.search(regex, value)) for regex, value in zip(regexes, args)
            )

        return self.filter(_filter_by_regex)

    def as_json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)

    # Magic/helper methods
    def _is_outdated(self, system: str, etag: str) -> bool:
        return self.data[system].get("_etag") != etag

    def _is_cached(self, system: str) -> bool:
        return system in self._cached and bool(self.data[system]["titles"])

    def __getitem__(self, system):
        # cache it lazily
        system_info = self.data[system]

        if not self._is_cached(system):

            response = self.session.get(system_info["url"], stream=True)

            if self._is_outdated(system, response.headers["ETag"]):

                # no etag (not cached yet) or there is a new index so update
                _log.debug("caching %s", system)
                self.data[system] = _parse_song_table(system_info, response)
                self._cached.add(system)

            else:
                _log.debug("system %s is cached already and up to date", system)

        return super().__getitem__(system)

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        if self._file is not None:
            self._file.seek(0)
            json.dump(self.data, self._file, indent=4)

        self.session.close()


if __name__ == "__main__":
    # import argparse

    outfile = "index.json"
    # create file if it does not exist
    with open(outfile, "a"):
        pass

    with open(outfile, "r+") as f:
        with API(data_file=f, force_cache=["Sony PlayStation 4"]) as api:
            pass
