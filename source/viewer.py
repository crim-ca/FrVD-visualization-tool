"""
Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results.
"""
import argparse
import difflib
import itertools
import logging
import math
import os
import re
import sys
import time
import uuid
from utils import (
    ToolTip,
    draw_bbox,
    parse_timestamp,
    read_metafile,
    seconds2timestamp,
    split_sentences,
    timestamp2seconds,
    write_metafile
)
from typing import Any, Dict, List, Optional

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
    version = "1.4.1"   # updated automatically from bump version
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
    NO_DATA_TEXT = "<no-metadata>"
    NO_MORE_TEXT = "(metadata exhausted)"
    NO_DATA_INDEX = None
    NO_MORE_INDEX = -1
    video_desc_meta = None
    video_desc_index = None     # type: Optional[int]
    video_infer_meta = None
    video_infer_indices = None  # type: Optional[List[int]]
    video_infer_multi = None    # type: Optional[List[bool]]
    text_annot_meta = None
    text_annot_index = None     # type: Optional[int]
    text_infer_meta = None
    text_infer_index = None     # type: Optional[int]
    mapping_label = None        # type: Optional[Dict[str, str]]
    mapping_regex = None        # type: Optional[Dict[re.Pattern, str]]
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
    checkbox_regions = None
    checkbox_regions_central = None
    display_regions = None
    display_regions_central = None
    display_colors = None
    play_button = None
    play_state = True
    play_label = None
    play_text = None
    font_header = ("Helvetica", 16, "bold")
    font_code = ("Courier", 12, "normal")
    font_normal = ("Times", 12, "normal")
    font_code_tag = "code"
    font_normal_tag = "normal"
    # shared metadata keys
    ref_section = "references"
    ref_key = "id"  # chosen specifically to match existing field in VD actors/scenes
    actors_key = "actors"
    scenes_key = "scenes"
    vd_key = "video_description"
    ta_key = "text_annotation"
    ti_key = "text_inference"
    vi_key = "video_inference"
    ts_key = "start_ms"
    te_key = "end_ms"
    precision = 2

    def __init__(self, video_file, video_description, video_inferences, text_annotations, text_inferences,
                 text_auto=None, merged_metadata_input=None, merged_metadata_output=None,
                 mapping_file=None, use_references=False, output=None,
                 scale=1.0, queue_size=10, frame_drop_factor=4, frame_skip_factor=1):
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
            self.setup_colors()

        valid_meta = self.setup_metadata(video_description, video_inferences, text_annotations, text_inferences,
                                         text_auto, merged_metadata_input, merged_metadata_output,
                                         mapping_file, use_references)
        if not valid_meta:
            return
        if video_file is None:
            LOGGER.info("No video to display")
            return
        self.update_metadata(seek=True)
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
        real_fps = self.video.get(cv.CAP_PROP_FPS)
        self.frame_fps = round(real_fps)
        self.frame_delta = 1. / float(real_fps) * 1000.
        self.frame_count = int(self.video.get(cv.CAP_PROP_FRAME_COUNT))
        self.video_duration = self.frame_delta * self.frame_count
        self.video_width = round(self.video.get(cv.CAP_PROP_FRAME_WIDTH))
        self.video_height = round(self.video.get(cv.CAP_PROP_FRAME_HEIGHT))
        expected_width = round(self.video_width * self.video_scale)
        if expected_width < 480:
            new_scale = 480. / float(self.video_width)
            LOGGER.warning("Readjusting video scale [%.3f] to [%.3f] to ensure minimal width [480px].",
                           self.video_scale, new_scale)
            self.video_scale = new_scale

    def setup_window(self):
        LOGGER.info("Creating window...")
        display_width = round(self.video_width * self.video_scale)
        display_height = round(self.video_height * self.video_scale)

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
        slider_interval = self.frame_count // round(10 * self.video_scale)
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

        txt_display_regions = "Display video inference regions"
        txt_display_central = "Display only central regions"
        checkbox_label_width = max(len(txt_display_central), len(txt_display_regions))
        self.checkbox_regions = tk.Frame(panel_video_viewer)
        self.display_regions = tk.IntVar(value=1)
        checkbox_regions_label = tk.Label(self.checkbox_regions, justify=tk.LEFT, anchor=tk.W,
                                          width=checkbox_label_width, text=txt_display_regions)
        checkbox_regions_label.grid(row=0, column=1)
        checkbox_regions_check = tk.Checkbutton(self.checkbox_regions, variable=self.display_regions)
        checkbox_regions_check.grid(row=0, column=0)
        ToolTip(checkbox_regions_check, justify=tk.LEFT,
                text="When displayed, dashed regions represent upcoming/passed central key frames.\n"
                     "Filled region box indicate current time is close to center key frame of video segment metadata.\n"
                     "This is because regions are defined only for the central key frame of each segment, rather than\n"
                     "following objects over each frame.")
        self.display_regions_central = tk.IntVar(value=1)
        checkbox_central_label = tk.Label(self.checkbox_regions, justify=tk.LEFT, anchor=tk.W,
                                          width=checkbox_label_width, text=txt_display_central)
        checkbox_central_label.grid(row=1, column=1)
        checkbox_central_check = tk.Checkbutton(self.checkbox_regions, variable=self.display_regions_central)
        checkbox_central_check.grid(row=1, column=0)
        ToolTip(checkbox_central_check, justify=tk.LEFT,
                text="When enabled, only full bounding boxes around the video segment central time are displayed.\n"
                     "Otherwise, both upcoming/passed center key (dashed) and central bounding boxes (full)\n"
                     "are displayed.")
        self.checkbox_regions.pack(side=tk.RIGHT, anchor=tk.SE)

        self.video_desc_label = tk.Label(panel_video_desc, text="Video Description Metadata",
                                         font=self.font_header, justify=tk.LEFT, anchor=tk.W)
        self.video_desc_label.pack(side=tk.TOP, fill=tk.X)
        video_desc_xy_scroll_box = tk.Frame(panel_video_desc, padx=0, pady=0)
        video_desc_xy_scroll_box.pack(fill=tk.BOTH, expand=True)
        self.video_desc_textbox = tk.Text(video_desc_xy_scroll_box, height=10, wrap=tk.WORD)
        self.video_desc_scrollY = tk.Scrollbar(video_desc_xy_scroll_box, command=self.video_desc_textbox.yview)
        self.video_desc_textbox.configure(yscrollcommand=self.video_desc_scrollY.set)
        self.video_desc_textbox.tag_configure(self.font_code_tag, font=self.font_code)
        self.video_desc_textbox.tag_configure(self.font_normal_tag, font=self.font_normal)
        self.video_desc_textbox.grid(row=0, column=0, sticky=tk.NSEW)
        self.video_desc_scrollY.grid(row=0, column=1, sticky=tk.NS)
        video_desc_xy_scroll_box.grid_rowconfigure(0, weight=1)
        video_desc_xy_scroll_box.grid_columnconfigure(0, weight=1)
        self.update_video_desc()

        self.video_infer_label = tk.Label(panel_video_infer, text="Video Inference Metadata",
                                          font=self.font_header, justify=tk.LEFT, anchor=tk.W)
        self.video_infer_label.pack(side=tk.TOP, fill=tk.X)
        video_infer_xy_scroll_box = tk.Frame(panel_video_infer, padx=0, pady=0)
        video_infer_xy_scroll_box.pack(fill=tk.BOTH, expand=True)
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

        self.text_annot_label = tk.Label(panel_text_annot, text="Text Annotation Metadata",
                                         font=self.font_header, justify=tk.LEFT, anchor=tk.W)
        self.text_annot_label.pack(side=tk.TOP, fill=tk.X)
        text_annot_xy_scroll_box = tk.Frame(panel_text_annot, padx=0, pady=0)
        text_annot_xy_scroll_box.pack(fill=tk.BOTH, expand=True)
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
        self.text_annot_scrollY.grid(row=0, column=1, sticky=tk.NS)
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
            index = round((event.x - coord_min[0]) * ratio)
            while index % self.frame_skip_factor:
                index += 1

        LOGGER.debug("Seek frame %8s from click event (%s, %s) between [%s, %s]",
                     index, event.x, event.y, coord_min, coord_max)
        self.seek_frame(index)
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
        if not metadata or not indices:
            text = self.NO_DATA_TEXT
        elif indices[0] == self.NO_DATA_INDEX:
            text = self.NO_DATA_TEXT
        elif indices[0] == self.NO_MORE_INDEX:
            text = self.NO_MORE_TEXT
        else:
            # only one dimension for this kind of annotation
            index = indices[0]
            metadata = metadata[0][index]
            # display plain video description text
            entry = "(index: {}, start: {:.2f}, end: {:.2f})".format(index, metadata["start"], metadata["end"])
            text = "{}\n\n{}".format(entry, metadata["vd"])
        self.video_desc_textbox.insert(tk.END, text, self.font_normal_tag)
        self.video_desc_textbox.insert(tk.END, "", self.font_code_tag)

    def format_video_infer(self, number, index, metadata, multi):
        """
        Format a single video inference metadata file into lines to be displayed.

        :param number: index of the metadata list (in case of multiple provided).
        :param index: index of the current entry within the corresponding metadata list.
        :param metadata: metadata list corresponding to number where index entry can be retrieved.
        :param multi: index of multi-predictions regions of entry if applicable (-1 if overall prediction on sequence).
        """
        template = "(file: {}, index: {})"
        if index == self.NO_MORE_INDEX:
            return [template.format(number, len(metadata)), self.NO_MORE_TEXT]
        if index == self.NO_DATA_INDEX:
            return [template.format(number, "n/a"), self.NO_DATA_TEXT]
        meta = metadata[index]
        info = ""
        entry = template.format(number, index)
        times = "(start: {:.2f}, end: {:.2f})".format(meta["start"], meta["end"])
        header = "[Score] [Classes]"
        if multi >= 0:
            meta = meta["regions"][multi]
            info = str(tuple(meta["bbox"]))
        values = ["[{:.2f}] {}".format(s, c)
                  for c, s in zip(meta["classes"], meta["scores"])]
        return [entry, times, info, "", header] + values

    @staticmethod
    def flatten_video_meta(indices, metadata, regions):
        """
        Flattens 2D lists of predictions to 1D for rendering.

        First dimension is along the number of provided video-inference files (length of :paramref:`indices`).
        Second dimension are along the number of regions with predictions within each of those files.
        If a file was defined with ``multi_predictions``, the number of (variable) predictions sets retrieved
        per bounding box at the given index are flattened as if they were provided with individual files.

            [file-1 predictions, file-2 multi-predictions-1, file-2 multi-predictions-2, file-3 predictions, ...]

        Each of the above predictions represent a set of [Top-K] classifications scores/classes.

        :param indices: list of indices of the current predictions set for each of the provided files
        :param metadata: parsed metadata list of predictions for each of the provided files.
        :param regions: boolean indicator for each file of whether it is formatted as single- or multi-predictions.
        :return: tuple of flattened (file indices, index of predictions set, corresponding metadata, region index)
        """
        multi_indices = [len(metadata[n][indices[n]]["regions"]) if regions[n] else -1 for n in range(len(metadata))]
        flatten_metadata = []
        flatten_indices = []
        flatten_number = []
        flatten_regions = []
        for i, count in enumerate(multi_indices):
            if count < 0:
                flatten_metadata.append(metadata[i])
                flatten_indices.append(indices[i])
                flatten_number.append(i)
                flatten_regions.append(-1)
            else:
                flatten_metadata.extend([metadata[i]] * count)
                flatten_indices.extend([indices[i]] * count)
                flatten_number.extend([i] * count)
                flatten_regions.extend(list(range(count)))
        return flatten_number, flatten_indices, flatten_metadata, flatten_regions

    def update_video_infer(self, metadata=None, indices=None):
        """
        Format video inference metadata entries side-by-side from N sources.
        """
        self.video_infer_textbox.delete("1.0", tk.END)
        if not metadata or not indices:
            text = self.NO_DATA_TEXT
        else:
            text = ""
            meta_lines = [
                self.format_video_infer(number, index, meta, multi)
                for (number, index, meta, multi)
                in zip(*self.flatten_video_meta(indices, metadata, self.video_infer_multi))
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
        if not metadata or not indices:
            text = self.NO_DATA_TEXT
        elif indices[0] == self.NO_DATA_INDEX:
            text = self.NO_DATA_TEXT
        elif indices[0] == self.NO_MORE_INDEX:
            text = self.NO_MORE_TEXT
        else:
            # only one dimension for this kind of annotation
            index = indices[0]
            metadata = metadata[0][index]
            # update displayed metadata as text table
            annotations = metadata["annotations"]
            fmt = "    {:<16s} | {:<24s} | {:<16s}"
            fields = ["POS", "type", "lemme"]
            header = fmt.format(*fields)
            entry = "(index: {}, start: {:.2f}, end: {:.2f})".format(index, metadata["start"], metadata["end"])
            text = "{}\n\n{}\n{}\n".format(entry, header, "_" * len(header))
            for i, annot in enumerate(annotations):
                text += "\n[{}]: {}\n".format(i, annot["sentence"])
                tokens = annot.get("words", annot.get("tokens", []))  # pre/post app version 1.x
                for item in tokens:
                    if "POS" in fields and "pos" in item:
                        fields[0] = "pos"  # v3/v4 is lowercase
                    if "type" in fields and "type" not in item:
                        fields[1] = "iob"  # v3/v4 removed type
                    if "iob" in fields:
                        item = dict(item)  # copy to edit and leave original intact
                        item["iob"] = ", ".join(item["iob"])  # can have multiple annotations
                    text += "\n" + fmt.format(*[item[f] for f in fields])
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
            if meta_container or meta_index == self.NO_DATA_INDEX:
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
                    index_total = len(meta_container[i])
                    if seek:
                        # search the earliest index that provides metadata within the new time
                        must_update = True
                        updated_index = self.NO_MORE_INDEX  # default if not found
                        for idx in range(index_total):
                            meta = meta_container[i][idx]
                            if meta[self.ts_key] >= self.frame_time:
                                updated_index = idx
                                break
                        else:
                            # validate meta is within time range of last entry, or out of scope
                            if meta_container[i][updated_index][self.te_key] >= self.frame_time:
                                updated_index = len(meta_container[i]) - 1
                    else:
                        # if next index exceeds the list, entries are exhausted
                        if current_index == self.NO_MORE_INDEX or current_index >= index_total:
                            computed_indices.append(self.NO_MORE_INDEX)  # set for following iterations
                            must_update = current_index == self.NO_MORE_INDEX  # updated last iteration
                            continue
                        # otherwise bump to next one if timestamp of the current is passed
                        current_meta = meta_container[i][current_index]  # type: dict
                        if self.frame_time > current_meta[self.te_key]:
                            updated_index = current_index + 1

                    # apply change of metadata, update all stack of metadata type if any must be changed
                    if current_index < index_total - 1 and current_index != updated_index:
                        must_update = True
                    computed_indices.append(updated_index)
                if must_update:
                    meta_updater(meta_container, computed_indices)
                return computed_indices
            return self.NO_DATA_INDEX

        self.video_desc_index = update_meta(self.video_desc_meta, self.video_desc_index, self.update_video_desc)
        self.video_infer_indices = update_meta(self.video_infer_meta, self.video_infer_indices, self.update_video_infer)
        self.text_annot_index = update_meta(self.text_annot_meta, self.text_annot_index, self.update_text_annot)

    def display_frame_info(self, frame, current_fps, average_fps):
        """
        Displays basic information on the frame.
        """
        text_offset = (10, 25)
        text_delta = 40
        font_scale = 0.5
        font_color = (209, 80, 0, 255)
        font_stroke = 1
        text0 = "Title: {}".format(self.video_title)
        text1 = "Original FPS: {}, Process FPS: {:0.2f} ({:0.2f})".format(self.frame_fps, current_fps, average_fps)
        cur_sec = self.frame_time / 1000.
        tot_sec = self.video_duration / 1000.
        cur_hms = time.strftime("%H:%M:%S", time.gmtime(cur_sec))
        tot_hms = time.strftime("%H:%M:%S", time.gmtime(tot_sec))
        text2 = "Time: {:0>.2f}/{:0.2f} ({}/{}) Frame: {}".format(cur_sec, tot_sec, cur_hms, tot_hms, self.frame_index)
        for text_row, text in [(0, text0), (-2, text1), (-1, text2)]:
            y_offset = round(text_delta * font_scale) * text_row
            if text_row < 0:
                y_offset = self.video_height + (y_offset - text_offset[1])
            text_pos = (text_offset[0], text_offset[1] + y_offset)
            cv.putText(frame, text, text_pos, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)

    def display_frame_regions(self, frame):
        """
        Displays bounding boxes whenever available from video inference metadata.

        Because regions defined by bounding boxes only refer to the central key frame ``tc`` within video segments where
        the associated action predictions are provided, it is possible that detection regions are not overlapping the
        actual visual person/object over the whole video segment. To indicate when the bounding box position overlaps
        the central key frame region, use a solid line rectangle when inside of a somewhat close interval ``dt`` from
        central ``tc``. For times outside that approximate interval, use a dashed line as potential but possibly
        erroneous person/object within the region. For a video segment spanning from ``ts`` to ``te``, the boxes will
        be rendered as dashed (``--``) or filled (``==``) as follows:

            ts        tc-dt    tc   tc+dt         te
            |-----------|======|======|-----------|

        """
        only_center = self.display_regions_central.get()
        for i, video_meta_index in enumerate(self.video_infer_indices):
            if self.video_infer_multi[i]:
                meta = self.video_infer_meta[i][video_meta_index]
                ts = meta["start_ms"]
                te = meta["end_ms"]
                # skip if region time is not yet reached or is passed
                if self.frame_time < ts or te < self.frame_time:
                    continue
                dt = 1000  # ms
                tc = ts + (te - ts) / 2
                ts_dt = tc - dt
                te_dt = tc + dt
                dash = 5  # dash spacing if not within ±dt, otherwise filled
                if ts_dt <= self.frame_time <= te_dt:
                    dash = None
                if only_center and dash:
                    continue  # skip draw dashed bounding box if not within ±dt when not requested
                for r, region in enumerate(meta["regions"]):
                    tl = (region["bbox"][0], region["bbox"][1])
                    br = (region["bbox"][2], region["bbox"][3])
                    color = self.display_colors[r % len(self.display_colors)]
                    label = "file: {}, bbox: {}".format(i, r)
                    draw_bbox(frame, tl, br, label, color,
                              box_thickness=1, box_dash_gap=dash, box_contour=False,
                              font_thickness=1, font_scale=0.5, font_contour=False)

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

        if self.display_regions.get():
            self.display_frame_regions(frame)   # must call before any resize to employ with original bbox dimensions

        frame_dims = (self.video_width, self.video_height)
        if self.video_scale != 1:
            frame_dims = (round(self.video_width * self.video_scale), round(self.video_height * self.video_scale))
            frame = cv.resize(frame, frame_dims, interpolation=cv.INTER_NEAREST)

        LOGGER.debug("Show Frame: %8s, Last: %8.2f, Time: %8.2f, Real Delta: %6.2fms, "
                     "Target Delta: %6.2fms, Call Delta: %6.2fms, Real FPS: %6.2f (%.2f) WxH: %s",
                     self.frame_index, self.last_time, self.frame_time, wait_time_delta,
                     self.frame_delta, call_msec_delta, call_fps, call_avg_fps, frame_dims)
        self.display_frame_info(frame, call_fps, call_avg_fps)

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
        frame_index = min(int(frame_index), self.frame_count - 1)

        # only execute an actual video frame seek() when it doesn't correspond to the next index, since it is already
        # fetched by the main loop using read()
        # without this, we would otherwise flush the frame queue and reset everything on each frame
        if frame_index not in [self.frame_index, self.frame_index - 1]:
            LOGGER.debug("Seek frame: %8s (fetching)", frame_index)
            self.frame_time = self.video.seek(frame_index)
            self.update_metadata(seek=True)  # enforce fresh update since everything changed drastically

        # update slider position
        self.video_slider.set(frame_index)
        self.frame_index = frame_index

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

    def setup_colors(self):
        """
        Generate list of colors for bounding boxes display.
        """
        # start with most distinct color variations using 0/255 RGB values
        self.display_colors = set(itertools.product([0, 255], repeat=3))
        # then add the intermediate colors to have more options
        half_colors = set(itertools.product([0, 128, 255], repeat=3)) - self.display_colors
        # remove black/white which are often hard to see against image
        self.display_colors.remove((0, 0, 0))
        self.display_colors.remove((255, 255, 255))
        # total 25 colors, more than enough for most use cases
        self.display_colors = list(self.display_colors) + list(half_colors)

    def setup_metadata(self, video_description, video_inferences, text_annotations, text_inferences,
                       text_auto, merged_metadata_input, merged_metadata_output, mapping_file, use_references):
        """
        Parse available metadata files and prepare the first entry according to provided file references.
        """
        try:
            video_desc_full_meta = video_infer_full_meta = text_annot_full_meta = text_infer_full_meta = None
            if merged_metadata_input:
                LOGGER.info("Detected input merged metadata. Generation and other metadata sources will be ignored.")
                LOGGER.info("Parsing merged metadata file [%s]...", merged_metadata_input)
                metadata = read_metafile(merged_metadata_input)
                merged, detail = metadata["merged"], metadata["details"]
                vi_indices = detail.get("total_{}".format(self.vi_key), [])
                vi_default = [None] * len(vi_indices)
                self.video_desc_meta = [meta.get(self.vd_key) for meta in merged if meta.get(self.vd_key) is not None]
                self.text_annot_meta = [meta.get(self.ta_key) for meta in merged if meta.get(self.ta_key) is not None]
                self.text_infer_meta = [meta.get(self.ti_key) for meta in merged if meta.get(self.ti_key) is not None]
                self.video_infer_meta = []
                self.video_infer_multi = [meta.get("multi_predictions", False) for meta in detail[self.vi_key]]
                for i in range(len(vi_indices)):
                    vi_meta = [meta.get(self.vi_key, vi_default)[i] for meta in merged]
                    self.video_infer_meta.append([meta for meta in vi_meta if meta is not None])
                self.video_desc_index = 0 if detail.get("total_{}".format(self.vd_key), 0) > 0 else None
                self.text_annot_index = 0 if detail.get("total_{}".format(self.ta_key), 0) > 0 else None
                self.text_infer_index = 0 if detail.get("total_{}".format(self.ti_key), 0) > 0 else None
                self.video_infer_indices = [0 if vi_index > 0 else None for vi_index in vi_indices]
                return True
            if mapping_file:
                LOGGER.info("Parsing class mapping file [%s]...", mapping_file)
                self.setup_mapper(mapping_file)
            if video_description and os.path.isfile(video_description):
                LOGGER.info("Parsing video description metadata [%s]...", video_description)
                self.video_desc_meta, video_desc_full_meta = self.parse_video_description_metadata(video_description)
                self.video_desc_index = 0
            elif video_description:
                LOGGER.warning("Skipping video description metadata file not found: [%s]", video_description)
            if video_inferences and isinstance(video_inferences, list):
                video_infer_full_meta = []
                for result in video_inferences:
                    if not os.path.isfile(result):
                        LOGGER.warning("Skipping video inference metadata file not found: [%s]", result)
                        continue
                    LOGGER.info("Parsing video inference metadata [%s]...", result)
                    meta, full_meta, multi = self.parse_video_inference_metadata(result)
                    video_infer_full_meta.append(full_meta)
                    if not self.video_infer_meta:
                        self.video_infer_meta = []
                        self.video_infer_indices = []
                        self.video_infer_multi = []
                    self.video_infer_meta.append(meta)
                    self.video_infer_indices.append(0)
                    self.video_infer_multi.append(multi)
            if text_annotations and os.path.isfile(text_annotations):
                LOGGER.info("Parsing text annotations metadata [%s]...", text_annotations)
                meta, full_meta = self.parse_text_annotations_metadata(text_annotations)
                text_method = ("auto" if text_auto else "manual") if isinstance(text_auto, bool) else "undefined"
                full_meta["method"] = text_method
                self.text_annot_meta, text_annot_full_meta = meta, full_meta
                self.text_annot_index = 0
            elif text_annotations:
                LOGGER.warning("Skipping text annotations metadata file not found: [%s]", text_annotations)
            if text_inferences and os.path.isfile(text_inferences):
                LOGGER.info("Parsing text inference metadata [%s]...", text_inferences)
                self.text_infer_meta, text_infer_full_meta = self.parse_text_inferences_metadata(text_inferences)
            elif text_inferences:
                LOGGER.warning("Skipping text inferences metadata file not found: [%s]", text_inferences)
            if merged_metadata_output:
                self.merge_metadata(video_desc_full_meta, video_infer_full_meta,
                                    text_annot_full_meta, text_infer_full_meta,
                                    self.video_desc_meta, self.video_infer_meta,
                                    self.text_annot_meta, self.text_infer_meta,
                                    merged_metadata_output, self.mapping_label, use_references)
        except Exception as exc:
            self.error = True
            LOGGER.error("Invalid formats. One or more metadata file could not be parsed.", exc_info=exc)
            return False
        return True

    def setup_mapper(self, path):
        """
        Setup label mapping with regex support.

        .. code-block:: YAML

            # replaces all labels with literal key match with the corresponding value
            "carry/hold (an object)": "carry/hold"

            # replaces all labels that have '<words> (an object)' by '<words> <something>'
            "(.+) \\(an object\\)": "\\1 <something>"

        .. seealso::
            - ``label_mapping.yml`` for more details and examples.

        """
        self.mapping_label = read_metafile(path)
        if self.mapping_label:
            LOGGER.info("\n  ".join(["Will use label mapping:"] +
                                    ["{}: {}".format(k, v) for k, v in self.mapping_label.items()]))
            self.mapping_regex = {}
            regexes = [(key, val) for key, val in self.mapping_label.items()
                       if "\\" in key or "\\" in val or any(p in key for p in [".*", ".+", ".?"])]
            for key, val in regexes:
                key = ("^" if not key.startswith("^") else "") + key + ("$" if not key.endswith("$") else "")
                self.mapping_regex[re.compile(key)] = val  # replace must be string for literal replace (no group)

    def map_label(self, label):
        """
        Replace label using provided mapping, with literal string match followed by regex substitution if applicable.
        """
        if not self.mapping_label:
            return label
        mapped = self.mapping_label.get(label)
        if mapped:
            return mapped
        for search, replace in self.mapping_regex.items():
            mapped = re.sub(search, replace, label)
            if mapped != label:
                return mapped
        return label

    def merge_metadata(self,
                       video_description_full_metadata, video_inference_full_metadata,
                       text_annotation_full_metadata, text_inferences_full_metadata,
                       video_description_time_metadata, video_inference_time_metadata,
                       text_annotation_time_metadata, text_inference_time_metadata,
                       merged_path, mapping, use_references):
        """
        Merges all provided metadata variations into a common file with timestamp alignment.

        .. seealso::
            :ref:`Metadata Merging <docs/usage.md#metadata-merging>` for full details and example.

        """
        if (
            not video_description_full_metadata and not video_description_time_metadata
            and not video_inference_full_metadata and not video_inference_time_metadata
            and not text_annotation_full_metadata and not text_annotation_time_metadata
            and not text_inferences_full_metadata and not text_inference_time_metadata
        ):
            LOGGER.error("No metadata provided, nothing to merge!")
            raise ValueError("Missing metadata")

        # define generic metadata details without the merged timestamped metadata
        metadata = {
            "version": self.version,
            "details": {self.vd_key: None, self.ta_key: None, self.ti_key: None, self.vi_key: None},
            "mapping": mapping,
            "merged": [],
        }
        if use_references:
            metadata[self.ref_section] = {
                self.vd_key: {}, self.ta_key: {}, self.vi_key: {}, self.ti_key: {},
                self.actors_key: {}, self.scenes_key: {}
            }

        if video_description_full_metadata:
            video_description_full_metadata.pop("standard_vd_metadata", None)
            video_description_full_metadata.pop("augmented_vd_metadata", None)
            metadata["details"][self.vd_key] = video_description_full_metadata
        if text_annotation_full_metadata:
            text_annotation_full_metadata.pop("data", None)
            metadata["details"][self.ta_key] = text_annotation_full_metadata
        if text_inferences_full_metadata:
            text_inferences_full_metadata.pop("data", None)
            metadata["details"][self.ti_key] = text_inferences_full_metadata
        if video_inference_full_metadata:
            for meta in video_inference_full_metadata:
                meta.pop("predictions", None)
                metadata["details"][self.vi_key] = video_inference_full_metadata

        def ref_link(meta_key, ref_id):
            return {"$ref": "#/{}/{}/{}".format(self.ref_section, meta_key, ref_id)}

        def make_ref(meta_entry, meta_key):
            """
            Generates the JSON link pointing to the metadata entry, and adds it to references if not already done.
            """
            meta_entry.setdefault(self.ref_key, str(uuid.uuid4()))
            ref_id = meta_entry[self.ref_key]
            refs = metadata[self.ref_section]  # type: Dict[str, Dict[str, Any]]
            if ref_id not in refs[meta_key]:
                refs[meta_key][ref_id] = meta_entry
            return ref_link(meta_key, ref_id)

        if use_references and metadata["details"][self.vd_key] is not None:
            # patch all existing VD references to use real JSON '$ref' instead of literal UUID placed as-is
            for meta_section in [self.actors_key, self.scenes_key]:
                section_items = metadata["details"][self.vd_key]["metadata"].pop(meta_section, [])  # noqa
                for meta_item in section_items:
                    make_ref(meta_item, meta_section)
                for vd in video_description_time_metadata:
                    for i in range(len(vd[meta_section])):
                        vd[meta_section][i] = ref_link(meta_section, vd[meta_section][i])

        # lookup timestamped metadata entries and combine them appropriately
        vd_index = None
        ta_index = None
        ti_index = None
        vi_indices = []
        if video_description_time_metadata:
            vd_index = 0
        else:
            video_description_time_metadata = []
        if text_annotation_time_metadata:
            ta_index = 0
        else:
            text_annotation_time_metadata = []
        if text_inference_time_metadata:
            ti_index = 0
        else:
            text_inference_time_metadata = []
        if video_inference_time_metadata:
            vi_indices = [0] * len(video_inference_time_metadata)
        else:
            video_inference_time_metadata = []

        def next_entry(meta_list, meta_index):
            """
            Finds the active metadata entry for any given metadata-type against current index and start/end times.
            """
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
        ti_total = len(text_inference_time_metadata)
        vi_totals = [len(vi_meta) for vi_meta in video_inference_time_metadata]
        while True:
            new_entry = {self.ts_key: None, self.te_key: None,
                         self.vd_key: None, self.ta_key: None, self.ti_key: None, self.vi_key: None}

            # find next entry for each metadata type against last time and current indices
            vd_entry, vd_index, vd_start, vd_end = next_entry(video_description_time_metadata, vd_index)
            ta_entry, ta_index, ta_start, ta_end = next_entry(text_annotation_time_metadata, ta_index)
            ti_entry, ti_index, ti_start, ti_end = next_entry(text_inference_time_metadata, ti_index)
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

            vd_txt = "(done)" if vd_index is None else "({}/{})".format(vd_index + 1, vd_total)
            ta_txt = "(done)" if ta_index is None else "({}/{})".format(ta_index + 1, ta_total)
            ti_txt = "(done)" if ti_index is None else "({}/{})".format(ti_index + 1, ti_total)
            vi_txt = ", ".join(["(done)" if vi_i is None else "({}/{})".format(vi_i + 1, vi_t)
                                for vi_i, vi_t in zip(vi_indices, vi_totals)])
            LOGGER.debug("Merged: VI [%s] TA [%s] TI [%s] VI [%s]", vd_txt, ta_txt, ti_txt, vi_txt)

            # check ending condition
            vd_done = vd_index is None or vd_index == vd_total
            ta_done = ta_index is None or ta_index == ta_total
            ti_done = ti_index is None or ti_index == ti_total
            vi_done = all(vi_indices[i] is None or vi_indices[i] == vi_totals for i, total in enumerate(vi_totals))
            done = [vd_done, ta_done, ti_done, vi_done]
            if not len(done) or all(done):
                break

            # first time could be different than zero if all items started with an offset
            if first_time is None:
                start_times = [vd_start, ta_start, ti_start] + vi_start_multi
                first_time = round(min(filter(lambda start: start is not None, start_times)), self.precision)
                last_time = first_time

            # find next loop start time with first end time of current iteration to find next cut point
            # ignore exhausted end times if last item from its metadata list was passed
            end_times = [vd_end, ta_end, ti_end] + vi_end_multi
            end_time = round(min(filter(lambda end: end is not None, end_times)), self.precision)

            # remove entries until the first entry of corresponding type is reached
            vd_entry = vd_entry if vd_entry and end_time >= vd_start else None
            ta_entry = ta_entry if ta_entry and end_time >= ta_start else None
            ti_entry = ti_entry if ti_entry and end_time >= ti_start else None
            vi_entries = [
                vi_entry if vi_entry and end_time >= vi_start else None
                for vi_entry, vi_start in zip(vi_entries, vi_start_multi)
            ]
            if all(entry is None for entry in [vd_entry, ta_entry, ti_entry] + vi_entries):
                continue

            # apply resolved merged start/end times
            new_entry[self.ts_key] = last_time  # new entry starts where last one finished
            new_entry[self.te_key] = end_time
            new_entry["start"] = last_time / 1000.
            new_entry["end"] = end_time / 1000.
            new_entry["TS"] = [seconds2timestamp(new_entry["start"]), seconds2timestamp(new_entry["end"])]

            # update current metadata entry, empty if time is lower/greater than current portion
            # start times need to be computed after 'next_entry' call to find the start time of all meta portions
            if use_references:
                new_entry[self.vd_key] = make_ref(vd_entry, self.vd_key) if vd_entry else None
                new_entry[self.ta_key] = make_ref(ta_entry, self.ta_key) if ta_entry else None
                new_entry[self.ti_key] = make_ref(ti_entry, self.ti_key) if ti_entry else None
                new_entry[self.vi_key] = [make_ref(vi_entries[i], self.vi_key) if vi_entries[i] else None
                                          for i in range(len(vi_entries))]
            else:
                new_entry[self.vd_key] = vd_entry
                new_entry[self.ta_key] = ta_entry
                new_entry[self.ti_key] = ti_entry
                new_entry[self.vi_key] = vi_entries

            # add to list of merged metadata
            new_entry[self.ts_key] = last_time
            new_entry[self.te_key] = end_time
            metadata["merged"].append(new_entry)
            last_time = end_time

        # add extra metadata and save to file
        merged = metadata["merged"]  # type: List[Dict[str, Any]]
        total_merged = len(merged)
        total_merged_vd = len([meta for meta in merged if meta[self.vd_key] is not None])
        total_merged_ta = len([meta for meta in merged if meta[self.ta_key] is not None])
        total_merged_ti = len([meta for meta in merged if meta[self.ti_key] is not None])
        total_merged_vi = [len([meta for meta in merged if meta[self.vi_key][i] is not None])
                           for i in range(len(vi_indices))]
        # rewrite details to have summary on top, followed by specific ones of each metadata type after
        detail = {
            self.ts_key: first_time,
            self.te_key: last_time,
            "start": first_time / 1000.,
            "end": last_time / 1000.,
            "TS": [seconds2timestamp(first_time / 1000.), seconds2timestamp(last_time / 1000.)],
            "total_merged": total_merged,
            "total_merged_{}".format(self.vd_key): total_merged_vd,
            "total_merged_{}".format(self.ta_key): total_merged_ta,
            "total_merged_{}".format(self.ti_key): total_merged_ti,
            "total_merged_{}".format(self.vi_key): total_merged_vi,
            "total_{}".format(self.vd_key): vd_total,
            "total_{}".format(self.ta_key): ta_total,
            "total_{}".format(self.ti_key): ti_total,
            "total_{}".format(self.vi_key): vi_totals,
        }
        detail.update(metadata["details"])
        metadata["details"] = detail
        LOGGER.debug("Total amount of merged metadata entries: %s", total_merged)
        LOGGER.info("Generating merged metadata file: [%s]", merged_path)
        write_metafile(metadata, merged_path)

    def parse_video_description_metadata(self, metadata_path):
        try:
            metadata = read_metafile(metadata_path)
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
            metadata = read_metafile(metadata_path)
            # ensure ordered by time
            predictions = list(sorted(metadata["predictions"], key=lambda p: p["start"]))
            multi_preds = metadata.get("multi_predictions", False)
            # convert times to ms for same base comparisons
            for pred in predictions:
                pred[self.ts_key] = round(pred["start"] * 1000, self.precision)
                pred[self.te_key] = round(pred["end"] * 1000, self.precision)
                for region in pred["regions"] if multi_preds else [pred]:
                    labels = region["classes"]
                    for i, _ in enumerate(region["classes"]):
                        labels[i] = self.map_label(labels[i])
            return predictions, metadata, multi_preds
        except Exception as exc:
            LOGGER.error("Could not parse video inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    def parse_text_inferences_metadata(self, metadata_path):
        """
        Parse TSV formatted text inference actions for different mapping techniques.

        :returns:
            tuple of:
            - subset of the parsed text action inferences
            - full metadata loaded
        """
        try:
            metadata = read_metafile(metadata_path)
            map_types = metadata[0][2:]  # 0: TS/TE, 1: action, 2..: mappings
            map_none = ["-", "_", ""]    # values considered as 'no-result'
            has_prox = map_types[-1] == "prox"
            if has_prox:
                map_types = map_types[:-1]
            metadata = metadata[1:]
            mappings = []
            for line in metadata:
                str_ts, str_te = line[0].split(";")
                ts = parse_timestamp(str_ts)
                te = parse_timestamp(str_te)
                sec_s = timestamp2seconds(ts)
                sec_e = timestamp2seconds(te)
                meta = {
                    self.ts_key: round(sec_s * 1000., self.precision),
                    self.te_key: round(sec_e * 1000., self.precision),
                    "start": sec_s,
                    "end": sec_e,
                    "TS": [str_ts, str_te],
                    "action": line[1],
                    "mappings": []
                }
                mapped = line[2:-1] if has_prox else line[2:]
                for name, values in zip(map_types, mapped):
                    map_values = [None if val in map_none else val for val in values.split(";")]
                    meta["mappings"].append({"type": name, "actions": map_values})
                    if name == "gold" and has_prox:
                        proximity = line[-1] if line[-1] not in map_none else 0
                        meta["mappings"][-1]["proximity"] = proximity
                mappings.append(meta)
            full_meta = {
                "data": mappings,
                "types": map_types,
                "proximity": has_prox,
            }
            return mappings, full_meta
        except Exception as exc:
            LOGGER.error("Could not parse text inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None

    def parse_text_annotations_metadata(self, metadata_path):
        """
        Parse various version of JSON text annotation files into a common list of employable items.

        Versions:
            1. Original format that provides ``annotations`` as list of objects with ``lemme``, ``POS`` and ``type``.
            2. Replaces ``annotations`` by ``annot_sentence``, and provides ``sentence`` directly.
            3. Support different format by field lists and renamed fields.

        :returns:
            tuple of:
            - subset of the parsed/corrected list of annotations
            - full metadata loaded, with added version detected
        """
        try:
            metadata = read_metafile(metadata_path)
            annotations = metadata["data"]
            for annot in annotations:
                # convert TS: [start,end] -> (ts, te) in milliseconds
                ts_s = parse_timestamp(annot["TS"][0])
                ts_e = parse_timestamp(annot["TS"][1])
                sec_s = timestamp2seconds(ts_s)
                sec_e = timestamp2seconds(ts_e)
                annot[self.ts_key] = round(sec_s * 1000., self.precision)
                annot[self.te_key] = round(sec_e * 1000., self.precision)
                annot["start"] = sec_s
                annot["end"] = sec_e
                # extend 2D list into sentences/words metadata and drop redundant VD
                vd_paragraph = annot.pop("vd", "")

                # v1 format only provides annotations directly (the 'words' with POS, lemme, type)
                # uses a 2D list of annotations for individually annotated sentences, but they are not provided:
                #   {"annotations": [[ { "POS": "", "lemme": "", "type": "" }, { ... } ], ... ]

                # v2 format contains the annotated sentence and corresponding annotations within this definition
                # they also employ the target format directly, except they use "annot_sentence" instead of "words"
                #   {"annotations": [{ "sentence": "", "annot_sentence": [{ "POS": "", "lemme": "", "type": "" }] }] }

                # v3 ensures precise annotations for every item, detect it and use them right away
                if "annot_precises" in annot:
                    metadata.setdefault("version", 3)
                    annot_key = "annot_precises"
                    token_key = "tokens"
                    is_precise = True
                # v4 format equivalent to v3 format uses "annotations" directly instead of "annot_precises"
                # distinguish from v2 "annotations" by looking for sub-field "annot_sentence"
                # distinguish from v1 "annotations" by format (2D list instead of list of dict)
                elif ("annotations" in annot
                      and not any(isinstance(a, list) for a in annot["annotations"])
                      and not any("annot_sentence" in a for a in annot["annotations"])):
                    metadata.setdefault("version", 4)
                    annot_key = "annotations"
                    token_key = "tokens"
                    is_precise = True
                else:
                    annot_key = "annotations"
                    token_key = "words"
                    is_precise = False
                annot_list = list(annot.pop(annot_key))  # ensure copy to avoid edit error while iterating
                annot_flat = [a for aa in annot_list for a in aa]  # flatten v1 2D list to check if is empty

                # skip empty annotations
                if (not annot_list or not annot_flat
                        or all("annot_sentence" in a and not a["annot_sentence"] for a in annot_list)):
                    annot["annotations"] = []
                    continue
                # parse v2/v3/v4
                elif is_precise or all("sentence" in a and "annot_sentence" in a for a in annot_list):
                    # show mismatches between v2 format sentences and how heuristics normally parse them in v1 format
                    # don't update them though if they exist, we employ provided sentences directly
                    metadata.setdefault("version", 2)
                    self.parse_diff_sentences(vd_paragraph, annot_list)
                    sentences = [annot_sentence["sentence"] for annot_sentence in annot_list]
                    if is_precise:
                        # v3 are already at the right level, but require of rewrite of structure format
                        annot_list = self.extract_sentence_tokens(annot_list)
                    else:
                        # v2 already offers a sub-list of partial 'token' objects for each annotated sentence
                        # bump structure upward since we are already processing per-sentence
                        annot_list = [annot_sentence["annot_sentence"] for annot_sentence in annot_list]
                # parse v1
                else:
                    # convert of 2D-list to list of object is done inline while extracting corresponding sentences
                    # sentences use the heuristics split from the VD
                    sentences, annot_list = self.parse_split_sentences(vd_paragraph, annot_list)
                annot["annotations"] = [{"sentence": s, token_key: a} for s, a in zip(sentences, annot_list)]

            # wait until all possible cases were considered to set the version
            # in case intermediate annotation somehow did not provide 'annot_sentence' that detects v2
            metadata.setdefault("version", 1)
            return list(sorted(annotations, key=lambda _a: _a[self.ts_key])), metadata

        except Exception as exc:
            LOGGER.error("Could not parse text inference metadata file: [%s]", metadata_path, exc_info=exc)
        return None, None

    @staticmethod
    def parse_diff_sentences(vd_paragraph, annotation_list):
        if not LOGGER.isEnabledFor(logging.DEBUG):
            return
        try:
            sentences_annot = [annot["sentence"] for annot in annotation_list]
            sentences_parsed = split_sentences(vd_paragraph)
            if sentences_parsed != sentences_annot:
                diff = difflib.context_diff(sentences_parsed, sentences_annot,
                                            fromfile="VD Split Sentences", tofile="Annotated Sentences")
                LOGGER.debug("Found mismatch sentences:\n  %s", "\n  ".join(diff))
        except Exception:  # noqa
            pass  # ignore failure as this parsing is only to attempt informing about found differences, not critical

    @staticmethod
    def parse_split_sentences(vd_paragraph, annotation_list):
        sentences = split_sentences(vd_paragraph)
        # note:
        #  Original annotations sometime have errors due to capital letters incorrectly interpreted
        #  as beginning of new sentence.
        #  Sometimes, they are instead missing some annotations against the number of sentences.
        #  Patch them as best as possible.
        while len(sentences) != len(annotation_list):
            if len(sentences) > len(annotation_list):
                # pad extra empty annotations where no lemme can be matched within the current sentence
                # if matched, move to next to find the best index at which to insert empty annotations
                i = 0
                for i, s in enumerate(sentences):
                    if i >= len(annotation_list):
                        break
                    if not any([a["lemme"].replace("_", " ") in s for a in annotation_list[i]]):
                        break
                annotation_list.insert(i, [])
            else:
                # merge over abundant annotations
                annotation_list[0].extend(annotation_list.pop(1))
        return sentences, annotation_list

    @staticmethod
    def extract_sentence_tokens(annotation_list):
        """
        Parses Text Annotation V3 format into similar format of previous merge result.

        Converts annotation tokens per sentence as (dict of field-lists of same lengths) to the corresponding
        (list of token objects with respective fields), which matches previous merging formats, with additional fields.
        The result is filtered out of any redundant details always expected to be available at higher level.
        """
        sentence_tokens = []
        for i, sentence in enumerate(annotation_list):
            sentence_tokens.append([])
            for tkt in range(len(sentence["token"])):
                # transfer items
                sentence_tokens[-1].append({})
                token = sentence_tokens[-1][tkt]
                for field in sentence:
                    if field in ["TS", "annot", "sentence"]:
                        continue  # ignore redundant metadata already available in parent
                    token[field] = sentence[field][tkt]
                # rewrite field formats
                offset = token["offset"].split(" ")
                token["offset"] = {"start": int(offset[0]), "end": int(offset[1])}
        return sentence_tokens


def make_parser():
    formatter = lambda prog: argparse.HelpFormatter(prog, width=120)  # noqa
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True, formatter_class=formatter)  # noqa
    main_args = ap.add_argument_group(title="Main Arguments", description="Main arguments")
    video_arg = main_args.add_mutually_exclusive_group()
    video_arg.add_argument("--video", "--vf", dest="video_file", help="Video file to view.")
    video_arg.add_argument("--no-video", action="store_true",
                           help="Disable video. Employ only metadata parsing. "
                                "Must be combined with merged metadata output.")
    meta_args = ap.add_argument_group(title="Metadata Annotation Arguments",
                                      description="Arguments for annotation and inference metadata files.")
    meta_mode = meta_args.add_mutually_exclusive_group()
    meta_mode.add_argument("--input-metadata", "--meta", dest="merged_metadata_input",
                           help="Pre-generated merged metadata file to load. "
                                "Cannot be combined with other metadata sources.")
    meta_multi = meta_mode.add_argument_group()
    meta_multi.add_argument("--video-description", "--vd", dest="video_description",
                            help="JSON/YAML metadata file with original video-description annotations.")
    meta_multi.add_argument("--video-inference", "--vi", dest="video_inferences",
                            nargs="*", action="append", default=[],
                            help="JSON/YAML metadata file(s) with video action recognition inference results. "
                                 "If multiple files are provided, they will be simultaneously displayed side-by-side.")
    meta_multi.add_argument("--text-annotation", "--ta", dest="text_annotations",
                            help="JSON/YAML metadata file with text subjects and verbs annotations.")
    meta_multi.add_argument("--text-inference", "--ti", dest="text_inferences",
                            help="TSV metadata file that contains text annotations mapping between actions "
                                 "and inferred values by other lexical resources or embeddings.")
    annot_mode = meta_multi.add_mutually_exclusive_group()
    annot_mode.add_argument("--text-auto", dest="text_auto", action="store_true", default=None,
                            help="Indicate that the provided text annotations where generated automatically. "
                                 "If not explicitly defined as automatic/manual, the result will indicate 'undefined'.")
    annot_mode.add_argument("--text-manual", dest="text_auto", action="store_false", default=None,
                            help="Indicate that the provided text annotations where generated manually. "
                                 "If not explicitly defined as automatic/manual, the result will indicate 'undefined'.")

    util_opts = ap.add_argument_group(title="Utility Options",
                                      description="Options that configure extra functionalities.")
    util_opts.add_argument("--output", "-o", default="/tmp/video-result-viewer",
                           help="Output location of frame snapshots (default: [%(default)s]).")
    util_opts.add_argument("--merged", "-m", dest="merged_metadata_output",
                           help="Output path of generated merged metadata JSON/YAML file from all other metadata files "
                                "from different sources with realigned timestamps of corresponding sections. "
                                "Disabled if input metadata is already a merged file (--input-metadata).")
    util_opts.add_argument("--references", "-R", dest="use_references", default=False, action="store_true",
                           help="Indicates if JSON references ($ref) should be employed when generating merged "
                                "metadata to avoid repeating elements. The merged content will use UUID links pointing "
                                "to references that overlap across sections instead of copying them.")
    util_opts.add_argument("--mapping", "--map", "-M", dest="mapping_file",
                           help="JSON/YAML file with class name mapping. When provided, class names within "
                                "text annotations and video inference metadata that correspond to a given key will "
                                "be replaced for rendering and merged output by the respective value.")
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
    if ns.no_video and not ns.merged_metadata_output:
        LOGGER.error("Merged metadata file is required when no video is employed (only process metadata).")
        return -1
    if ns.no_video and ns.merged_metadata_input:
        LOGGER.error("Merged metadata file as input cannot be viewed without a video.")
        return -1
    for rm_arg in ["debug", "quiet", "no_video"]:
        args.pop(rm_arg, None)
    # flatten video inferences regardless of multi-files after single '--vi' or with repeated '--vi' options
    args["video_inferences"] = [vi for vi_list in args["video_inferences"] for vi in vi_list]
    return VideoResultPlayerApp(**args)  # auto-map arguments by name


if __name__ == "__main__":
    main()
