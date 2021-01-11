# vgmusic.py

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/vgmusic)](https://pypi.org/project/vgmusic)
![PyPI - License](https://img.shields.io/pypi/l/vgmusic)
![PyPI](https://img.shields.io/pypi/v/vgmusic)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/vgmusic)
![Lines of code](https://img.shields.io/tokei/lines/github/ongyx/vgmusic.py)

(unofficial) Python API for [VGMusic](vgmusic.com).
This project is in no way affiliated with or sponsered by Mike Newman or any of the staff at VGMusic.

## Usage

Thoughout these examples, we will be using the `API` object as the api:

```python
import vgmusic

api = vgmusic.API()
```

It is recommended to close it once you are done:

```python
# do something here...
api.close()
```

The best way is to use a [context manager](https://www.python.org/dev/peps/pep-0343/), a.k.a `with` statement:

```python
with vgmusic.API() as api:
    # do something here
```

Note that the API is lazy: It will only retrieve data for a console/system the first time it is queried for it.
To override this behaviour, use `force_cache` (see [Module Documentation](##module-documentation)).

## API Specification

```text
// Any keys starting with '$' are variable.
{
    // The system's name
    "$system_name": {
        // The system's url, i.e https://www.vgmusic.com/music/console/sony/ps4/
        "url": ...,
        // The section's name, i.e Sony
        "section": ...,
        // All the titles available for this system
        "titles": {
            // The game's name.
            "$game_name": [
                // The direct url to the song's MIDI file
                "song_url": ...,
                // The song's title
                "song_title": ...,
                // The song's file size, in bytes (as an int)
                "file_size": ...,
                // Who sequenced the midi
                "sequenced_by": ...,
                // url to comments
                "comments_url": ...,
            ]
        },
        // When the system's page was last updated (as a Unix timestamp as int)
        "last_updated": ...,
        // Used to track page revisions
        "_etag": ...,
        // Version of the VGMusic indexer.
        "indexer_version": ...
    }
}
```

## Backends

The API has two backends: dictionary-like (access from Python code) and a REST-based web interface (through Flask, from elsewhere) (WIP).
You can also use it from the command-line.

### Dictionary/Key

To query songs, you have to provide the name of the system/catagory and the game title:

```python
songs = api["Sony PlayStation 4"]["titles"]["Persona 5"]
```

You can manipulate the API using standard dictionary methods:

```python
# list all titles for a system
titles = list(api["Nintendo Switch"].keys())  # ['Sonic Mania'], as of 5/1/2021
# count how many songs in total
total = sum(len(songs) for songs in api["Nintendo Switch"]["titles"].values())  # 12, as of 5/1/2021
```

Anything you can do with a dictionary, it's basically possible with this API.

You can also search using a function and by regex:
(`search_by_regex()` uses `re.search()`.)

```python
# Find all songs where system name has "Nintendo", game name has "Mario", and song name is any.
songs = api.search_by_regex("Nintendo", "Mario", "")
```

To use another key in song_info for the last regex, use `song_info_key`:

```python
# Find all songs authored by '!!!!!'
songs = api.search_by_regex("", "", "^!!!!!$", song_info_key="sequenced_by")
```

For the keys that can be used, see [API Specification](##api-specification).

### CLI

Install the CLI first:

```text
pip install vgmusic[cli]
```

And then run with

```text
vgmusic
```

On first run, it might take a while to initally cache all the systems. Maybe grab a cup of tea or two.

Once parsing is done, it will download **all** the MIDI files by default.

To fliter out songs using regex, use the `-s/--search` option:

```text
vgmusic -s "Sony PlayStation \d::Persona \d::.*"
```

This downloads all songs from the system `Sony PlayStation \d` and the game `Persona \d` which has any name.

`-s/--search` maps directly to `API.search_by_regex()`.

Help is always useful:

```text
vgmusic --help
```

### REST/fastapi

**NOTE**: This is WIP, it has not been finished yet.
Make sure you have installed the REST extension:

```text
pip install vgmusic[REST]
```

and then start the server with

```text
python3 -m vgmusic.rest
```

Right now, there are two endpoints:

* `GET /systems` (array): all available systems
* `GET /system/{system}` (object): info for a system
* `GET /search?query=...&song_info_key=...` (array): songs matching the query (see `API.search_by_regex()`)

The data returned is in this format:

```text
{
    // status code of response
    "code": ...,
    // the response data
    "data": ...,
}
```

TODO: GET /search is currently broken.

## License
MIT.
