"""
Robot Functions Module for LISA

This module provides hardware control and interaction functions for the Unitree Go2 robot.
It handles camera operations, text-to-speech synthesis, speech recognition, and clicker input.

Key Functionalities:
- Unitree SDK initialization and client management
- Robot camera control and image capture
- Text-to-speech using Piper TTS
- Audio playback through robot speakers
- Speech recognition using Whisper ASR
- Wireless presenter clicker detection and input
- Audio recording with visual/audio cues

Dependencies:
- Unitree SDK 2 Python bindings
- Piper TTS for speech synthesis
- Whisper for speech recognition
- evdev for clicker device input
- sounddevice for audio I/O

Configuration:
- ASR_MODEL: Whisper model size (default: tiny.en)
- UNITREE_SDK_PATH: Path to Unitree SDK (configurable via environment)

Author: [Your team/organization]
Version: 2.0
"""
import os
import time
import sys
import math
import subprocess
import threading
import wave
import numpy as np
from pydub import AudioSegment
from piper.voice import PiperVoice
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import evdev
from select import select
import re

# Add Unitree SDK path (configurable via environment variable)
unitree_sdk_path = os.environ.get("UNITREE_SDK_PATH", "/home/unitree/unitree_sdk2_python")
if os.path.exists(unitree_sdk_path):
    sys.path.append(unitree_sdk_path)
else:
    print(f"Warning: Unitree SDK path not found: {unitree_sdk_path}")
    print("Set UNITREE_SDK_PATH environment variable if SDK is in a different location")

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.go2.vui.vui_client import VuiClient
from unitree_sdk2py.go2.audiohub.audiohub_client import AudioHubClient
from unitree_sdk2py.go2.video.video_client import VideoClient

# Global flag to track SDK initialization
_sdk_initialized = False
_sport_client = None
_vui_client = None
_audio_client = None
_video_client = None

# Global cache for Piper TTS voice model
_piper_voice_cache = {}

# Configuration
ASR_MODEL = "tiny.en"  # Whisper ASR model to use: tiny.en, base.en, small.en, medium.en, large

def detect_usb_headset():
    """
    Detect USB headset (Logitech) for audio I/O using sounddevice.
    
    Returns:
        tuple: (input_device_index, output_device_index) or (None, None) if not found
    """
    try:
        devices = sd.query_devices()
        input_device = None
        output_device = None
        
        for idx, device in enumerate(devices):
            device_name = device['name'].lower()
            # Look for USB headsets - Logitech, Jieli, and other gaming/USB headsets
            # Patterns: logitech, 046d (Logitech vendor ID), g435, g733, jieli, l80pro, gaming headset
            if any(pattern in device_name for pattern in ['logitech', '046d', 'g435', 'g733', 'jieli', 'l80pro', 'gaming headset', 'usb audio']):
                # Check if device supports input (recording)
                if device['max_input_channels'] > 0:
                    input_device = idx
                    print(f"[Audio] Found USB headset input: {device['name']} (device {idx})")
                # Check if device supports output (playback)
                if device['max_output_channels'] > 0:
                    output_device = idx
                    print(f"[Audio] Found USB headset output: {device['name']} (device {idx})")
        
        return input_device, output_device
    except Exception as e:
        print(f"Error detecting USB headset: {e}")
        return None, None

def detect_usb_headset_input():
    """
    Detect USB headset (Logitech) as an input device for button events using evdev.
    
    Returns:
        list: List of evdev.InputDevice objects for the USB headset
    """
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        selected_devices = []
        for device in devices:
            device_name = device.name.lower()
            # Look for USB headsets (Logitech, Jieli, etc.)
            if any(pattern in device_name for pattern in ['logitech', '046d', 'jieli', 'l80pro', 'usb']):
                selected_devices.append(device)
                print(f"[Input] Found USB headset input device: {device.name}")
        return selected_devices
    except Exception as e:
        print(f"Error detecting USB headset input devices: {e}")
        print("Please ensure you have necessary permissions (e.g., add user to 'input' group).")
        return []

