# LISA Navigation & Camera System

A voice-controlled robot assistant that can execute compound commands involving navigation and camera operations.

## Quick Start

1. **Run the main voice assistant:**
   ```bash
   cd /home/unitree/LISA_v3_nav
   python3 lisa_nav_cam.py
   ```

2. **Example voice commands:**
   - "Go to the dispenser and take a picture"
   - "Take a picture and tell me what you see"
   - "Navigate to the workbench, wait 3 seconds, then take a picture and describe it"

3. **Test without voice input:**
   ```bash
   python3 test_nav_cam.py
   ```

## Key Features

- **Compound Commands**: Execute multiple actions from a single voice command
- **Smart Parsing**: Natural language understanding for complex instructions
- **Image Analysis**: Take pictures and get AI-powered descriptions
- **Navigation**: Move between predefined waypoints (station, workbench, dispenser)

## Files

- `lisa_nav_cam.py` - Main voice-controlled assistant
- `nav_cam_sys_prompt.md` - System prompt for the LLM
- `test_nav_cam.py` - Test script for debugging
- `lisa_nav_cam_usage.md` - Detailed usage guide

## Requirements

- Ollama with `gemma3:4b-it-qat` model
- ROS navigation system running
- UDP bridge listening on port 5005
- Unitree robot SDK

See `lisa_nav_cam_usage.md` for detailed documentation. 