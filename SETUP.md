# LISA Setup Guide

This guide provides detailed instructions for setting up LISA on your Unitree Go2 robot.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Hardware Setup](#hardware-setup)
3. [Software Dependencies](#software-dependencies)
4. [Unitree SDK Installation](#unitree-sdk-installation)
5. [ROS 2 Setup](#ros-2-setup)
6. [Ollama Installation](#ollama-installation)
7. [Python Environment Setup](#python-environment-setup)
8. [TTS Models Setup](#tts-models-setup)
9. [Audio Device Configuration](#audio-device-configuration)
10. [Network Configuration](#network-configuration)
11. [Configuration and Testing](#configuration-and-testing)

---

## System Requirements

### Hardware
- Unitree Go2 quadruped robot
- Linux-based control computer (onboard or external)
- Wireless presenter clicker (optional, for clicker-based input)
  - Supported: "Wireless Present Wireless Present Keyboard"
  - Supported: "KNORVAY Knorvay Wireless Presenter Keyboard"

### Software
- **Operating System**: Ubuntu 20.04 or later (tested on Ubuntu 20.04/22.04)
- **Python**: 3.8 or later
- **ROS 2**: Humble Hawksbill or later
- **Storage**: At least 10GB free space for models and dependencies

---

## Hardware Setup

1. **Power on the Unitree Go2 robot**
   - Ensure battery is charged
   - Wait for robot to complete boot sequence

2. **Network Connection**
   - Connect to robot's WiFi network or
   - Ensure robot and control computer are on same network

3. **Test Robot Connection**
   ```bash
   ping <robot-ip-address>
   ```

---

## Software Dependencies

### System Packages

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install basic dependencies
sudo apt install -y \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    espeak-ng

# Install ROS 2 dependencies (if not already installed)
sudo apt install -y \
    ros-humble-desktop \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup
```

### Audio Permissions

Add your user to the audio and input groups:
```bash
sudo usermod -a -G audio $USER
sudo usermod -a -G input $USER
```

**Important**: Log out and log back in for group changes to take effect.

---

## Unitree SDK Installation

### 1. Download Unitree SDK 2

```bash
cd ~
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
```

### 2. Install SDK

Follow the official Unitree SDK installation instructions:
```bash
pip3 install -e .
```

### 3. Set Environment Variable

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export UNITREE_SDK_PATH="/home/unitree/unitree_sdk2_python"
```

Then reload:
```bash
source ~/.bashrc
```

### 4. Test SDK Installation

```python
python3 -c "from unitree_sdk2py.core.channel import ChannelFactoryInitialize; print('SDK OK')"
```

---

## ROS 2 Setup

### 1. Install ROS 2 Humble

If not already installed, follow the official ROS 2 installation guide:
```bash
# Add ROS 2 repository
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install ros-humble-desktop -y
```

### 2. Source ROS 2

Add to your `~/.bashrc`:
```bash
source /opt/ros/humble/setup.bash
```

### 3. Set Up ROS 2 Navigation Bridge

LISA communicates with ROS 2 navigation via UDP (ports 5005/5006). You need a ROS 2 node that:
- Listens for goal poses on UDP port 5005
- Publishes to `/goal_pose` topic
- Sends goal status updates to UDP port 5006

Create a bridge node or use the provided bridge script (contact maintainers for the ROS 2 bridge package).

### 4. Configure Navigation Waypoints

Edit `ros_functions.py` to set your custom waypoint coordinates:

```python
waypoints = {
    'station': {
        'x': 2.95, 'y': 1.54, 'z': 0.0,
        'qx': 0.0, 'qy': 0.0, 'qz': -0.69, 'qw': 0.72
    },
    'storage_area': {
        'x': 2.36, 'y': -1.53, 'z': 0.0,
        'qx': 0.0, 'qy': 0.0, 'qz': 0.0, 'qw': 1.0
    },
    'work_area': {
        'x': 12.17, 'y': -7.09, 'z': 0.0,
        'qx': 0.0, 'qy': 0.0, 'qz': 0.75, 'qw': 0.66
    }
}
```

To find coordinates, use RViz to record positions in your mapped environment.

---

## Ollama Installation

### Local Installation (Recommended for low latency)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull gemma3:4b   # For local scripts
ollama pull gemma3:27b  # For better quality (requires more VRAM)
```

### Remote API Setup

If using a remote Ollama server:

1. **On the server machine**, install and run Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama serve
   ```

2. **Configure the API endpoint** in `lisa_api_kb.py` or `lisa_api_clicker.py`:
   ```python
   OLLAMA_API_BASE = "http://<server-ip>:11434"
   ```

3. **Test connection**:
   ```bash
   curl http://<server-ip>:11434/api/tags
   ```

---

## Python Environment Setup

### 1. Create Virtual Environment (Optional but Recommended)

```bash
cd ~/LISA_v3_nav_clean
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- `cyclonedds` - ROS 2 Python client
- `ollama` - Ollama Python client
- `pydub` - Audio processing
- `piper-tts` - Text-to-speech
- `openai-whisper` - Speech recognition
- `sounddevice` - Audio I/O
- `numpy`, `scipy` - Numerical computing

### 3. Verify Whisper Installation

```bash
python3 -c "import whisper; print(whisper.available_models())"
```

---

## TTS Models Setup

### 1. Create TTS Models Directory

```bash
mkdir -p ~/LISA_v3_nav_clean/TTS_models
cd ~/LISA_v3_nav_clean/TTS_models
```

### 2. Download Piper TTS Models

Download models from [Piper TTS releases](https://github.com/rhasspy/piper/releases):

```bash
# Example: Download English (US) Amy voice
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/en_US-amy-medium.onnx
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/en_US-amy-medium.onnx.json
```

Recommended models:
- `en_US-amy-medium.onnx` (good quality, medium speed)
- `en_US-libritts-high.onnx` (high quality, slower)
- `en_GB-*` models for British accent

### 3. Update TTS Model Path (if needed)

The default model is `en_US-amy-medium.onnx`. To change, edit `robot_functions.py`:

```python
def robot_speak(text, model_name="en_US-amy-medium.onnx"):
```

---

## Audio Device Configuration

### 1. Install Clicker Support (for ASR mode)

The clicker devices should be recognized automatically. To verify:

```bash
ls /dev/input/by-id/
```

Look for devices matching the clicker names.

### 2. Test Audio Input

```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

### 3. Configure Default Audio Device (if needed)

If you have multiple audio devices, set the default:

```bash
# List devices
arecord -l
aplay -l

# Set default in ~/.asoundrc
cat > ~/.asoundrc << EOF
defaults.pcm.card 0
defaults.pcm.device 0
EOF
```

### 4. Generate Cue Sounds

The repository includes `start_cue.wav` and `stop_cue.wav`. To regenerate or customize:

```bash
# Example: Generate simple beep tones
sox -n start_cue.wav synth 0.2 sine 880
sox -n stop_cue.wav synth 0.3 sine 440
```

---

## Network Configuration

### 1. Configure Robot Network Interface

Ensure the network interface matches your setup. Edit the `initialize_sdk()` function in `robot_functions.py` if needed:

```python
def initialize_sdk(interface="eth0"):  # or "wlan0" for WiFi
```

### 2. Configure Firewall (if needed)

Allow UDP ports for ROS 2 bridge:

```bash
sudo ufw allow 5005/udp
sudo ufw allow 5006/udp
```

### 3. Test UDP Communication

```bash
# Terminal 1: Listen for navigation goals
nc -ul 5005

# Terminal 2: Send test goal
echo '{"x": 1.0, "y": 2.0, "z": 0.0, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0}' | nc -u localhost 5005
```

---

## Configuration and Testing

### 1. Environment Variables Summary

Create a configuration file `~/.lisa_env`:

```bash
# Unitree SDK
export UNITREE_SDK_PATH="/home/unitree/unitree_sdk2_python"

# Model configuration
export LISA_CHAT_MODEL="gemma3:27b"
export LISA_VISION_MODEL="gemma3:27b"

# Optional: Ollama API endpoint (for remote API)
# export OLLAMA_API_BASE="http://192.168.50.103:11434"
```

Load it before running:
```bash
source ~/.lisa_env
```

### 2. Test Individual Components

**Test Robot Functions**:
```python
python3 -c "from robot_functions import initialize_sdk; initialize_sdk(); print('Robot OK')"
```

**Test ROS Functions**:
```python
python3 -c "from ros_functions import start_status_listener; start_status_listener(); print('ROS OK')"
```

**Test TTS**:
```python
python3 -c "from robot_functions import robot_speak; robot_speak('Hello, this is LISA')"
```

### 3. Run LISA

Start with keyboard input mode for easier testing:

```bash
# For local Ollama
python lisa_local_kb.py

# For remote API
python lisa_api_kb.py
```

Try basic commands:
- "Hello"
- "What can you do?"
- "Take a picture"

### 4. Test Navigation

Ensure ROS 2 navigation is running, then:
```
User: Go to the station
```

LISA should navigate to the configured waypoint.

---

## Troubleshooting

### Common Issues

**1. SDK Import Error**
```
ModuleNotFoundError: No module named 'unitree_sdk2py'
```
**Solution**: Verify `UNITREE_SDK_PATH` is set and SDK is installed.

**2. Ollama Connection Error**
```
API request failed: Connection refused
```
**Solution**: 
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check firewall settings
- Verify API endpoint in script

**3. No Audio Output**
```
Error playing audio: ...
```
**Solution**:
- Check audio device: `aplay -l`
- Verify user in audio group: `groups`
- Test robot speaker directly with SDK

**4. Clicker Not Detected**
```
No matching clicker devices found
```
**Solution**:
- Check permissions: `ls -l /dev/input/event*`
- Add user to input group: `sudo usermod -a -G input $USER`
- Reconnect clicker device

**5. Navigation Not Working**
```
Navigation to <location> failed: None
```
**Solution**:
- Verify ROS 2 bridge is running
- Check UDP communication on ports 5005/5006
- Verify waypoints are configured correctly

---

## Next Steps

After successful setup:
1. Read [USAGE.md](USAGE.md) for usage examples
2. Review [experimentation.md](experimentation.md) for test scenarios
3. Customize prompts in `prompt_v2.md` and `safety_prompt_v2.md`
4. Configure your environment-specific waypoints

---

## Support

For issues or questions:
- Check the troubleshooting section above
- Review log files in `chat_logs_api/` or `chat_logs_local/`
- Consult Unitree SDK documentation
- Contact project maintainers

---

**Last Updated**: October 2025

