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
from typing import List, Optional

import cv2 as cv
import PIL.Image
import PIL.ImageTk
import tkinter as tk

from stream import VideoCaptureThread  # noqa

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
    video_desc_index = None     # type: Optional[int]
    video_infer_meta = None
    video_infer_indices = None  # type: Optional[List[int]]
    text_annot_meta = None
    text_annot_index = None     # type: Optional[int]
    # handles to UI elements
    window = None
    video_viewer = None
    video_slider = None
    video_desc_label = None
    video_desc_scrollY = None
    video_desc_textbox = None
    video_infer_label = None
    video_infer_scrollX = None
    video_infer_scrollY = None
    video_infer_textbox = None
    text_annot_label = None
    text_annot_scrollX = None
    text_annot_scrollY = None
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
    # shared metadata keys
    vd_key = "video_description"
    ta_key = "text_annotation"
    vi_key = "video_inference"
    ts_key = "start_ms"
    te_key = "end_ms"
    precision = 2

    def __init__(self, video_file, video_description, video_results, text_annotations, merged_metadata=None,
                 output=None, scale=1.0, queue_size=10, frame_drop_factor=4, frame_skip_factor=1):
        if video_file is not None:
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

        if not self.setup_metadata(video_description, video_results, text_annotations, merged_metadata):
            return
        if video_file is None:
            LOGGER.info("No video to display")
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
        self.video_desc_scrollY = tk.Scrollbar(panel_video_desc, command=self.video_desc_textbox.yview)
        self.video_desc_textbox.configure(yscrollcommand=self.video_desc_scrollY.set)
        self.video_desc_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.video_desc_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.video_desc_textbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_desc_scrollY.pack(side=tk.RIGHT, fill=tk.Y, expand=True)
        self.update_video_desc()

        self.video_infer_label = tk.Label(panel_video_infer, text="Video Inference Metadata", font=self.font_header)
        self.video_infer_label.pack(side=tk.TOP)
        video_infer_xy_scroll_box = tk.Frame(panel_video_infer, padx=0, pady=0)
        video_infer_xy_scroll_box.pack()
        self.video_infer_textbox = tk.Text(video_infer_xy_scroll_box, wrap=tk.NONE)
        self.video_infer_scrollX = tk.Scrollbar(video_infer_xy_scroll_box, orient=tk.HORIZONTAL,
                                                command=self.video_infer_textbox.xview)
        self.video_infer_scrollY = tk.Scrollbar(video_infer_xy_scroll_box, orient=tk.VERTICAL,
                                                command=self.video_infer_textbox.yview)
        self.video_infer_textbox.configure(xscrollcommand=self.video_infer_scrollX.set,
                                           yscrollcommand=self.video_infer_scrollY.set)
        self.video_infer_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.video_infer_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.video_infer_textbox.grid(row=0, column=0, sticky=tk.NSEW)
        self.video_infer_scrollY.grid(row=0, column=1, sticky=tk.NS)
        self.video_infer_scrollX.grid(row=1, column=0, sticky=tk.EW)
        video_infer_xy_scroll_box.grid_rowconfigure(0, weight=1)
        video_infer_xy_scroll_box.grid_columnconfigure(0, weight=1)
        self.update_video_infer()

        self.text_annot_label = tk.Label(panel_text_annot, text="Text Annotation Metadata", font=self.font_header)
        self.text_annot_label.pack(side=tk.TOP, fill=tk.X)
        text_annot_xy_scroll_box = tk.Frame(panel_text_annot, padx=0, pady=0)
        text_annot_xy_scroll_box.pack()
        self.text_annot_textbox = tk.Text(text_annot_xy_scroll_box, wrap=tk.NONE)
        self.text_annot_scrollX = tk.Scrollbar(text_annot_xy_scroll_box, orient=tk.HORIZONTAL,
                                               command=self.text_annot_textbox.xview)
        self.text_annot_scrollY = tk.Scrollbar(text_annot_xy_scroll_box, orient=tk.VERTICAL,
                                               command=self.text_annot_textbox.yview)
        self.text_annot_textbox.configure(xscrollcommand=self.text_annot_scrollX.set,
                                          yscrollcommand=self.text_annot_scrollY.set)
        self.text_annot_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.text_annot_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.text_annot_textbox.grid(row=0, column=0, sticky=tk.NSEW)
        self.text_annot_scrollX.grid(row=0, column=1, sticky=tk.NS)
        self.text_annot_scrollX.grid(row=1, column=0, sticky=tk.EW)
        text_annot_xy_scroll_box.grid_rowconfigure(0, weight=1)
        text_annot_xy_scroll_box.grid_columnconfigure(0, weight=1)
        self.update_text_annot()

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

    def update_video_desc(self, metadata=None, indices=None):
        self.video_desc_textbox.delete("1.0", tk.END)
        if metadata is None:
            text = self.NO_DATA
            self.video_desc_textbox.insert(tk.END, "", self.font_normal_tag)
            self.video_desc_textbox.insert(tk.END, text, self.font_code_tag)
        else:
            # only one dimension for this kind of annotation
            index = indices[0]
            metadata = metadata[0][index]
            # display plain video description text
            entry = "(index: {}, start: {:.2f}, end: {:.2f})".format(index, metadata["start"], metadata["end"])
            text = "{}\n\n{}".format(entry, metadata["vd"])
            self.video_desc_textbox.insert(tk.END, text, self.font_normal_tag)
            self.video_desc_textbox.insert(tk.END, "", self.font_code_tag)

    @staticmethod
    def format_video_infer(number, index, metadata):
        """
        Format a single video inference metadata file into lines to be displayed.
        """
        meta = metadata[index]
        entry = "(file: {}, index: {})".format(number, index)
        times = "(start: {:.2f}, end: {:.2f})".format(meta["start"], meta["end"])
        header = "[Score] [Classes]"
        values = ["[{:.2f}] {}".format(s, c) for c, s in zip(meta["classes"], meta["scores"])]
        return [entry, times, "", header] + values

    def update_video_infer(self, metadata=None, indices=None):
        """
        Format video inference metadata entries side-by-side from N sources.
        """
        self.video_infer_textbox.delete("1.0", tk.END)
        if metadata is None:
            text = self.NO_DATA
            self.video_infer_textbox.insert(tk.END, "", self.font_normal_tag)
            self.video_infer_textbox.insert(tk.END, text, self.font_code_tag)
        else:
            text = ""
            meta_lines = [
                self.format_video_infer(number, index, meta)
                for number, (index, meta) in enumerate(zip(indices, metadata))
            ]
            # display lines ordered from top-1 to lowest top-k, with possibility variable amounts for each
            max_lines = max([len(lines) for lines in meta_lines])
            for line_index in range(max_lines):
                for meta in meta_lines:
                    line = meta[line_index] if line_index < len(meta) else ""
                    # reasonable padding to align columns, adjust if class names are too long to display
                    text += "{:<32s}".format(line)
                text += "\n"
            self.video_infer_textbox.insert(tk.END, "", self.font_normal_tag)
            self.video_infer_textbox.insert(tk.END, text, self.font_code_tag)

    def update_text_annot(self, metadata=None, indices=None):
        self.text_annot_textbox.delete("1.0", tk.END)
        if metadata is None:
            text = self.NO_DATA
            self.text_annot_textbox.insert(tk.END, "", self.font_normal_tag)
            self.text_annot_textbox.insert(tk.END, text, self.font_code_tag)
        else:
            # only one dimension for this kind of annotation
            index = indices[0]
            metadata = metadata[0][index]
            # update displayed metadata as text table
            annotations = metadata["annotations"]
            fmt = "    {:<16s} | {:<24s} | {:<16s}"
            fields = "POS", "type", "lemme"
            header = fmt.format(*fields)
            entry = "(index: {}, start: {:.2f}, end: {:.2f})".format(index, metadata["start"], metadata["end"])
            text = "{}\n\n{}\n{}\n".format(entry, header, "_" * len(header))
            for i, annot in enumerate(annotations):
                text += "\n[{}]: {}\n".format(i, annot["sentence"])
                text += "\n".join([fmt.format(*[item[f] for f in fields]) for item in annot["words"]])
            self.text_annot_textbox.insert(tk.END, "", self.font_normal_tag)
            self.text_annot_textbox.insert(tk.END, text, self.font_code_tag)

    def update_metadata(self, seek=False):
        def update_meta(meta_container, meta_index, meta_updater):
            """
            Updates the view element with the next metadata if the time for it to change was reached.
            If seek was requested, searches from the start to find the applicable metadata.

            :param meta_container: all possible metadata entries, assumed ascending pre-ordered by 'ts' key.
            :param meta_index: active metadata index
            :param meta_updater: method that updates the view element for the found metadata entry
            :return: index of updated metadata or already active one if time is still applicable for current metadata
            """
            # update only if metadata container entries are available
            if meta_container:
                # convert containers to 2D list regardless of original inputs
                if not isinstance(meta_index, list):
                    meta_index = [meta_index]
                    meta_container = [meta_container]
                if not isinstance(meta_container[0], list):
                    meta_container = [meta_container]

                must_update = False
                computed_indices = []
                for i, index in enumerate(meta_index):
                    current_index = 0 if seek else index
                    updated_index = current_index  # if nothing needs to change (current is still valid for timestamp)
                    current_meta = meta_container[i][current_index]  # type: dict
                    index_total = len(meta_container[i])
                    if seek:
                        # search the earliest index that provides metadata within the new time
                        for idx in range(index_total):
                            meta = meta_container[i][idx]
                            if meta[self.ts_key] >= self.frame_time:
                                updated_index = idx
                                break
                    elif self.frame_time > current_meta[self.te_key]:
                        # otherwise bump to next one if timestamp of the current is passed
                        updated_index = current_index + 1

                    # apply change of metadata, update all meta of each stack if any must be changed
                    if index < index_total - 1 and current_index != updated_index or updated_index == 0:
                        must_update = True
                    computed_indices.append(updated_index)
                if must_update:
                    meta_updater(meta_container, computed_indices)
                return computed_indices
            return None

        self.video_desc_index = update_meta(self.video_desc_meta, self.video_desc_index, self.update_video_desc)
        self.video_infer_indices = update_meta(self.video_infer_meta, self.video_infer_indices, self.update_video_infer)
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

    def setup_metadata(self, video_description, video_results, text_annotations, merged_metadata):
        """
        Parse available metadata files and prepare the first entry according to provided file references.
        """
        try:
            video_desc_full_meta = video_infer_full_meta = text_annot_full_meta = None
            if video_description and os.path.isfile(video_description):
                LOGGER.info("Parsing video description metadata [%s]...", video_description)
                self.video_desc_meta, video_desc_full_meta = self.parse_video_description_metadata(video_description)
                self.video_desc_index = 0
            if video_results and isinstance(video_results, list):
                video_infer_full_meta = []
                for result in video_results:
                    if os.path.isfile(result):
                        LOGGER.info("Parsing video inference metadata [%s]...", video_results)
                    meta, full_meta = self.parse_video_inference_metadata(result)
                    video_infer_full_meta.append(full_meta)
                    if not self.video_infer_meta:
                        self.video_infer_meta = []
                        self.video_infer_indices = []
                    self.video_infer_meta.append(meta)
                    self.video_infer_indices.append(0)
            if text_annotations and os.path.isfile(text_annotations):
                LOGGER.info("Parsing text inference metadata [%s]...", text_annotations)
                self.text_annot_meta, text_annot_full_meta = self.parse_text_annotations_metadata(text_annotations)
                self.text_annot_index = 0
            if merged_metadata:
                self.merge_metadata(video_desc_full_meta, video_infer_full_meta, text_annot_full_meta,
                                    self.video_desc_meta, self.video_infer_meta, self.text_annot_meta, merged_metadata)
        except Exception as exc:
            self.error = True
            LOGGER.error("Invalid formats. One or more metadata file could not be parsed.", exc_info=exc)
            return False
        return True

    def merge_metadata(self,
                       video_description_full_metadata, video_inference_full_metadata, text_annotation_full_metadata,
                       video_description_time_metadata, video_inference_time_metadata, text_annotation_time_metadata,
                       merged_path):
        """
        Merges all provided metadata variations into a common file.

        Section ``details`` provide general metadata provenance information from the corresponding metadata types.
        Entries marked as ``None`` mean that no corresponding metadata file of that type was provided as input.

        Section ``merged`` provides the combined/extended timestamp entries where concordance between metadata types
        could be mapped. Metadata text annotations are usually aligned with video-description, but this is not
        necessarily the case of video inferences. For this reason, additional entries are padded as follows:

            [META-TYPE]                 ts                                               te
            meta-video-desc     (VD)    |....... entry-1 ..... | ........ entry-2 ...... |
            meta-text-annot     (TA)    |....... entry-1 ..... | ........ entry-2 ...... |
            meta-video-infer    (VD[N]) |... entry-1 ...|... entry-2 ...|... entry-3 ....|
            merged                      |..... M1 ......|. M2 .|.. M3 ..|...... M4 ......|
                                        t0              t1     t2       t3               t4

        Top-level start/end time correspond to first/last times found across every single metadata type/entry (ts/te).

        Then, for each merged entry, start/end time indicate the limits of each cut portion, respectively (t0/t1),
        (t1/t2), (t3/t4) for the 4 generated entries above example.

        Under each entry, available VD, TA, VI[N] will have their **original** start/end time
        (which will extend passed merged portions start/end times).

        Whenever metadata of some type cannot be found within the given merged portion, ``None`` is placed instead.
        This can happen for example when VD did not yet start, was over, or nothing happens for a long duration while
        VI continues to predict continuously.
        """
        if not video_description_full_metadata and not video_description_time_metadata and \
                not video_inference_full_metadata and not video_inference_time_metadata and \
                not text_annotation_full_metadata and not text_annotation_time_metadata:
            LOGGER.error("No metadata provided, nothing to merge!")
            raise ValueError("Missing metadata")

        # define generic metadata details without the merged timestamped metadata
        metadata = {
            self.ts_key: None,
            self.te_key: None,
            "details": {self.vd_key: None, self.ta_key: None, self.vi_key: None},
            "merged": []
        }
        if video_description_full_metadata:
            video_description_full_metadata.pop("standard_vd_metadata", None)
            video_description_full_metadata.pop("augmented_vd_metadata", None)
            metadata["details"][self.vd_key] = video_description_full_metadata
        if text_annotation_full_metadata:
            text_annotation_full_metadata.pop("data", None)
            metadata["details"][self.ta_key] = text_annotation_full_metadata
        if video_inference_full_metadata:
            for meta in video_inference_full_metadata:
                meta.pop("predictions", None)
                metadata["details"][self.vi_key] = video_inference_full_metadata

        # lookup timestamped metadata entries and combine them appropriately
        vd_index = None
        ta_index = None
        vi_indices = []
        if video_description_time_metadata:
            vd_index = 0
        else:
            video_description_time_metadata = []
        if text_annotation_time_metadata:
            ta_index = 0
        else:
            text_annotation_time_metadata = []
        if video_description_time_metadata:
            vi_indices = [0] * len(video_inference_time_metadata)
        else:
            video_inference_time_metadata = []

        def next_entry(meta_list, meta_index):
            """Finds the active metadata entry for any given metadata-type against current index and start/end times."""
            if meta_index is None:
                return None, None, None, None
            meta_entry = meta_list[meta_index]
            meta_end = round(meta_entry[self.te_key], self.precision)
            # move to next meta index if end time of previous one was reached
            if last_time >= meta_end:
                meta_index += 1
                # if passed last item, no more metadata for this portion against other metadata types
                if meta_index >= len(meta_list):
                    # return no end time to ignore that value in compare with other metadata types
                    return None, None, None, None
                meta_entry = meta_list[meta_index]
                meta_end = round(meta_entry[self.te_key], self.precision)
            meta_start = round(meta_entry[self.ts_key], self.precision)
            return meta_entry, meta_index, meta_start, meta_end

        first_time = None
        last_time = 0
        vd_total = len(video_description_time_metadata)
        ta_total = len(text_annotation_time_metadata)
        vi_totals = [len(vi_meta) for vi_meta in video_inference_time_metadata]
        while True:
            vd_txt = "(done)" if vd_index is None else "({}/{})".format(vd_index + 1, vd_total)
            ta_txt = "(done)" if ta_index is None else "({}/{})".format(vd_index + 1, vd_total)
            vi_txt = ", ".join(["(done)" if vi_i is None else "({}/{})".format(vi_i + 1, vi_t)
                                for vi_i, vi_t in zip(vi_indices, vi_totals)])
            LOGGER.debug("Merged: VI [%s] TA [%s] VI [%s]", vd_txt, ta_txt, vi_txt)
            new_entry = {self.ts_key: None, self.te_key: None, self.vd_key: None, self.ta_key: None, self.vi_key: None}

            # find next entry for each metadata type against last time and current indices
            vd_entry, vd_index, vd_start, vd_end = next_entry(video_description_time_metadata, vd_index)
            ta_entry, ta_index, ta_start, ta_end = next_entry(text_annotation_time_metadata, ta_index)
            vi_start_multi = []
            vi_end_multi = []
            vi_entries = []
            for i, vi_index in enumerate(vi_indices):
                if not new_entry[self.vi_key]:
                    new_entry[self.vi_key] = []
                vi_entry, vi_index, vi_start, vi_end = next_entry(video_inference_time_metadata[i], vi_index)
                vi_indices[i] = vi_index
                vi_start_multi.append(vi_start)
                vi_end_multi.append(vi_end)
                vi_entries.append(vi_entry)

            # check ending condition
            vd_done = vd_index is None or vd_index == vd_total
            ta_done = ta_index is None or ta_index == ta_total
            vi_done = all(vi_indices[i] is None or vi_indices[i] == vi_totals for i, total in enumerate(vi_totals))
            done = [vd_done, ta_done, vi_done]
            if not len(done) or all(done):
                break

            # first time could be different than zero if all items started with an offset
            if first_time is None:
                first_time = min(filter(lambda start: start is not None, [vd_start, ta_start] + vi_start_multi))
                first_time = round(first_time, self.precision)
                last_time = first_time

            # find next loop start time with first end time of current iteration to find next cut point
            # ignore exhausted end times if last item from its metadata list was passed
            end_time = min(filter(lambda end: end is not None, [vd_end, ta_end] + vi_end_multi))
            end_time = round(end_time, self.precision)

            # update current metadata entry, empty if time is lower/greater than current portion
            # start times need to be computed after 'next_entry' call to find the start time of all meta portions
            new_entry[self.vd_key] = None if not vd_entry or vd_entry[self.ts_key] < last_time else vd_entry
            new_entry[self.ta_key] = None if not ta_entry or ta_entry[self.ts_key] < last_time else ta_entry
            new_entry[self.vi_key] = [None if not v or v[self.ts_key] < last_time else v for v in vi_entries]

            # apply current merged start/end times and add to list of merged metadata
            new_entry[self.ts_key] = last_time
            new_entry[self.te_key] = end_time
            metadata["merged"].append(new_entry)
            last_time = end_time

        metadata[self.ts_key] = first_time
        metadata[self.te_key] = last_time

        LOGGER.debug("Total amount of merged metadata entries: %s", len(metadata["merged"]))
        LOGGER.info("Generating merged metadata file: [%s]", merged_path)
        with open(merged_path, "w") as meta_file:
            json.dump(metadata, meta_file, indent=4, ensure_ascii=False)

    def parse_video_description_metadata(self, metadata_path):
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
                    meta["end_ts"] = meta["end"]
                    meta["start"] = meta[self.ts_key] / 1000.
                    meta["end"] = meta[self.te_key] / 1000.
                    meta[self.ts_key] = round(meta[self.ts_key], self.precision)
                    meta[self.te_key] = round(meta[self.te_key], self.precision)
                # ensure sorted entries
                return list(sorted(meta_vd, key=lambda vd: vd[self.ts_key])), metadata
        except Exception as exc:
            LOGGER.error("Could not parse video annotation metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    def parse_video_inference_metadata(self, metadata_path):
        try:
            with open(metadata_path) as meta_file:
                metadata = json.load(meta_file)
            # ensure ordered by time
            predictions = list(sorted(metadata["predictions"], key=lambda p: p["start"]))
            # convert times to ms for same base comparisons
            for pred in predictions:
                pred[self.ts_key] = round(pred["start"] * 1000, self.precision)
                pred[self.te_key] = round(pred["end"] * 1000, self.precision)
            return predictions, metadata
        except Exception as exc:
            LOGGER.error("Could not parse video inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    def parse_text_annotations_metadata(self, metadata_path):
        try:
            with open(metadata_path) as meta_file:
                metadata = json.load(meta_file)
            annotations = metadata["data"]
            for annot in annotations:
                # convert TS: [start,end] -> (ts, te) in milliseconds
                ts_s = datetime.strptime(annot["TS"][0], "T%H:%M:%S.%f")
                ts_e = datetime.strptime(annot["TS"][1], "T%H:%M:%S.%f")
                sec_s = float("{}.{}".format((ts_s.hour * 3600 + ts_s.minute * 60 + ts_s.second), ts_s.microsecond))
                sec_e = float("{}.{}".format((ts_e.hour * 3600 + ts_e.minute * 60 + ts_e.second), ts_e.microsecond))
                annot[self.ts_key] = round(sec_s * 1000., self.precision)
                annot[self.te_key] = round(sec_e * 1000., self.precision)
                annot["start"] = sec_s
                annot["end"] = sec_e
                # extend 2D list into sentences/words metadata and drop redundant VD
                vd = annot.pop("vd", "")
                sentences = [s + "." if not s.endswith(".") else s for s in vd.split(". ")]
                annot_list = list(annot["annotations"])  # ensure copy to avoid edit error while iterating
                # note:
                #  Original annotations sometime have errors due to capital letters incorrectly interpreted
                #  as beginning of new sentence.
                #  Sometimes, they are instead missing some annotations against the number of sentences.
                #  Patch them as best as possible.
                while len(sentences) != len(annot_list):
                    if len(sentences) > len(annot_list):
                        # pad extra empty annotations where no lemme can be matched within the current sentence
                        # if matched, move to next to find the best index at which to insert empty annotations
                        i = 0
                        for i, s in enumerate(sentences):
                            if i >= len(annot_list):
                                break
                            if not any([a["lemme"].replace("_", " ") in s for a in annot_list[i]]):
                                break
                        annot_list.insert(i, [])
                    else:
                        # merge over abundant annotations
                        annot_list[0].extend(annot_list.pop(1))
                annot["annotations"] = [{"sentence": s, "words": a} for s, a in zip(sentences, annot_list)]
            return list(sorted(annotations, key=lambda _a: _a[self.ts_key])), metadata
        except Exception as exc:
            LOGGER.error("Could not parse text inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None


def make_parser():
    formatter = lambda prog: argparse.HelpFormatter(prog, width=120)  # noqa
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True, formatter_class=formatter)  # noqa
    main_args = ap.add_argument_group(title="Main Arguments",
                                      description="Main arguments")
    video_arg = main_args.add_mutually_exclusive_group()
    video_arg.add_argument("--video", "--vf", dest="video_file", help="Video file to view.")
    video_arg.add_argument("--no-video", action="store_true",
                           help="Disable video. Employ only metadata parsing. "
                                "Must be combined with merged metadata output.")
    main_args.add_argument("--video-description", "--vd", dest="video_description",
                           help="JSON metadata file with original video-description annotations.")
    main_args.add_argument("--video-inference", "--vi", nargs="*", dest="video_results",
                           help="JSON metadata file(s) with video action recognition inference results. "
                                "If multiple files are provided, they will be simultaneously displayed side-by-side.")
    main_args.add_argument("--text-annotation", "--ta", dest="text_annotations",
                           help="JSON metadata file with text subjects and verbs annotations.")
    main_args.add_argument("--merged", "-m", dest="merged_metadata",
                           help="Output path of merged metadata JSON file from all other metadata files with realigned "
                                "timestamps of corresponding sections.")
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
    if ns.no_video and not ns.merged_metadata:
        LOGGER.error("Merged metadata file is required when no video is employed (only process metadata).")
        return -1
    for rm_arg in ["debug", "quiet", "no_video"]:
        args.pop(rm_arg, None)
    return VideoResultPlayerApp(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
