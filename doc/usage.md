
## Usage 

### Installation

You only need a few dependencies as specified in [requirements.txt](../requirements.txt).
They can be installed like such: 

    pip install -r requirements.txt


### Execution

#### Viewing Results

The tool is executed by calling the script as follows: 

    python source/viewer.py [-h] [...]


The help CLI output indicates extensive options and configurations that can be specified to customize video playback
and results being displayed and/or generated.

The only mandatory input is the video to play, but this does not provide much insight in itself. The other arguments
to provide specific metadata files (see also [metadata formats](metadata_format.md)) should also be provided for proper
analysis. Missing or omitted files are ignored and not rendered. Each metadata type is parsed separately. Therefore,
partially only providing metadata files will not impact the rendering of the provided ones.  


### Extra Features

Additional functionalities can be accomplished using the script since parsing of the various metadata formats for
manual video-description (VD), text annotations (TA) and video inference of actions (VI) is accomplished. 

#### Label Mapping

Using custom mapping JSON/YAML file such as [label_mapping.yml][mapping-example], it is possible to both replace
class label names with desired values, and combine multiple classes into common groups. 
 
Label mapping supports regexes for advance renaming possibilities, as well as cross-dataset renaming since they are 
applied indistinctly over all parsed metadata files regardless of the reference model predictions were made from.

Please refer to [label_mapping.yml][mapping-example] for explicit examples and details. 

[mapping-example]: ../label_mapping.yml

#### Extensions

Whenever a metadata file is referenced, either JSON or YAML are accepted interchangeably. 
Parsing is accomplished automatically based on the specified extension.

#### Metadata Merging 

