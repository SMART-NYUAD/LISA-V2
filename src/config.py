"""
LISA Configuration Module

Loads configuration from environment variables and .env file.
Provides centralized configuration management for all LISA scripts.

Usage:
    from config import config
    print(config.OLLAMA_API_BASE)
    print(config.CHAT_MODEL)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Try to load .env file from project root
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[Config] Loaded environment from {env_file}")
else:
    # Try config.env as fallback
    config_env = PROJECT_ROOT / "config.env"
    if config_env.exists():
        load_dotenv(config_env)
        print(f"[Config] Loaded environment from {config_env}")


class Config:
    """Centralized configuration class for LISA"""
    
    # ============================================
    # System Paths
    # ============================================
    UNITREE_SDK_PATH = os.getenv("UNITREE_SDK_PATH", "/home/unitree/unitree_sdk2_python")
    CYCLONEDDS_HOME = os.getenv("CYCLONEDDS_HOME", "/home/unitree/cyclonedds/install")
    
    # ============================================
    # Ollama Configuration
    # ============================================
    OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://192.168.50.103:11434")
    OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_API_BASE}/api/chat"
    
    # Model configuration
    CHAT_MODEL = os.getenv("LISA_CHAT_MODEL", "gemma3:27b")
    VISION_MODEL = os.getenv("LISA_VISION_MODEL", "gemma3:27b")
    
    # Local models (fallback)
    LOCAL_CHAT_MODEL = os.getenv("LISA_CHAT_MODEL", "gemma3:4b")
    LOCAL_VISION_MODEL = os.getenv("LISA_VISION_MODEL", "gemma3:4b")
    
    # ============================================
    # TTS Configuration
    # ============================================
    TTS_MODEL_NAME = os.getenv("TTS_MODEL_NAME", "en_US-amy-medium.onnx")
    
    # ============================================
    # ASR Configuration
    # ============================================
    ASR_MODEL = os.getenv("ASR_MODEL", "tiny.en")
    
    # ============================================
    # Robot Configuration
    # ============================================
    ROBOT_INTERFACE = os.getenv("ROBOT_INTERFACE", "eth0")
    ENABLE_SPEECH = os.getenv("ENABLE_SPEECH", "true").lower() == "true"
    
    # ============================================
    # Logging Configuration
    # ============================================
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    
    @classmethod
    def print_config(cls):
        """Print current configuration (for debugging)"""
        print("\n=== LISA Configuration ===")
        print(f"Unitree SDK Path: {cls.UNITREE_SDK_PATH}")
        print(f"CycloneDDS Home: {cls.CYCLONEDDS_HOME}")
        print(f"Ollama API Base: {cls.OLLAMA_API_BASE}")
        print(f"Chat Model: {cls.CHAT_MODEL}")
        print(f"Vision Model: {cls.VISION_MODEL}")
        print(f"TTS Model: {cls.TTS_MODEL_NAME}")
        print(f"ASR Model: {cls.ASR_MODEL}")
        print(f"Robot Interface: {cls.ROBOT_INTERFACE}")
        print(f"Speech Enabled: {cls.ENABLE_SPEECH}")
        print(f"Log Directory: {cls.LOG_DIR}")
        print("==========================\n")


# Create global config instance
config = Config()

# Set environment variables for system components that need them
os.environ["CYCLONEDDS_HOME"] = config.CYCLONEDDS_HOME
os.environ["UNITREE_SDK_PATH"] = config.UNITREE_SDK_PATH

