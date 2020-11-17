# video-result-viewer

Minimalistic video player that allows visualization and easier interpretation of FAR-VVD results. 

![demo](./doc/demo-preview.png)

## Description

The tool takes as input the following information and displays them for corresponding timestamps.

- Original video file (production)
- Extracted video-description annotations metadata (as generated by [FAR-VVD/data-extraction][metadata_extract]) 
- Video action inference results (as generated by [FAR-VVD/video-action-recognition][video_infer]) 
- Text subjects and verbs results (as generated by [FAR-VVD/Annotation-VD][text_results])

[metadata_extract]: https://www.crim.ca/stash/projects/FAR/repos/data-extraction/ 
[text_results]: https://www.crim.ca/stash/projects/FAR/repos/annotation-vd/
[video_infer]: https://www.crim.ca/stash/projects/FAR/repos/video-action-recognition/


## Expected Formats of Metadata

Please refer to [format details](./doc/metadata_format.md).


## Installation and Execution

Please refer to [usage details](./doc/usage.md).
