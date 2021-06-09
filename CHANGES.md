## CHANGES

[Unreleased](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer) (latest)
------------------------------------------------------------------------------------------------------------------------
____________

* Nothing new for the moment.

[1.4.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/1.4.0) (2021-06-09)
------------------------------------------------------------------------------------------------------------------------
____________

* Fix invalid links when using JSON reference generation (`$ref` notations) to ensure they can be properly loaded by 
  packages such as [jsonref](https://pypi.org/project/jsonref/).

* Fix an issue where unspecified Video Inference (VI) metadata files would raise an error during argument parsing.

* Support input files that could employ `$ref` links inside JSON or YAML metadata.

* Support directly providing an input and pre-generated merged metadata file (`--input-metadata`) to be viewed 
  with a video, skipping the metadata generation phase from the individual metadata file sources.
  
* Add metadata *total* entries following merge strategy that can deduplicate original entries to align timestamps,
  and therefore do not necessarily match the original amount from the corresponding source. Both totals are reported.

[1.3.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/1.3.0) (2021-06-09)
------------------------------------------------------------------------------------------------------------------------
____________

* Provide the `--text-auto` and `--text-manual` options to define the Text Annotation *method* that was employed.
  If specified, *merged* result will contain the `method: "<method>"` entry or `"undefined"` value in the 
  summary detail section of `text_annotaitons` metadata source.
  
* Implement parsing and merging of Text Inference TSV files that provide action mappings between different types of 
  lexical resources, embeddings generation and reference gold standard definitions against the original VD action.
  The new Text Inference metadata should be provided with `--ti`/`--text-inference` options similarly to other sources.
  
* Update documentation about new Text Inference (TI) content format. 
  
* Avoid initial metadata entries of each source to be incorrectly added during merge or displayed in viewer until 
  the corresponding first start time is reached.

[1.2.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/1.2.0) (2021-06-07)
------------------------------------------------------------------------------------------------------------------------
____________

* Add checkbox option to display only the central video-segment bounding boxes when provided from Video Inference 
  metadata instead of enforced both central and dashed (outside delta central key frame) bounding boxes. 
* Fix invalid resolution of V1 Text Annotations against other version formats when the provided annotations were empty
  for some entries, and checked against to attempt detection of V4 *precise* definitions. 
* Fix handling of Text Annotations `POS` vs `pos` case and `type` vs `iob` according to parsed annotation version 
  when displaying results on viewer.

[1.1.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/1.1.0) (2021-05-20)
------------------------------------------------------------------------------------------------------------------------
____________

* Support Text Annotations version 4: 
  - Detect ``annotations`` that directly provide the same metadata format as V3 instead of ``annot_precises``,  
    and differentiate it from older format using ``annot_sentences`` (V2).

[1.0.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/1.0.0) (2021-05-17)
------------------------------------------------------------------------------------------------------------------------
____________

* Support Text Annotations version 3:
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

[0.5.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.5.0) (2021-04-26)
------------------------------------------------------------------------------------------------------------------------
____________

* Support Text Annotations version 2:
  - Directly employ provided `sentence` when available, or keep generating them otherwise. 
  - Adjust dynamically the loaded `annot_sentence` used instead of `annotations`.

[0.4.1](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.4.1) (2021-03-01)
------------------------------------------------------------------------------------------------------------------------
____________

* Fix timestamp milliseconds parsing that caused errors in some cases because of too strict format.

[0.4.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.4.0) (2021-01-26)
------------------------------------------------------------------------------------------------------------------------
____________

* Support multiple video predictions provided through variable bounding boxes targets in the scene.
* Display provided bounding boxes when available.

[0.3.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.3.0) (2020-11-27)
------------------------------------------------------------------------------------------------------------------------
____________

* Support multiple Video Inference metadata files simultaneously rendered in data fields.
* Add better scrollbars support to allow moving around the data result fields.
* Add initial merged file generation from other metadata sources. 
* Fix error of frame seek at the end of the video not able to properly retrieve the last metadata items.
* Update the demo screenshot with the added metadata rendering.

[0.2.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.2.0) (2020-11-17)
------------------------------------------------------------------------------------------------------------------------
____________

* Add documentation.
  - Expected data formats and details.
  - Usage information to run the application.
  - Add demo screenshot of the displayed results.

* Add snapshot button to save results of a single frame.

[0.1.0](https://www.crim.ca/stash/projects/FAR/repos/video-result-viewer/browse?at=refs/tags/0.1.0) (2020-11-17)
------------------------------------------------------------------------------------------------------------------------
____________

* First implementation of the result viewer.
  - Video display area.
  - Time slider to seek frames.
  - Buttons to control playback.
  - Text box to provide raw data.
