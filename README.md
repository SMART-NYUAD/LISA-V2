# LISA - Local Intelligent Safety Assistant

LISA (Local Intelligent Safety Assistant) is an LLM-powered assistant that runs on quadruped robots (Unitree Go2W) to provide autonomous navigation, visual inspection, and safety monitoring capabilities for construction sites and industrial environments.

## Features

- 🤖 **Autonomous Navigation**: Navigate to predefined waypoints using ROS2
- 📸 **Camera Control**: Take pictures and analyze visual data
- 🔍 **Vision Analysis**: Use vision models to understand and describe scenes
- 🦺 **Safety Monitoring**: Detect PPE violations (hard hat detection) and execute safety protocols
- 🎤 **Voice Interaction**: Support for keyboard and USB headset voice input (with volume button trigger)
- 🔊 **Text-to-Speech**: Natural voice responses using Piper TTS
- 🎧 **USB Headset Support**: Full audio I/O via USB headset (Logitech) with configurable robot speaker fallback
- 🌐 **Flexible Deployment**: Run with local Ollama or remote API backends

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface Layer                   │
│           (Keyboard Input / Clicker + Microphone/Speaker)   │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                    LISA Main Scripts                        │
│  • lisa_api_kb.py (Remote API + Keyboard)                   │
│  • lisa_local_kb.py (Local Ollama + Keyboard)               │
│  • lisa_api_clicker.py (Remote API + Clicker/ASR)           │
└────────┬──────────────────────────────┬─────────────────────┘
         │                              │
┌────────▼──────────┐         ┌─────────▼──────────┐
│  Unitree SDK      │         │   ROS Functions    │
│  • Camera         │         │   • Navigation     │
│  • Speaker        │         │                    │
└───────────────────┘         └────────────────────┘
         │                               │
┌────────▼───────────────────────────────▼────────────────────┐
│              Hardware / External Services                   │
│  • Unitree Go2 Robot                                        │
│  • ROS 2 Navigation Stack                                   │
│  • Ollama LLM (Local or Remote)                             │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Linux OS (tested on Ubuntu 20.04+)
- Python 3.8+ (system) and Python 3.11 (LISA venv)
- ROS2 (tested on Foxy)
- Unitree SDK
- CycloneDDS
- Ollama (if using local inference)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd LISA_v3_nav_clean
   ```

2. **Create a Python 3.11 virtual environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   **Option A: Using config.env (Quick Start)**
   ```bash
   # Edit config.env to match your setup
   nano config.env
   
   # Source it before running LISA
   source config.env
   ```
   
   **Option B: Using .env file (Recommended for Production)**
   ```bash
   # Copy template and edit
   cp config.env .env
   nano .env
   # Remove 'export' keywords from each line
   
   # The .env file is automatically loaded by LISA
   ```
   
   Key settings to configure:
   - `UNITREE_SDK_PATH` - Path to Unitree SDK
   - `CYCLONEDDS_HOME` - Path to CycloneDDS installation
   - `OLLAMA_API_BASE` - Ollama API endpoint
   - `LISA_CHAT_MODEL` - Chat model name
   - `LISA_VISION_MODEL` - Vision model name
   
   See [CONFIG.md](CONFIG.md) for complete configuration guide.

5. **Download TTS models** (Required for speech)
   See `TTS_models/README.md` for download instructions.

6. **Configure navigation waypoints**
   Edit `src/ros_functions.py` to set your custom waypoint coordinates.

### Running LISA

**First, configure the environment:**
```bash
# Source the configuration (contains all environment variables)
source config.env
```

**Then run LISA:**

**Option 1: Remote API with Keyboard Input**
```bash
python scripts/lisa_api_kb.py
```

**Option 2: Local Ollama with Keyboard Input**
```bash
python scripts/lisa_local_kb.py
```

**Option 3: Remote API with Clicker/Voice Input**
```bash
python scripts/lisa_api_clicker.py
```

**One-liner (with config):**
```bash
source config.env && python scripts/lisa_api_kb.py
```

## Usage Examples

### Basic Commands

- **Navigation**: "Go to the work area"
- **Inspection**: "Take a picture and tell me what you see"
- **Safety Check**: "Inspect the work area" (navigates, takes photo, analyzes, reports)
- **Announcement**: "Tell everyone to clear the area"

### Safety Protocol

When LISA detects a worker without a hard hat:
1. Confirms violation with worker
2. Navigates to storage area to request hard hat
3. Returns to worker with hard hat
4. Provides safety guidance
5. Reports to supervisor at station

## Project Structure

```
LISA-V2/
├── README.md                  # This file
├── SETUP.md                   # Detailed setup instructions
├── USAGE.md                   # Usage guide and examples
├── CONFIG.md                  # Configuration guide 
├── requirements.txt           # Python dependencies 
├── config.env                 # Configuration template 
├── .env                       # Local configuration 
├── .gitignore                 # Git ignore patterns
│
├── scripts/                   # Main executable scripts
│   ├── lisa_api_kb.py         # Remote API + Keyboard input
│   ├── lisa_local_kb.py       # Local Ollama + Keyboard input
│   └── lisa_api_clicker.py    # Remote API + Clicker/ASR input
│
├── src/                       # Core modules
│   ├── config.py              # Configuration management 
│   ├── robot_functions.py     # Robot control (SDK, TTS, camera)
│   └── ros_functions.py       # ROS navigation and waypoints
│
├── prompts/                   # System prompts
│   ├── main_prompt.md         # Main system prompt
│   ├── side_prompt.md         # Safety protocol prompt
│   └── visual_prompt.md       # Vision analysis prompt
│
├── audio/                     # Audio cue files
│   ├── start_cue.wav          # Recording start cue
│   ├── stop_cue.wav           # Recording stop cue
│   └── README.md              # Audio files documentation
│
├── logs/                      # Session logs
│   ├── api/                   # API mode logs
│   └── local/                 # Local mode logs
│
├── tmp/                       # Temporary files (images, audio)
├── TTS_models/                # Piper TTS models (download required)
│   └── README.md              # TTS setup instructions
│
└── _archive/                  # Historical code (reference only)
    └── README.md              # Archive explanation