def initialize_sdk(interface="eth0"):
    """Initialize the Unitree SDK and clients"""
    global _sdk_initialized, _sport_client, _vui_client, _audio_client, _video_client
    
    # Only initialize once
    if not _sdk_initialized:
        try:
            ChannelFactoryInitialize(0, interface)
            _sdk_initialized = True
        except Exception as e:
            print(f"Warning: Channel factory already initialized or error: {e}")
            _sdk_initialized = True  # Assume it's already initialized

    # Create clients if they don't exist yet
    if _sport_client is None:
        _sport_client = SportClient()
        _sport_client.SetTimeout(10.0)
        _sport_client.Init()
        
    if _vui_client is None:
        _vui_client = VuiClient()
        _vui_client.SetTimeout(3.0)
        _vui_client.Init()
        
    if _audio_client is None:
        _audio_client = AudioHubClient()
        _audio_client.SetTimeout(3.0)
        _audio_client.Init()
        
    if _video_client is None:
        _video_client = VideoClient()
        _video_client.SetTimeout(3.0)
        _video_client.Init()
    
    return _sport_client, _vui_client, _audio_client

def robot_hello():
    """
    Makes the robot perform a hello motion
    
    Returns:
        bool: True if successful, False otherwise
    """
    sport_client, _, _ = initialize_sdk()
    
    try:
        print("Making robot say hello...")
        # Redirect stdout/stderr temporarily
        with open(os.devnull, 'w') as devnull:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = devnull
            sys.stderr = devnull
            
            # Execute the hello motion
            sport_client.Hello()
            
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def robot_take_pic(use_flash=True, flash_brightness=5, output_file=None):
    """
    Makes the robot take a picture with the front camera using the SDK
    
    Args:
        use_flash (bool): Whether to use the searchlight
        flash_brightness (int): Brightness level (0-10)
        output_file (str): Path to save the captured frame (default: PROJECT_ROOT/tmp/frame.jpg)
    
    Returns:
        bool: True if frame was captured successfully
    """
    # Default output path - project root / tmp / frame.jpg
    if output_file is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        output_file = os.path.join(project_root, "tmp", "frame.jpg")
    
    _, vui_client, _ = initialize_sdk()
    # Get video client separately since it's not returned by initialize_sdk
    video_client = _video_client
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:  # Only create if there's a directory component
        os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Set flash if requested
        if use_flash:
            vui_client.SetBrightness(flash_brightness)
            time.sleep(0.2)
        
        # Capture image using VideoClient
        print("Capturing image...")
        code, data = video_client.GetImageSample()
        
        if code != 0:
            print(f"Failed to capture image. Error code: {code}")
            return False
        
        # Save the image data to file
        with open(output_file, "wb") as f:
            f.write(bytes(data))
        
        # Turn off flash if it was on
        if use_flash:
            vui_client.SetBrightness(0)
        
        #print(f"Picture captured: {output_file}")
        print(f"Picture captured")
        return True
        
    except Exception as e:
        print(f"Error capturing image: {e}")
        # Ensure flash is turned off even if there's an error
        if use_flash:
            try:
                vui_client.SetBrightness(0)
            except:
                pass
        return False

# Speech utility functions
def set_volume(volume_level=6):
    """
    Set the robot's speaker volume
    
    Args:
        volume_level (int): Volume level (0-10)
    
    Returns:
        int: Current volume level after setting
    """
    # Use the global client
    #_, vui_client, _ = initialize_sdk()
    
    try:
        # Set volume
        vui_client.SetVolume(volume_level)
        
        # Get and return current volume
        code, current_volume = vui_client.GetVolume()
        print(f"Volume set to: {current_volume}")
        return current_volume
    except Exception as e:
        print(f"Error setting volume: {e}")
        return -1

def preload_tts_model(model_name="en_US-amy-medium.onnx"):
    """
    Preload the TTS model into cache to avoid latency on first speech generation.
    
    Args:
        model_name (str): Name of the model file in TTS_models directory
    """
    global _piper_voice_cache
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get project root (parent of src directory)
    project_root = os.path.dirname(script_dir)
    
    # Full path to model file - check if model_name is already an absolute path
    if os.path.isabs(model_name):
        model_path = model_name
    else:
        model_path = os.path.join(project_root, "TTS_models", model_name)
    
    # Only load if not already cached
    if model_path not in _piper_voice_cache:
        print(f"[TTS] Preloading model: {model_name}...", end=" ", flush=True)
        load_start = time.time()
        voice = PiperVoice.load(model_path)
        _piper_voice_cache[model_path] = voice
        print(f"done ({time.time() - load_start:.2f}s)")
    else:
        print(f"[TTS] Model already cached: {model_name}")

