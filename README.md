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
To override this behaviour, use `force_cache` (see [Module Documentation](#module-documentation)).

## Module Documentation

(Systems are analogous to game consoles, it is just a more general name.)

### `Song`

A dataclass with the following fields:

```
@dataclass
class Song:
    url: str  # direct link to midi file
    title: str
    size: int  # number of bytes of midi file
    author: str
    md5: str  # md5 checksum of midi file according to VGMusic
```

The rest of the fields should be self-explainatory.

### `API[system_name]` (`API.__getitem__(system_name)`)

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
# count how many songs/games in total
total_games, total_songs = system.total()

# ...and of course, how many songs in a game
total_game_songs = len(game)
```

### `len(API)`

Return the number of systems in VGMusic.

### `API.search(criteria)`

Return a list of songs according to criteria.

`criteria`: a function with type signature `def criteria(system_name, game_name, song) -> bool`
    where {system,game}_name is self-explainatory, and song is a `Song` object.

Example:

```python
def criteria(system, game, song):
    return song.size < 1000  # find all songs below 1 KB
```

### `API.search_by_regex(**regexes)`

Return a list of songs filtered by regex.

`**regexes`: The regexes to use. If the regex has the key 'system' or 'game',
    it will be used to filter system name and game name.
    Regexes with other keys match to fields in the `Song` objects.

Example:

```python
api.search_by_regex(title="[Bb]attle")  # find all songs with 'Battle' or 'battle' in their titles.
```

### `API.force_cache()`

Cache all systems preemptively.
(No further caching will be done on further `API[system]` calls.)

## Backends

The API has two backends: dictionary-like (access from Python code) and a REST-based web interface (through Flask, from elsewhere) (WIP).

### Using REST/fastapi

**NOTE**: This is WIP (need to fix to the new rewrite).

Make sure you have installed the REST extension:

```bash
$ pip install vgmusic[REST]
```

and then start the server with

```bash
$ python3 -m vgmusic.rest
```

Right now, there are two endpoints:

* `GET /systems` (array): all available systems
* `GET /system/{system}` (object): info for a system
* `GET /search?system=...&title=...` (array): songs matching the query (see `API.search_by_regex()`)

The data returned is in this format:

```json
{
    // the response data
    "data": ...
}
```

## License
MIT.
