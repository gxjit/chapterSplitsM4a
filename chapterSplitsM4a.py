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
        description="Split m4a files with bookmarks using ffmpeg."
    )
    parser.add_argument(
        "-d", "--dir", required=True, help="Directory path", type=dirPath
    )
    parser.add_argument(
        "-c", "--gen-cue", action="store_true", help="Generate cuesheet .cue instead of splits."
    )
    parser.add_argument(
        "-n",
        "--no-write",
        required=False,
        help="Do not write anything to Disk(except logs) / Dry run.",
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

getFileList = lambda dirPath: [
    x for x in dirPath.iterdir() if x.is_file() and ".info.json" in x.name
]


def HMSToMS(time):
    timeArr = [int(e) for e in time.split(":")]
    if timeArr[0] != 0:
        for h in range(timeArr[0] - 1):
            timeArr[1] += 60
    timeStr = [str(e).zfill(2) for e in timeArr[1:]]
    return ":".join(timeStr)


def main(pargs):

    dirPath = pargs.dir.resolve()

    fileList = getFileList(dirPath)

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

        artist = js["creator"] or js["uploader"]

        album = js["title"]

        extractDirName = slugifyP(album)

        if not pargs.no_write:
            extractDir = makeTargetDirs(extractDirName, dirPath)

        if pargs.gen_cue:
            cue = dirPath.joinpath(f"{baseName}.cue")
            with open(cue, "w") as f:
                f.write(f'\nPERFORMER "{artist}"')
                f.write(f'\nTITLE "{album}"')
                f.write(f'\nFILE "{m4aFile}" AAC')

        logsDir = makeTargetDirs("logs", dirPath)

        with open(logsDir.joinpath(f"{baseName}.log"), "w") as log:
            printLogP = fn.partial(printLog, logRef=log)
            printLogP("\n\n==============================")
            printLogP(f"\n\nProcessing {album}")
            printLogP(f"\nOutput directory name: {extractDirName}")

            if not isinstance(js["chapters"], Iterable):
                printLogP(f"\n\n\nSkipping {album}, Chapters info not found.")
                continue

            for i, chapter in enumerate(js["chapters"]):
                startTime = secondsToHMS(chapter["start_time"])
                endTime = secondsToHMS(chapter["end_time"])
                title = chapter["title"]
                track = i + 1
                fileName = f"{track}. {slugifyP(title)}.m4a"
                printLogP("\n\n------------------------------")
                printLogP(f"\n\nProcessing {title} from {startTime} to {endTime}")
                printLogP(f"\nOutput file name: {fileName}")
                if not pargs.no_write:
                    if pargs.gen_cue:
                        with open(cue, "a") as f:
                            f.write(f"\n  TRACK {str(track).zfill(2)} AUDIO")
                            f.write(f'\n    TITLE "{title}"')
                            f.write(f"\n    INDEX 01 {HMSToMS(startTime)}:00 ")
                    else:
                        out = subprocess.check_output(  # check output
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
                        ).decode("utf-8")
                        printLogP(out)
        input("Press any key to continue processing.")


# inp = input(f'\n\nCurren Album: {album}\nInput c to continue, s to skip.')

main(parseArgs())
