# Copyright (c) 2020 Gurjit Singh

# This source code is licensed under the MIT license that can be found in
# the accompanying LICENSE file or at https://opensource.org/licenses/MIT.


import argparse
import datetime as DT
import functools as fn
import json
import os
import os.path as path
import pathlib
import subprocess
import sys
from collections.abc import Iterable

from slugify import slugify


def parseArgs():
    def dirPath(pth):
        pthObj = pathlib.Path(pth)
        if pthObj.is_dir():
            return pthObj
        else:
            raise argparse.ArgumentTypeError("Invalid Directory path")

    parser = argparse.ArgumentParser(
        description="Split Youtube m4a files with bookmarks using ffmpeg."
    )
    parser.add_argument(
        "-d", "--dir", required=True, help="Directory path", type=dirPath
    )
    parser.add_argument(
        "-n",
        "--no-write",
        required=False,
        help="Do not write anything to Disk / Dry run.",
        action="store_true",
    )
    pargs = parser.parse_args()

    return pargs


secondsToHMS = lambda sec: str(DT.timedelta(seconds=sec))


def makeTargetDirs(name, dirPath):
    newPath = dirPath.joinpath(name)
    if not newPath.exists():
        os.mkdir(newPath)
    return newPath


def printLog(data, logRef):
    print(data)
    logRef.write(data)


slugifyP = fn.partial(
    slugify,
    separator=" ",
    lowercase=False,
    replacements=([[":", "_"], ["-", "_"], ["[", "("], ["]", ")"]]),
    regex_pattern=r"\)\(\.",
    save_order=True,
)


def main(pargs):

    dirPath = pargs.dir.resolve()

    fileList = [x for x in dirPath.iterdir() if x.is_file() and ".info.json" in x.name]

    if not fileList:
        print("Nothing to do.")
        sys.exit()

    for file in fileList:

        baseName = str(file.name).replace(".info.json", "")

        m4aFile = dirPath.joinpath(f"{baseName}.m4a")

        if not m4aFile.exists():
            print(f"\n\n\nNo matching m4a file found for {file}")
            continue

        with open(file, "r", encoding="utf-8") as f:
            js = json.loads(f.read())

        artist = js["creator"]
        album = js["title"]

        extractDirName = slugifyP(album)

        if not pargs.no_write:
            extractDir = makeTargetDirs(extractDirName, dirPath)

        with open(dirPath.joinpath(f"{baseName}.log"), "w") as log:
            printLogP = fn.partial(printLog, logRef=log)
            printLogP("\n\n==============================")
            printLogP(f"\n\nProcessing {album}")
            printLogP(f"\nOutput directory name: {extractDirName}")

            if not isinstance(js["chapters"], Iterable):
                print(f"\n\n\nSkipping {album}, Chapters info not found.")
                continue

            for i, chapter in enumerate(js["chapters"]):
                startTime = secondsToHMS(chapter["start_time"])
                endTime = secondsToHMS(chapter["end_time"])
                title = chapter["title"]
                track = i + 1
                fileName = f"{track}. {slugifyP(title)}.m4a"
                printLogP("\n\n------------------------------")
                printLogP(f"\n\nProcessing {title} from {startTime} to {endTime}")
                printLogP(f"Output file name: {fileName}")
                if not pargs.no_write:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-ss",
                            startTime,
                            "-to",
                            endTime,  # --ss -to need to be prior to -i
                            "-i",
                            m4aFile,
                            "-c:a",
                            "copy",
                            "-metadata",
                            f"track={track}",
                            "-metadata",
                            f"title={title}",
                            "-metadata",
                            f"artist={artist}",
                            "-metadata",
                            f"album_artist={artist}",
                            "-metadata",
                            f"album={album}",
                            "-loglevel",
                            "warning",
                            path.join(extractDir, fileName),
                        ]
                    )
        input("Press any key to continue processing.")


# inp = input(f'\n\nCurren Album: {album}\nInput c to continue, s to skip.')

main(parseArgs())
