# LISA Navigation & Camera Assistant Usage Guide

## Overview
`lisa_nav_cam.py` is an enhanced version of LISA that can execute multiple robot functions in sequence through natural language voice commands. It combines navigation, camera operations, and image analysis capabilities.

## Features
- **Compound Command Processing**: Understands and executes multiple actions from a single voice command
- **Navigation**: Can navigate to predefined locations (station, workbench, dispenser)
- **Camera Operations**: Takes pictures using the robot's front camera
- **Image Analysis**: Analyzes captured images and describes what it sees
- **Timing Control**: Can wait between actions for precise timing

## Example Voice Commands

### Basic Commands
- "Go to the dispenser"
- "Take a picture"
- "Tell me what you see" (after taking a picture)

### Compound Commands
- "Go to the dispenser and take a picture"
- "Take a picture and tell me what you see"
- "Go to the workbench, take a picture, and tell me what you see"
- "Navigate to the station, wait 5 seconds, then take a picture"
- "Go to the dispenser, take a picture, and describe what's there"

## How It Works

1. **Voice Input**: The system listens for your voice command using the robot's microphone
2. **Command Parsing**: The LLM parses your natural language into a sequence of actions
3. **Action Execution**: The robot executes each action in order:
   - Navigation commands send goal poses to the ROS navigation system
   - Camera commands control the robot's camera and flash
   - Wait commands pause execution for specified durations
4. **Image Analysis**: When requested, the LLM analyzes captured images and provides descriptions
5. **Voice Feedback**: The robot speaks responses and analysis results

## Running the Script

```bash
cd /home/unitree/LISA_v3_nav
python3 lisa_nav_cam.py
```

## Technical Details

### Available Actions
- `navigate_to`: Moves robot to a location
  - Locations: 'station', 'workbench', 'dispenser'
- `take_picture`: Captures image with front camera
  - Saves to: `/home/unitree/LISA_v3_nav/tmp/frame.jpg`
- `analyze_image`: Analyzes the last captured image
- `wait`: Pauses for specified seconds

### System Requirements
- Ollama with `gemma3:4b-it-qat` model
- ROS navigation system running
- Robot SDK initialized
- Microphone and speaker access

### File Structure
```
LISA_v3_nav/
├── lisa_nav_cam.py          # Main script
├── nav_cam_sys_prompt.md    # System prompt for LLM
├── robot_functions.py       # Robot control functions
├── ros_functions.py         # ROS navigation functions
└── tmp/                     # Directory for captured images
    └── frame.jpg           # Latest captured image
```

## Troubleshooting

### Navigation Not Working
- Ensure ROS navigation stack is running
- Check that the ROS bridge is listening on UDP port 5005
- Verify waypoint coordinates in `ros_functions.py`

### Camera Issues
- Make sure the robot SDK is properly initialized
- Check camera permissions
- Verify the output directory exists (`/home/unitree/LISA_v3_nav/tmp/`)

### Voice Recognition Problems
- Speak clearly and wait for the listening prompt
- Reduce background noise
- Check microphone connection and permissions

## Customization

### Adding New Locations
Edit `ros_functions.py` and add new waypoints to the `waypoints` dictionary in the `navigate_to` function.

### Modifying Actions
Edit `lisa_nav_cam.py` and add new action types in the `execute_compound_action` function.

### Changing the LLM Model
Update the `MODEL` variable in `lisa_nav_cam.py` to use a different Ollama model.

## Safety Notes
- The robot will move autonomously - ensure clear paths
- Navigation timeout is set to 10 seconds per location
- Camera flash may be bright in dark environments
- Always supervise robot operation 