# vgmusic.py

(unofficial) Python API for [VGMusic](vgmusic.com).
This project is in no way affiliated with or sponsered by Mike Newman or any of the staff at VGMusic.

## Usage
```python
import vgmusic

# initalise the API object
with vgmusic.VGMusic() as api:
    # to access music info for a system, use the API as a dictionary
    ps4 = api["Sony PlayStation 4"]
    # get song by game title (it's a list of songs)
    song_info = ps4["titles"]["Persona 5"][0]
    print(song_info["sequenced_by"])  # fakt13 (shoutout :3)
```

CLI is coming soon...

## License
MIT.