def generate_speech(text, model_name="en_US-amy-medium.onnx", output_dir="tmp", target_sample_rate=48000):
    """
    Generate speech from text and save it as a WAV file.
    Resamples to target_sample_rate if needed (for USB headset compatibility).
    
    Args:
        text (str): The text to convert to speech
        model_name (str): Name of the model file in TTS_models directory
        output_dir (str): Directory to save the output file (relative to LISA_v1)
        target_sample_rate (int): Target sample rate for output (default 48000 for USB headsets)
        
    Returns:
        str: Path to the generated audio file
    """
    global _piper_voice_cache
    start_time = time.time()
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get project root (parent of src directory)
    project_root = os.path.dirname(script_dir)
    
    # Full path to model file - check if model_name is already an absolute path
    if os.path.isabs(model_name):
        model_path = model_name
    else:
        model_path = os.path.join(project_root, "TTS_models", model_name)
    
    # Ensure output directory exists
    output_path = os.path.join(script_dir, output_dir)
    os.makedirs(output_path, exist_ok=True)
    
    # Output file path
    output_file = os.path.join(output_path, "output.wav")
    
    # Load or retrieve cached Piper voice
    if model_path in _piper_voice_cache:
        voice = _piper_voice_cache[model_path]
        print(f"[TTS] Using cached model")
    else:
        load_start = time.time()
        voice = PiperVoice.load(model_path)
        _piper_voice_cache[model_path] = voice
        print(f"[TTS] Model loaded in {time.time() - load_start:.2f}s")
    
    # Synthesize audio (collect all chunks first)
    synth_start = time.time()
    audio_chunks = []
    for chunk in voice.synthesize(text):
        audio_chunks.append(np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16))
    
    # Concatenate all audio chunks
    audio_data = np.concatenate(audio_chunks) if audio_chunks else np.array([], dtype=np.int16)
    source_sample_rate = voice.config.sample_rate
    
    # Resample if needed (once during generation for best quality)
    if source_sample_rate != target_sample_rate:
        print(f"[TTS] Resampling {source_sample_rate}Hz -> {target_sample_rate}Hz")
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(source_sample_rate, target_sample_rate)
        up = target_sample_rate // g
        down = source_sample_rate // g
        audio_data = resample_poly(audio_data, up, down).astype(np.int16)
        final_sample_rate = target_sample_rate
    else:
        final_sample_rate = source_sample_rate
    
    # Write to WAV file
    write(output_file, final_sample_rate, audio_data)
    
    print(f"[TTS] Synthesis completed in {time.time() - synth_start:.2f}s")
    print(f"[TTS] Total generation time: {time.time() - start_time:.2f}s")
    return output_file

def play_audio_usb(audio_file, output_device=None):
    """
    Play audio file on USB headset using sounddevice.
    Audio should already be at the correct sample rate (48kHz for most USB headsets).
    
    Args:
        audio_file (str): Path to the audio file
        output_device (int): Device index for output (optional, will be detected if None)
    """
    try:
        # Detect USB headset if device not specified
        if output_device is None:
            _, output_device = detect_usb_headset()
            if output_device is None:
                print("Error: USB headset output device not found")
                return False
        
        # Load audio file
        from scipy.io import wavfile
        sample_rate, audio_data = wavfile.read(audio_file)
        
        # Get audio duration
        duration_s = len(audio_data) / sample_rate
        print(f"Audio duration: {duration_s:.1f} seconds")
        
        # Play audio directly (should already be at 48kHz from TTS generation)
        print("Playing audio on USB headset...")
        sd.play(audio_data, samplerate=sample_rate, device=output_device)
        sd.wait()  # Wait until playback is finished
        print("Playback completed!")
        return True
        
    except Exception as e:
        print(f"Error playing audio on USB headset: {e}")
        return False

