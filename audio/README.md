# Audio Cue Files

This directory contains audio cue files used by LISA for user feedback during voice recording.

## Files

- **start_cue.wav** - Played when voice recording starts (after pressing the clicker button)
- **stop_cue.wav** - Played when voice recording stops (after pressing the clicker button again)

## Purpose

These audio cues provide immediate feedback to the user when using the clicker/ASR input mode, confirming that:
1. Recording has started (start cue)
2. Recording has stopped and is being processed (stop cue)

## Usage

These files are automatically loaded by `robot_functions.py` when using the clicker input mode (`lisa_api_clicker.py`). No manual configuration is needed.

## Customization

To customize the audio cues:
1. Replace the existing `.wav` files with your own
2. Ensure they are short (< 1 second recommended)
3. Use standard audio format (16-bit PCM WAV)
4. Keep the same filenames or update references in `robot_functions.py`

## Generating Custom Cues

You can generate simple beep tones using `sox`:

```bash
# Generate a high-pitched beep for start
sox -n start_cue.wav synth 0.2 sine 880

# Generate a lower-pitched beep for stop
sox -n stop_cue.wav synth 0.3 sine 440
```

Or use any audio editing software to create custom sounds.

