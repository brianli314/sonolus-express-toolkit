from pathlib import Path
import argparse
import urllib.request
from urllib.request import Request, urlopen
import json
import os
from utils import localize, generate_background
import time
import shutil
import io
from sonolus_converters import sus, next_sekai
from pydub import AudioSegment
import pydub
from pydub.silence import detect_leading_silence


SOURCE = Path(__file__).resolve().parents[1] / "source"
LEVELS_DIR = SOURCE / "levels"
PLAYLIST_DIR = SOURCE / "playlists"
BACKGROUNDS_DIR = SOURCE / "backgrounds"
ENGINE = "next-rush-sbuga"

repo = "https://raw.githubusercontent.com/Sekai-World/"
DIFFICULTIES = ("easy", "normal", "hard", "expert", "master", "append")
MASTER_DATABASE_REPOSITORIES = {
    "jp": "sekai-master-db-diff",
    "en": "sekai-master-db-en-diff",
    "kr": "sekai-master-db-kr-diff",
    "cn": "sekai-master-db-cn-diff",
    "tw": "sekai-master-db-tc-diff",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a song from sekai.best")
    parser.add_argument(
        "--engine",
        default=ENGINE,
        help="Name of engine to use",
    )

    parser.add_argument(
        "--ids", 
        required=True,
        nargs='+',
        type=int,
        help="PJSK Song id",
    )

    parser.add_argument(
        "--locale",
        default="en",
        help="Locale to use when processing files"
    )

    return parser.parse_args()


def download_table(region: str, table: str):
    repository = MASTER_DATABASE_REPOSITORIES[region]
    url = (
        "https://raw.githubusercontent.com/Sekai-World/"
        f"{repository}/refs/heads/main/{table}.json"
    )
    request = Request(url, headers={"User-Agent": "sonolus-server-importer"})
    try:
        with urlopen(request, timeout=30) as response:
            entries = json.load(response)
            return entries
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"Could not download PJSK table from {url}"
        ) from exc



def download_data(url, dest, level_name, data_type):
    url = "https://storage.sekai.best/sekai-jp-assets/music/" + url
    local_filename = SOURCE / dest / level_name / data_type
    local_filename.parent.mkdir(parents=True, exist_ok=True)  # make sure the folder exists

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "sonolus-server-importer"
        }
    )

    with urllib.request.urlopen(req) as response, open(local_filename, "wb") as out_file:
        out_file.write(response.read())

    print(f"Download {level_name} - {data_type} complete!")

def get_item_json(difficulty, music, engine, vocals, characters):
    out = {
        "version": 1,
        "rating": difficulty["playLevel"],
        "engine": engine,
        "useSkin": {
            "useDefault": True
        },
        "useParticle": {
            "useDefault": True
        },
        "useEffect": {
            "useDefault": True
        },
        "title": localize(music["title"]), 
        "author": localize("Project Sekai: Colorful Stage!")
    }

    char_ids = [c["characterId"] for c in vocals["characters"]]
    chrs = [c for c in characters if c["id"] in char_ids]

    names = []
    for c in chrs:
        if c.get("firstName"):
            name = c["firstName"] + " " + c["givenName"]
        else: 
            name = c["givenName"]
        names.append(name)
    chrs_string = " & ".join(names)
    out["artists"] = localize(chrs_string)

    tags = [
        {
            "title": f"#{difficulty["musicDifficulty"].upper()}"
        },
        {
            "title": vocals["caption"]
        }
    ]

    out["tags"] = localize(tags)
    desc = [
        f"Lyricist: {music.get("lyricist")}",
        f"Composer: {music.get("composer")}", 
        f"Arranger: {music.get("arranger")}", 
        "", 
        music["title"]

    ]
    description = "\n".join(desc)
    out["description"] = localize(description)

    return out

def get_playlist_json(music, vocals_list, levels, num_difficulties):
    out = {
        "version": 1,
        "time": int(time.time()),
        "title": localize(music["title"]), 
        "author": localize("Project Sekai: Colorful Stage!"),
        "subtitle": localize(f"{len(vocals_list)} versions, {num_difficulties} difficulties")
    }

    captions = [vocal["caption"] for vocal in vocals_list]
    tags = []
    for caption in captions:
        tags.append(
            {
                "title": caption
            }
        )

    out["tags"] = localize(tags)
    desc = [
        f"Lyricist: {music.get("lyricist")}",
        f"Composer: {music.get("composer")}", 
        f"Arranger: {music.get("arranger")}", 
        "", 
        music["title"]

    ]
    description = "\n".join(desc)
    out["description"] = localize(description)

    out["levels"] = levels

    return out



