import vgmusic

with vgmusic.API(force_cache=["Nintendo Switch"]) as api:
    print(api.filter_by_regex("Nintendo Switch", "Sonic Mania", "Act"))
