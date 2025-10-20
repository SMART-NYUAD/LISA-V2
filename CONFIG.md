# LISA Configuration Guide

This document explains how to configure LISA using environment variables and configuration files.

## Configuration Methods

LISA supports two methods for configuration:

### Method 1: Using config.env file (Recommended for Development)

1. The `config.env` file contains all configuration with `export` statements
2. Source it before running LISA:
   ```bash
   source config.env
   python scripts/lisa_api_kb.py
   ```

### Method 2: Using .env file (Recommended for Production)

1. Copy `config.env` to `.env`:
   ```bash
   cp config.env .env
   ```

2. Edit `.env` and remove the `export` keyword from each line:
   ```bash
   # Instead of: export OLLAMA_API_BASE="http://192.168.50.103:11434"
   # Use:        OLLAMA_API_BASE=http://192.168.50.103:11434
   ```

3. The `.env` file is automatically loaded by LISA (via python-dotenv)
4. The `.env` file is gitignored for security

## Configuration Options

### System Paths

```bash
# Path to Unitree SDK
export UNITREE_SDK_PATH="/home/unitree/unitree_sdk2_python"

# Path to CycloneDDS installation (required for ROS 2)
export CYCLONEDDS_HOME="/home/unitree/cyclonedds/install"
```

### Ollama API Configuration

```bash
# Base URL for Ollama API (for remote inference)
export OLLAMA_API_BASE="http://192.168.50.103:11434"

# Chat model for text conversations
export LISA_CHAT_MODEL="gemma3:27b"

# Vision model for image analysis
export LISA_VISION_MODEL="gemma3:27b"
```

**For local inference** (using local Ollama instance), use smaller models:
```bash
export LISA_CHAT_MODEL="gemma3:4b"
export LISA_VISION_MODEL="gemma3:4b"
```

### TTS Configuration

```bash
# TTS model file name (must exist in TTS_models/ directory)
export TTS_MODEL_NAME="en_US-amy-medium.onnx"
```

### ASR Configuration

```bash
# Whisper model size for speech recognition
# Options: tiny.en, base.en, small.en, medium.en, large
export ASR_MODEL="tiny.en"
```

### Robot Configuration

```bash
# Network interface for robot communication
export ROBOT_INTERFACE="eth0"

# Enable/disable speech output
export ENABLE_SPEECH="true"
```

### Logging Configuration

```bash
# Directory for log files (relative to project root)
export LOG_DIR="logs"
```

## Usage Examples

### Quick Start (Development)

```bash
# 1. Source the config file
source config.env

# 2. Run LISA
python scripts/lisa_api_kb.py
```

### Production Setup

```bash
# 1. Create .env file
cp config.env .env

# 2. Edit .env (remove 'export' keywords)
nano .env

# 3. Run LISA (automatically loads .env)
python scripts/lisa_api_kb.py
```

### Override Specific Settings

You can override individual settings without editing files:

```bash
# Override just the chat model
export LISA_CHAT_MODEL="llama3:8b"
python scripts/lisa_api_kb.py
```

### Using Different Configurations

```bash
# Development (local models)
export LISA_CHAT_MODEL="gemma3:4b"
python scripts/lisa_local_kb.py

# Production (remote API with larger models)
export LISA_CHAT_MODEL="gemma3:27b"
export OLLAMA_API_BASE="http://remote-server:11434"
python scripts/lisa_api_kb.py
```

## Checking Current Configuration

LISA loads configuration from the `config.py` module. To verify your settings:

```python
from src.config import config

# Print all settings
config.print_config()

# Access individual settings
print(f"Using model: {config.CHAT_MODEL}")
print(f"API endpoint: {config.OLLAMA_API_BASE}")
```

## Environment Variable Precedence

Configuration is loaded in the following order (later overrides earlier):

1. Default values in `config.py`
2. Values from `.env` file (if exists)
3. Values from `config.env` file (if sourced)
4. Environment variables set in current shell

## Migration from Old Setup

If you were previously using manual `export` commands, you can now:

1. **Replace manual exports:**
   ```bash
   # Old way:
   export UNITREE_SDK_PATH="/home/unitree/unitree_sdk2_python"
   export CYCLONEDDS_HOME="/home/unitree/cyclonedds/install"
   export LISA_CHAT_MODEL="gemma3:27b"
   
   # New way:
   source config.env
   ```

2. **All scripts now use the same configuration** - no need to set variables separately for each script

3. **Configuration is automatically validated** - the config module checks paths and sets up the environment

## Troubleshooting

### LISA can't find Unitree SDK
```bash
# Check SDK path is set correctly
echo $UNITREE_SDK_PATH
ls -la $UNITREE_SDK_PATH

# Fix: Update path in config.env or .env
export UNITREE_SDK_PATH="/correct/path/to/unitree_sdk2_python"
```

### CycloneDDS errors
```bash
# Check CycloneDDS home is set
echo $CYCLONEDDS_HOME
ls -la $CYCLONEDDS_HOME

# Fix: Update path in config.env or .env
export CYCLONEDDS_HOME="/home/unitree/cyclonedds/install"
```

### Wrong model being used
```bash
# Check what model is configured
python -c "from src.config import config; print(f'Chat: {config.CHAT_MODEL}, Vision: {config.VISION_MODEL}')"

# Fix: Update in config.env or set environment variable
export LISA_CHAT_MODEL="your-preferred-model"
```

### Configuration not loading
```bash
# Make sure you're in the project directory
cd /home/unitree/Projects/LISA-V2

# For config.env: make sure to source it
source config.env

# For .env: make sure python-dotenv is installed
pip install python-dotenv
```

## Security Notes

- The `.env` file is gitignored and won't be committed to version control
- Never commit API keys, passwords, or sensitive paths to git
- Use `config.env` as a template and copy it to `.env` for local use
- Share `config.env` as a template, but keep `.env` private

## Advanced: Python Config Module

The configuration is centralized in `src/config.py`. All scripts import from there:

```python
from config import config

# Use configuration values
api_url = config.OLLAMA_API_BASE
model = config.CHAT_MODEL
```

This ensures:
- ✅ Single source of truth for configuration
- ✅ Type checking and validation
- ✅ Easy debugging (config.print_config())
- ✅ Consistent behavior across all scripts

