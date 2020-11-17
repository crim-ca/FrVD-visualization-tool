"""
Test video-frame loop processing time required for display with :mod:`tkinter` UI.
"""
import argparse
import logging
import os
import sys
import time

import cv2 as cv
import tkinter as tk
from PIL import Image, ImageTk

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


class BasicVideoApp(object):
    def __init__(self, video_file):
        self.video = VideoCaptureThread(video_file)
        self.video.start()
        self.root = tk.Tk()
        self.frame = None
        self.image = None
        self.panel = None
        self.loop()

    def loop(self):
        last = time.perf_counter()
        cumul0 = cumul1 = cumul2 = cumul3 = counter = 0
        while True:
            grabbed, self.frame, _, _ = self.video.read()
            if not grabbed:
                continue
            t0 = time.perf_counter()
            self.image = cv.cvtColor(self.frame, cv.COLOR_BGR2RGB)
            t1 = time.perf_counter()
            self.image = Image.fromarray(self.image)
            t2 = time.perf_counter()
            self.image = ImageTk.PhotoImage(self.image)
            t3 = time.perf_counter()

            # if the panel is not None, we need to initialize it
            if self.panel is None:
                self.panel = tk.Label(image=self.image)
                self.panel.image = self.image
                self.panel.pack(side="left", padx=10, pady=10)

            # otherwise, simply update the panel
            else:
                self.panel.configure(image=self.image)
                self.panel.image = self.image
            t4 = time.perf_counter()
            delta0 = 1000. * (t1 - t0)
            cumul0 += delta0
            delta1 = 1000. * (t2 - t1)
            cumul1 += delta1
            delta2 = 1000. * (t3 - t2)
            cumul2 += delta2
            delta3 = 1000. * (t4 - t3)
            cumul3 += delta3
            counter += 1
            LOGGER.debug("FPS: %6.2f | %6.2fms (%6.2fms), %6.2fms (%6.2fms), %6.2fms (%6.2fms), %6.2fms (%6.2fms)",
                         1. / (time.perf_counter() - last),
                         delta0, cumul1 / counter, delta0, cumul1 / counter,
                         delta2, cumul2 / counter, delta3, cumul3 / counter)
            last = time.perf_counter()


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
    return BasicVideoApp(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
