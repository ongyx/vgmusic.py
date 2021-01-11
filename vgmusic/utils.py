# coding: utf8
"""Utils used by the vgmusic.py API."""

import collections
import logging
import re
import urllib.parse
from email.utils import parsedate_to_datetime

import bs4
import requests

from vgmusic.exceptions import ParseError

_log = logging.getLogger("vgmusic.py")

BS4_PARSER = "html5lib"
# parse the indexer version.
RE_INDEX_VER = re.compile(r"([\d\.]{3,}[^\.])")


def _setup_logging(level=logging.DEBUG):
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.basicConfig(level=level, format=" %(levelname)-8s :: %(message)s")


def clean_header(name: str) -> str:
    return name.lower().replace(" ", "_")


def sanitize_filename(name: str) -> str:
    return re.sub(
        "_{2,}", "_", "".join([c if c.isalnum() else "_" for c in name])
    ).strip("_")


def soup_from_response(response: requests.models.Response) -> bs4.BeautifulSoup:
    return bs4.BeautifulSoup(response.text, BS4_PARSER)


class SongTable:
    """A VGMusic song table.

    Args:
        response: The VGMusic table page (downloaded using requests.get).

    Attributes:
        headers (list): The table's headers.
        info (dict): The table, parsed as a dict.
        url (str): The table page's url.
        table (bs4.Tag): The unparsed (raw) table.
    """

    def __init__(self, response: requests.models.Response):
        self.info = {
            # a map of game titles to their songs
            "titles": collections.defaultdict(list),
        }
        self.url = response.url

        soup = soup_from_response(response)
        self.table = soup.tbody

        self.info["last_updated"] = parsedate_to_datetime(
            response.headers["Last-Modified"]
        ).timestamp()

        # we use etag to check for changes (last updated is for client-side)
        self.info["_etag"] = response.headers["ETag"]

        # indexer version
        # idk who would actually need this, but still...
        self.info["indexer_version"] = RE_INDEX_VER.findall(
            soup.address.get_text(strip=True)
        )[0]

        # This header specifies the info on each song.
        # We just map it to the 'table row' tags below each title header onwards.
        self.headers = [
            clean_header(h.text) for h in self.table.tr.find_all("th", class_="header")
        ]

        # The first two table rows specify the header, we don't need them anymore.
        for _ in range(2):
            row = self.table.tr
            if row is None:
                raise ParseError(
                    "table does not have any rows (system does not have any songs?)"
                )
            row.decompose()

    def parse(self) -> dict:
        """Parse the table's rows into self.info["titles"], with each title (game)
        mapped to a list of songs.

        Returns:
            The parsed rows.
        """
        title = None
        for row in self.table.find_all("tr"):

            if row.get("class", [""])[0] == "header":
                # there is no song info, skip
                title = row.td.a.text
                continue

            if not row.get_text(strip=True):
                # a blank row?
                continue

            self.info["titles"][title].append(self._parse_song(row))

        return self.info

    def _parse_song(self, row: bs4.Tag) -> dict:
        song_info = {}
        for header, tag in zip(self.headers, row.find_all("td")):

            # Currently, the following headers are used on VGMusic.com.
            # song_title: Self-explainatory.
            # file_size: Size in bytes.
            # sequenced_by: Who created the midi.
            # comments: How many comments (does not work when getting HTML)

            # vgmusic.py adds these headers:
            # song_url: Direct URL to the midi file.
            # comments_url: Direct URL to the comments page.

            if header in ("song_title", "comments"):
                # so we won't end up with 'song_title_url'
                normalized = header.split("_")[0]

                song_info[f"{normalized}_url"] = urllib.parse.urljoin(
                    self.url, tag.a["href"]
                )
                value = tag.get_text(strip=True)

            elif header == "file_size":
                value = int(tag.text.split()[0])

            else:
                value = tag.get_text(strip=True)

            song_info[header] = value

        del song_info["comments"]
        return song_info
