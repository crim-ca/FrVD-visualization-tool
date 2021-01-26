import json
import yaml


def read_metafile(path):
    with open(path) as meta_file:
        metadata = yaml.safe_load(meta_file)
    return metadata


def write_metafile(metadata, path):
    with open(path, "w") as meta_file:
        if path.endswith(".json"):
            json.dump(metadata, meta_file, indent=4, ensure_ascii=False)
        else:
            yaml.safe_dump(metadata, meta_file)
