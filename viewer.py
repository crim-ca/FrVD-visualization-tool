"""
Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results.
"""
import argparse
import cv2
import logging
import numpy as np
import os
import sys

__NAME__ = os.path.splitext(os.path.split(__file__)[-1])[0]
LOGGER = logging.getLogger(__NAME__)
LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)-10.10s [%(threadName)s][%(name)s] %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


def run(video_file, video_annotations, video_results, text_results):
    video_file = os.path.abspath(video_file)
    if not os.path.isfile(video_file):
        raise ValueError("Cannot find video file: [{}]".format(video_file))
    LOGGER.info("Using video file: %s", video_file)

    cap = cv2.VideoCapture(video_file)
    while True:
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        cv2.imshow("frame", gray)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def make_parser():
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True)
    ap.add_argument("video_file", help="Video file to view.")
    ap.add_argument("video_annotations", help="File with original video-description annotations.")
    ap.add_argument("video_results", help="File with video actions inference results.")
    ap.add_argument("text_results", help="File with text subjects and verbs results.")
    ap.add_argument("--debug", "-d", action="store_true", help="Debug logging.")
    return ap


def main():
    ap = make_parser()
    argv = None if sys.argv[1:] else ["--help"]  # auto-help message if no args
    ns = ap.parse_args(args=argv)
    if ns.debug:
        LOGGER.setLevel(logging.DEBUG)
    args = vars(ns)
    args.pop("debug", None)
    return run(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
