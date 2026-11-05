from utils import generate_background
import shutil
from pathlib import Path
import os

PLS = Path(__file__).resolve().parents[1] / "source" / "playlists"
BGS = Path(__file__).resolve().parents[1] / "source" / "backgrounds"

def main():
    for bg in os.listdir(BGS):
        if not bg == "black":
            shutil.rmtree(BGS / bg)
    for pl in os.listdir(PLS):
        generate_background(PLS / pl / "thumbnail", pl)

if __name__ == "__main__":
    main()