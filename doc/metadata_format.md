
## Expected Formats of Metadata

The tool can simultaneously display synchronized metadata from video-description (VD), text annotations and video
action recognition from model inference. Each metadata file have different expected format aligned with their original
definition, as presented in following sub-sections.

[metadata_extract]: https://www.crim.ca/stash/projects/FAR/repos/data-extraction/ 
[text_results]: https://www.crim.ca/stash/projects/FAR/repos/annotation-vd/
[video_infer]: https://www.crim.ca/stash/projects/FAR/repos/video-action-recognition/


### Video-description Metadata

Following is the expected format of the original video-description JSON metadata 

See also:

- Source code: 
  [FAR-VVD/data-extraction][metadata_extract]
- Data samples: 
  [FAR-VVD/VD](/misc/data23-bs/FAR-VVD/nobackup) 
  (see reference listing in ``metadata_files.json``)
  
Multiple additional fields from the exhaustive format are not presented below for simplicity.
Required fields from the ``metadata_files`` part are either the *series* or the *films* related items, depending 
on whether the *old* or *new* ``vd_files_format`` is employed. The parser will detect which one according to available
fields and handle each case. All fields of both format are presented below for reference, but there should only be one
of the two in real metadata files. 
 
Following the top-level metadata, either the ``augmented_vd_metadata`` or the ``standard_vd_metadata`` are looked for.
The extended one is selected first if available, and falls back to the standard one otherwise. Both formats are 
identical, and are therefore only represented once below.

For each video-description entry, the mandatory fields are ``start_ms``, ``end_ms`` and ``vd``. Other elements are not
currently employed. The extracted timestamps are mapped against corresponding ones of metadata files from next sections.

``` json 
{
    "version": "0.0.1",
    "date_generated": "2020-02-22 02:27:53.305967",
    "vd_files_format": "old|new",
    "metadata_files": {
        "serie_name": "Dans une galaxie",
        "serie_export_path": "/mnt/m/data23-bs/FAR-VVD/nobackup/Export/OPHQ/Dans_une_Galaxie_Pres_de_Chez_Vous/Disque1/Episode14",
        "serie_production_path": "/mnt/m/data23-bs/FAR-VVD/nobackup/Production/OPHQ/Dans une Galaxie/DGPCV_14",
        "serie_collection_name": "OPHQ",
        "serie_episode_number": 14,
        "film_export_path": "/mnt/m/data23-bs/FAR-VVD/nobackup/Export/BAnQ",
        "film_production_path": "/mnt/m/data23-bs/FAR-VVD/nobackup/Production/BAnQ",
        "film_export_subpath": "15Fevrier1839",
        "film_production_subpath": "15Fevrier1839/15Fevrier183920160119",
        "film_collection_name": "BAnQ",
        "video_file": "../../../../../Data/OPHQ/Data/Dans_une_Galaxie_Près_de_Chez_Vous/DGPCV_Ep14.avi"
    },
    "standard_vd_metadata": [],
    "augmented_vd_metadata": [
        {
            "vd": "Veuillez noter que la traduction des dialogues anglais sera donnée en vidéodescription augmentée.",
            "video": "../../../../../Production/BAnQ/15Fevrier1839/15Fevrier183920160119/Video/Title_1.mp4",
            "actors": [],
            "scenes": [],
            "duration_ms": 5264,
            "start_ms": 0,
            "end_ms": 5264,
            "start": "T00:00:00",
            "end": "T00:00:05.264000"
        }
    ]
}
```


### Video Action Recognition Inference Metadata

Following is the expected format of the action recognition predictions inferred from video 

See also:

- Source code: 
  [FAR-VVD/video-action-recognition][video_infer]
- Data samples: 
  [FAR-VVD/Inference](/misc/data23-bs/FAR-VVD/nobackup/Inference)

The only mandatory field is ``predictions``, and more specifically, the ``start``, ``end``, ``classes`` 
and ``scores`` entries for each of those list items. Each segment timestamps are converted to be matched against other
metadata files. 

``` json 
{
    "command": "<command>",
    "model": "<model_name>",
    "sample_count": <sample_count>,
    "predictions": [
        {
            "segment": "<video>",
            "name": "<name>",
            "start": <seconds-time-start>,
            "end": <seconds-time-end>,
            "part": "<segment>/<sample_count>",
            "classes": [ "a", "b", "c", "d", "e" ],
            "scores": [ 0.60, 0.20, 0.10, 0.03, 0.02 ]
        }
    ]
}
```

### Text Annotation Metadata

Following is the expected format from text annotation metadata JSON files.

See also:

- Source code: 
  [FAR-VVD/Annotation-VD][text_results]
- Data samples:
  [FAR-VVD/DATA_TEXTE](/misc/data23-bs/FAR-VVD/DATA_TEXTE/8-Text_inference)

The ``vd`` fields are not employed (original VD from its ``metadata.json`` is employed).

The ``annotations`` can have any amount of 2D-list, where first dimension is the sentence and the second represent the
annotated lemmes within each sentence.

Timestamps of a given annotation are mapped with start/end time and converted appropriately to match them against 
equivalent timestamps of other metadata files.
 

``` json
{
    "name": "<identification-name>",
    "data": [
        {
            "vd": "<video-description>",
            "annotations": [
                [
                    {
                        "lemme": "vaisseau_spatial",
                        "POS": "NOUN_ADJ",
                        "type": "Sujet-Objet"
                    }
                ]
            ],
            "TS": [
                "T00:00:23.423000",
                "T00:00:28.860000"
            ]
        }
    ]
}
```

