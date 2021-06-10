# video-result-viewer

<img alt="version-1.4.2" src="https://img.shields.io/badge/version-1.4.2-blue"/>

Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results. 

![demo](./doc/demo-preview.png)

## Description

The tool takes as input the following information and displays them for corresponding timestamps.

- [required] Original video file (production)
- [optional] Extracted video-description annotations metadata (as generated by [FAR-VVD/data-extraction][metadata_extract]) 
- [optional] Video action inference results (as generated by [FAR-VVD/video-action-recognition][video_infer]) 
- [optional] Text subjects and verbs results (as generated by [FAR-VVD/Annotation-VD][text_results])

[metadata_extract]: https://www.crim.ca/stash/projects/FAR/repos/data-extraction/ 
[text_results]: https://www.crim.ca/stash/projects/FAR/repos/annotation-vd/
[video_infer]: https://www.crim.ca/stash/projects/FAR/repos/video-action-recognition/

It can also combine all of those results into a [merged file](doc/usage.md#metadata-merging) with aligned timestamps.

**NOTE** <br>
Further options are available using the CLI script.


## Expected Formats of Metadata

Please refer to [format details](./doc/metadata_format.md).


## Installation and Execution

Please refer to [usage details](./doc/usage.md).