def play_audio(audio_file, audio_client=None):
    """
    Play audio file on the robot speaker or USB headset based on configuration
    
    Args:
        audio_file (str): Path to the audio file
        audio_client: AudioHubClient instance (optional, will be created if None)
    """
    # Import config here to avoid circular dependency
    from config import config
    
    # Route to appropriate output device
    if config.AUDIO_OUTPUT_DEVICE == "usb_headset":
        return play_audio_usb(audio_file)
    
    # Otherwise use robot speaker (original implementation)
    # Get the global client if not provided
    if audio_client is None:
        _, _, audio_client = initialize_sdk()
        
    try:
        # Get audio duration
        audio = AudioSegment.from_wav(audio_file)
        duration_ms = len(audio)
        print(f"Audio duration: {duration_ms/1000:.1f} seconds")
    except Exception as e:
        print(f"Warning: Could not get audio duration: {e}")
        duration_ms = 5000  # fallback to 5 seconds

    # Enable Megaphone
    megaphone_start = time.time()
    audio_client.MegaphoneEnter()
    print(f"[Playback] Megaphone enabled in {time.time() - megaphone_start:.2f}s")

    # Upload audio file
    upload_start = time.time()
    print("Uploading audio to robot...")
    audio_client.MegaphoneUpload(audio_file)
    print(f"[Playback] Upload completed in {time.time() - upload_start:.2f}s")
    
    # Wait for playback without verbose progress; just print a single status line
    try:
        print("Playing audio...")
        time.sleep(max(0, duration_ms / 1000.0))
        print("Playback completed!")
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user")
    finally:
        # Disable Megaphone
        audio_client.MegaphoneExit()

def play_cue_sound(audio_client, cue_filename):
    """Plays the specified cue sound file on USB headset or robot speaker."""
    # Import config here to avoid circular dependency
    from config import config
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cue_path = os.path.join(script_dir, "..", "audio", cue_filename)
    
    if not os.path.exists(cue_path):
        print(f"Warning: Cue file not found at {cue_path}")
        return
        
    print(f"Playing cue: {cue_filename}")
    
    # Route to appropriate output device
    if config.AUDIO_OUTPUT_DEVICE == "usb_headset":
        try:
            _, output_device = detect_usb_headset()
            if output_device is None:
                print("Error: USB headset output device not found for cue sound")
                return
            
            # Load cue sound (should already be at 48kHz)
            from scipy.io import wavfile
            sample_rate, audio_data = wavfile.read(cue_path)
            
            # Play cue sound directly
            sd.play(audio_data, samplerate=sample_rate, device=output_device)
            sd.wait()
        except Exception as e:
            print(f"Error playing cue sound on USB headset ({cue_filename}): {e}")
    else:
        # Use robot speaker (original implementation)
        try:
            # Enable Megaphone
            audio_client.MegaphoneEnter()
            
            # Upload and play audio
            audio_client.MegaphoneUpload(cue_path)
            
            # Wait a short fixed duration for the cue to play
            time.sleep(0.5) # Adjust if the cues are longer
            
        except Exception as e:
            print(f"Error playing cue sound ({cue_filename}): {e}")
        finally:
            # Ensure Megaphone is disabled
            try:
                audio_client.MegaphoneExit()
            except Exception as e:
                print(f"Error exiting megaphone mode during cue playback: {e}")

def robot_speak(text, model_name="en_US-amy-medium.onnx"):
    """
    Convert text to speech and play it on the configured audio output device
    (USB headset or robot speaker based on AUDIO_OUTPUT_DEVICE config)
    
    Args:
        text (str): The text to convert to speech and play
        model_name (str): Name of the TTS model file in TTS_models directory or absolute path
    """
    # Sanitize the input text
    # Only remove asterisks
    sanitized_text = re.sub(r'\*', '', text) # Changed regex to only remove asterisks
    if not sanitized_text.strip(): # If sanitization results in an empty string (e.g., input was just "***")
        print("Warning: Sanitized text is empty after removing asterisks. Nothing to speak.")
        return None # Or handle as appropriate, e.g., play a default sound

    # Initialize SDK (will reuse existing initialization)
    _, _, audio_client = initialize_sdk()
    
    # Generate speech with the sanitized text
    audio_file = generate_speech(sanitized_text, model_name)
    
    # Play audio
    if audio_file: # Check if audio_file was successfully created
        play_audio(audio_file, audio_client)
    
    return audio_file

# -------- Clicker Detection (Copied from presenter_test.py) --------
def detect_clickers():
    """
    Scan for input devices and return a list of devices that match the two clicker names.
    """
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        selected_devices = []
        for device in devices:
            # Match the two specific device names. Adjust if needed.
            if device.name in [
                "Wireless Present Wireless Present Keyboard",
                "KNORVAY Knorvay Wireless Presenter Keyboard"
            ]:
                selected_devices.append(device)
        return selected_devices
    except Exception as e:
        print(f"Error detecting clicker devices: {e}")
        print("Please ensure you have necessary permissions (e.g., add user to 'input' group).")
        return []
