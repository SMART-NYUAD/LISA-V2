# LISA - AI-Powered Robot Navigation & Safety Assistant

LISA (Location-Intelligent Safety Assistant) is an AI-powered assistant that runs on quadruped robots (Unitree Go2) to provide autonomous navigation, visual inspection, and safety monitoring capabilities for construction sites and industrial environments.

## Features

- 🤖 **Autonomous Navigation**: Navigate to predefined waypoints using ROS 2
- 📸 **Camera Control**: Take pictures and analyze visual data
- 🔍 **AI Vision Analysis**: Use vision models to understand and describe scenes
- 🦺 **Safety Monitoring**: Detect PPE violations (hard hat detection) and execute safety protocols
- 🎤 **Voice Interaction**: Support for both keyboard and clicker-based voice input
- 🔊 **Text-to-Speech**: Natural voice responses using Piper TTS
- 🌐 **Flexible Deployment**: Run with local Ollama or remote API backends

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface Layer                     │
│  (Keyboard Input / Clicker + Whisper ASR)                    │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                    LISA Main Scripts                         │
│  • lisa_api_kb.py (Remote API + Keyboard)                   │
│  • lisa_local_kb.py (Local Ollama + Keyboard)               │
│  • lisa_api_clicker.py (Remote API + Clicker/ASR)           │
└────────┬───────────────────────────────┬────────────────────┘
         │                               │
┌────────▼──────────┐         ┌─────────▼──────────┐
│  Robot Functions  │         │   ROS Functions    │
│  • Camera         │         │   • Navigation     │
│  • TTS/ASR        │         │   • UDP Bridge     │
│  • Unitree SDK    │         │   • Goal Tracking  │
└───────────────────┘         └────────────────────┘
         │                               │
┌────────▼───────────────────────────────▼────────────────────┐
│              Hardware / External Services                    │
│  • Unitree Go2 Robot                                         │
│  • ROS 2 Navigation Stack                                    │
│  • Ollama LLM (Local or Remote)                              │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Linux OS (tested on Ubuntu 20.04+)
- Python 3.8+
- ROS 2 (Humble or later)
- Unitree Go2 robot with SDK
- Ollama (local or remote access)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd LISA_v3_nav_clean
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables** (optional)
   ```bash
   export UNITREE_SDK_PATH="/path/to/unitree_sdk2_python"
   export LISA_CHAT_MODEL="gemma3:27b"
   export LISA_VISION_MODEL="gemma3:27b"
   ```

4. **Download TTS models** (Required for speech)
   See `TTS_models/README.md` for download instructions.

5. **Configure navigation waypoints**
   Edit `src/ros_functions.py` to set your custom waypoint coordinates.

### Running LISA

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
LISA_v3_nav_clean/
├── README.md                  # This file
├── SETUP.md                   # Detailed setup instructions
├── USAGE.md                   # Usage guide and examples
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore patterns
│
├── scripts/                   # Main executable scripts
│   ├── lisa_api_kb.py         # Remote API + Keyboard input
│   ├── lisa_local_kb.py       # Local Ollama + Keyboard input
│   └── lisa_api_clicker.py    # Remote API + Clicker/ASR input
│
├── src/                       # Core modules
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

- **[SETUP.md](SETUP.md)** - Detailed installation and configuration
- **[USAGE.md](USAGE.md)** - Complete usage guide with examples
- **[experimentation.md](experimentation.md)** - Experiment scenarios

## Key Technologies

- **Unitree SDK 2**: Robot control and hardware interfaces
- **ROS 2**: Navigation stack and goal management
- **Ollama**: LLM inference (Gemma, Llama, etc.)
- **Whisper**: Automatic speech recognition
- **Piper TTS**: Text-to-speech synthesis
- **OpenCV / VideoClient**: Camera and image capture

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `UNITREE_SDK_PATH` | Path to Unitree SDK | `/home/unitree/unitree_sdk2_python` |
| `LISA_CHAT_MODEL` | Chat model name | `gemma3:27b` (API) / `gemma3:4b` (Local) |
| `LISA_VISION_MODEL` | Vision model name | `gemma3:27b` (API) / `gemma3:4b` (Local) |

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

## License

[Add your license information here]

## Contact

[Add contact information or project maintainer details]

## Acknowledgments

Built for construction site safety and worker assistance applications using Unitree Go2 quadruped robot platform.

