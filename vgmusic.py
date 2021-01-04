# coding: utf8
"""Python API for vgmusic.com."""

import collections
import json
import urllib.parse
from typing import List, Optional

import bs4
import requests

__version__ = "0.1.0a0"

VGMUSIC_URL = "https://vgmusic.com"
BS4_PARSER = "html5lib"
# parse the 'last updated' info at the end of each page
TIMESTAMP_FORMAT = "%B %d, %Y at %I:%M %p"


def _clean_header(name):
    return name.lower().replace(" ", "_")


# NOTE: 'system' refers to the game system (NES, SNES, etc.)
# 'section' refers to the company that made the system (Atari, etc.)
class VGMusic(collections.UserDict):
    """VGMusic API.

    Args:
        force_cache: A list of systems to pre-cache (normally loaded lazily).
            Defaults to None.

    Attributes:
        session (requests.Session): The session used to retrieve the listings.
        soup (bs4.BeautifulSoup): The main index page.
        data (dict): A map of system names to their info.
    """

    def __init__(self, force_cache: Optional[List[str]] = None):
        self.session = requests.Session()
        # retrieve the index
        self.soup = self._get_soup(VGMUSIC_URL)
        # the first menu element is info, etc.
        self.soup.find("p", class_="menu").decompose()

        # build the index
        self.data = {}
        for section in self.soup.find_all("p", class_="menu"):
            section_name = section.find_previous_sibling(
                "p", class_="menularge"
            ).text.strip()

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
        return bs4.BeautifulSoup(self.session.get(*args, **kwargs).text, BS4_PARSER)

    def __getitem__(self, system):
        # cache it lazily
        if not self.data[system]["titles"]:

            system_url = self.data[system]["url"]
            system_page = self._get_soup(system_url)
            table = system_page.tbody

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
                    title = row.td.a.text
                    continue

                if not row.get_text(strip=True):
                    # a blank row?
                    continue

                song_info = {}

                for header_name, tag in zip(header_names, row.find_all("td")):

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
                        header_value = tag.text.strip()

                    elif header_name == "file_size":
                        header_value = int(tag.text.split()[0])

                    else:
                        header_value = tag.text.strip()

                    song_info[header_name] = header_value

                del song_info["comments"]
                self.data[system]["titles"][title].append(song_info)

        return super().__getitem__(system)


if __name__ == "__main__":
    mus = VGMusic(force_cache=["Sony PlayStation 4"])
    with open("out.json", mode="w") as f:
        json.dump(mus.data, f, indent=4)
