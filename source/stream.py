import logging
import os
import queue
import time
import threading

import cv2 as cv

__NAME__ = os.path.splitext(os.path.split(__file__)[-1])[0]
LOGGER = logging.getLogger(__NAME__)
LOGGER.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)-10.10s [%(threadName)s][%(name)s] %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
_handler.setFormatter(_formatter)
LOGGER.addHandler(_handler)


class VideoCaptureThread(object):
    def __init__(self, source=0, width=None, height=None, queue_size=10):
        self.source = source
        self.video = cv.VideoCapture(self.source)
        if width:
            self.video.set(cv.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.video.set(cv.CAP_PROP_FRAME_HEIGHT, height)
        self.started = False
        self.thread = None
        self.queue = queue.Queue(maxsize=queue_size)
        self.read_lock = threading.Lock()

    def get(self, setting):
        return self.video.get(setting)

    def set(self, setting, value):
        self.video.set(setting, value)

    def start(self):
        if self.started:
            LOGGER.warning("Threaded video capturing has already been started.")
            return None
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.start()
        return self

    def update(self):
        last = time.perf_counter()
        while self.started:
            if not self.queue.full():
                grabbed, frame = self.video.read()
                if not grabbed:
                    return
                with self.read_lock:
                    index = int(self.get(cv.CAP_PROP_POS_FRAMES))
                    msec = self.get(cv.CAP_PROP_POS_MSEC)
                    self.queue.put((grabbed, frame.copy(), index, msec))
                    current = time.perf_counter()
                    delta = current - last
                    LOGGER.debug("Grab frame: %8s, Last: %8.2f, Time: %8.2f, Real Delta: %6.2fms, Real FPS: %6.2f",
                                 index, last, current, delta * 1000., 1. / delta)
                    last = current

    def seek(self, frame_index):
        self.stop()
        # max value -2 to avoid immediate freeze on next fetch
        frame_index = min(frame_index, self.get(cv.CAP_PROP_FRAME_COUNT) - 2)
        self.set(cv.CAP_PROP_POS_FRAMES, frame_index)
        ms = self.get(cv.CAP_PROP_POS_MSEC)
        with self.read_lock:
            with self.queue.mutex:
                self.queue.queue.clear()
        self.start()
        return ms

    def read(self):
        grabbed, frame, index, msec = self.queue.get()
        return grabbed, frame, index, msec

    def stop(self):
        self.started = False
        self.thread.join()

    def __exit__(self, exec_type, exc_value, traceback):
        self.video.release()
