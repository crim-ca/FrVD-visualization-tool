
## Usage 

### Installation

You only need a few dependencies as specified in [requirements.txt](../requirements.txt).
They can be installed like such: 

    pip install -r requirements.txt


### Execution

The tool is executed by calling the script as follows: 

    python source/viewer.py [-h] [...]


The help CLI output indicates extensive options and configurations that can be specified to customize video playback
and results being displayed and/or generated.

The only mandatory input is the video to play, but this does not provide much insight in itself. The other arguments
to provide specific metadata files (see also [metadata formats](metadata_format.md)) should also be provided for proper
analysis. Missing or omitted files are ignored and not rendered. Each metadata type is parsed separately. Therefore,
providing only some of the metadata files will not impact the rendering of the provided ones.  
