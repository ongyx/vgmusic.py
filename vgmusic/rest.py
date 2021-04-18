# coding: utf8

import json
import pathlib

import fastapi
import uvicorn

from .vgmusic import API


app = fastapi.FastAPI()

cache_path = pathlib.Path() / "cache.json"

try:
    cache = json.loads(cache_path.read_text())
except FileNotFoundError:
    cache = None

api = API(cache=cache)


@app.get("/systems")
def systems():
    """Get a list of all systems available."""
    return {"data": list(api.keys())}


@app.get("/systems/{system}")
def systems_data(system: str):
    """Get data for a system."""
    return {"data": api[system].cache()}


@app.get("/search")
def search(query: fastapi.Request):
    """Get a list of songs by search query.
    The query(s) must be a vaild regular expression.

    A song is an object:
    {
        'url': // The song download url.
        'title': // The song name.
        'size': // The size of the song (number of bytes).
        'author': // Name of the author.
        'md5': // The md5 checksum of the song file (from VGMusic).
    }

    The query (in the form of /search?query1=...&query2=...) can have the following fields:

    'system' - Match the system name (i.e NES, SNES, etc.).
    'game' - Match the game name.

    'url', 'title', 'size', 'author', 'md5': Match against the song's respective field.
    """
    return {"data": [s.cache() for s in api.search_by_regex(**query.query_params)]}


@app.on_event("shutdown")
def shutdown():
    cache_path.write_text(json.dumps(api.cache()))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
