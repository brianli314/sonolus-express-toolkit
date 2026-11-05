from utils import generate_background
import shutil
from pathlib import Path
import os

PLS = Path(__file__).resolve().parents[1] / "source" / "playlists"
BGS = Path(__file__).resolve().parents[1] / "source" / "backgrounds"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a song from sekai.best")

    parser.add_argument(
        "--cover_path", 
        required=True,
        type=int,
        help="Path relative to source",
    )

    parser.add_argument(
        "--locale",
        default="en",
        help="Locale to use when processing files"
    )

    return parser.parse_args()

def main():
    for bg in os.listdir(BGS):
        if not bg == "black":
            shutil.rmtree(BGS / bg)
    for pl in os.listdir(PLS):
        generate_background(PLS / pl / "thumbnail", pl)

main()