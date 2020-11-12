"""
Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results.
"""
import argparse
import json
import logging
import math
import os
import sys
import time

import cv2 as cv
import PIL.Image
import PIL.ImageTk
import tkinter as tk

__NAME__ = os.path.splitext(os.path.split(__file__)[-1])[0]
LOGGER = logging.getLogger(__NAME__)
LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)-10.10s [%(threadName)s][%(name)s] %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


def setup_text_window():
    LOGGER.info("Setup text window to display results")
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: root.quit())
    scrollbar = tk.Scrollbar(root)
    textbox = tk.Text(root, height=4, width=50)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    textbox.pack(side=tk.LEFT, fill=tk.Y)
    scrollbar.config(command=textbox.yview)
    textbox.config(yscrollcommand=scrollbar.set)
    textbox.insert(tk.END, "<nodata>")
    return root


class VideoResultPlayerApp(object):
    """
    BUilds and runs the player by looping video frames and handling events.
    """
    # flags and control
    error = False
    # video information
    video = None
    video_width = None
    video_height = None
    video_frame = None
    duration = None
    fps = None
    frame = None
    frame_time = 0
    frame_last = 0
    frame_index = None
    frame_count = None
    frame_output = None
    # metadata references
    video_annot_meta = None
    video_infer_meta = None
    text_infer_meta = None
    # handles to UI elements
    window = None
    video_viewer = None
    video_annot_label = None
    video_annot_scroll = None
    video_annot_textbox = None
    snapshot_button = None
    play_button = None
    play_state = True
    play_label = None
    play_text = None

    def __init__(self, video_file, video_annotations, video_results, text_results, output=None):
        self.video_source = os.path.abspath(video_file)
        if not os.path.isfile(video_file):
            raise ValueError("Cannot find video file: [{}]".format(video_file))
        LOGGER.info("Using video file: %s", video_file)
        # use video name as best title minimally available, adjust after if possible with metadata
        self.video_title = os.path.splitext(os.path.split(video_file)[-1])[0]
        self.frame_output = output

        self.setup_player()
        self.setup_metadata(video_annotations, video_results, text_results)
        self.setup_window()

        self.run()

    def run(self):
        self.update()
        self.update_video()  # after called once, update method will call itself with delay to loop frames
        self.window.mainloop()  # blocking
        LOGGER.log(logging.INFO if self.error else logging.ERROR, "Exit")

    def __del__(self):
        if self.video and self.video.isOpened():
            self.video.release()

    def setup_player(self):
        LOGGER.info("Creating player...")
        self.video = cv.VideoCapture(self.video_source)
        self.frame_index = 0
        self.frame_time = 0.0
        self.fps = int(self.video.get(cv.CAP_PROP_FPS))
        self.frame_count = int(self.video.get(cv.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_delta * self.frame_count
        self.video_width = self.video.get(cv.CAP_PROP_FRAME_WIDTH)
        self.video_height = self.video.get(cv.CAP_PROP_FRAME_HEIGHT)

    def setup_window(self):
        self.window = tk.Tk()
        self.window.title("Result Viewer")
        # Create a canvas that can fit the above video source size
        self.video_viewer = tk.Canvas(self.window, width=self.video_width, height=self.video_height)
        self.video_viewer.pack()

        # Button that lets the user take a snapshot
        self.snapshot_button = tk.Button(self.window, text="Snapshot", width=50, command=self.snapshot)
        self.snapshot_button.pack(anchor=tk.E, expand=True)

        self.play_state = True
        self.play_text = tk.StringVar()
        self.play_text.set("PAUSE")
        self.play_button = tk.Button(self.window, textvariable=self.play_text, width=40, command=self.toggle_playing)
        self.play_button.pack(side=tk.RIGHT)

        self.video_annot_label = tk.Label(self.window, textvariable="Video Annotation Metadata\n")
        self.video_annot_label.pack(side=tk.LEFT)
        #self.video_annot_label.tag_configure("big", font=("Arial", 20, "bold"))
        self.video_annot_textbox = tk.Text(self.window, height=20, width=50)
        self.video_annot_scroll = tk.Scrollbar(self.window, command=self.video_annot_textbox.yview)
        self.video_annot_textbox.configure(yscrollcommand=self.video_annot_scroll.set)
        self.video_annot_textbox.tag_configure("big", font=("Arial", 20, "bold"))
        self.video_annot_textbox.tag_configure("code", font=("Courier", 12, "normal"))
        self.video_annot_textbox.tag_configure("normal", foreground='#476042', font=("Arial", 12, "bold"))
        #self.video_annot_textbox.tag_bind("follow", "<1>", lambda e, t=self.video_annot_textbox: t.insert(tk.END, "event"))
        #self.video_annot_textbox.insert(tk.END, "Video Annotation Metadata\n", "big")
        #self.video_annot_textbox.insert(tk.END, textvariable=self.video_annotation, "normal")
        self.video_annot_textbox.insert(tk.END, "<nodata>", "code")
        self.video_annot_textbox.pack(side=tk.LEFT)
        self.video_annot_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def toggle_playing(self):
        if self.play_state:
            self.play_text.set("PLAY")
            LOGGER.debug("Video paused.")
        else:
            self.play_text.set("PAUSE")
            LOGGER.debug("Video resume.")
        self.play_state = not self.play_state

    def update(self):
        self.window.after(10, self.update)

    def update_text(self, text):
        self.video_annot_textbox.delete("1.0", tk.END)
        self.video_annot_textbox.insert(tk.END, text, "normal")

    def update_video(self):
        """
        Periodic update of video frame. Self-calling.
        """

        if not self.play_state:
            self.window.after(30, self.update_video)
            return

        LOGGER.debug("Frame: %s, Real FPS: %s", self.frame_index, self.frame_time - self.frame_last)
        ret, frame = self.video.read()
        if not ret:
            LOGGER.error("Playback error occurred when reading next video frame.")
            self.error = True
            return

        self.frame_index = int(self.video.get(cv.CAP_PROP_POS_FRAMES))
        self.frame_last = self.frame_time
        self.frame_time = self.video.get(cv.CAP_PROP_POS_MSEC)

        # display basic information
        text_position = (10, 25)
        text_delta = 40
        font_scale = 0.5
        font_color = (209, 80, 0, 255)
        font_stroke = 1
        cv.putText(frame, "Title: {}, FPS: {}, Frame: {}".format(self.video_title, self.fps, self.frame_index),
                   text_position, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)
        text_position = (text_position[0], text_position[1] + int(text_delta * font_scale))
        cv.putText(frame, "Time: {:0>.2f}/{:0.2f}".format(self.frame_time / 1000., self.duration / 1000.),
                   text_position, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)

        # note: 'self.frame' is important as without instance reference, it gets garbage collected and is not displayed
        self.video_frame = frame  # in case of snapshot
        self.frame = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
        self.video_viewer.create_image(0, 0, image=self.frame, anchor=tk.NW)
        self.window.after(math.floor(self.frame_delta), self.update_video)

    def setup_metadata(self, video_annotations, video_results, text_results):
        # parse available metadata files
        if video_annotations and os.path.isfile(video_annotations):
            LOGGER.info("Parsing video inference metadata [%s]...", video_annotations)
            self.video_annot_meta = self.parse_video_annotation_metadata(video_annotations)
        if video_results and os.path.isfile(video_results):
            LOGGER.info("Parsing video inference metadata [%s]...", video_results)
            self.video_infer_meta = self.parse_video_inference_metadata(video_results)
        if text_results and os.path.isfile(text_results):
            LOGGER.info("Parsing text inference metadata [%s]...", text_results)
            self.text_infer_meta = self.parse_text_inference_metadata(text_results)

    def parse_video_annotation_metadata(self, metadata_path):
        try:
            with open(metadata_path) as meta_file:
                metadata = json.load(meta_file)
            meta = metadata.get("metadata_files", {})
            title = meta.get("serie_name") or meta.get("film_export_subpath")
            episode = meta.get("serie_episode_number", "")
            collection = meta.get("serie_collection_name") or meta.get("film_collection_name")

            LOGGER.debug("Updating video name")
            episode_str = " - {}".format(episode) if episode else ""
            self.video_title = "[{}] {}{}".format(collection, title, episode_str)

            return metadata
        except Exception as exc:
            LOGGER.error("Could not parse video annotation metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    def parse_video_inference_metadata(self, metadata_path):
        try:
            with open(metadata_path) as meta_file:
                metadata = json.load(meta_file)
            # ensure ordered by time
            metadata["predictions"] = list(sorted(metadata["predictions"], key=lambda p: p["start"]))

            # ease retrieval of active prediction against current video frame
            cumul_ms = 0.
            delta_ms = self.frame_delta
            total = delta_ms
            frame = 0
            for pred in metadata["predictions"]:
                if pred["start"] > delta_ms:
                    frame += 1
                pred["frame"] = frame
                cumul_ms += pred["end"]
            return metadata
        except Exception as exc:
            LOGGER.error("Could not parse video inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    def parse_text_inference_metadata(self, metadata_path):
        try:
            pass
        except Exception as exc:
            LOGGER.error("Could not parse text inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    @property
    def frame_delta(self):
        return 1. / float(self.fps) * 1000.

    def snapshot(self):
        """
        Save current frame of the video with corresponding metadata.
        """
        if self.video_frame is None:
            LOGGER.warning("No available frame snapshot to save.")
            return

        name_clean = self.video_title.replace(" ", "-")
        frame_name = "{}_{}_{:.2f}.jpg".format(name_clean, self.frame_index, self.frame_time)
        os.makedirs(self.frame_output, exist_ok=True)
        frame_path = os.path.join(self.frame_output, frame_name)
        cv.imwrite(frame_path, cv.cvtColor(self.video_frame, cv.COLOR_RGB2BGR))
        LOGGER.info("Saved frame snapshot: [%s]", frame_path)


def make_parser():
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True)
    ap.add_argument("video_file", help="Video file to view.")
    ap.add_argument("video_annotations", help="File with original video-description annotations.")
    ap.add_argument("video_results", help="File with video actions inference results.")
    ap.add_argument("text_results", help="File with text subjects and verbs results.")
    ap.add_argument("--output", "-o", help="Output location of frame snapshots.", default="/tmp/video-result-viewer")
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
    return VideoResultPlayerApp(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
