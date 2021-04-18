# vgmusic.py

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/vgmusic)](https://pypi.org/project/vgmusic)
![PyPI - License](https://img.shields.io/pypi/l/vgmusic)
![PyPI](https://img.shields.io/pypi/v/vgmusic)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/vgmusic)
![Lines of code](https://img.shields.io/tokei/lines/github/ongyx/vgmusic.py)

(unofficial) Python API for [VGMusic](https://vgmusic.com).
This project is in no way affiliated with or sponsered by Mike Newman or any of the staff at VGMusic.

## Caches

vgmusic.py relies heavily on caches to avoid downloading VGMusic pages repeatedly; the CLI auto-caches for you into a `cache.json` file.

An example of a cache file is at the root of this repo; it is a pre-parsed full dump of info
(direct links, authors, etc.) on all the songs currently on VGMusic.
It weighs in at ~8.5 MB right now (as JSON; experimentation with msgpack yielded ~5 MB of data.)

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
To override this behaviour, use `force_cache` (see [Module Documentation](#module-documentation)).

## Module Documentation

(Systems are analogous to game consoles, it is just a more general name.)

### Song

A dataclass with the following fields:

```python
@dataclass
class Song:
    url: str  # direct link to midi file
    title: str
    size: int  # number of bytes of midi file
    author: str
    md5: str  # md5 checksum of midi file according to VGMusic
```

The rest of the fields should be self-explainatory.

#### Song.download(session=None, verify=False)

Return the downloaded bytes of the song's midi file, optionally using a `requests.Session` object (to download).

If verify is True, the bytes will be compared to the size and md5 checksum provided by VGMusic.
A mismatch will raise a ValueError.

### API

Public API class to query/download songs.

Optionally, a previously saved cache (from `cache()`) can be passed to __init__ using the 'cache' keyword argument.

It has the following fields:

```python
class API:
    session: requests.Session
    systems: Dict[str, System]  # map of system name to System objects
```

#### API[system_name]

Return a `System` object (collection of songs per each game.)
The system's name is the same as in VGMusic (i.e NES, SNES, etc.)

`System` objects support indexing over their games, so you can do this:

```python
game = api["Nintendo Switch"]["Sonic Mania"]  # get a list of Songs for a specific system and game
```

You can also use standard dictionary methods:

```python
system = api["Nintendo Switch"]

# list all titles for a system
titles = list(system.keys())

# count how many songs in total
# equivalent to 'sum(len(game) for game in system)'
total_songs = system.total_songs()

# ...and how many songs in a game
total_game_songs = len(game)
```

#### len(API)

Return the number of systems in VGMusic.

#### API.search(criteria)

Return a list of songs according to criteria.

`criteria`: a function with type signature `def criteria(system_name, game_name, song) -> bool`
    where {system,game}_name is self-explainatory, and song is a `Song` object.

Example:

```python
def criteria(system, game, song):
    return song.size < 1000  # find all songs below 1 KB
```

#### API.search_by_regex(**regexes)

Return a list of songs filtered by regex.

`**regexes`: The regexes to use. If the regex has the key 'system' or 'game',
    it will be used to filter system name and game name.
    Regexes with other keys match to fields in the `Song` objects.

Example:

```python
api.search_by_regex(title="[Bb]attle")  # find all songs with 'Battle' or 'battle' in their titles.
```

#### API.download(songs, to=".", max_request=5)

Download a list of songs (i.e from `search()` or `search_by_regex()`) to a directory (by default curdir).

#### API.force_cache()

Cache all systems preemptively.
(No further caching will be done on further `API[system]` calls.)

#### API.close()

Close the current session.
Any attempt to access/use the API object after it is closed is **strongly** discouraged.

## CLI

The command-line interface can be used to download MIDI files concurrently (useful for scripting).

Make sure to install the CLI extra first:

```
pip install vgmusic[cli]
```

For more info on how to use the cli, run `vgmusic --help`.

## REST

Install the rest extension:

```
pip install vgmusic[rest]
```

and start the server with `python3 -m vgmusic.rest`.

For docs, visit [here](http://localhost:8000/docs) once you've started the server.

## License
MIT.
