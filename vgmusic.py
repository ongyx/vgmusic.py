# coding: utf8
"""Python API for vgmusic.com."""

import collections
import json
import locale
import re
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional

import bs4
import requests

try:
    import flask
except ImportError:
    flask = None

__version__ = "0.1.1a0"

VGMUSIC_URL = "https://vgmusic.com"
BS4_PARSER = "html5lib"
# parse the 'last updated' info at the end of each page
TIMESTAMP_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"
# parse the indexer version.
RE_INDEX_VER = re.compile(r"([\d\.]{3,}[^\.])")

# in case you are not in the US or using an English locale.
locale.setlocale(locale.LC_TIME, "en_US.utf8")


def _clean_header(name: str) -> str:
    return name.lower().replace(" ", "_")


def _parse_song_info(system_url: str, headers: List[str], row: bs4.element.Tag) -> dict:
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


# NOTE: 'system' refers to the game system (NES, SNES, etc.)
# 'section' refers to the company that made the system (Atari, etc.)
class API(collections.UserDict):
    """VGMusic API.

    Args:
        force_cache: A list of systems to pre-cache (normally loaded lazily).
            Defaults to None.

    Attributes:
        session (requests.Session): The session used to retrieve the listings.
        soup (bs4.BeautifulSoup): The main index page.
        data (dict): A map of system names to their info.
    """

    def __init__(
        self,
        force_cache: Optional[List[str]] = None,
    ):
        self.session = requests.Session()
        # retrieve the index
        self.soup, _ = self._get_soup(VGMUSIC_URL)
        # the first menu element is info, etc.
        self.soup.find("p", class_="menu").decompose()

        # build the index
        self.data = {}
        for section in self.soup.find_all("p", class_="menu"):
            section_name = section.find_previous_sibling(
                "p", class_="menularge"
            ).get_text(strip=True)

            # avoid namespace clash with 'system' module
            for system in section.find_all("a", href=True):
                self.data[system.text] = {
                    # url is relative to root
                    "url": urllib.parse.urljoin(VGMUSIC_URL, system["href"]),
                    "section": section_name,
                    # a map of game titles to their songs
                    "titles": collections.defaultdict(list),
                }

        if force_cache is not None:
            for system in force_cache:
                self.__getitem__(system)

    def _get_soup(self, *args, **kwargs) -> bs4.BeautifulSoup:
        response = self.session.get(*args, **kwargs)
        return bs4.BeautifulSoup(response.text, BS4_PARSER), response

    def __getitem__(self, system):
        # cache it lazily
        if not self.data[system]["titles"]:

            system_url = self.data[system]["url"]
            system_page, response = self._get_soup(system_url)
            table = system_page.tbody

            # get last updated
            self.data[system]["last_updated"] = (
                datetime.strptime(response.headers["Last-Modified"], TIMESTAMP_FORMAT)
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )

            # we use etag (last updated is for client-side)
            self.data[system]["_etag"] = response.headers["ETag"]

            # indexer version
            # idk who would actually need this, but still...
            self.data[system]["indexer_version"] = RE_INDEX_VER.findall(
                system_page.address.get_text(strip=True)
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

                self.data[system]["titles"][title].append(
                    _parse_song_info(system_url, header_names, row)
                )

        return super().__getitem__(system)

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        self.session.close()

    def as_json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)


if __name__ == "__main__":
    # import argpare
    with API(force_cache=["Sony PlayStation 4"]) as api:
        with open("out.json", "w") as f:
            f.write(api.as_json(indent=4))
