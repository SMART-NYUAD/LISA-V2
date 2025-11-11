# USB Headset Audio Migration Guide

## Overview

LISA has been updated to support USB headset audio for both input and output, replacing the previous setup of external wireless microphone and robot speaker.

## What Changed

### Configuration (`config.env`)

New environment variables added:
- `AUDIO_OUTPUT_DEVICE="usb_headset"` - Controls audio output (options: `usb_headset` or `robot_speaker`)
- `AUDIO_INPUT_DEVICE="usb_headset"` - Controls audio input (options: `usb_headset` or `default`)

### Hardware Support

**Supported USB Headsets:**
- Logitech USB headsets (Vendor ID: 046d)
- Logitech G435 Wireless Gaming Headset
- Logitech G733 Gaming Headset
- Other Logitech gaming headsets with USB audio
- Auto-detected by device name patterns: logitech, 046d, g435, g733, gaming headset

**Input Trigger:**
- Changed from wireless clicker TAB key to USB headset **Volume Up button**
- Volume Up button (`KEY_VOLUMEUP`) triggers audio recording start/stop
- PAGEDOWN still clears chat history (if supported by device)

### Code Changes

#### New Functions (`src/robot_functions.py`)

1. **`detect_usb_headset()`**
   - Detects Logitech USB headset for audio I/O
   - Returns tuple: (input_device_index, output_device_index)
   - Auto-detects by vendor ID "046d" or device name containing "logitech"

2. **`detect_usb_headset_input()`**
   - Detects USB headset as input device for button events (evdev)
   - Returns list of evdev.InputDevice objects
   - Used for capturing volume button presses

3. **`play_audio_usb(audio_file, output_device=None)`**
   - Plays audio on USB headset using sounddevice
   - Automatically detects headset if device not specified

#### Modified Functions

1. **`play_audio()`**
   - Now routes to USB headset or robot speaker based on `AUDIO_OUTPUT_DEVICE` config
   - Maintains backward compatibility with robot speaker

2. **`play_cue_sound()`**
   - Supports both USB headset and robot speaker
   - Plays start/stop cues through configured output device

3. **`robot_speak()`**
   - Updated docstring to reflect config-based routing
   - Automatically uses configured output device

4. **`record_audio()`**
   - Changed default trigger key from `KEY_TAB` to `KEY_VOLUMEUP`
   - Added `input_device` parameter for USB headset audio capture
   - Auto-detects USB headset if configured

5. **`robot_listen()`**
   - Changed from detecting clickers to detecting USB headset
   - Uses `detect_usb_headset_input()` instead of `detect_clickers()`
   - Default trigger key changed to `KEY_VOLUMEUP`

### Configuration Module (`src/config.py`)

- Added `AUDIO_OUTPUT_DEVICE` property
- Added `AUDIO_INPUT_DEVICE` property
- Updated `print_config()` to display audio device settings

## How to Use

### 1. Set Up Configuration

Edit `config.env`:
```bash
# For USB headset (default)
export AUDIO_OUTPUT_DEVICE="usb_headset"
export AUDIO_INPUT_DEVICE="usb_headset"

# To revert to robot speaker
export AUDIO_OUTPUT_DEVICE="robot_speaker"
export AUDIO_INPUT_DEVICE="default"
```

### 2. Connect USB Headset

- Plug in Logitech USB headset
- Ensure user is in `audio` and `input` groups:
  ```bash
  sudo usermod -a -G audio $USER
  sudo usermod -a -G input $USER
  ```
- Log out and back in for group changes to take effect

### 3. Test Configuration

Run the test script:
```bash
cd /home/unitree/Projects/LISA-V2
python test_usb_audio.py
```

This will:
- List all audio devices
- Detect USB headset input/output
- Test audio playback
- Verify button input detection

### 4. Run LISA

Use LISA normally with the clicker script:
```bash
source config.env
python scripts/lisa_api_clicker.py
```

**New controls:**
- Press **Volume Up** button on headset to start/stop recording
- Press **PAGEDOWN** (if available) to clear chat history

## Backward Compatibility

The system remains fully backward compatible:

1. **Robot Speaker Mode:**
   - Set `AUDIO_OUTPUT_DEVICE="robot_speaker"` in config.env
   - All TTS and audio cues will play through robot speaker
   - Recording still works from configured input device

2. **Default Audio Input:**
   - Set `AUDIO_INPUT_DEVICE="default"` to use system default microphone
   - Useful for testing or alternate audio setups

3. **Clicker Support:**
   - Old `detect_clickers()` function still exists
   - Can be manually called if needed for custom implementations

## Troubleshooting

### USB Headset Not Detected

**Check device is connected:**
```bash
lsusb | grep -i logitech
```

**List all audio devices:**
```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

**Check input devices:**
```bash
ls -l /dev/input/by-id/ | grep -i logitech
```

### No Audio Output

- Verify `AUDIO_OUTPUT_DEVICE="usb_headset"` in config
- Check headset is not muted
- Test with: `python test_usb_audio.py`

### Volume Button Not Working

- Ensure user is in `input` group
- Check device permissions: `ls -l /dev/input/event*`
- Verify button detection: Monitor for `KEY_VOLUMEUP` events

### Audio Quality Issues

- Check sample rate compatibility (default: 44100 Hz)
- Verify sufficient USB bandwidth
- Try different USB port if available

## Technical Details

### Audio Pipeline

**Recording (USB Headset):**
1. User presses Volume Up button
2. `detect_usb_headset_input()` captures button event via evdev
3. `record_audio()` starts sounddevice input stream from USB headset
4. Audio captured at 44.1kHz, mono
5. Saved as WAV file
6. Transcribed with Whisper ASR

**Playback (USB Headset):**
1. Text generated by LLM
2. `robot_speak()` calls `generate_speech()` (Piper TTS)
3. `play_audio()` routes to `play_audio_usb()`
4. Audio loaded from WAV file
5. Played via sounddevice to USB headset

**Playback (Robot Speaker):**
1. Same TTS generation
2. `play_audio()` routes to robot speaker path
3. Audio uploaded via AudioHubClient
4. Played through robot's Megaphone mode

### Dependencies

All existing dependencies remain:
- `sounddevice` - Audio I/O
- `scipy` - WAV file handling
- `evdev` - Input device events
- `whisper` - Speech recognition
- `piper-tts` - Text-to-speech
- `unitree_sdk2py` - Robot control

## Migration Notes

For systems currently using wireless clicker:

1. **Physical Change:** Replace clicker with USB headset
2. **Config Change:** Update `config.env` with new audio settings
3. **User Training:** Inform users about Volume Up button for recording
4. **Testing:** Run `test_usb_audio.py` to verify setup

For systems wanting to keep both options:

1. Keep both clicker and USB headset connected
2. Use config to switch between modes
3. Create separate config files (e.g., `config-headset.env`, `config-clicker.env`)

## Future Enhancements

Potential improvements:
- Support for multiple headset brands/models
- Configurable button mapping
- Auto-detection and switching between available devices
- Bluetooth headset support
- Audio level monitoring and adjustment

## Support

For issues or questions:
- Run diagnostic script: `python test_usb_audio.py`
- Check logs in `logs/` directory
- Verify configuration with `config.print_config()`
- Review this migration guide

---

**Last Updated:** November 2025

