"""
Most basic video-frame loop to evaluate FPS.
"""
import argparse
import logging
import os
import sys
import time

import cv2 as cv

from stream import VideoCaptureThread

__NAME__ = os.path.splitext(os.path.split(__file__)[-1])[0]
LOGGER = logging.getLogger(__NAME__)
LOGGER.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)-10.10s [%(threadName)s][%(name)s] %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
_handler.setFormatter(_formatter)
LOGGER.addHandler(_handler)


def make_parser():
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True)
    ap.add_argument("video_file", help="Video file to view.")
    ap.add_argument("--quiet", "-q", action="store_true", help="Do not output anything else than error.")
    ap.add_argument("--debug", "-d", action="store_true", help="Enable extra debug logging.")
    return ap


def run(video_file):
    cv.namedWindow("window")
    video = VideoCaptureThread(video_file)
    video.start()
    last = time.perf_counter()
    while True:
        if cv.waitKey(1) & 0xFF == ord("q"):
            break
        grabbed, frame, _, _ = video.read()
        if not grabbed:
            continue
        cv.imshow("window", frame)
        LOGGER.debug("FPS: %6.2f", 1. / (time.perf_counter() - last))
        last = time.perf_counter()

    LOGGER.info("Exit")


def main():
    ap = make_parser()
    argv = None if sys.argv[1:] else ["--help"]  # auto-help message if no args
    ns = ap.parse_args(args=argv)
    if ns.debug:
        LOGGER.setLevel(logging.DEBUG)
    if ns.quiet:
        LOGGER.setLevel(logging.ERROR)
    args = vars(ns)
    args.pop("debug", None)
    args.pop("quiet", None)
    return run(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
