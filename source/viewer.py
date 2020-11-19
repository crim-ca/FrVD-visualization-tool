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
from datetime import datetime

import cv2 as cv
import PIL.Image
import PIL.ImageTk
import tkinter as tk

from stream import VideoCaptureThread

__NAME__ = os.path.splitext(os.path.split(__file__)[-1])[0]
LOGGER = logging.getLogger(__NAME__)
LOGGER.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)-10.10s [%(threadName)s][%(name)s] %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
_handler.setFormatter(_formatter)
LOGGER.addHandler(_handler)


class VideoResultPlayerApp(object):
    """
    Builds and runs the player by looping video frames and handling events.
    """
    # flags and control
    error = False
    # video information
    video = None
    video_scale = 1.0
    video_width = None
    video_height = None
    video_frame = None
    video_duration = None
    frame = None
    frame_fps = 0
    frame_time = 0
    frame_queue = 10
    frame_delta = None
    frame_index = None
    frame_count = None
    frame_output = None
    frame_drop_factor = 4
    frame_skip_factor = 1
    last_time = 0
    next_time = 0
    call_cumul_count = 0
    call_cumul_value = 0
    # metadata references
    video_desc_meta = None
    video_desc_index = None
    video_infer_meta = None
    video_infer_index = None
    text_annot_meta = None
    text_annot_index = None
    # handles to UI elements
    window = None
    video_viewer = None
    video_slider = None
    video_desc_label = None
    video_desc_scroll = None
    video_desc_textbox = None
    video_infer_label = None
    video_infer_scroll = None
    video_infer_textbox = None
    text_annot_label = None
    text_annot_scroll = None
    text_annot_textbox = None
    snapshot_button = None
    play_button = None
    play_state = True
    play_label = None
    play_text = None
    font_header = ("Helvetica", 16, "bold")
    font_code = ("Courier", 12, "normal")
    font_normal = ("Times", 12, "normal")
    font_code_tag = "code"
    font_normal_tag = "normal"
    NO_DATA = "<no-data>"

    def __init__(self, video_file, video_description, video_results, text_annotations,
                 output=None, scale=1.0, queue_size=10, frame_drop_factor=4, frame_skip_factor=1):
        self.video_source = os.path.abspath(video_file)
        if not os.path.isfile(video_file):
            raise ValueError("Cannot find video file: [{}]".format(video_file))
        LOGGER.info("Using video file: [%s]", video_file)
        # use video name as best title minimally available, adjust after if possible with metadata
        self.video_title = os.path.splitext(os.path.split(video_file)[-1])[0]
        self.frame_output = output
        self.video_scale = scale
        if scale <= 0:
            raise ValueError("Invalid scaling must be greater than 0.")
        if queue_size > 1:
            LOGGER.debug("Setting queue size: %s", queue_size)
            self.frame_queue = queue_size
        if frame_drop_factor > 1:
            LOGGER.debug("Setting frame drop factor: %s", frame_drop_factor)
            self.frame_drop_factor = frame_drop_factor
        if frame_skip_factor > 1:
            LOGGER.debug("Setting frame skip factor: %s", frame_skip_factor)
            self.frame_skip_factor = frame_skip_factor

        self.setup_player()
        self.setup_window()
        if not self.setup_metadata(video_description, video_results, text_annotations):
            return

        self.run()

    def run(self):
        self.update_video()  # after called once, update method will call itself with delay to loop frames
        self.window.mainloop()  # blocking
        LOGGER.log(logging.INFO if self.error else logging.ERROR, "Exit")

    def setup_player(self):
        LOGGER.info("Creating player...")
        self.video = VideoCaptureThread(self.video_source, queue_size=self.frame_queue).start()
        self.frame_index = 0
        self.frame_time = 0.0
        self.frame_fps = int(self.video.get(cv.CAP_PROP_FPS))
        self.frame_delta = 1. / float(self.frame_fps) * 1000.
        self.frame_count = int(self.video.get(cv.CAP_PROP_FRAME_COUNT))
        self.video_duration = self.frame_delta * self.frame_count
        self.video_width = int(self.video.get(cv.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.video.get(cv.CAP_PROP_FRAME_HEIGHT))
        expected_width = int(self.video_width * self.video_scale)
        if expected_width < 480:
            new_scale = 480. / float(self.video_width)
            LOGGER.warning("Readjusting video scale [%.3f] to [%.3f] to ensure minimal width [480px].",
                           self.video_scale, new_scale)
            self.video_scale = new_scale

    def setup_window(self):
        LOGGER.info("Creating window...")
        display_width = int(self.video_width * self.video_scale)
        display_height = int(self.video_height * self.video_scale)

        self.window = tk.Tk()
        self.window.title("Video Result Viewer: {}".format(self.video_title))
        self.window.attributes("-fullscreen", False)
        self.window.bind("<F11>",
                         lambda _: self.window.attributes("-fullscreen", not self.window.attributes("-fullscreen")))
        self.window.bind("<Escape>", lambda _: self.window.attributes("-fullscreen", False))
        self.window.bind("<space>", lambda _: self.toggle_playing())

        padding = 5
        split_main_left_right = (4, 2)      # number of columns for left/right distribution
        split_left_top_bottom = (4, 1)      # number of rows for left-size distribution of top/bottom
        split_right_top_bottom = (1, 4)     # number of rows for right-size distribution of top/bottom
        panel_video_viewer = tk.Frame(self.window, padx=padding, pady=padding)
        panel_video_viewer.grid(row=0, column=0,
                                rowspan=split_main_left_right[0], columnspan=split_left_top_bottom[0], sticky=tk.NSEW)
        panel_video_infer = tk.Frame(self.window, padx=padding, pady=padding)
        panel_video_infer.grid(row=0, column=split_main_left_right[0] + 1,
                               rowspan=split_right_top_bottom[0], columnspan=split_main_left_right[1], sticky=tk.NSEW)
        panel_video_desc = tk.Frame(self.window, padx=padding, pady=padding)
        panel_video_desc.grid(row=split_left_top_bottom[0] + 1, column=0,
                              rowspan=split_left_top_bottom[1], columnspan=split_main_left_right[0], sticky=tk.NSEW)
        panel_text_annot = tk.Frame(self.window, padx=padding, pady=padding)
        panel_text_annot.grid(row=split_right_top_bottom[0] + 1, column=split_main_left_right[0] + 1,
                              rowspan=split_right_top_bottom[1], columnspan=split_main_left_right[1], sticky=tk.NSEW)
        self.window.grid_columnconfigure(0, weight=0)
        self.window.grid_columnconfigure(split_main_left_right[0] + 1, weight=1)
        self.window.grid_rowconfigure(0, weight=0)
        self.window.grid_rowconfigure(split_left_top_bottom[0] + 1, weight=1)
        self.window.grid_rowconfigure(split_right_top_bottom[0] + 1, weight=1)

        # Create a canvas that can fit the above video source size
        self.video_viewer = tk.Canvas(panel_video_viewer, width=display_width, height=display_height)
        self.video_viewer.pack(anchor=tk.NW, fill=tk.BOTH, expand=True)
        # adjust number of labels displayed on slider with somewhat dynamic amount based on video display scaling
        slider_interval = self.frame_count // int(10 * self.video_scale)
        slider_elements = self.frame_count // slider_interval
        slider_interval = self.frame_count // (slider_elements if slider_elements % 2 else slider_elements + 1)
        self.video_slider = tk.Scale(panel_video_viewer, from_=0, to=self.frame_count - 1, length=display_width,
                                     tickinterval=slider_interval, orient=tk.HORIZONTAL,
                                     repeatinterval=1, repeatdelay=1, command=self.seek_frame)
        self.video_slider.bind("<Button-1>", self.trigger_seek)
        self.video_slider.pack(side=tk.TOP, anchor=tk.NW, expand=True)

        self.play_state = True
        self.play_text = tk.StringVar()
        self.play_text.set("PAUSE")
        self.play_button = tk.Button(panel_video_viewer, width=20, padx=padding, pady=padding,
                                     textvariable=self.play_text, command=self.toggle_playing)
        self.play_button.pack(side=tk.LEFT, anchor=tk.NW)

        self.snapshot_button = tk.Button(panel_video_viewer, text="Snapshot",
                                         width=20,  padx=padding, pady=padding, command=self.snapshot)
        self.snapshot_button.pack(side=tk.LEFT, anchor=tk.NW)

        self.video_desc_label = tk.Label(panel_video_desc, text="Video Description Metadata", font=self.font_header)
        self.video_desc_label.pack(side=tk.TOP)
        self.video_desc_textbox = tk.Text(panel_video_desc, height=10, wrap=tk.WORD)
        self.video_desc_scroll = tk.Scrollbar(panel_video_desc, command=self.video_desc_textbox.yview)
        self.video_desc_textbox.configure(yscrollcommand=self.video_desc_scroll.set)
        self.video_desc_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.video_desc_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.video_desc_textbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_desc_scroll.pack(side=tk.RIGHT, fill=tk.Y, expand=True)
        self.update_video_desc(None)

        self.video_infer_label = tk.Label(panel_video_infer, text="Video Inference Metadata", font=self.font_header)
        self.video_infer_label.pack(side=tk.TOP)
        self.video_infer_textbox = tk.Text(panel_video_infer)
        self.video_infer_scroll = tk.Scrollbar(panel_video_infer, command=self.video_infer_textbox.yview)
        self.video_infer_textbox.configure(yscrollcommand=self.video_infer_scroll.set)
        self.video_infer_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.video_infer_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.video_infer_textbox.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.SE)
        self.video_infer_scroll.pack(side=tk.RIGHT, fill=tk.Y, expand=True)
        self.update_video_infer(None)

        self.text_annot_label = tk.Label(panel_text_annot, text="Text Annotation Metadata", font=self.font_header)
        self.text_annot_label.pack(side=tk.TOP, fill=tk.X)
        self.text_annot_textbox = tk.Text(panel_text_annot)
        self.text_annot_scroll = tk.Scrollbar(panel_text_annot, command=self.text_annot_textbox.yview)
        self.text_annot_textbox.configure(yscrollcommand=self.text_annot_scroll.set)
        self.text_annot_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.text_annot_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.text_annot_textbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_annot_scroll.pack(side=tk.RIGHT, fill=tk.Y, expand=True)
        self.update_text_annot(None)

    def trigger_seek(self, event):
        coord_min = self.video_slider.coords(0)
        coord_max = self.video_slider.coords(self.frame_count)
        if self.video_slider.identify(event.x, event.y) == "slider":
            return  # ignore event when clicking directly on the slider

        # wait for seek to complete to resume frame display
        # (avoids random flickers of the displayed metadata)
        self.play_state = False

        # find and apply seek location from mouse click
        if event.x <= coord_min[0]:
            index = 0
        elif event.x >= coord_max[0]:
            index = self.frame_count - 1
        else:
            ratio = float(self.frame_count) / float(coord_max[0] - coord_min[0])
            index = int((event.x - coord_min[0]) * ratio)
            while index % self.frame_skip_factor:
                index += 1

        LOGGER.debug("Seek frame %8s from click event (%s, %s) between [%s, %s]",
                     index, event.x, event.y, coord_min, coord_max)
        self.seek_frame(index)
        self.update_metadata(seek=True)  # enforce fresh update since everything changed drastically
        self.play_state = True   # resume

    def toggle_playing(self):
        if self.play_state:
            self.play_text.set("PLAY")
            LOGGER.debug("Video paused.")
        else:
            self.play_text.set("PAUSE")
            LOGGER.debug("Video resume.")
        self.play_state = not self.play_state

    def update_video_desc(self, metadata):
        self.video_desc_textbox.delete("1.0", tk.END)
        if metadata is None:
            text = self.NO_DATA
            self.video_desc_textbox.insert(tk.END, "", self.font_normal_tag)
            self.video_desc_textbox.insert(tk.END, text, self.font_code_tag)
        else:
            entry = "(index: {}, start: {}, end: {})".format(self.video_desc_index, metadata["start"], metadata["end"])
            text = "{}\n\n{}".format(entry, metadata["vd"])
            self.video_desc_textbox.insert(tk.END, text, self.font_normal_tag)
            self.video_desc_textbox.insert(tk.END, "", self.font_code_tag)

    def update_video_infer(self, metadata):
        self.video_infer_textbox.delete("1.0", tk.END)
        if metadata is None:
            text = self.NO_DATA
            self.video_infer_textbox.insert(tk.END, "", self.font_normal_tag)
            self.video_infer_textbox.insert(tk.END, text, self.font_code_tag)
        else:
            entry = "(index: {}, start: {}, end: {})".format(self.video_infer_index, metadata["start"], metadata["end"])
            header = "{}\n\n[Score] [Classes]\n\n".format(entry)
            values = "\n".join(["[{:.2f}] {}".format(s, c) for c, s in zip(metadata["classes"], metadata["scores"])])
            text = header + values
            self.video_infer_textbox.insert(tk.END, "", self.font_normal_tag)
            self.video_infer_textbox.insert(tk.END, text, self.font_code_tag)

    def update_text_annot(self, metadata):
        self.text_annot_textbox.delete("1.0", tk.END)
        if metadata is None:
            text = self.NO_DATA
            self.text_annot_textbox.insert(tk.END, "", self.font_normal_tag)
            self.text_annot_textbox.insert(tk.END, text, self.font_code_tag)
        else:
            annotations = metadata["annotations"]
            fmt = "      {:<16s} | {:<24s} | {:<16s}"
            fields = "POS", "type", "lemme"
            header = fmt.format(*fields)
            entry = "(index: {}, start: {}, end: {})".format(self.text_annot_index, metadata["start"], metadata["end"])
            text = "{}\n\n{}\n{}\n".format(entry, header, "_" * len(header))
            for i, annot in enumerate(annotations):
                text += "\n[{}]:\n".format(i)
                text += "\n".join([fmt.format(*[item[f] for f in fields]) for item in annot])
            self.text_annot_textbox.insert(tk.END, "", self.font_normal_tag)
            self.text_annot_textbox.insert(tk.END, text, self.font_code_tag)

    def update_metadata(self, seek=False):
        def update_meta(meta_container, meta_index, meta_updater):
            """
            Updates the view element with the next metadata if the time for it to change was reached.
            If seek was requested, searches from the start to find the applicable metadata.

            :param meta_container: all possible metadata entries, assumed ascending pre-ordered by 'start_ms' key.
            :param meta_index: active metadata index
            :param meta_updater: method that updates the view element for the found metadata entry
            :return: index of updated metadata or already active one if time is still applicable for current metadata
            """
            # update only if metadata container entries are available
            if meta_container:
                current_index = 0 if seek else meta_index
                updated_index = current_index  # if nothing needs to change (current on is still valid for timestamp)
                current_meta = meta_container[current_index]
                index_total = len(meta_container)
                if seek:
                    # search the earliest index that provides metadata within the new time
                    for index in range(index_total):
                        meta = meta_container[index]
                        if meta["start_ms"] >= self.frame_time:
                            updated_index = index
                            break
                elif self.frame_time > current_meta["end_ms"]:
                    # otherwise bump to next one if timestamp of the current is passed
                    updated_index = current_index + 1

                # apply change of metadata
                if meta_index < index_total - 1 and current_index != updated_index or updated_index == 0:
                    meta_updater(meta_container[updated_index])
                return updated_index
            return None

        self.video_desc_index = update_meta(self.video_desc_meta, self.video_desc_index, self.update_video_desc)
        self.video_infer_index = update_meta(self.video_infer_meta, self.video_infer_index, self.update_video_infer)
        self.text_annot_index = update_meta(self.text_annot_meta, self.text_annot_index, self.update_text_annot)

    def update_video(self):
        """
        Periodic update of video frame. Self-calling.
        """
        self.next_time = time.perf_counter()

        # in case of pause button or normal end of video reached, just loop for next event to resume reading video
        if not self.play_state or self.frame_index >= self.frame_count:
            self.window.after(30, self.update_video)
            return

        grabbed, frame, self.frame_index, self.frame_time = self.video.read()
        if not grabbed:
            LOGGER.error("Playback error occurred when reading next video frame.")
            self.error = True
            return

        self.next_time = time.perf_counter()
        call_time_delta = self.next_time - self.last_time
        self.last_time = self.next_time
        # default if cannot be inferred from previous time
        wait_time_delta = 1 if call_time_delta > self.frame_delta else max(self.frame_delta - call_time_delta, 1)
        # if delays become too big, drop frames to catch up, ignore first that is always big because no previous one
        call_msec_delta = call_time_delta * 1000.
        call_fps = 1. / call_time_delta

        if self.frame_index not in [0, self.frame_count] and self.frame_index % self.frame_skip_factor:
            LOGGER.debug("Skip Frame: %8s", self.frame_index)
            self.window.after(1, self.update_video)
            return

        if call_msec_delta > self.frame_delta * self.frame_drop_factor and self.frame_index > 1:
            LOGGER.warning("Drop Frame: %8s, Last: %8.2f, Time: %8.2f, Real Delta: %6.2fms, "
                           "Target Delta: %6.2fms, Call Delta: %6.2fms, Real FPS: %6.2f",
                           self.frame_index, self.last_time, self.frame_time, wait_time_delta,
                           self.frame_delta, call_msec_delta, call_fps)
            self.window.after(1, self.update_video)
            return

        self.call_cumul_value += call_time_delta
        self.call_cumul_count += 1
        call_avg_fps = self.call_cumul_count / self.call_cumul_value

        frame_dims = (self.video_width, self.video_height)
        if self.video_scale != 1:
            frame_dims = (int(self.video_width * self.video_scale), int(self.video_height * self.video_scale))
            frame = cv.resize(frame, frame_dims, interpolation=cv.INTER_NEAREST)

        LOGGER.debug("Show Frame: %8s, Last: %8.2f, Time: %8.2f, Real Delta: %6.2fms, "
                     "Target Delta: %6.2fms, Call Delta: %6.2fms, Real FPS: %6.2f (%.2f) WxH: %s",
                     self.frame_index, self.last_time, self.frame_time, wait_time_delta,
                     self.frame_delta, call_msec_delta, call_fps, call_avg_fps, frame_dims)

        # display basic information
        text_offset = (10, 25)
        text_delta = 40
        font_scale = 0.5
        font_color = (209, 80, 0, 255)
        font_stroke = 1
        text0 = "Title: {}".format(self.video_title)
        text1 = "Original FPS: {}, Process FPS: {:0.2f} ({:0.2f})".format(self.frame_fps, call_fps, call_avg_fps)
        cur_sec = self.frame_time / 1000.
        tot_sec = self.video_duration / 1000.
        cur_hms = time.strftime("%H:%M:%S", time.gmtime(cur_sec))
        tot_hms = time.strftime("%H:%M:%S", time.gmtime(tot_sec))
        text2 = "Time: {:0>.2f}/{:0.2f} ({}/{}) Frame: {}".format(cur_sec, tot_sec, cur_hms, tot_hms, self.frame_index)
        for text_row, text in [(0, text0), (-2, text1), (-1, text2)]:
            y_offset = int(text_delta * font_scale) * text_row
            if text_row < 0:
                y_offset = self.video_height + (y_offset - text_offset[1])
            text_pos = (text_offset[0], text_offset[1] + y_offset)
            cv.putText(frame, text, text_pos, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)

        # note: 'self.frame' is important as without instance reference, it gets garbage collected and is not displayed
        self.video_frame = frame  # in case of snapshot
        self.frame = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(cv.cvtColor(frame, cv.COLOR_RGB2BGR)))
        self.video_viewer.create_image(0, 0, image=self.frame, anchor=tk.NW)
        self.video_slider.set(self.frame_index)
        self.update_metadata()

        wait_time_delta = 1  # WARNING: just go as fast as possible... tkinter image convert is the limiting factor
        self.window.after(math.floor(wait_time_delta), self.update_video)
        self.video_viewer.update_idletasks()

    def seek_frame(self, frame_index):
        """
        Moves the video to the given frame index (if not the next one).
        Finally, updates the visual feedback of video progress with the slider.
        """
        frame_index = int(frame_index)

        # only execute an actual video frame seek() when it doesn't correspond to the next index, since it is already
        # fetched by the main loop using read()
        # without this, we would otherwise flush the frame queue and reset everything on each frame
        if frame_index not in [self.frame_index, self.frame_index - 1]:
            LOGGER.debug("Seek frame: %8s (fetching)", frame_index)
            self.frame_time = self.video.seek(frame_index)

        # update slider position
        self.frame_index = frame_index
        self.video_slider.set(frame_index)

    def setup_metadata(self, video_description, video_results, text_annotations):
        """
        Parse available metadata files and prepare the first entry according to provided file references.
        """
        try:
            if video_description and os.path.isfile(video_description):
                LOGGER.info("Parsing video description metadata [%s]...", video_description)
                self.video_desc_meta = self.parse_video_annotation_metadata(video_description)
                self.video_desc_index = 0
            if video_results and os.path.isfile(video_results):
                LOGGER.info("Parsing video inference metadata [%s]...", video_results)
                self.video_infer_meta = self.parse_video_inference_metadata(video_results)
                self.video_infer_index = 0
            if text_annotations and os.path.isfile(text_annotations):
                LOGGER.info("Parsing text inference metadata [%s]...", text_annotations)
                self.text_annot_meta = self.parse_text_annotations_metadata(text_annotations)
                self.text_annot_index = 0
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
            episode_str = " - Episode {}".format(episode) if episode else ""
            self.video_title = "[{}] {}{}".format(collection, title, episode_str)

            meta_vd = metadata.get("augmented_vd_metadata")
            if meta_vd:
                LOGGER.info("Retrieved augmented video-description metadata.")
            else:
                meta_vd = metadata.get("standard_vd_metadata")
                if meta_vd:
                    LOGGER.info("Retrieved standard video-description metadata (augmented not provided).")
            if meta_vd:
                # backup original timestamps and update with second times
                for meta in meta_vd:
                    meta["start_ts"] = meta["start"]
                    meta["start"] = meta["start_ms"] / 1000.
                    meta["end_ts"] = meta["end"]
                    meta["end"] = meta["end_ms"] / 1000.
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
    def parse_text_annotations_metadata(metadata_path):
        try:
            with open(metadata_path) as meta_file:
                metadata = json.load(meta_file)
            annotations = metadata["data"]
            for annot in annotations:
                # convert TS: [start,end] -> start_ms, end_ms
                ts_s = datetime.strptime(annot["TS"][0], "T%H:%M:%S.%f")
                ts_e = datetime.strptime(annot["TS"][1], "T%H:%M:%S.%f")
                sec_s = float("{}.{}".format((ts_s.hour * 3600 + ts_s.minute * 60 + ts_s.second), ts_s.microsecond))
                sec_e = float("{}.{}".format((ts_e.hour * 3600 + ts_e.minute * 60 + ts_e.second), ts_e.microsecond))
                annot["start_ms"] = sec_s * 1000.
                annot["end_ms"] = sec_e * 1000.
                annot["start"] = sec_s
                annot["end"] = sec_e
            return list(sorted(annotations, key=lambda a: a["start_ms"]))
        except Exception as exc:
            LOGGER.error("Could not parse text inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

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
        cv.imwrite(frame_path, self.video_frame)
        LOGGER.info("Saved frame snapshot: [%s]", frame_path)


def make_parser():
    formatter = lambda prog: argparse.HelpFormatter(prog, width=120)  # noqa
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True, formatter_class=formatter)  # noqa
    main_args = ap.add_argument_group(title="Main Arguments",
                                      description="Main arguments")
    main_args.add_argument("video_file", help="Video file to view.")
    main_args.add_argument("--video-description", "--vd", dest="video_description",
                           help="JSON metadata file with original video-description annotations.")
    main_args.add_argument("--video-inference", "--vi", nargs="*", dest="video_results",
                           help="JSON metadata file(s) with video action recognition inference results. "
                                "If multiple files are provided, they will be simultaneously displayed side-by-side.")
    main_args.add_argument("--text-annotation", "--ta", dest="text_annotations",
                           help="JSON metadata file with text subjects and verbs annotations.")
    util_opts = ap.add_argument_group(title="Utility Options",
                                      description="Options that configure extra functionalities.")
    util_opts.add_argument("--output", "-o", default="/tmp/video-result-viewer",
                           help="Output location of frame snapshots (default: [%(default)s]).")
    video_opts = ap.add_argument_group(title="Video Options",
                                       description="Options that configure video processing.")
    video_opts.add_argument("--scale", "-s", type=float, default=VideoResultPlayerApp.video_scale,
                            help="Scale video for bigger/smaller display "
                                 "(warning: impacts FPS) (default: %(default)s).")
    video_opts.add_argument("--queue", "-Q", type=int, default=VideoResultPlayerApp.frame_queue, dest="queue_size",
                            help="Queue size to attempt preloading frames "
                                 "(warning: impacts FPS) (default: %(default)s).")
    video_opts.add_argument("--frame-drop-factor", "--drop", type=int, default=VideoResultPlayerApp.frame_drop_factor,
                            help="Factor by which the delayed video frames should be dropped if exceeding target FPS. "
                                 "Avoids long sporadic lags (default: %(default)s).")
    video_opts.add_argument("--frame-skip-factor", "--skip", type=int, default=VideoResultPlayerApp.frame_skip_factor,
                            help="Factor by which to voluntarily skip video frames to make them pass faster. "
                                 "If playback feels like it still has too much lag, increasing this value can help by "
                                 "purposely dropping frames between every X frame interval specified by this factor. "
                                 "(warning: too high value could make the video become like a slide-show) "
                                 "(default: %(default)s, ie: don't skip any frame)")
    log_opts = ap.add_argument_group(title="Logging Options",
                                     description="Options that configure output logging.")
    log_opts.add_argument("--quiet", "-q", action="store_true", help="Do not output anything else than error.")
    log_opts.add_argument("--debug", "-d", action="store_true", help="Enable extra debug logging.")
    return ap


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
    return VideoResultPlayerApp(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
