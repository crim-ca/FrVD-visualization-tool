
## Expected Formats of Metadata

The tool can simultaneously display synchronized metadata from video-description (VD), text annotations and video
action recognition from model inference. Each metadata file have different expected format aligned with their original
definition, as presented in following sub-sections.

All of these files are employed to generate a [merged file](usage.md#metadata-merging) if requested.

[metadata_extract]: https://www.crim.ca/stash/projects/FAR/repos/data-extraction/ 
[text_results]: https://www.crim.ca/stash/projects/FAR/repos/annotation-vd/
[video_infer]: https://www.crim.ca/stash/projects/FAR/repos/video-action-recognition/


### Video-description Metadata (VD)

Following is the expected format of the original video-description JSON metadata 

See also:

- Source code: 
  [FAR-VVD/data-extraction][metadata_extract]
- Data samples: 
  `/misc/data23-bs/FAR-VVD/nobackup` <br> 
  (see reference ``metadata_files.json`` that lists paths to every corresponding video `metadata.json` file)
  
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

```json 
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


### Video Action Recognition Inference Metadata (VI)

Following is the expected format of the action recognition predictions inferred from video 

See also:

- Source code: 
  [FAR-VVD/video-action-recognition][video_infer]
- Data samples: 
  `/misc/data23-bs/FAR-VVD/nobackup/Inference`

The only mandatory field is ``predictions``, and more specifically, the ``start``, ``end``, ``classes`` 
and ``scores`` entries for each of those list items. Each segment timestamps are converted to be matched against other
metadata files. 

```json 
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

### Text Annotation Metadata (TA)

Following are the expected formats from text annotation metadata JSON files.

See also:

- Source code: 
  [FAR-VVD/Annotation-VD][text_results]
- Data samples:
  `/misc/data23-bs/FAR-VVD/DATA_TEXTE` <br>
  (sub-directory `TEXT_INFERENCE_ALL` for latest, older in order sibling locations)

**NOTE** <br>
Different formats are presented to keep track of their evolution over time. <br> 
They should still all work interchangeably, but latest one would usually offer more metadata contents.


#### V1 - Original Annotations

```json
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

The ``data`` contains any amount of annotations metadata, for which timestamps under ``TS`` and ``annotations`` must
always be provided. The ``vd`` fields are not directly employed, unless no original VD ``metadata.json`` file is given,
as they duplicate this information.

The ``annotations`` can have any amount of 2D-list, where first dimension represents some *sentence*, 
and the second represent the annotated lemmes within each *sentence*. Because no explicit ``sentence`` is 
provided here, the [merge operation](usage.md#metadata-merging) generates them as good as possible using heuristics.
Each ``annotation`` is used to generate the ``words`` list in the [merged result](usage.md#merged-result).

Timestamps ``TS`` of a given annotation are mapped with start/end time and converted appropriately to match them 
against equivalent timestamps of other metadata files.

#### V2 - Sentence Annotations

```json
{
  "name": "<identification-name>",
  "data": [
    {
      "vd": "<video-description>",
      "annotations": [
        { 
          "sentence": "", 
          "annot_sentence": [
            { 
              "POS": "", 
              "lemme": "", 
              "type": "" 
            }
          ]
        }
      ],
      "TS": [
        "T00:00:23.423000",
        "T00:00:28.860000"
      ]
    }
  ]
}
```

This format modified the previous 2D-list to employ a list of objects instead, each containing the original 
annotation format under the field ``annot_sentence``.

Additionally, the pre-processed ``sentence`` field is provided, but sometimes the amount of provided entries does
not correspond to the detected number of *sentences* within the ``vd``. Heuristics of the previous 
[V1](#v1---original-annotations) version are therefore still processed to display (debug) and differences encountered.
The provided `senttence` are preserved regardless of mismatches.

#### V3 - Precise Annotations

```json
{
  "name": "<identification-name>",
  "data": [
    {
      "vd": "<video-description>",
      "TS": [],
      "sentence": "...",
      "annot": [ [ {} ] ],
      "annotations": [ {} ],
      "annot_precises": [
        {
          "TS": [
            "T00:00:00.066000",
            "T00:00:10.528000"
          ],
          "token": [
            "Avertissement",
            "."
          ],
          "lemme": [
            "avertissement",
            "."
          ],
          "offset": [
            "0 13",
            "13 14"
          ],
          "pos": [
            "NOUN",
            "PUNCT"
          ],
          "iob": [
            [
              "O"
            ],
            [
              "O"
            ]
          ]
        }
      ]
    }
  ]
}
```

This new version provides all previous version formats simultaneously. 

The `vd`, `TS` and `sentence` are identical to previous definitions, but `sentence` always provided. Therefore, 
heuristics are not applied anymore to generate them.

The `annot` corresponds to the 2D-list of [V1](#v1---original-annotations).  The `annotations` instead correspond to 
the format of [V2](#v2---sentence-annotations). Both are simplified in the above example to make it more concise and 
focus on new elements.

The `annot_precises` field provides a list of objects similar to `annotatons`, where each item is a `sentence` from 
the `vd`. For each of those sentences, additional metadata with more explicit information about every annotated `token`
is provided.

Corresponding indices of each `token` refer to the same elements in other lists. For example, index 0 of ``token`` 
indicates the word ``Avertissement``, which refers to the ``lemme`` of index 0 `avertissement`, located at `offset` 
characters (start: `0`, end: `13`, string separated by single space) within the ``sentence``. 
The Part-Of-Speech (`pos`) and Inside-Outside-Beginning (`iob`) information relative to the sentence entity 
for the `token` are also available.

#### V4 - Precise Annotations (as Annotations)

In more recent cases, the field ``annotations`` is provided directly in place of ``annot_precises``. 
The format under it is exactly the same as ``annot_precises`` of [V3](#v3---precise-annotations), but due to 
possible parsing confusion with ``annotations`` from [V2](#v2---sentence-annotations), the sub-field ``annot_sentence`` 
is looked for explicitly to distinguish between them. 

If the field ``annot_sentence`` is present, [V2](#v2---sentence-annotations) parsing is employed.
Otherwise, parsing proceeds using [V3](#v3---precise-annotations), applying all usual formatting rules.

### Text Inference Metadata (TI)

This file is expected to be provided in TSV format. 

It is intended to provide action mapping strategies between different types of lexical resources, embeddings 
generation methods and reference gold standard definitions, against the original VD action.

The format is presented below.

```text
<timestamp>    action    <mapping-strategy-1>    <mapping-strategy-2>    [...]    gold    [prox]
T<ts>;T<te>    verb      action-1;action-2       (- | _ | '')                     verb    (- | <int>) 
[...]
```

The first line is the header that indicates the name of each mapping strategy.
The timestamp name is ignored, but assumed to be placed in the first column.
Any number of mapping strategy can be defined. The `gold` standard is expected as the last one. 
Optionally, the `prox` (proximity) can also be provided after the `gold` standard.

For each line, the first column is the start and end timestamps of the entry (ISO times prefixed by `T`). 
They must be concatenated by `;`. Following is the single action for which mappings are generated for.
For each following mapping strategy, any amount of *action* mapping values separated by `;` can be provided.

Items annotated by either a single `-`, `_` or a blank entry will be assumed as *no action mapping* to be provided 
for that case. Those unavailable mappings will be replaced by `null` during the merging strategy. 

The `gold` standard should be a single mapping value (no `;` concatenated values). 
It can again be `-`, `_` or an empty string when not provided.

Finally, the `prox` field can be provided last.
If missing, it is simply ignored.  Otherwise, the value should be either a single value formed of 
either `-`, `_` or empty string (eg: when `gold` is also undefined) or an integer expected to represent the proximity
of the key `action` against the mappings.
Integers are preserved as is, while any other values are replaced by `0` during the parsing and merging strategy.
