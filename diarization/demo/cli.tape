# The README's terminal demo. Record with: cd diarization && vhs demo/cli.tape
# The live screen is our test harness; Secure MOM itself is the web app in DESIGN.md.

Output demo/cli.gif
Output demo/cli.txt

Set Shell zsh
Set FontSize 15
Set Width 1400
Set Height 860
Set Padding 24
Set Framerate 12
Set PlaybackSpeed 2
Set TypingSpeed 35ms
Set Theme { "name": "amber", "background": "#0d0b07", "foreground": "#ffb000", "cursor": "#ffb000", "selection": "#3a2c00", "black": "#0d0b07", "red": "#ffb000", "green": "#ffb000", "yellow": "#ffb000", "blue": "#ffb000", "magenta": "#ffb000", "cyan": "#ffb000", "white": "#ffb000", "brightBlack": "#806000", "brightRed": "#ffb000", "brightGreen": "#ffb000", "brightYellow": "#ffb000", "brightBlue": "#ffb000", "brightMagenta": "#ffb000", "brightCyan": "#ffb000", "brightWhite": "#ffc640" }

Hide
Type "setopt interactivecomments; source .venv/bin/activate && export PS1='$ ' && clear"
Enter
Sleep 1s
Show

Type "# testing tool only: this is how we check the diarizer. The product is the Secure MOM web app."
Enter
Sleep 1s
Type "# 5 people: Ion (RO), Maria (RO+RU), David (EN), Sofia (RU), Alexandru (RU)"
Enter
Sleep 1s
Type "diarizer live --replay demo/meeting.wav"
Enter

# introductions, one at a time, while the room check runs
Sleep 34s
Enter

# name the voices in the order they spoke
Sleep 2s
Type "Ion"
Enter
Sleep 600ms
Type "Maria"
Enter
Sleep 600ms
Type "David"
Enter
Sleep 600ms
Type "Sofia"
Enter
Sleep 600ms
Type "Alexandru"
Enter

# the meeting
Sleep 90s
Enter

# the summary
Sleep 10s
