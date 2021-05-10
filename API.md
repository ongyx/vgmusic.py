# Table of Contents

* [vgmusic.vgmusic](#vgmusic.vgmusic)
  * [Song](#vgmusic.vgmusic.Song)
    * [cache](#vgmusic.vgmusic.Song.cache)
    * [download](#vgmusic.vgmusic.Song.download)
  * [System](#vgmusic.vgmusic.System)
    * [cache](#vgmusic.vgmusic.System.cache)
    * [total\_songs](#vgmusic.vgmusic.System.total_songs)
  * [API](#vgmusic.vgmusic.API)
    * [search](#vgmusic.vgmusic.API.search)
    * [search\_by\_regex](#vgmusic.vgmusic.API.search_by_regex)
    * [download](#vgmusic.vgmusic.API.download)
    * [cache](#vgmusic.vgmusic.API.cache)
    * [force\_cache](#vgmusic.vgmusic.API.force_cache)

<a name="vgmusic.vgmusic"></a>
# vgmusic.vgmusic

<a name="vgmusic.vgmusic.Song"></a>
## Song Objects

```python
@dataclass
class Song()
```

A song in a game's soundtrack as midi.

**Arguments**:

- `url` - The absolute direct url to the midi file.
- `title` - The name of the song.
- `size` - The size of the song (number of bytes).
- `author` - The name of the person who sequenced the song to midi.
- `md5` - The MD5sum of the midi file.
  

**Attributes**:

  See args.

<a name="vgmusic.vgmusic.Song.cache"></a>
#### cache

```python
 | cache() -> dict
```

Serialise all fields in this song to a dictionary representation.

<a name="vgmusic.vgmusic.Song.download"></a>
#### download

```python
 | download(session: Optional[requests.Session] = None, verify: bool = False) -> bytes
```

Download this song's midi file.

**Arguments**:

- `session` - The session to use to download.
  If not specified, requests.get will be used instead.
- `verify` - Whether or not to check if the size and md5 checksum matches the midi file.
  If not specified, defaults to False.
  

**Returns**:

  The bytes of the midi file.
  

**Raises**:

  ValueError, if verify=True and the check failed.

<a name="vgmusic.vgmusic.System"></a>
## System Objects

```python
class System(c_abc.Mapping)
```

A collection of songs associated with game titles in a (video game) system.

**Arguments**:

- `url` - The absolute url to the system page.
- `session` - The session used to download the page.
  If not specified, defaults to None (a new session is created).
- `cache` - The previously serialised dict from .cache().
  If not specified, defaults to None.
  

**Attributes**:

- `url` _str_ - See args.
- `session` _requests.Session_ - See args.
- `games` _Dict[str, List[Songs]]_ - A map of video game titles to a list of songs.
- `version` _str_ - The version of the VGMusic indexer used to create the system page.

<a name="vgmusic.vgmusic.System.cache"></a>
#### cache

```python
 | cache() -> dict
```

Serialise all songs to a dictionary format that can be saved on disk and subsequently loaded.

**Returns**:

  The serialised songs.

<a name="vgmusic.vgmusic.System.total_songs"></a>
#### total\_songs

```python
 | total_songs() -> int
```

Return the total number of songs.

<a name="vgmusic.vgmusic.API"></a>
## API Objects

```python
class API(c_abc.Mapping)
```

Public api to VGMusic.

**Arguments**:

- `cache` - The previously serialised dict from .cache().
  If not specified, defaults to None.
  

**Attributes**:

- `session` - The requests session used to download pages/songs.
- `systems` - A map of system names to System objects.

<a name="vgmusic.vgmusic.API.search"></a>
#### search

```python
 | search(criteria: Callable[[str, str, Song], bool]) -> List[Song]
```

Search for songs using criteria.

**Arguments**:

- `criteria` - A function that accepts three arguments (system_name, game_name, song) and returns True or False.
  

**Returns**:

  Songs that match the criteria.

<a name="vgmusic.vgmusic.API.search_by_regex"></a>
#### search\_by\_regex

```python
 | search_by_regex(**regexes) -> List[Song]
```

Search for songs using regex as criteria.

NOTE: re.search is used, not re.match.
To anchor regexes, use '^' and '$'.

**Arguments**:

- `regexes` - The regexes to use as criteria.
  'system' and 'game' match the system name and game name; anything else matches to fields in the song.
  

**Returns**:

  Songs matching the regexes.

<a name="vgmusic.vgmusic.API.download"></a>
#### download

```python
 | download(songs: List[Song], to: Union[str, pathlib.Path], max_requests: int = 5)
```

Download songs to path.
Any illegal characters in the song's title are escaped/converted before being used as the filename.

To download individual songs, use 'Song.download()' instead.

**Arguments**:

- `songs` - The list of Song objects to download.
- `to` - The directory to download to.
- `max_requests` - How many concurrent downloads can happen at the same time.
  To avoid pinging VGMusic servers too much, it is recommended to set this at 10 or below.
  If not specified, defaults to 5.

<a name="vgmusic.vgmusic.API.cache"></a>
#### cache

```python
 | cache() -> dict
```

Serialise all systems to a dictionary format that can be saved on disk and subsequently loaded.

**Returns**:

  The serialised systems.

<a name="vgmusic.vgmusic.API.force_cache"></a>
#### force\_cache

```python
 | force_cache()
```

Pre-emptively cache all system pages (no further lazy caching is done).

