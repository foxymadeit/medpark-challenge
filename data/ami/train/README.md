# AMI training meetings (projection training)

38 AMI meetings, far-field microphone (Array1-01) as 16 kHz mono FLAC, with
their "only_words" RTTM labels. They trained the voiceprint projection in
`diarization/models/titanet-small.backend.d64.npz`
(`python -m train.fit_backend --data ../data/ami/train --dims 64`).

`picked.txt` lists the 40 meetings chosen (8 per recording site); IS1003b and
IS1007d have no far-field recording on the AMI mirror, so 38 remain.
None of these meetings is in the dev or test lists used for scoring.

Source and license: AMI Meeting Corpus, CC-BY 4.0 (https://groups.inf.ed.ac.uk/ami/corpus/).
RTTM files from https://github.com/pyannote/AMI-diarization-setup.
