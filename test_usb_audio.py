#!/usr/bin/env python3
"""
Test script for USB headset audio configuration

This script tests the USB headset detection and basic audio functionality
for the LISA system.

Usage:
    python test_usb_audio.py
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from robot_functions import detect_usb_headset, detect_usb_headset_input
from config import config
import sounddevice as sd

def test_audio_detection():
    """Test USB headset detection for audio I/O"""
    print("\n=== Testing USB Headset Detection ===")
    print(f"Configuration:")
    print(f"  AUDIO_OUTPUT_DEVICE: {config.AUDIO_OUTPUT_DEVICE}")
    print(f"  AUDIO_INPUT_DEVICE: {config.AUDIO_INPUT_DEVICE}")
    print()
    
    # Test audio device detection
    print("Detecting USB headset for audio I/O...")
    input_device, output_device = detect_usb_headset()
    
    if input_device is not None:
        print(f"✓ USB headset input device found: {input_device}")
    else:
        print("✗ USB headset input device not found")
    
    if output_device is not None:
        print(f"✓ USB headset output device found: {output_device}")
    else:
        print("✗ USB headset output device not found")
    
    return input_device, output_device

def test_input_device_detection():
    """Test USB headset detection for button events"""
    print("\n=== Testing USB Headset Input Device Detection ===")
    print("Detecting USB headset input devices for button events...")
    
    headset_devices = detect_usb_headset_input()
    
    if headset_devices:
        print(f"✓ Found {len(headset_devices)} USB headset input device(s):")
        for device in headset_devices:
            print(f"  - {device.name}")
            print(f"    Path: {device.path}")
        return True
    else:
        print("✗ No USB headset input devices found")
        return False

def list_all_audio_devices():
    """List all available audio devices"""
    print("\n=== All Available Audio Devices ===")
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        print(f"Device {idx}: {device['name']}")
        print(f"  Max input channels: {device['max_input_channels']}")
        print(f"  Max output channels: {device['max_output_channels']}")
        print(f"  Default sample rate: {device['default_samplerate']}")
        print()

def test_playback(output_device):
    """Test audio playback on USB headset"""
    print("\n=== Testing USB Headset Playback ===")
    
    # Look for test audio files
    test_files = [
        "audio/start_cue.wav",
        "audio/stop_cue.wav"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"Testing playback of {test_file}...")
            try:
                from scipy.io import wavfile
                sample_rate, audio_data = wavfile.read(test_file)
                print(f"Playing audio on device {output_device}...")
                sd.play(audio_data, sample_rate, device=output_device)
                sd.wait()
                print("✓ Playback successful")
                return True
            except Exception as e:
                print(f"✗ Playback failed: {e}")
                return False
    
    print("No test audio files found")
    return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("USB Headset Audio Configuration Test")
    print("="*60)
    
    # Test 1: List all audio devices
    list_all_audio_devices()
    
    # Test 2: Detect USB headset for audio
    input_device, output_device = test_audio_detection()
    
    # Test 3: Detect USB headset for input events
    input_detection_success = test_input_device_detection()
    
    # Test 4: Test playback if output device found
    playback_success = False
    if output_device is not None:
        playback_success = test_playback(output_device)
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Audio input detection:   {'✓ PASS' if input_device is not None else '✗ FAIL'}")
    print(f"Audio output detection:  {'✓ PASS' if output_device is not None else '✗ FAIL'}")
    print(f"Button input detection:  {'✓ PASS' if input_detection_success else '✗ FAIL'}")
    print(f"Playback test:           {'✓ PASS' if playback_success else '✗ SKIP'}")
    print("="*60)
    
    if input_device is not None and output_device is not None and input_detection_success:
        print("\n✓ All critical tests passed! USB headset is properly configured.")
        return 0
    else:
        print("\n✗ Some tests failed. Please check your USB headset connection.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

