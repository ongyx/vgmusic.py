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
It weighs in at 8.5 MB as JSON (6 MB without indentation).

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

See [API.md](API.md).

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
