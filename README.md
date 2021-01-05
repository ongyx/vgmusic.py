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

## Backends

The API has two backends: dictionary-like (access from Python code) and a REST-based web interface (through Flask, from elsewhere).
You can also use it from the command-line (WIP).

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

### REST/Flask

**NOTE**: This is WIP, it has not been finished yet.
Make sure you have installed the Flask extension:

```text
pip install vgmusic[REST]
```

## License
MIT.