When [multiple metadata sources](metadata_format.md) (VD, TA, VI) are simultaneously loaded and successfully parsed, 
it is possible to request the [merged result](#merged-result) (see ``--merged`` option) that combines them with 
timestamped segment alignment across metadata sources. 

##### Merge Procedure

Because metadata come from multiple sources, their annotated or predicted classes during model inference could 
correspond to video *sections* of different durations and/or be misaligned. This makes it difficult to parse data
linearly because the misalignment of the source generates objects with overlapping time ranges.

The merging procedure alleviate these problems with appropriate adjustments to facilitate comparison analysis of all
metadata sources for corresponding timestamps, as if they all came from a single source. The result is a flat list of
unified annotations that can be parsed sequentially, without worries about overlapping time ranges.

The resulting file contents is [presented in the next section](#merged-result). Following illustrates and describes
in more details the procedure.

Metadata of [Text Annotations](metadata_format.md#text-annotation-metadata-ta) (TA) is usually aligned with 
[Video-Description](metadata_format.md#video-description-metadata-vd) (VD), but this is not necessarily the case 
for [Video Inferences](metadata_format.md#video-action-recognition-inference-metadata-vi) (VI). 

For this reason, additional entries are padded as illustrated below:

    [META-TYPE]                 ts                                                              te

    meta-video-desc     (VD)    |........entry-1..........|.................entry-2.............|
    meta-text-annot     (TA)    |........entry-1..........|..........entry-2........|...<none>..|
    meta-video-infer    (VD[1]) |...entry-1...|.....entry-2....|....entry-3....|.....entry-4....|
    meta-video-infer    (VD[N]) |........entry-1.....|.....entry-2....|....entry-3..|..entry-3..|

    merged                      |.....M1......|..M2..|.M3.|.M4.|..M5..|...M6...|.M7.|.....M8....|
                                t0            t1     t2   t3   t4     t5       t6   t7          t8

*NOTE*: please refer to [next section](#merged-result) for explicit location of described fields.

Top-level start/end time in `details` section correspond to first/last times found across every single
metadata type/entry *section* (see above `ts`/`te`).

Then, for each merged entry inside `merged` section, start/end time indicate the limits of each largest and 
uninterrupted cut *section* over all metadata sources. In the above example, this corresponds to the 8 generated 
entries (i.e.: `t0` to `t1`,  `t1` to `t2`, and so on for merged `M1` to `M8` portions). Metadata of different 
sources will therefore be replicated over each time range it overlaps with.

Under each merged entry, available `VD`, `TA`, `VI[N]` will have their *original* start/end time for reference in 
sub-sections. This means timestamps will extend pass merged portions start/end times. For example, `entry-1` of the
`VD` source will indicate an end time `t3` with is larger than `t0` to `t1` for the generated `M1` merged *section*. 
A merged timestamp will be available, representing the `t#` ranges represented in above example. These will indicate 
the *combined* limits across data sources. 

Since VD time range can often appear much earlier than the moment when the represented actions are actually
displayed on video, start time of each *section* are ignored to ensure that the first available entry are padded
until the next entry can be found with timestamps.

Whenever metadata of some type cannot be resolved within the given merged *section* (when entries are exhausted),
the field is set to `None`. This can happen for example when VD continues, but no corresponding TA was
provided. This is common at the end of videos showing the end credits, while VI can continue to predict 
continuously (although inferred items do not make much sense).

##### Merged Result

Section `details` provide general metadata provenance information from the corresponding metadata types.
Entries marked as `None` mean that no corresponding metadata file of that type was provided as input.

Section `merged` provides the combined/extended timestamp entries where concordance between metadata types
could be mapped, as illustrated in [previous section](#merge-procedure).

Sections `version` and `references` are available only since version 1.0.0. 
The `references` are added only when requested with ``--reference`` option, and easily reduces by half the size of 
the resulting merged metadata by using JSON ``{"$ref": "references/<section>/<uuid>"}`` format to refer to repeated
object definitions. Repetitions can occur very often, simply due to the misalignment problem of the various data 
sources described in the [previous section](#merge-procedure).

The format described above is summarized below. 
Note that some items within `text_annotations` can change slightly in content based on the Text Annotation 
[version format and content](metadata_format.md#text-annotation-metadata-ta) that was provided. Corresponding
adjustments are denoted by (V1, V2, etc.) below for corresponding changes.

```yaml
version: <major.minor.patch>  # only available above 1.x
details: 
  # contains global/shared metadata of specific sources for each individual VD, TA, VI sections
  # for example, the location of original metadata files, the video title, configurations, etc. will be available here
  video_description: { <...> }
  text_annotation:  { <...> }
  video_inference: { <...> }
  
merged:
  # First merged section (M1) 
  - start: <t0>         # real start time of merged M1 portion
    end: <t1>           # real end time of merged M1 portion
    video_description   # (VD entry-1)
      # VD metadata dump of the original file with extended details (e.g.: corrected timestamps formats)   
      vd:               # (VD entry-1)
        [...]
        # <t3> is the original end time of VD metadata. It spans pass the end <t1> of merged portion. 
        # Next "merged" entry will have the exact same values since VI needs to be replicated (see lower comments). 
        start_ms: <t0>  # (in milliseconds)
        end_ms: <t3>    # (in milliseconds)
        start: <t0>     # (in seconds.fraction)
        end": <t3>      # (in seconds.fraction)
        start_ts: "Thh:mm:ss.fff"
        end_ts: "Thh:mm:ss.fff"
    text_annotation:    # (TA entry-1)
      annotations: 
        - sentence: <fist sentense of VD>
          tokens:  # warning: this was named 'words' before 1.x, it is renamed because they are not necessarily 'words'
            - lemme: "<word|token>"
              pos: "NOUN|NOUN_ADJ|VERB|PRON_VERB|..."
              # if TA V1/V2, 'type' is provided, otherwise TA V3 replaces it by an extended IOB notation with classes
              type: "Sujet-Objet|Action-CasGénéral|Objet-Indirect-Objet|..."
              # if TA V3, following are also available, V1 and V2 don't have them
              token: "<token>"
              iob:  # any amount applicable for that given token
                - "O"                                                             # "O" for no previous annotation 
                - "I|B+Sujet-Objet|Action-CasGénéral|Objet-Indirect-Objet|..."    # extended 'type' annotation 
              offset:
                - start: 0  # offset in sentence
                - stop: 12  # start + len(token)
            - [...]     # and so on for each text annotated token of the sentence 
          TS: 
            - "Thh:mm:ss.fff"   # raw start timestamp
            - "Thh:mm:ss.fff"   # raw end timestamp
          # In this case, timestamps of TA entry-1 just so happened to be aligned with VD entry-1
          # In the case of VD entry-2, two 'merged' separate entries would exist, one for TA entry-2 and 
          # another for entry-3. Both would have the same VD spanning between t3 and t8. Those entries would 
          # respectively have t3/t7 and t7/t8 as start/end times for the TA sub-section. 
          start_ms: <t0>
          end_ms: <t3>
          start: <t0>
          end: <t3>
        - [...]     # and so on for other sentences if VD provided multiple onces
    video_inference:   # (VI entry-1)
      - segment: <filename>
        name: <name>
        # Notice how below end time is <t1>. This is because the VI was the smallest portion between VD, TA, VI
        # which resulted into this merged portion.
        start: <t0>
        end: <t1>
  # Second merged portion (M2)
  # everything will be a complete copy-paste of the previous M1 portion, except below fields. 
  - start: <t1>       # start time of merged M2 portion
    end: <t2>         # end time of merged M2 portion
    [...]
    # Since VI is again the smallest portion and that no new VD/TA metadata was overlapping, only VI changes.
    # If another VD and/or TA appeared first, below <t2> would span pass the final 'merged' time of that portion.
    video_inference:  # (VI entry-2)
      - [...]
        start: <t1>
        end: <t2>
  # [...] and so on
  
  # only if 1.x version or above, and when using option '--references', following sections are generated
  # all previous objects are regrouped here and linked using JSON {"$ref": "references/<section>/<uuid>"}
  references:
    # UUID to object mappings
    actors: {}
    scenes: {}
    video_description: {}
    video_inference: {}
    text_annotation: {}
```
