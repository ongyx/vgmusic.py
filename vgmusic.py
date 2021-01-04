# coding: utf8
"""Python API for vgmusic.com."""

import collections
import json
import urllib.parse

import bs4
import requests

__version__ = "0.1.0a"

VGMUSIC_URL = "https://vgmusic.com"
BS4_PARSER = "html5lib"


def _clean_header(name):
    return name.lower().replace(" ", "_")


class VGMusic(collections.abc.MutableMapping):
    def __init__(self):
        self.session = requests.Session()
        # retrieve the index
        self.soup = self._get_soup(VGMUSIC_URL)
        # the first menu element is info, etc.
        self.soup.find("p", class_="menu").decompose()

        # build the index
        self.index = {}
        for section in self.soup.find_all("p", class_="menu"):
            section_name = section.find_previous_sibling(
                "p", class_="menularge"
            ).text.strip()

            # avoid namespace clash with 'platform' module
            for _platform in section.find_all("a", href=True):
                self.index[_platform.text] = {
                    # url is relative to root
                    "url": urllib.parse.urljoin(VGMUSIC_URL, _platform["href"]),
                    "section": section_name,
                    # a map of game titles to their songs
                    "titles": collections.defaultdict(list),
                }

    def _get_soup(self, *args, **kwargs) -> bs4.BeautifulSoup:
        return bs4.BeautifulSoup(self.session.get(*args, **kwargs).text, BS4_PARSER)

    def __getitem__(self, _platform):
        if not self.index[_platform]["titles"]:
            # cache it lazily
            platform_page = self._get_soup(self.index[_platform]["url"])

            # This header specifies the info on each song.
            # We just map it to the 'table row' tags below each title header onwards.
            header = platform_page.find("tr", class_="header")
            header_names = [
                _clean_header(h.text) for h in header.find_all("th", class_="header")
            ]

            # The first two table rows specify the header, we don't need them anymore.
            header.decompose()
            # just a blank line below header
            platform_page.find("tr").decompose()

            for row in platform_page.tbody.find_all("tr"):
                title = row.find_previous_sibling("tr", class_="header").td.a.text

                if not row.get_text(strip=True):
                    # a blank row?
                    continue

                song_info_raw = row.find_all("td")
                song_info = {k: v.text for k, v in zip(header_names, song_info_raw)}

                # first column is always song title and url (href) as an 'a' tag.
                song_info["song_url"] = song_info_raw[0].a["href"]
                # comments will always be the word 'Comments', so replace with url
                song_info["comments"] = song_info_raw[3].a["href"]
                song_info["file_size"] = int(song_info["file_size"].split()[0])

                self.index[_platform]["titles"][title].append(song_info)

        return self.index[_platform]


if __name__ == "__main__":
    mus = VGMusic()
    with open("out.json", mode="w") as f:
        json.dump(mus.index, f, indent=4)
