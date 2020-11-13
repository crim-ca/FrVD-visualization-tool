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
    frame_index = None
    frame_count = None
    frame_output = None
    last_time = 0
    # metadata references
    video_annot_meta = None
    video_annot_index = None
    video_infer_meta = None
    video_infer_index = None
    text_infer_meta = None
    text_infer_index = None
    # handles to UI elements
    window = None
    video_viewer = None
    video_annot_label = None
    video_annot_scroll = None
    video_annot_textbox = None
    video_infer_label = None
    video_infer_scroll = None
    video_infer_textbox = None
    text_infer_label = None
    text_infer_scroll = None
    text_infer_textbox = None
    snapshot_button = None
    play_button = None
    play_state = True
    play_label = None
    play_text = None
    font_header = ("Arial", 16, "bold")
    font_code = ("Courier", 12, "normal")
    font_normal = ("Arial", 12, "normal")

    def __init__(self, video_file, video_annotations, video_results, text_results, output=None):
        self.video_source = os.path.abspath(video_file)
        if not os.path.isfile(video_file):
            raise ValueError("Cannot find video file: [{}]".format(video_file))
        LOGGER.info("Using video file: %s", video_file)
        # use video name as best title minimally available, adjust after if possible with metadata
        self.video_title = os.path.splitext(os.path.split(video_file)[-1])[0]
        self.frame_output = output

        self.setup_player()
        self.setup_window()
        if not self.setup_metadata(video_annotations, video_results, text_results):
            return

        self.run()

    def run(self):
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
        self.video_viewer.pack(anchor=tk.NW)

        self.video_annot_label = tk.Label(self.window, text="Video Annotation Metadata", font=self.font_header)
        self.video_annot_label.pack(side=tk.LEFT)
        self.video_annot_textbox = tk.Text(self.window, height=20, width=50)
        self.video_annot_scroll = tk.Scrollbar(self.window, command=self.video_annot_textbox.yview)
        self.video_annot_textbox.configure(yscrollcommand=self.video_annot_scroll.set)
        self.video_annot_textbox.tag_configure("big", font=self.font_header)
        self.video_annot_textbox.tag_configure("code", font=self.font_code)
        self.video_annot_textbox.tag_configure("normal", foreground='#476042', font=self.font_normal)
        self.video_annot_textbox.insert(tk.END, "<nodata>", "code")
        self.video_annot_textbox.pack(side=tk.LEFT)
        self.video_annot_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.video_infer_label = tk.Label(self.window, text="Video Inference Metadata", font=self.font_header)
        self.video_infer_label.pack(side=tk.LEFT)
        self.video_infer_textbox = tk.Text(self.window, height=20, width=50)
        self.video_infer_scroll = tk.Scrollbar(self.window, command=self.video_infer_textbox.yview)
        self.video_infer_textbox.configure(yscrollcommand=self.video_infer_scroll.set)
        self.video_infer_textbox.tag_configure("big", font=self.font_header)
        self.video_infer_textbox.tag_configure("code", font=self.font_code)
        self.video_infer_textbox.tag_configure("normal", foreground='#476042', font=self.font_normal)
        self.video_infer_textbox.insert(tk.END, "<nodata>", "code")
        self.video_infer_textbox.pack(side=tk.LEFT)
        self.video_infer_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_infer_label = tk.Label(self.window, text="Text Inference Metadata", font=self.font_header)
        self.text_infer_label.pack(side=tk.LEFT)
        self.text_infer_textbox = tk.Text(self.window, height=20, width=50)
        self.text_infer_scroll = tk.Scrollbar(self.window, command=self.text_infer_textbox.yview)
        self.text_infer_textbox.configure(yscrollcommand=self.text_infer_scroll.set)
        self.text_infer_textbox.tag_configure("big", font=self.font_header)
        self.text_infer_textbox.tag_configure("code", font=self.font_code)
        self.text_infer_textbox.tag_configure("normal", foreground="#476042", font=self.font_normal)
        self.text_infer_textbox.insert(tk.END, "<nodata>", "code")
        self.text_infer_textbox.pack(side=tk.LEFT)
        self.text_infer_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.snapshot_button = tk.Button(self.window, text="Snapshot", width=50, command=self.snapshot)
        self.snapshot_button.pack(side=tk.LEFT)

        self.play_state = True
        self.play_text = tk.StringVar()
        self.play_text.set("PAUSE")
        self.play_button = tk.Button(self.window, textvariable=self.play_text, width=40, command=self.toggle_playing)
        self.play_button.pack(side=tk.LEFT)

    def toggle_playing(self):
        if self.play_state:
            self.play_text.set("PLAY")
            LOGGER.debug("Video paused.")
        else:
            self.play_text.set("PAUSE")
            LOGGER.debug("Video resume.")
        self.play_state = not self.play_state

    def update_annotation(self, metadata):
        text = metadata["vd"]
        self.video_annot_textbox.delete("1.0", tk.END)
        self.video_annot_textbox.insert(tk.END, text, "normal")

    def update_infer_video(self, metadata):
        header = "[Score] [Classes] (ordered)\n\n  "
        values = "\n  ".join(["[{:.2f}]  {})".format(s, c) for c, s in zip(metadata["classes"], metadata["scores"])])
        text = header + values
        self.video_infer_textbox.delete("1.0", tk.END)
        self.video_infer_textbox.insert(tk.END, text, "normal")

    def update_infer_text(self, metadata):
        text = json.dumps(metadata, indent=2, ensure_ascii=False)
        self.text_infer_textbox.delete("1.0", tk.END)
        self.text_infer_textbox.insert(tk.END, text, "normal")

    def update_metadata(self):
        if self.video_annot_meta:
            current_meta = self.video_annot_meta[self.video_annot_index]
            if self.frame_time > current_meta["end_ms"]:
                if self.video_annot_index < len(self.video_annot_meta) - 1:
                    self.video_annot_index += 1
                    self.update_annotation(self.video_annot_meta[self.video_annot_index])
                else:
                    self.update_annotation(None)
        if self.video_infer_meta:
            current_meta = self.video_infer_meta[self.video_infer_index]
            if self.frame_time > current_meta["end_ms"]:
                if self.video_infer_index < len(self.video_infer_meta) - 1:
                    self.video_infer_index += 1
                    self.update_infer_video(self.video_infer_meta[self.video_infer_index])
                else:
                    self.update_infer_video(None)
        if self.text_infer_meta:
            current_meta = self.text_infer_meta[self.text_infer_index]
            if self.frame_time > current_meta["end_ms"]:
                if self.text_infer_index < len(self.text_infer_meta) - 1:
                    self.text_infer_index += 1
                    self.update_infer_text(self.text_infer_meta[self.text_infer_index])
                else:
                    self.update_infer_text(None)

    def update_video(self):
        """
        Periodic update of video frame. Self-calling.
        """

        if not self.play_state:
            self.window.after(30, self.update_video)
            return

        LOGGER.debug("Frame: %s, Real FPS: %s", self.frame_index, self.frame_time - self.last_time)
        ret, frame = self.video.read()
        if not ret:
            LOGGER.error("Playback error occurred when reading next video frame.")
            self.error = True
            return

        self.frame_index = int(self.video.get(cv.CAP_PROP_POS_FRAMES))
        self.last_time = self.frame_time
        self.frame_time = self.video.get(cv.CAP_PROP_POS_MSEC)
        self.update_metadata()

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
        """
        Parse available metadata files and prepare the first entry according to provided file references.
        """
        try:
            if video_annotations and os.path.isfile(video_annotations):
                LOGGER.info("Parsing video description metadata [%s]...", video_annotations)
                self.video_annot_meta = self.parse_video_annotation_metadata(video_annotations)
                self.video_annot_index = 0
            if video_results and os.path.isfile(video_results):
                LOGGER.info("Parsing video inference metadata [%s]...", video_results)
                self.video_infer_meta = self.parse_video_inference_metadata(video_results)
                self.video_infer_index = 0
            if text_results and os.path.isfile(text_results):
                LOGGER.info("Parsing text inference metadata [%s]...", text_results)
                self.text_infer_meta = self.parse_text_inference_metadata(text_results)
                self.text_infer_index = 0
        except Exception as exc:
            self.error = True
            LOGGER.error("Invalid formats. One or more metadata file could not be parsed.", exc_info=exc)
            return False
        return True

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

            meta_vd = metadata.get("augmented_vd_metadata")
            if meta_vd:
                LOGGER.info("Retrieved augmented video-description metadata.")
            else:
                meta_vd = metadata.get("standard_vd_metadata")
                if meta_vd:
                    LOGGER.info("Retrieved standard video-description metadata (augmented not provided).")
            if meta_vd:
                # ensure sorted entries
                return list(sorted(meta_vd, key=lambda vd: vd["start_ms"]))
        except Exception as exc:
            LOGGER.error("Could not parse video annotation metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    @staticmethod
    def parse_video_inference_metadata(metadata_path):
        try:
            with open(metadata_path) as meta_file:
                metadata = json.load(meta_file)
            # ensure ordered by time
            predictions = list(sorted(metadata["predictions"], key=lambda p: p["start"]))
            # convert times to ms for same base comparisons
            for pred in predictions:
                pred["start_ms"] = pred["start"] * 1000
                pred["end_ms"] = pred["end"] * 1000
            return predictions
        except Exception as exc:
            LOGGER.error("Could not parse video inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    @staticmethod
    def parse_text_inference_metadata(metadata_path):
        try:
            pass
            # TODO: convert TS: [start,end] -> start_ms, end_ms
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
    ap.add_argument("video_annotations", help="JSON metadata file with original video-description annotations.")
    ap.add_argument("video_results", help="JSON metadata file with video actions inference results.")
    ap.add_argument("text_results", help="JSON metadata file with text subjects and verbs results.")
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
