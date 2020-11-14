"""
Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results.
"""
import argparse
import json
import logging
import math
import os
import queue
import sys
import time
import threading

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
        while self.started:
            if not self.queue.full():
                grabbed, frame = self.video.read()
                if not grabbed:
                    return
                with self.read_lock:
                    index = int(self.get(cv.CAP_PROP_POS_FRAMES))
                    msec = self.get(cv.CAP_PROP_POS_MSEC)
                    self.queue.put((grabbed, frame.copy(), index, msec))

    def seek(self, frame_index):
        self.stop()
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
    frame_queue = 128
    frame_delta = None
    frame_index = None
    frame_count = None
    frame_output = None
    last_time = 0
    next_time = 0
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
    video_slider = None
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

    def __init__(self, video_file, video_annotations, video_results, text_results, output=None, scale=1.0, queue=128):
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
        if queue > 1:
            LOGGER.debug("Setting queue size: %s", queue)
            self.frame_queue = queue

        self.setup_player()
        self.setup_window()
        if not self.setup_metadata(video_annotations, video_results, text_results):
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
        self.window = tk.Tk()
        self.window.title("Result Viewer")
        # Create a canvas that can fit the above video source size
        display_width = self.video_width * self.video_scale
        display_height = self.video_height * self.video_scale
        self.video_viewer = tk.Canvas(self.window, width=display_width, height=display_height)
        self.video_viewer.pack(anchor=tk.NW)
        self.video_slider = tk.Scale(self.window, from_=0, to=self.frame_count - 1, length=display_width,
                                     tickinterval=self.frame_count // 10, orient=tk.HORIZONTAL,
                                     repeatinterval=1, repeatdelay=1, command=self.seek_frame)
        self.video_slider.bind("<Button-1>", self.trigger_seek)
        self.video_slider.pack(side=tk.LEFT)

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
        self.video_infer_textbox.pack(side=tk.BOTTOM)
        self.video_infer_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_infer_label = tk.Label(self.window, text="Text Inference Metadata", font=self.font_header)
        self.text_infer_label.pack(side=tk.BOTTOM)
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

    def trigger_seek(self, event):
        coord_min = self.video_slider.coords(0)
        coord_max = self.video_slider.coords(self.frame_count)
        if self.video_slider.identify(event.x, event.y) == "slider":
            return  # ignore event when clicking directly on the slider
        if event.x <= coord_min[0]:
            index = 0
        elif event.x >= coord_max[0]:
            index = self.frame_count - 1
        else:
            ratio = float(self.frame_count) / float(coord_max[0] - coord_min[0])
            index = int((event.x - coord_min[0]) * ratio)
        LOGGER.debug("Seek frame %s from click event (%s, %s) between [%s, %s]",
                     index, event.x, event.y, coord_min, coord_max)
        self.seek_frame(index)

    def toggle_playing(self):
        if self.play_state:
            self.play_text.set("PLAY")
            LOGGER.debug("Video paused.")
        else:
            self.play_text.set("PAUSE")
            LOGGER.debug("Video resume.")
        self.play_state = not self.play_state

    def update_annotation(self, metadata):
        if metadata is None:
            text = "<no-data>"
        else:
            text = metadata["vd"]
        self.video_annot_textbox.delete("1.0", tk.END)
        self.video_annot_textbox.insert(tk.END, text, "normal")

    def update_infer_video(self, metadata):
        if metadata is None:
            text = "<no-data>"
        else:
            header = "[Score] [Classes]\n\n  "
            values = "\n  ".join(["[{:.2f}] {})".format(s, c) for c, s in zip(metadata["classes"], metadata["scores"])])
            text = header + values
        self.video_infer_textbox.delete("1.0", tk.END)
        self.video_infer_textbox.insert(tk.END, text, "normal")

    def update_infer_text(self, metadata):
        if metadata is None:
            text = "<no-data>"
        else:
            text = json.dumps(metadata, indent=2, ensure_ascii=False)
        self.text_infer_textbox.delete("1.0", tk.END)
        self.text_infer_textbox.insert(tk.END, text, "normal")

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
                        if self.frame_time >= current_meta["start_ms"]:
                            updated_index = index
                            break
                elif self.frame_time > current_meta["end_ms"]:
                    # otherwise bump to next one if timestamp of the current is passed
                    updated_index = current_index + 1

                if meta_index < index_total - 1:
                    meta_updater(meta_container[updated_index])
                else:
                    meta_updater(None)
                return updated_index
            return None

        self.video_annot_index = update_meta(self.video_annot_meta, self.video_annot_index, self.update_annotation)
        self.video_infer_index = update_meta(self.video_infer_meta, self.video_infer_index, self.update_infer_video)
        self.text_infer_index = update_meta(self.text_infer_meta, self.text_infer_index, self.update_infer_text)

    def update_video(self):
        """
        Periodic update of video frame. Self-calling.
        """
        self.next_time = time.perf_counter()

        if not self.play_state:
            self.window.after(30, self.update_video)
            return

        grabbed, frame, self.frame_index, self.frame_time = self.video.read()
        if not grabbed:
            LOGGER.error("Playback error occurred when reading next video frame.")
            self.error = True
            return

        frame_dims = (self.video_width, self.video_height)
        if self.video_scale != 1:
            frame_dims = (int(self.video_width * self.video_scale), int(self.video_height * self.video_scale))
            frame = cv.resize(frame, frame_dims, interpolation=cv.INTER_NEAREST)
        self.update_metadata()

        # default if cannot be inferred from previous time
        next_time = time.perf_counter()
        call_time_delta = next_time - self.last_time
        self.last_time = next_time
        wait_time_delta = 1 if call_time_delta > self.frame_delta else max(self.frame_delta - call_time_delta, 0)
        fps = 1. / call_time_delta
        LOGGER.debug("Frame: %8s, Last: %8.2f, Time: %8.2f, Real Delta: %6.2fms, "
                     "Call Delta: %6.2fms, Target Delta: %6.2fms, Real FPS: %6.2f WxH: %s",
                     self.frame_index, self.last_time, self.frame_time, wait_time_delta,
                     call_time_delta * 1000., self.frame_delta, fps, frame_dims)

        # display basic information
        text_position = (10, 25)
        text_delta = 40
        font_scale = 0.5
        font_color = (209, 80, 0, 255)
        font_stroke = 1
        text = "Title: {}, Target FPS: {}, Real FPS: {:0.2f}".format(self.video_title, self.frame_fps, fps)
        cv.putText(frame, text, text_position, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)
        text_position = (text_position[0], text_position[1] + int(text_delta * font_scale))
        cur_sec = self.frame_time / 1000.
        tot_sec = self.video_duration / 1000.
        cur_hms = time.strftime("%H:%M:%S", time.gmtime(cur_sec))
        tot_hms = time.strftime("%H:%M:%S", time.gmtime(tot_sec))
        text = "Time: {:0>.2f}/{:0.2f} ({}/{}) Frame: {}".format(cur_sec, tot_sec, cur_hms, tot_hms, self.frame_index)
        cv.putText(frame, text, text_position, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)

        # note: 'self.frame' is important as without instance reference, it gets garbage collected and is not displayed
        self.video_frame = frame  # in case of snapshot
        self.frame = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(cv.cvtColor(frame, cv.COLOR_RGB2BGR)))
        self.video_viewer.create_image(0, 0, image=self.frame, anchor=tk.NW)
        self.video_slider.set(self.frame_index)
        self.window.after(math.floor(wait_time_delta), self.update_video)

    def seek_frame(self, frame_index):
        """
        Moves the video to the given frame index and fetches metadata starting at that moment.
        """
        frame_index = int(frame_index)
        self.frame_time = self.video.seek(frame_index)
        self.frame_index = frame_index
        self.video_slider.set(frame_index)
        self.update_metadata(seek=True)

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
    ap = argparse.ArgumentParser(prog=__NAME__, description=__doc__, add_help=True)
    main_args = ap.add_argument_group(title="Main Arguments",
                                      description="Main arguments")
    main_args.add_argument("video_file", help="Video file to view.")
    main_args.add_argument("--video-description", "--vd", dest="video_annotations",
                           help="JSON metadata file with original video-description annotations.")
    main_args.add_argument("--video-inference", "--vi", dest="video_results",
                           help="JSON metadata file with video actions inference results.")
    main_args.add_argument("--text-inference", "--ti", dest="text_results",
                           help="JSON metadata file with text subjects and verbs results.")
    util_opts = ap.add_argument_group(title="Utility Options",
                                      description="Options that configure extra functionalities.")
    util_opts.add_argument("--output", "-o", default="/tmp/video-result-viewer",
                           help="Output location of frame snapshots.")
    video_opts = ap.add_argument_group(title="Video Options",
                                       description="Options that configure video processing.")
    video_opts.add_argument("--scale", "-s", type=float, default=1.0,
                            help="Scale video for bigger/smaller display (warning: impacts FPS).")
    video_opts.add_argument("--queue", "-q", type=int, default=128,
                            help="Queue size to attempt preloading frames (warning: impacts FPS).")
    video_opts.add_argument("--debug", "-d", action="store_true", help="Debug logging.")
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
