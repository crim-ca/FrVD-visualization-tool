"""
Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results.
"""
import argparse
import json
import logging
import os
import sys

import cv2 as cv
import tkinter as tk

__NAME__ = os.path.splitext(os.path.split(__file__)[-1])[0]
LOGGER = logging.getLogger(__NAME__)
LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)-10.10s [%(threadName)s][%(name)s] %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


def parse_video_annotation_metadata(metadata_path, playback):
    try:
        with open(metadata_path) as meta_file:
            metadata = json.load(meta_file)
        meta = metadata.get("metadata_files", {})
        title = meta.get("serie_name") or meta.get("film_export_subpath")
        episode = meta.get("serie_episode_number", "")
        collection = meta.get("serie_collection_name") or meta.get("film_collection_name")

        LOGGER.debug("Updating video name")
        episode_str = " - {}".format(episode) if episode else ""
        playback["title"] = "[{}] {}{}".format(collection, title, episode_str)



        return metadata
    except Exception as exc:
        LOGGER.error("Could not parse video annotation metadata file: [%s]", metadata_path, exc_info=exc)
    return None


def parse_video_inference_metadata(metadata_path, playback):
    try:
        with open(metadata_path) as meta_file:
            metadata = json.load(meta_file)
        # ensure ordered by time
        metadata["predictions"] = list(sorted(metadata["predictions"], key=lambda p: p["start"]))

        # ease retrieval of active prediction against current video frame
        fps = playback["fps"]
        delta_ms = playback["frame_msec"]
        cumul_ms = 0.
        count = playback["frame_count"]
        total = delta_ms
        frame = 0
        for pred in metadata["predictions"]:
            if pred["start"] > delta_ms:
                frame_i += 1
            pred["frame"] = frame_i
            cumul_ms += pred["end"]
        return metadata
    except Exception as exc:
        LOGGER.error("Could not parse video inference metadata file: [%s]", metadata_path, exc_info=exc)
    return None


def parse_text_inference_metadata(metadata_path, playback):
    try:
        pass
    except Exception as exc:
        LOGGER.error("Could not parse text inference metadata file: [%s]", metadata_path, exc_info=exc)
    return None


def run(video_file, video_annotations, video_results, text_results):
    video_file = os.path.abspath(video_file)
    if not os.path.isfile(video_file):
        raise ValueError("Cannot find video file: [{}]".format(video_file))
    LOGGER.info("Using video file: %s", video_file)
    video_title = os.path.splitext(os.path.split(video_file)[-1])[0]  # best name available, adjust after if possible

    LOGGER.info("Creating player...")
    window_name = "Video"
    cv.namedWindow(window_name, cv.WINDOW_NORMAL)
    playback = {"video": cv.VideoCapture(video_file), "frame": 0, "time": 0.0}
    playback["fps"] = int(playback["video"].get(cv.CAP_PROP_FPS))
    playback["frame_msec"] = 1. / float(playback["fps"]) * 1000.
    playback["frame_count"] = int(playback["video"].get(cv.CAP_PROP_FRAME_COUNT))
    playback["duration"] = playback["frame_msec"] * playback["frame_count"]

    def get_frame(i_frame):
        LOGGER.debug("Move to frame %s", i_frame)
        playback["frame"] = i_frame
        playback["video"].set(cv.CAP_PROP_POS_FRAMES, i_frame)

    def set_speed(speed):
        playback["fps"] = max(speed, 1)
        LOGGER.debug("Adjusted speed to %s", playback["fps"])

    track_name = "Frame"
    speed_name = "Speed"
    cv.createTrackbar(track_name, window_name, 0, playback["frame_count"], get_frame)
    cv.createTrackbar(speed_name, window_name, playback["fps"], 100, set_speed)

    # parse available metadata files
    if video_annotations and os.path.isfile(video_annotations):
        LOGGER.info("Parsing video inference metadata [%s]...", video_annotations)
        parse_video_annotation_metadata(video_annotations, playback)
    if video_results and os.path.isfile(video_results):
        LOGGER.info("Parsing video inference metadata [%s]...", video_results)
        parse_video_inference_metadata(video_results, playback)
    if text_results and os.path.isfile(text_results):
        LOGGER.info("Parsing text inference metadata [%s]...", text_results)
        parse_text_inference_metadata(text_results, playback)

    LOGGER.info("Playing...")
    ret = True
    while ret:
        ret, frame = playback["video"].read()
        if not ret:
            LOGGER.error("Playback error occurred when reading next video frame.")
            break
        playback["time"] = playback["video"].get(cv.CAP_PROP_POS_MSEC)
        playback["frame"] = int(playback["video"].get(cv.CAP_PROP_POS_FRAMES))

        # display basic information
        text_position = (10, 30)
        text_delta = 40
        font_scale = 0.5
        font_color = (209, 80, 0, 255)
        font_stroke = 2
        cv.putText(frame, "Title: {}, FPS: {}, Frame: {}".format(video_title, playback["fps"], playback["frame"]),
                   text_position, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)
        text_position = (text_position[0], text_position[1] + int(text_delta * font_scale))
        cv.putText(frame, "Time: {:0>.2f}/{:0.2f}".format(playback["time"] / 1000., playback["duration"] / 1000.),
                   text_position, cv.FONT_HERSHEY_SIMPLEX, font_scale, font_color, font_stroke)

        # display video metadata information
        # TODO


        # display inference metadata information

        # update video and slider positions on trackbar
        cv.imshow("Video", frame)
        cv.setTrackbarPos(track_name, window_name, int(playback["video"].get(cv.CAP_PROP_POS_FRAMES)))

        # handle key captures or move to next frame
        key = cv.waitKey(int(playback["frame_msec"]))
        if key & 0xFF == ord("p"):
            LOGGER.info("Pause")
            while True:
                # wait for resume
                key = cv.waitKey(0)
                if key & 0xFF == ord("p"):
                    LOGGER.info("Resume")
                    break

        if key & 0xFF == ord("q"):
            LOGGER.info("Quit")
            break

    LOGGER.log("Exit", level=logging.INFO if ret else logging.ERROR)
    playback["video"].release()
    cv.destroyAllWindows()


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
