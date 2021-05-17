## CHANGES


### [Unreleased](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer) (latest)

* Support Text Annotations version 2:
  - Detect and employ `annot_precise` metadata when provided in Text Annotations.
    This metadata contains similar information as `annotations`, but with additional fields that where not previously 
    available (`iob`, `offset`, etc.). 
  - Resolve modified field names  (e.g.: `POS` becomes `pos`).
  - Handle new formats. Instead of a list of annotations object each with their `POS`, `lemme`, etc. fields, each of 
    those fields are directly lists of same length matching the number of annotations.

* Insert the current application version within the merged file to allow tracking.
  Merged files that do not provide ``version`` are generated with a prior version.

* Add ``--references`` (`-r`) options to generate ``--merge`` file with references. Each time a VD, TA or VI item is
  used to generate the combined result, a UUID is placed instead of the literal object. All corresponding objects are
  then listed in separate mappings to avoid unnecessary duplication of data. When using this option, parsing of a file
  will require resolution of those references. Otherwise, the duplicated data is still returned (without `-r` flag).
  
* Use explicit loading of JSON format when detected through ``json`` package since it parses large metadata 
  much faster than ``yaml``.
  
* Remove unnecessary cary-over of ``annot`` and ``annot_precise`` original data from Text Annotations when generating 
  merge, since the same information (different format) is already contained in the parsed and resolved merge result.

### [0.5.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.5.0) (2021-04-26)

* Support Text Annotations version 2:
  - Directly employ provided `sentence` when available, or keep generating them otherwise. 
  - Adjust dynamically the loaded `annot_sentence` used instead of `annotations`.

### [0.4.1](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.4.1) (2021-03-01)

* Fix timestamp milliseconds parsing that caused errors in some cases because of too strict format.

### [0.4.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.4.0) (2021-01-26)

* Support multiple video predictions provided through variable bounding boxes targets in the scene.
* Display provided bounding boxes when available.

### [0.3.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.3.0) (2020-11-27)

* Support multiple Video Inference metadata files simultaneously rendered in data fields.
* Add better scrollbars support to allow moving around the data result fields.
* Add initial merged file generation from other metadata sources. 
* Fix error of frame seek at the end of the video not able to properly retrieve the last metadata items.
* Update the demo screenshot with the added metadata rendering.

### [0.2.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.2.0) (2020-11-17)

* Add documentation.
  - Expected data formats and details.
  - Usage information to run the application.
  - Add demo screenshot of the displayed results.

* Add snapshot button to save results of a single frame.

### [0.1.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.1.0) (2020-11-17)

* First implementation of the result viewer.
  - Video display area.
  - Time slider to seek frames.
  - Buttons to control playback.
  - Text box to provide raw data.