# LISA Usage Guide

This guide provides detailed instructions for using LISA in different modes and scenarios.

## Table of Contents

1. [Running LISA](#running-lisa)
2. [Input Modes](#input-modes)
3. [Basic Commands](#basic-commands)
4. [Navigation](#navigation)
5. [Vision and Image Analysis](#vision-and-image-analysis)
6. [Safety Protocol](#safety-protocol)
7. [Advanced Features](#advanced-features)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

---

## Running LISA

### Script Variants

LISA has three main script variants for different deployment scenarios:

| Script | Backend | Input Method | Use Case |
|--------|---------|--------------|----------|
| `lisa_local_kb.py` | Local Ollama | Keyboard | Development, testing |
| `lisa_api_kb.py` | Remote API | Keyboard | Testing with more powerful models |
| `lisa_api_clicker.py` | Remote API | Clicker + ASR | Production deployment, hands-free |

### Starting LISA

**Local Ollama with Keyboard**:
```bash
python lisa_local_kb.py
```

**Remote API with Keyboard**:
```bash
python lisa_api_kb.py
```

**Remote API with Clicker**:
```bash
python lisa_api_clicker.py
```

### Stopping LISA

- **Keyboard mode**: Type `quit`, `exit`, or `q`
- **Clicker mode**: Press `Ctrl+C`

---

## Input Modes

### Keyboard Input Mode

Type your commands directly:
```
You: Go to the work area
```

Special commands:
- `quit` / `exit` / `q` - Exit the program
- `clear` - Clear conversation history

### Clicker Input Mode

1. **Press the trigger key** (default: TAB) to start recording
2. **Speak your command** clearly
3. **Press the trigger key again** to stop recording
4. Wait for transcription and LISA's response

Special clicker functions:
- **PAGEDOWN key**: Clear conversation history

---

## Basic Commands

### Conversational Interaction

LISA understands natural language. You don't need to use exact phrases.

**Examples**:
```
Hello
How are you?
What can you do?
Tell me about your capabilities
```

### Navigation Commands

Navigate to predefined waypoints:

```
Go to the station
Navigate to the work area
Head to the storage area
Take me to the work area
```

Available locations:
- `station` - Supervisor location
- `storage_area` - Equipment storage
- `work_area` - Work location

### Camera Commands

Take pictures:
```
Take a picture
Capture an image
Can you take a photo?
```

Analyze current view:
```
What do you see?
Describe the scene
Look around and tell me what's there
```

### Combined Commands

Chain actions together naturally:
```
Go to the work area and take a picture
Navigate to the station, then take a picture and describe it
Check the work area
```

### Announcements

Make LISA speak custom messages:
```
Tell everyone to take a break
Announce that lunch is ready
Say "the meeting starts in 5 minutes"
```

---

## Navigation

### Available Waypoints

The default waypoints are:
- **station**: Supervisor/command post location
- **storage_area**: Equipment and PPE storage
- **work_area**: Main work location

### Customizing Waypoints

Edit `ros_functions.py` to add or modify waypoints:

```python
waypoints = {
    'my_custom_location': {
        'x': 5.0,        # X position in map frame
        'y': 3.0,        # Y position in map frame
        'z': 0.0,        # Z position (usually 0)
        'qx': 0.0,       # Quaternion orientation
        'qy': 0.0,
        'qz': 0.0,
        'qw': 1.0
    }
}
```

### Recording Waypoints

Use RViz to find coordinates:
1. Open RViz with your navigation stack
2. Use "2D Pose Estimate" tool to place robot at desired location
3. Note the coordinates from the topic `/amcl_pose` or similar
4. Add to `ros_functions.py`

### Navigation Status

LISA will announce:
- When navigation starts
- Navigation progress (if applicable)
- When destination is reached
- If navigation fails

---

## Vision and Image Analysis

### Taking Pictures

Simply ask LISA to take a picture:
```
Take a picture
Capture an image
Take a photo
```

The image is saved to `tmp/frame.jpg`.

### Analyzing Images

After taking a picture, you can ask about it:
```
What do you see?
Describe the image
What's in the picture?
Is there a person in the image?
```

### Inspection Workflow

Use the "inspect" command for comprehensive location checks:
```
Inspect the work area
Check the storage area
Examine the station
```

LISA will:
1. Navigate to the location
2. Take a picture
3. Analyze the image
4. Detect safety violations (if configured)
5. Report findings

### Vision Capabilities

LISA's vision analysis can:
- Detect people in images
- Identify clothing and PPE (hard hats, vests)
- Describe scenes and objects
- Count items
- Read text (depending on model)

---

## Safety Protocol

### Automatic Safety Detection

When inspecting a location, LISA automatically checks for:
- Workers without hard hats
- Missing PPE
- Safety violations

### Safety Violation Workflow

When LISA detects a safety violation:

**Step 1: Confirm with Worker**
```
LISA: "I notice you're not wearing a hard hat. This is a safety violation.
       What's your name? Would you like me to fetch one for you?"
```

**Step 2: Navigate to Storage**
- LISA goes to `storage_area`

**Step 3: Request Hard Hat**
```
LISA: "Hello, I need a hard hat for [worker name] who is at [location].
       Can you provide one?"
```

**Step 4: Confirm Receipt**
```
LISA: "Thank you. Is the hard hat secure and ready for transport?"
```

**Step 5: Return to Worker**
- LISA navigates back to the worker's location

**Step 6: Deliver Hard Hat**
```
LISA: "Here's your hard hat from storage. Please wear it at all times."
```

**Step 7: Report to Supervisor**
- LISA navigates to `station`
- Reports the incident and resolution

### Manual Safety Protocol Activation

You can manually trigger the safety protocol:
```
Activate safety protocol
There's a safety violation
A worker isn't wearing their hard hat
```

### Customizing Safety Rules

Edit `safety_prompt_v2.md` to customize:
- Safety rules and violations to check
- Workflow steps
- Announcement messages
- Required PPE items

---

## Advanced Features

### Multi-Step Commands

LISA can handle complex, multi-step requests:

```
Go to the work area, take a picture, analyze it,
then come back to the station and tell me what you found
```

LISA will:
1. Parse the entire request
2. Execute each step in sequence
3. Remember context between steps
4. Report results at the end

### Context Awareness

LISA maintains conversation context:

```
You: Go to the work area
LISA: [navigates]
You: Take a picture
LISA: [takes picture at current location]
You: What do you see?
LISA: [analyzes the picture just taken]
```

### Clearing Conversation History

To start fresh:
- **Keyboard mode**: Type `clear`
- **Clicker mode**: Press PAGEDOWN key

This clears all conversation context and starts a new session.

---

## Configuration

### Environment Variables

Set before running LISA:

```bash
# Model selection
export LISA_CHAT_MODEL="gemma3:27b"
export LISA_VISION_MODEL="gemma3:27b"

# Unitree SDK path
export UNITREE_SDK_PATH="/home/unitree/unitree_sdk2_python"
```

### Script Configuration

Edit the scripts directly to configure:

**API Endpoint** (in `lisa_api_kb.py` and `lisa_api_clicker.py`):
```python
OLLAMA_API_BASE = "http://192.168.50.103:11434"
```

**Speech Enable/Disable** (in all scripts):
```python
ENABLE_SPEECH = True  # Set to False to disable TTS
```

**ASR Model** (in `robot_functions.py`):
```python
ASR_MODEL = "tiny.en"  # Options: tiny.en, base.en, small.en, medium.en, large
```

**TTS Voice** (in `robot_functions.py`):
```python
def robot_speak(text, model_name="en_US-amy-medium.onnx"):
```

### Prompt Customization

Customize LISA's behavior by editing:

**`prompt_v2.md`** - Main system prompt
- Core capabilities
- Response format
- Function definitions
- Communication style

**`safety_prompt_v2.md`** - Safety protocol
- Safety rules
- Workflow steps
- Required checks

**`visual_prompt.md`** - Vision analysis
- What to look for in images
- Description format

---

## Troubleshooting

### LISA doesn't understand my command

**Try**:
- Rephrase more clearly
- Break complex requests into simpler steps
- Use explicit location names: "work area" not "over there"

### Navigation fails

**Check**:
- ROS 2 navigation stack is running
- Robot is localized in the map
- Path to destination is clear
- Waypoint coordinates are correct

**Debug**:
```bash
# Check ROS 2 topics
ros2 topic list
ros2 topic echo /goal_pose

# Check navigation status
ros2 topic echo /action_status
```

### Camera doesn't work

**Check**:
- Robot SDK is properly initialized
- Camera is not in use by another process
- `tmp/` directory is writable

**Test**:
```python
from robot_functions import robot_take_pic
robot_take_pic()
```

### Speech not working

**Check**:
- Audio device is connected and working
- User is in `audio` group: `groups`
- TTS models are in `TTS_models/` directory
- Volume is not muted

**Test**:
```python
from robot_functions import robot_speak
robot_speak("This is a test")
```

### Clicker not responding

**Check**:
- Clicker is charged and powered on
- User is in `input` group: `groups`
- Device is recognized: `ls /dev/input/by-id/`

**Test**:
```bash
python3 -c "from robot_functions import detect_clickers; print(detect_clickers())"
```

### Vision analysis returns errors

**Check**:
- Image file exists: `ls tmp/frame.jpg`
- Vision model is loaded in Ollama: `ollama list`
- Sufficient memory for model inference

### High latency or slow responses

**Solutions**:
- Use smaller models (`gemma3:4b` instead of `27b`)
- Run Ollama locally instead of remote API
- Reduce image resolution in `robot_functions.py`
- Use faster Whisper model (`tiny.en` instead of `medium.en`)

---

## Best Practices

### For Keyboard Mode Testing

1. Start with simple commands to verify functionality
2. Test navigation first before combining with other actions
3. Use `clear` between test scenarios
4. Monitor terminal output for DEBUG messages

### For Production Deployment (Clicker Mode)

1. Train users on clicker button functions
2. Test in actual environment before deployment
3. Ensure clear audio path (minimal background noise)
4. Keep commands concise and clear
5. Wait for LISA to complete one task before issuing next command

### For Safety Monitoring

1. Always have human supervision
2. Test safety protocol workflow in safe environment first
3. Verify waypoint paths are obstacle-free
4. Configure appropriate detection thresholds
5. Train personnel on robot interaction

---

## Example Sessions

### Basic Inspection

```
You: Hello LISA
LISA: Hello! I'm LISA, your navigation and camera assistant...

You: Inspect the work area
LISA: I'll navigate to the work area, take a picture, and check for any issues.
[Navigates, takes picture, analyzes]
LISA: I'm at the work area. I can see a person wearing a hard hat and safety vest...
```

### Safety Violation Response

```
You: Check the work area
LISA: [Navigates to work area, takes picture]
LISA: I've detected a safety violation...
[Executes full safety protocol workflow]
```

### Multi-Location Patrol

```
You: Check all three locations and report back
LISA: I'll inspect the station, storage area, and work area, then provide a summary.
[Executes inspections]
LISA: Inspection complete. Station: clear. Storage area: equipment organized...
```

---

## Logging and Monitoring

### Log Files

Logs are automatically saved to:
- `chat_logs_api/terminal_<timestamp>.txt` - API mode logs
- `chat_logs_local/terminal_<timestamp>.txt` - Local mode logs

### Log Contents

- User inputs
- LISA responses
- Function executions
- Navigation status
- Errors and warnings
- Response times

### Reviewing Logs

```bash
# View latest log
tail -f chat_logs_api/terminal_*.txt | tail -1

# Search for errors
grep -i error chat_logs_api/terminal_*.txt
```

---

## Tips and Tricks

1. **Be specific**: "Go to the work area" is better than "go there"
2. **Wait for completion**: Let LISA finish one task before starting another
3. **Use natural language**: LISA understands context, not just keywords
4. **Check logs**: Terminal output shows what LISA is thinking
5. **Test incrementally**: Verify each component works before combining

---

**Last Updated**: October 2025

