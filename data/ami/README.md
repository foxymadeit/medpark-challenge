# AMI meeting subset (evaluation and tuning)

Six meetings from the AMI Meeting Corpus, which we use to measure and tune
the diarizer. Each one has four speakers in a real meeting room.

| Split | Meetings | Used for |
|---|---|---|
| dev | ES2011a, IS1008a | choosing thresholds |
| test | ES2004a, IS1009a, TS3003a, EN2002a | the numbers we report; never tuned on |

Files per meeting:

- `<meeting>.Array1-01.flac`: first microphone of the table array (far-field, 16 kHz mono).
  It sounds closest to a phone or laptop left in the middle of the table.
- `<meeting>.rttm`: who spoke when, one line per turn
  (`SPEAKER <meeting> 1 <start> <duration> <NA> <NA> <speaker> <NA> <NA>`).
- `<meeting>.uem`: the part of the recording that is scored.

The close-talk headset mixes (`Mix-Headset`) aren't committed because they are
large. `./fetch_ami.sh` downloads them, plus any of the WAV originals.

Source and license: AMI Meeting Corpus, University of Edinburgh and partners,
CC-BY 4.0 (https://groups.inf.ed.ac.uk/ami/corpus/). RTTM and UEM files come
from https://github.com/pyannote/AMI-diarization-setup ("only_words" setup).
