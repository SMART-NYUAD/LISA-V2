#!/usr/bin/env python3
"""
Test script for lisa_nav_cam.py functionality
This allows testing the compound action execution without voice input
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lisa_nav_cam import execute_compound_action
from robot_functions import robot_speak, initialize_sdk

def test_navigation_and_camera():
    """Test navigation to dispenser and taking a picture"""
    print("\n=== Test 1: Navigate to dispenser and take picture ===")
    
    # Initialize SDK first
    initialize_sdk()
    
    actions = [
        {"type": "navigate_to", "params": {"location": "dispenser"}},
        {"type": "take_picture", "params": {}}
    ]
    
    robot_speak("Starting test: navigating to dispenser and taking a picture")
    print("This will now wait for navigation to complete before taking the picture")
    result = execute_compound_action(actions)
    print(f"Result: {result}")
    
def test_picture_and_analysis():
    """Test taking a picture and analyzing it"""
    print("\n=== Test 2: Take picture and analyze ===")
    
    actions = [
        {"type": "take_picture", "params": {}},
        {"type": "analyze_image", "params": {}}
    ]
    
    robot_speak("Starting test: taking a picture and analyzing it")
    result = execute_compound_action(actions)
    print(f"Result: {result}")

def test_complex_sequence():
    """Test a complex sequence with navigation, waiting, and camera"""
    print("\n=== Test 3: Complex sequence ===")
    
    actions = [
        {"type": "navigate_to", "params": {"location": "workbench"}},
        {"type": "wait", "params": {"seconds": 3}},
        {"type": "take_picture", "params": {}},
        {"type": "analyze_image", "params": {}}
    ]
    
    robot_speak("Starting test: complex sequence with navigation, waiting, and analysis")
    print("This will execute actions in proper sequence:")
    print("1. Navigate to workbench (wait for completion)")
    print("2. Wait 3 seconds")
    print("3. Take picture")
    print("4. Analyze image")
    result = execute_compound_action(actions)
    print(f"Result: {result}")

def test_sequential_navigation():
    """Test sequential navigation to multiple locations"""
    print("\n=== Test 4: Sequential navigation ===")
    
    actions = [
        {"type": "navigate_to", "params": {"location": "station"}},
        {"type": "wait", "params": {"seconds": 2}},
        {"type": "navigate_to", "params": {"location": "workbench"}},
        {"type": "wait", "params": {"seconds": 2}},
        {"type": "navigate_to", "params": {"location": "dispenser"}},
        {"type": "take_picture", "params": {}}
    ]
    
    robot_speak("Starting test: sequential navigation to multiple locations")
    print("This will navigate to station, then workbench, then dispenser, then take a picture")
    print("Each navigation will wait for completion before proceeding")
    result = execute_compound_action(actions)
    print(f"Result: {result}")

def main():
    """Main test function"""
    print("LISA Navigation & Camera Test Suite")
    print("===================================")
    
    # Select which test to run
    print("\nAvailable tests:")
    print("1. Navigate to dispenser and take picture")
    print("2. Take picture and analyze")
    print("3. Complex sequence (navigate, wait, picture, analyze)")
    print("4. Sequential navigation (station → workbench → dispenser)")
    print("5. Run all tests")
    
    choice = input("\nSelect test (1-5): ").strip()
    
    if choice == "1":
        test_navigation_and_camera()
    elif choice == "2":
        test_picture_and_analysis()
    elif choice == "3":
        test_complex_sequence()
    elif choice == "4":
        test_sequential_navigation()
    elif choice == "5":
        test_navigation_and_camera()
        input("\nPress Enter to continue to next test...")
        test_picture_and_analysis()
        input("\nPress Enter to continue to next test...")
        test_complex_sequence()
        input("\nPress Enter to continue to next test...")
        test_sequential_navigation()
    else:
        print("Invalid choice")
    
    print("\nTest completed!")

if __name__ == "__main__":
    main() 