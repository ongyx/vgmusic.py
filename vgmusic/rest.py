# coding: utf8
"""REST JSON-based backend for vgmusic.py."""

from typing import Optional

import fastapi

import vgmusic.public


app = fastapi.FastAPI()

vgapi = vgmusic.public.API()


@app.get("/systems")
def get_systems():
    return {"data": list(vgapi.keys())}


@app.get("/systems/{system}")
def get_system(system: str):
    system_info = vgapi[system]
    # don't send so much data at once
    system_info.pop("titles")
    return {"data": system_info}


@app.get("/titles/{system}")
def get_titles(system: str):
    return {"data": vgapi[system]["titles"]}


@app.get("/search")
def get_search(query: str = "", song_info_key: Optional[str] = None):
    regex_query = query.split("::")
    song_info_key = song_info_key or "song_title"
    return {"data": vgapi.search_by_regex(*regex_query, song_info_key)}