```

## Documentation

- **[CONFIG.md](CONFIG.md)** - **⭐ Configuration guide** (environment variables, settings)
- **[SETUP.md](SETUP.md)** - Detailed installation and configuration
- **[USAGE.md](USAGE.md)** - Complete usage guide with examples

## Key Technologies

- **Unitree SDK 2**: Robot control and hardware interfaces
- **ROS 2**: Navigation stack and goal management
- **Ollama**: LLM inference (Gemma, Llama, etc.)
- **Whisper**: Automatic speech recognition
- **Piper TTS**: Text-to-speech synthesis
- **OpenCV / VideoClient**: Camera and image capture

## Configuration

LISA uses a centralized configuration system for easy setup and deployment.

### Quick Configuration

```bash
# 1. Edit the configuration file
nano config.env

# 2. Source it to set environment variables
source config.env

# 3. Run LISA
python scripts/lisa_api_kb.py
```

### Key Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `UNITREE_SDK_PATH` | Path to Unitree SDK | `/home/unitree/unitree_sdk2_python` |
| `CYCLONEDDS_HOME` | Path to CycloneDDS | `/home/unitree/cyclonedds/install` |
| `OLLAMA_API_BASE` | Ollama API endpoint | `http://192.168.50.103:11434` |
| `LISA_CHAT_MODEL` | Chat model name | `gemma3:27b` (API) / `gemma3:4b` (Local) |
| `LISA_VISION_MODEL` | Vision model name | `gemma3:27b` (API) / `gemma3:4b` (Local) |
| `TTS_MODEL_NAME` | TTS model file | `en_US-amy-medium.onnx` |
| `ASR_MODEL` | Whisper ASR model | `tiny.en` |
| `ENABLE_SPEECH` | Enable speech output | `true` |
| `AUDIO_OUTPUT_DEVICE` | Audio output device | `usb_headset` / `robot_speaker` |
| `AUDIO_INPUT_DEVICE` | Audio input device | `usb_headset` / `default` |

**📖 See [CONFIG.md](CONFIG.md) for complete configuration documentation**

## Contributing

Contributions are welcome! Please ensure:
- Code follows existing style conventions
- Scripts are tested on actual hardware when possible
- Documentation is updated for new features

## Safety Considerations

⚠️ **Important Safety Notes**:
- Always supervise the robot during autonomous operation
- Ensure the environment is clear of obstacles
- Test navigation waypoints in a safe environment first
- The robot does not physically manipulate objects (safety equipment delivery is simulated)
- Vision-based safety detection should be used as a supplement to, not replacement for, human oversight

## Contact

nas@nyu.edu