# --------------------------------------------------------------------

def record_audio(devices, output_path="tmp/recorded_audio.wav", sample_rate=None, trigger_key="KEY_VOLUMEUP", clear_key="KEY_PAGEDOWN", input_device=None, check_stop_func=None):
    """
    Records audio when a specific key is pressed on given devices, stops on second press.
    Also listens for a clear key to signal chat clearing.

    Args:
        devices (list): List of evdev.InputDevice objects to listen to.
        output_path (str): Path to save the recorded audio.
        sample_rate (int): Sample rate for the recording (optional, will use device's native rate if None).
        trigger_key (str): The keycode string (e.g., 'KEY_VOLUMEUP') to trigger recording.
        clear_key (str): The keycode string (e.g., 'KEY_PAGEDOWN') to signal chat clear.
        input_device (int): Audio input device index for sounddevice (optional, will be detected if None)
        check_stop_func (callable): Optional function that returns True if recording should be aborted.

    Returns:
        str: Path to the recorded audio file, "CLEAR_CHAT" if clear key was pressed,
             or None if recording failed or was cancelled.
    """
    # Import config here to avoid circular dependency
    from config import config
    
    # Ensure SDK is initialized and get the audio client (for robot speaker cues if configured)
    _, _, audio_client = initialize_sdk()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Detect USB headset for audio input if needed
    if input_device is None and config.AUDIO_INPUT_DEVICE == "usb_headset":
        input_device, _ = detect_usb_headset()
        if input_device is None:
            print("Error: USB headset input device not found")
            return None
    
    # Use device's native sample rate if not specified
    if sample_rate is None:
        if input_device is not None:
            device_info = sd.query_devices(input_device)
            sample_rate = int(device_info['default_samplerate'])
            print(f"[Audio] Using device sample rate: {sample_rate}Hz")
        else:
            sample_rate = 44100  # Fallback default

    print(f"Press '{trigger_key}' on the USB headset to start/stop recording, or '{clear_key}' to clear chat history...")

    audio_data = []
    recording = False
    stream = None

    try:
        while True:
            # Check for external stop signal
            if check_stop_func and check_stop_func():
                print("Recording aborted by stop signal.")
                if stream and recording:
                    stream.stop()
                    stream.close()
                return None

            r, _, _ = select(devices, [], [], 0.1) # Timeout avoids busy-waiting
            for device in r:
                try:
                    for event in device.read():
                        if event.type == evdev.ecodes.EV_KEY:
                            key_event = evdev.categorize(event)
                            if key_event.keystate == evdev.KeyEvent.key_down:
                                # --- Handle Recording Start/Stop ---
                                if key_event.keycode == trigger_key:
                                    if not recording:
                                        # Start recording
                                        print(f"Recording started... Press '{trigger_key}' again to stop.")

                                        # Play start cue
                                        play_cue_sound(audio_client, "start_cue.wav")

                                        audio_data = []
                                        def callback(indata, frames, time, status):
                                            if status:
                                                print(f"Recording status error: {status}")
                                            audio_data.append(indata.copy())
                                        
                                        # Create input stream with device specification
                                        stream_kwargs = {'callback': callback, 'channels': 1, 'samplerate': sample_rate}
                                        if input_device is not None:
                                            stream_kwargs['device'] = input_device
                                        stream = sd.InputStream(**stream_kwargs)
                                        stream.start()
                                        recording = True
                                    else:
                                        # Stop recording
                                        print("Recording stopped.")

                                        # Play stop cue
                                        play_cue_sound(audio_client, "stop_cue.wav")

                                        if stream:
                                            stream.stop()
                                            stream.close()
                                        
                                        if not audio_data:
                                            print("No audio data recorded.")
                                            return None
                                            
                                        audio_array = np.concatenate(audio_data, axis=0)
                                        write(output_path, sample_rate, audio_array)
                                        print(f"Audio saved to {output_path}")
                                        return output_path # Recording finished successfully

                                # --- Handle Chat Clear ---
                                elif key_event.keycode == clear_key:
                                    print("Chat clear requested by clicker.")
                                    if recording:
                                        # Stop recording if it was in progress
                                        print("Stopping active recording due to clear request.")
                                        if stream:
                                            stream.stop()
                                            stream.close()
                                        recording = False # Ensure recording flag is reset
                                    # Play a confirmation cue? (Optional)
                                    # play_cue_sound(audio_client, "clear_cue.wav") # Example
                                    return "CLEAR_CHAT"
                except BlockingIOError:
                    # No events available to read, continue loop
                    continue
                except Exception as e:
                    print(f"Error reading from device {device.path}: {e}")
                    # Optionally remove the problematic device? For now, just continue.
                    continue
            # Add a small sleep if no devices were ready to prevent potential high CPU usage
            if not r:
                time.sleep(0.01)
                
    except KeyboardInterrupt:
        print("Recording interrupted by user (Ctrl+C).")
        if stream and recording:
            stream.stop()
            stream.close()
        return None # Indicate interruption
    except Exception as e:
        print(f"Unexpected error in recording loop: {e}")
        return None
    finally:
        # Ensure stream is closed if loop exits unexpectedly
        if stream and not stream.closed:
            stream.stop()
            stream.close()
            print("Stream closed on exit.")