def main():
    args = parse_args()

    LEVELS_DIR.mkdir(exist_ok=True)
    PLAYLIST_DIR.mkdir(exist_ok=True)
    BACKGROUNDS_DIR.mkdir(exist_ok=True)
    musicDifficulties = download_table(args.locale, "musicDifficulties")
    musics = download_table(args.locale, "musics")
    musicVocals = download_table(args.locale, "musicVocals")
    gameCharacters = download_table(args.locale, "gameCharacters")


    for musicid in args.ids:
        filtered_difficulties = [d for d in musicDifficulties if d["musicId"] == musicid]
        filtered_musics = [m for m in musics if m["id"] == musicid]
        filtered_vocals = [m for m in musicVocals if m["musicId"] == musicid]

        if len(filtered_musics) != 1:
            print(f"Music for {musicid} not found, or too many musics")
            continue

        music = filtered_musics[0]

        levels = []

        pl_name = f"{10_000_000_000 - time.time()}-sekai-best-{musicid}"

        exist = False
        for lvl in os.listdir(PLAYLIST_DIR):
            if lvl.endswith(f"sekai-best-{musicid}"):
                exist = True
                break

        if exist:
            print(f"Level: sekai-best-{musicid} already exists! Skipping")
            continue

        os.mkdir(PLAYLIST_DIR / pl_name)
        download_data(f"jacket/{music["assetbundleName"]}/{music["assetbundleName"]}.png", "playlists", pl_name, "thumbnail")

        generate_background(PLAYLIST_DIR / pl_name / "thumbnail", f"sekai-best-{musicid}")

        jacket_path = PLAYLIST_DIR / pl_name / "thumbnail"
        
        for vocals in filtered_vocals:
            for difficulty in filtered_difficulties:
                name = f"{10_000_000_000 - time.time()}-sekai-best-{musicid}-{vocals["id"]}-{difficulty["musicDifficulty"]}"
                levels.append(name)
                os.makedirs(LEVELS_DIR / name, exist_ok=True)

                asset_name = vocals["assetbundleName"]

                ffmpeg_bin = Path(__file__).resolve().parents[1] / "ffmpeg" / "ffmpeg-master-latest-linuxarm64-gpl" / "bin"
                pydub.utils.get_prober_name = lambda: str(ffmpeg_bin / "ffprobe")
                AudioSegment.converter = str(ffmpeg_bin / "ffmpeg")  # this one actually works as documented

                bgm_data_loc = LEVELS_DIR / name / "bgm.mp3"
                download_data(f"long/{asset_name}/{asset_name}.mp3", "levels", name, "bgm.mp3")
                audio = AudioSegment.from_mp3(bgm_data_loc)
                trim_ms = detect_leading_silence(audio, silence_threshold=-50.0)
                trimmed = audio[trim_ms:]
                trimmed.export(LEVELS_DIR / name / "bgm", format="mp3")
                bgm_data_loc.unlink(missing_ok=True)


                download_data(f"short/{asset_name}/{asset_name}_short.mp3", "levels", name, "preview")


                chart_data_loc = LEVELS_DIR / name / "data.sus"
                download_data(f"music_score/{asset_name.split("_", 1)[1]}/{difficulty["musicDifficulty"]}.txt", "levels", name, "data.sus")
                with open(chart_data_loc, encoding="utf-8-sig") as f:
                    score = sus.load(f)
                next_sekai.export(LEVELS_DIR / name / "data", score, as_compressed=True)
                chart_data_loc.unlink(missing_ok=True)


                shutil.copy2(jacket_path, LEVELS_DIR / name / "cover")

                item = get_item_json(difficulty, music, args.engine, vocals, gameCharacters)
                item["useBackground"] = {
                    "useDefault": False,
                    "item": f"sekai-best-{musicid}-v3-bg"
                }
                with open(LEVELS_DIR / name / "item.json", 'w') as f:
                    json.dump(item, f, indent=4)

        item = get_playlist_json(music, filtered_vocals, list(reversed(levels)), len(filtered_difficulties))
        with open(PLAYLIST_DIR / pl_name / "item.json", 'w') as f:
            json.dump(item, f, indent=4)

        print(f"Imported {music["title"]}")

    print(f"Imported {len(args.ids)} songs")



if __name__ == "__main__":
    main()