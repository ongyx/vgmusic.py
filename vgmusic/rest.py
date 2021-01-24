# coding: utf8
"""REST JSON-based backend for vgmusic.py."""

import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI

import vgmusic.public
from vgmusic.utils import _setup_logging

app = FastAPI()

vgapi = vgmusic.public.API()
vgapi.force_cache_all()

_log = logging.getLogger("vgmusic.py")
_setup_logging()


@app.get("/systems")
def get_systems():
    return {"data": list(vgapi.keys())}


@app.get("/system/{system}")
def get_system(system: str):
    return {"data": vgapi[system]}


@app.get("/search")
def get_search(query: str, song_info_key: Optional[str] = None):
    regex_query = query.split("::")
    song_info_key = song_info_key or "song_title"
    _log.info("[rest] query %s", regex_query)
    return {"data": vgapi.search_by_regex(*regex_query, song_info_key=song_info_key)}


@app.on_event("shutdown")
def cleanup():
    vgapi.close()


if __name__ == "__main__":
    uvicorn.run("vgmusic.rest:app", host="127.0.0.1", port=5000, log_level="info")