def transcribe_audio(audio_path, model_name=ASR_MODEL):
    """
    Transcribes audio file to text using Whisper
    
    Args:
        audio_path (str): Path to the audio file
        model_name (str): Whisper model to use
        
    Returns:
        str: Transcribed text
    """
    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path, fp16=False)
    return result["text"]

def robot_listen(output_path="tmp/recorded_audio.wav", sample_rate=None, model_name=ASR_MODEL, trigger_key="KEY_VOLUMEUP", clear_key="KEY_PAGEDOWN", check_stop_func=None):
    """
    Detects USB headset, records audio when the trigger key is pressed, stops recording
    on second press, transcribes the audio, OR detects the clear key press.

    Args:
        output_path (str): Path to save the recorded audio.
        sample_rate (int): Sample rate for the recording.
        model_name (str): Whisper model to use.
        trigger_key (str): The keycode string to trigger recording (e.g., 'KEY_VOLUMEUP').
        clear_key (str): The keycode string to trigger chat clear (e.g., 'KEY_PAGEDOWN').
        check_stop_func (callable): Optional function that returns True if listening should be aborted.

    Returns:
        str: Transcribed text from the recorded audio, "CLEAR_CHAT" if clear key was pressed,
             or None if recording failed/cancelled.
    """
    # Import config here to avoid circular dependency
    from config import config
    
    print("Detecting USB headset input devices...")
    headset_devices = detect_usb_headset_input()
    
    if not headset_devices:
        print("Error: No matching USB headset devices found. Cannot start listening.")
        print("Please ensure a Logitech USB headset is connected and you have permissions.")
        return None
        
    print("Found USB headset input devices:")
    for device in headset_devices:
        # Grab exclusive access to the devices to prevent others (like the OS) from using them
        try:
            device.grab() 
            print(f" - {device.name} (Grabbed successfully)")
        except IOError as e:
            print(f" - {device.name} (Failed to grab: {e}. Events might be captured elsewhere.)")
            # Decide if we should continue without grab or fail? Let's try continuing.
            
    # Check stop signal before starting
    if check_stop_func and check_stop_func():
        print("Listening cancelled before start.")
        # Release grabbed devices before returning
        for device in headset_devices:
            try:
                device.ungrab()
            except:
                pass
            try:
                device.close()
            except:
                pass
        return None

    try:
        record_result = record_audio(headset_devices, output_path, sample_rate, trigger_key, clear_key, check_stop_func=check_stop_func)

        if record_result == "CLEAR_CHAT":
            return "CLEAR_CHAT" # Pass the signal up
        elif record_result: # Path to audio file returned
            print("Transcribing audio...")
            text = transcribe_audio(record_result, model_name)
            print(f"Transcribed text: {text}")
            return text
        else:
            print("Recording was cancelled or failed.")
            return None
            
    finally:
        # Release and close the devices to avoid noisy __del__ errors on Ctrl+C
        print("Releasing USB headset input devices...")
        for device in headset_devices:
            try:
                try:
                    device.ungrab()
                except Exception as e:
                    print(f"Could not ungrab {device.name}: {e}")
                # Explicitly close the device fd to prevent evdev __del__ errors
                try:
                    device.close()
                except Exception as e:
                    print(f"Could not close {device.name}: {e}")
            except Exception:
                # Swallow any unexpected errors during cleanup
                pass
        