import csv
import cv2 as cv
import json
import tkinter as tk
import yaml
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import jsonref

if TYPE_CHECKING:
    from typing import List, Union


def read_metafile(path):
    with open(path) as meta_file:
        if path.endswith(".tsv"):
            reader = csv.reader(meta_file, delimiter="\t", quotechar='"')
            metadata = [line for line in reader]
        elif path.endswith(".json"):
            metadata = jsonref.load(meta_file)
        else:
            metadata = yaml.safe_load(meta_file)
            metadata = jsonref.JsonRef.replace_refs(metadata)
    return metadata


def write_metafile(metadata, path):
    with open(path, "w") as meta_file:
        if path.endswith(".json"):
            json.dump(metadata, meta_file, indent=4, ensure_ascii=False)
        else:
            yaml.safe_dump(metadata, meta_file)


def split_sentences(text):
    # type: (str) -> List[str]
    """
    Heuristic to generate the list of sentences from a paragraph.
    """
    punctuations = [".", "!", "?"]
    for stop in punctuations:
        text = text.replace("{} ".format(stop), "{}<STOP>".format(stop))
    sentences = text.split("<STOP>")
    sentences = [s + "." if s[-1] not in punctuations else s for s in sentences if s]
    return sentences


def parse_timestamp(timestamp):
    # type: (str) -> datetime
    """
    Parses a timestamp with flexible formats.
    """
    try:
        return datetime.strptime(timestamp, "T%H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(timestamp, "T%H:%M:%S")


def timestamp2seconds(ts):
    # type: (datetime) -> float
    """
    Converts the timestamp into seconds duration.
    """
    return float("{}.{}".format((ts.hour * 3600 + ts.minute * 60 + ts.second), ts.microsecond))


def seconds2timestamp(sec):
    # type: (Union[int, float]) -> str
    """
    Converts seconds into the corresponding ISO time.
    """
    assert sec <= 86400, "Unsupported seconds longer then a day."
    ts = str(timedelta(seconds=sec))
    if (len(ts.split(".")[0])) == 7:
        ts = "0" + ts
    return "T" + ts


def draw_bbox(image, tl, br, text, color,
              box_thickness=2, box_contour=True, box_dash_gap=None,
              font_thickness=1, font_scale=0.4, font_contour=True):
    """
    Draws a single bounding box on a given image with added text label in the corner.
    """
    # fix float positions
    tl = (round(float(tl[0])), round(float(tl[1])))
    br = (round(float(br[0])), round(float(br[1])))

    # draw label with background rectangle to ensure it is visible
    text_size, baseline = cv.getTextSize(text, fontFace=cv.FONT_HERSHEY_SIMPLEX,
                                         fontScale=font_scale, thickness=font_thickness)
    text_bl = (tl[0] + box_thickness + 1, tl[1] + text_size[1] + box_thickness + 1)
    # note: text will overflow if box is too small
    text_box_br = (text_bl[0] + text_size[0] + box_thickness, text_bl[1] + box_thickness * 2)
    cv.rectangle(image, (tl[0] - 1, tl[1] - 1), (text_box_br[0] + 1, text_box_br[1] + 1),
                 color=(0, 0, 0), thickness=-1)
    if box_contour:
        cv.rectangle(image, tl, br, color=(0, 0, 0), thickness=box_thickness + 1)
    cv.rectangle(image, tl, text_box_br, color=color, thickness=-1)
    # label text itself can be either white with black contour,
    # or simply black assuming lighter rectangle background color
    if font_contour:
        cv.putText(image, text, text_bl, fontFace=cv.FONT_HERSHEY_SIMPLEX, fontScale=font_scale,
                   color=(0, 0, 0), thickness=font_thickness + 1)
        cv.putText(image, text, text_bl, fontFace=cv.FONT_HERSHEY_SIMPLEX, fontScale=font_scale,
                   color=(255, 255, 255), thickness=font_thickness)
    else:
        cv.putText(image, text, text_bl, fontFace=cv.FONT_HERSHEY_SIMPLEX, fontScale=font_scale,
                   color=(0, 0, 0), thickness=font_thickness)

    # draw surrounding box
    if isinstance(box_dash_gap, int):
        x1, y1, x2, y2 = tl[0], tl[1], br[0], br[1]
        dx = x1
        dy = y1
        corner = 2  # leave some space for a single dot in corners
        while dx + corner < x2:
            cv.line(image, (dx, y1), (dx + corner, y1), color, box_thickness, lineType=8, shift=0)
            cv.line(image, (dx, y2), (dx + corner, y2), color, box_thickness, lineType=8, shift=0)
            dx += box_dash_gap + corner
        while dy + corner < y2:
            cv.line(image, (x1, dy), (x1, dy + corner), color, box_thickness, lineType=8, shift=0)
            cv.line(image, (x2, dy), (x2, dy + corner), color, box_thickness, lineType=8, shift=0)
            dy += box_dash_gap + corner
        cv.line(image, (x1, y1), (x1, y1), color, box_thickness, lineType=8, shift=0)
        cv.line(image, (x1, y2), (x1, y2), color, box_thickness, lineType=8, shift=0)
        cv.line(image, (x2, y1), (x2, y1), color, box_thickness, lineType=8, shift=0)
        cv.line(image, (x2, y2), (x2, y2), color, box_thickness, lineType=8, shift=0)
    else:
        cv.rectangle(image, tl, br, color=color, thickness=box_thickness)


class ToolTip:
    tooltip = None

    def __init__(self, widget, text=None, **kwargs):

        def on_enter(event):
            self.tooltip = tk.Toplevel()
            self.tooltip.overrideredirect(True)
            self.tooltip.geometry("+{}+{}".format(event.x_root + 15, event.y_root + 10))

            self.label = tk.Label(self.tooltip, text=self.text, **kwargs)
            self.label.pack()

        def on_leave(event):  # noqa
            self.tooltip.destroy()

        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", on_enter)
        self.widget.bind("<Leave>", on_leave)
