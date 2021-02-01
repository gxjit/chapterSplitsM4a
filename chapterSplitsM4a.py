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
import re
import subprocess
import sys
import time
import unicodedata
from collections.abc import Iterable


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
        "-c",
        "--gen-cue",
        action="store_true",
        help="Generate cuesheet .cue instead of splits.",
    )
    parser.add_argument(
        "-fn", "--fn-tags", action="store_true", help="Infer tags from filenames.",
    )
    parser.add_argument(
        "-n",
        "--no-write",
        required=False,
        help="Do not write anything to Disk(except logs) / Dry run.",
        action="store_true",
    )
    parser.add_argument(
        "-w",
        "--wait",
        nargs="?",
        default=None,
        const=10,
        type=int,
        help="Wait time in seconds between each iteration, default is 10",
    )
    pargs = parser.parse_args()

    return pargs


secondsToHMS = lambda sec: str(DT.timedelta(seconds=sec))


def makeTargetDirs(name, dirPath):
    newPath = dirPath.joinpath(name)
    if not newPath.exists():
        os.mkdir(newPath)
    return newPath


def nSort(s, _nsre=re.compile("([0-9]+)")):
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def printLog(data, logRef):
    print(data)
    logRef.write(data)


def getInput():
    print("\nPress Enter Key continue or input 'e' to exit.")
    try:
        choice = input("\n> ")
        if choice not in ["e", ""]:
            raise ValueError

    except ValueError:
        print("\nInvalid input.")
        choice = getInput()

    return choice


def wait(sec):
    print(f"\nWaiting for {str(sec)} seconds.\n>")
    time.sleep(int(sec))


def slugify(value, replace={}, keepSpace=True):
    """
    Adapted from django.utils.text.slugify
    https://docs.djangoproject.com/en/3.0/_modules/django/utils/text/#slugify
    """
    replace.update({"[": "(", "]": ")", ":": "_", "()": ""})
    value = str(value)
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )

    for k, v in replace.items():
        value = value.replace(k, v)
    value = re.sub(r"[^\w\s)(_-]", "", value).strip()

    if keepSpace:
        value = re.sub(r"[\s]+", " ", value)
    else:
        value = re.sub(r"[-\s]+", "-", value)
    return value


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


def getJson(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.loads(f.read())


pargs = parseArgs()

dirPath = pargs.dir.resolve()

fileList = sorted(getFileList(dirPath), key=lambda k: nSort(str(k.stem)))

if not fileList:
    print("Nothing to do.")
    sys.exit()

for file in fileList:

    baseName = str(file.name).replace(".info.json", "")

    m4aFile = dirPath.joinpath(f"{baseName}.m4a")

    if not m4aFile.exists():
        print(f"\n\n\nNo matching m4a file found for {file}")
        continue

    js = getJson(file)

    if pargs.fn_tags:
        tagName = baseName.rsplit("-", 1)[0].strip()
        artist = slugify(tagName.split(" - ")[0].strip())
        album = slugify(tagName.split(" - ")[1].strip()) or artist
    else:
        artist = slugify(js["creator"] or js["uploader"])
        album = slugify(js["title"])

    logsDir = makeTargetDirs("logs", dirPath)

    log = open(logsDir.joinpath(f"{baseName}.log"), "w")

    printLogP = fn.partial(printLog, logRef=log)
    printLogP("\n\n==============================")
    printLogP(f"\n\nProcessing {album}")

    if not isinstance(js["chapters"], Iterable):
        printLogP(f"\n\n\nSkipping {album}, Chapters info not found.")
        continue

    if not pargs.no_write:
        if pargs.gen_cue:
            cue = dirPath.joinpath(f"{baseName}.cue")
            with open(cue, "w") as f:
                f.write(f'\nPERFORMER "{artist}"')
                f.write(f'\nTITLE "{album}"')
                f.write(f'\nFILE "{m4aFile.name}" AAC')
        else:
            artistDir = makeTargetDirs(artist, dirPath)
            extractDir = makeTargetDirs(album, artistDir)
            printLogP(f"\nOutput directory name: {extractDir}")

    for i, chapter in enumerate(js["chapters"]):
        startTime = secondsToHMS(chapter["start_time"])
        endTime = secondsToHMS(chapter["end_time"])
        title = slugify(chapter["title"])
        track = i + 1
        fileName = f"{track}. {title}.m4a"
        printLogP("\n\n------------------------------")
        printLogP(f"\n\nProcessing {title} from {startTime} to {endTime}")
        if pargs.no_write:
            continue

        if pargs.gen_cue:
            with open(cue, "a") as f:
                f.write(f"\n  TRACK {str(track).zfill(2)} AUDIO")
                f.write(f'\n    TITLE "{title}"')
                f.write(f"\n    INDEX 01 {HMSToMS(startTime)}:00 ")
        else:
            printLogP(f"\nOutput file name: {fileName}")
            out = subprocess.check_output(
                [
                    "ffmpeg",
                    "-ss",
                    startTime,
                    "-to",
                    endTime,  # --ss -to needs to be prior to -i
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

    log.close()
    if pargs.wait:
        wait(pargs.wait)
    else:
        choice = getInput()
        if choice == "e":
            break
