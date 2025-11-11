#!/usr/bin/env python3
"""
LISA - AI-Powered Safety Analysis Assistant (API + Clicker/ASR Mode)

This script runs LISA with a remote Ollama API backend and hands-free voice input
via wireless presenter clicker and Whisper ASR. Simplified for conference demos.

Key Features:
- Remote Ollama API for LLM inference
- Clicker-triggered voice input (hands-free)
- Automatic speech recognition (Whisper)
- Camera control and vision analysis
- Safety-focused image analysis
- Text-to-speech announcements with audio cues

Usage:
    python lisa_api_clicker.py

Controls:
    TAB key: Start/stop audio recording
    PAGEDOWN key: Clear conversation history
    Ctrl+C: Exit program

Environment Variables:
    LISA_CHAT_MODEL: Chat model name (default: gemma3:27b)
    LISA_VISION_MODEL: Vision model name (default: gemma3:27b)
    UNITREE_SDK_PATH: Path to Unitree SDK (default: /home/unitree/unitree_sdk2_python)

Supported Clicker Devices:
    - Wireless Present Wireless Present Keyboard
    - KNORVAY Knorvay Wireless Presenter Keyboard

Author: [Your team/organization]
Version: 3.0 - Conference Demo Edition
"""
import sys
import time
import datetime
import os
import json
import signal
import requests
import re
import base64

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import config
from robot_functions import robot_take_pic, robot_speak, robot_listen, preload_tts_model, preload_asr_model, set_volume
from ros_functions import (
    navigate_to, 
    start_status_listener, 
    wait_for_goal_completion
)


# Enable speech (from config)
ENABLE_SPEECH = config.ENABLE_SPEECH

def setup_terminal_log(log_dir: str) -> str:
    """Tee stdout/stderr to a timestamped log file in the given directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, log_dir)
    os.makedirs(target_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%m%d_%H%M%S")
    log_path = os.path.join(target_dir, f"terminal_{ts}.txt")

    class Tee:
        def __init__(self, *streams):
            self.streams = streams
        def write(self, data):
            for s in self.streams:
                s.write(data)
                s.flush()
        def flush(self):
            for s in self.streams:
                s.flush()

    logfile = open(log_path, 'a', encoding='utf-8')
    sys.stdout = Tee(sys.stdout, logfile)
    sys.stderr = Tee(sys.stderr, logfile)
    print(f"Logging terminal output to: {log_path}")
    return log_path

# Ollama API configuration (from config)
OLLAMA_API_BASE = config.OLLAMA_API_BASE
OLLAMA_CHAT_ENDPOINT = config.OLLAMA_CHAT_ENDPOINT

# Models (from config)
DEFAULT_CHAT_MODEL = config.CHAT_MODEL
DEFAULT_VISION_MODEL = config.VISION_MODEL

# Path to last captured image (from config - absolute path)
LAST_IMAGE_PATH = str(config.LAST_IMAGE_PATH)

def encode_image_to_base64(image_path):
    """Read image from disk and return base64-encoded string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def load_prompt(file_path):
    """Load the entire prompt file content as a single system prompt string."""
    with open(file_path, 'r', encoding='utf-8') as prompt_file:
        return prompt_file.read().strip()

def chat_with_api(model, messages, options=None):
    """Send a chat request to the Ollama API."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    if options:
        payload["options"] = options
    
    try:
        response = requests.post(OLLAMA_CHAT_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")

def _strip_code_fences(raw: str) -> str:
    """Remove Markdown code fences like ```json ... ``` or ``` ... ``` from text."""
    # Remove fenced code blocks with optional language
    raw = re.sub(r"```[a-zA-Z]*\n", "", raw)
    raw = raw.replace("```", "")
    return raw

def _normalize_smart_quotes(raw: str) -> str:
    """Normalize curly quotes to straight ASCII quotes to help JSON parsing."""
    replacements = {
        "\u201c": '"',  # “
        "\u201d": '"',  # ”
        "\u2018": "'",  # ‘
        "\u2019": "'",  # ’
    }
    for k, v in replacements.items():
        raw = raw.replace(k, v)
    return raw

def extract_function_call(text):
    """Extract function call JSON from LLM response robustly."""
    if not text:
        return None
    cleaned = _strip_code_fences(text)
    cleaned = _normalize_smart_quotes(cleaned)
    # Look for JSON blocks in the cleaned response
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, cleaned, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict) and "function" in data:
                return data
        except json.JSONDecodeError:
            continue
    return None

def execute_function(function_call, chat_model, vision_model, messages, logger):
    """Execute a function call and return the result."""
    function_name = function_call.get("function")
    params = function_call.get("params", {})
    speak_message = function_call.get("speak")
    
    # Announce what we're doing if specified (but not for 'speak' function to avoid duplication)
    if speak_message and function_name != "speak":
        print(f"LISA: {speak_message}")
        if ENABLE_SPEECH:
            try:
                robot_speak(speak_message)
            except KeyboardInterrupt:
                raise  # Re-raise to allow outer handlers to catch it
            except Exception as e:
                print(f"Speech error: {e}")
    
    start_time = time.time()
    
    try:
        if function_name == "take_picture":
            print("Taking a picture...")
            success = robot_take_pic()
            
            if success:
                success_msg = "Picture taken successfully"
                print(success_msg)
                return success_msg
            else:
                error_msg = "Failed to take picture"
                print(error_msg)
                return error_msg
                
        elif function_name == "analyze_image":
            if not os.path.exists(LAST_IMAGE_PATH):
                return "Error: No image available to analyze"
            
            print("Analyzing image...")
            image_analysis_start = time.time()
            image_data = encode_image_to_base64(LAST_IMAGE_PATH)
            analysis_prompt = params.get("prompt", "Describe what you see in this image")
            
            # Load visual prompt template from file
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                visual_prompt_path = os.path.join(script_dir, "..", "prompts", "visual_prompt.md")
                visual_prompt_template = load_prompt(visual_prompt_path)
                # Use the visual prompt directly
                full_prompt = visual_prompt_template
            except Exception as e:
                return f"Error loading visual prompt: {e}"
            
            # Create clean analysis messages (no system prompt to avoid JSON confusion)
            analysis_messages = [{
                "role": "user",
                "content": full_prompt + "\n\nRespond with plain text analysis only, no JSON format.",
                "images": [image_data]
            }]
            
            response = chat_with_api(
                model=vision_model or chat_model,
                messages=analysis_messages,
                options={'temperature': 0.2}
            )
            
            analysis_duration = time.time() - image_analysis_start
            print(f"LISA analyzed image in {analysis_duration:.2f} seconds.")
            
            analysis_result = response['message']['content'].strip()
            print(f"Analysis result: {analysis_result}")
            if ENABLE_SPEECH:
                try:
                    robot_speak(analysis_result)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"Speech error during analysis: {e}")
            
            return f"Image analysis: {analysis_result}"
            
        elif function_name == "speak":
            message = speak_message if speak_message else params.get("message")
            if not message:
                return "Error: No message specified for speak function"
            
            print(f"LISA: {message}")
            if ENABLE_SPEECH:
                try:
                    robot_speak(message)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"Speech error: {e}")
            
            return f"Spoke: {message}"
            
        else:
            return f"Error: Unknown function '{function_name}'"
            
    except Exception as e:
        error_msg = f"Function execution failed: {str(e)}"
        print(error_msg)
        return error_msg


_shutdown_requested = False

def _handle_sigint(signum, frame):
    global _shutdown_requested
    print("\nCtrl+C received, shutting down...")
    _shutdown_requested = True

def main():
    """Main function to run the navigation and camera assistant with ASR/clicker input."""
    global _shutdown_requested
    
    chat_model = DEFAULT_CHAT_MODEL
    vision_model = DEFAULT_VISION_MODEL
    
    # Tee terminal output to file
    setup_terminal_log("../logs/api")
    
    # Setup audio system (default source and mic gain)
    config.setup_audio()
    
    # Initialize status listener
    start_status_listener()
    
    # Initialize message history
    messages = []
    
    # Welcome message
    print("\n=== LISA - Safety Analysis Assistant (Conference Demo) ===")
    print(f"Using Ollama chat model: {chat_model}")
    print(f"Using Ollama vision model: {vision_model}")
    print(f"API endpoint: {OLLAMA_API_BASE}")
    print(f"ASR model: {config.ASR_MODEL}")
    print("Uses clicker for input and ASR for speech recognition")
    print("==========================================\n")
    
    # Preload TTS model to eliminate first-call latency
    preload_tts_model()
    
    # Preload ASR model to eliminate first-transcription latency
    preload_asr_model()
    
    welcome_message = "Hello! I'm LISA"
    print(f"LISA: {welcome_message}")
    if ENABLE_SPEECH:
        try:
            robot_speak(welcome_message)
            set_volume(10)
        except KeyboardInterrupt:
            print("\nInterrupted during welcome message")
            _shutdown_requested = True
            return
    
    # Install graceful Ctrl+C handler
    signal.signal(signal.SIGINT, _handle_sigint)

    # Main conversation loop via ASR/clicker
    while not _shutdown_requested:
        try:
            user_input = robot_listen(shutdown_flag_getter=lambda: _shutdown_requested)
            
            # Check shutdown after listening (in case Ctrl+C was pressed)
            if _shutdown_requested:
                break
            
            # Handle case where listening failed or was cancelled
            if user_input is None:
                print("Listening cancelled or failed, waiting for next input.")
                if _shutdown_requested:
                    break
                continue
            
            # Check for the clear chat signal
            if user_input == "CLEAR_CHAT":
                print("--- Clearing Chat History ---")
                messages = []
                continue
            
        except (EOFError, KeyboardInterrupt):
            print("\n\nShutting down gracefully...")
            _shutdown_requested = True
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            if _shutdown_requested:
                break
            continue
        
        # Check shutdown before processing
        if _shutdown_requested:
            break
        
        # Handle empty input
        if not user_input or not user_input.strip():
            continue
        
        print(f"You: {user_input}")
        
        # Load system prompt if this is the first interaction or messages were cleared
        if not messages:
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                prompt_path = os.path.join(script_dir, "..", "prompts", "main_prompt.md")
                if os.path.exists(prompt_path):
                    system_prompt = load_prompt(prompt_path)
                    messages.append({"role": "system", "content": system_prompt})
                else:
                    print("Error: System prompt file not found!")
                    continue
            except Exception as e:
                print(f"Error loading system prompt: {e}")
                continue
        
        # Add user input to messages
        messages.append({"role": "user", "content": user_input})
        
        try:
            # Check shutdown before expensive operations
            if _shutdown_requested:
                break
            
            print("LISA is thinking...")
            start_time = time.time()
            
            # Get LLM response
            api_response = chat_with_api(
                model=chat_model,
                messages=messages,
                options={'temperature': 0.3}
            )
            
            # Check shutdown after LLM call
            if _shutdown_requested:
                break
            
            duration = time.time() - start_time
            print(f"LISA thought for {duration:.2f} seconds.")
            
            assistant_response = api_response['message']['content'].strip()
            
            # Check if response contains a function call
            function_call = extract_function_call(assistant_response)
            
            if function_call:
                # Execute the function
                print(f"DEBUG: Executing function: {function_call}")
                result = execute_function(function_call, chat_model, vision_model, messages, None)
                
                # Add assistant response and function result to messages
                messages.append({"role": "assistant", "content": assistant_response})
                messages.append({"role": "user", "content": f"Function result: {result}"})
                
                # Special case: if take_picture succeeded, automatically analyze the image
                if function_call.get("function") == "take_picture" and "successfully" in result.lower():
                    if _shutdown_requested:
                        break
                    
                    print("Automatically analyzing the captured image...")
                    # Announce that we're analyzing
                    analysis_announcement = "Analyzing the image"
                    print(f"LISA: {analysis_announcement}")
                    if ENABLE_SPEECH:
                        try:
                            robot_speak(analysis_announcement)
                        except KeyboardInterrupt:
                            print("\nInterrupted during analysis announcement")
                            _shutdown_requested = True
                            break
                    
                    if _shutdown_requested:
                        break
                    
                    analyze_call = {
                        "function": "analyze_image",
                        "params": {"prompt": "Describe what you see with attention to safety"}
                    }
                    analyze_result = execute_function(analyze_call, chat_model, vision_model, messages, None)
                    messages.append({"role": "assistant", "content": "Analyzing image..."})
                    messages.append({"role": "user", "content": f"Function result: {analyze_result}"})
                
            else:
                # Regular conversational response
                print(f"LISA: {assistant_response}")
                if ENABLE_SPEECH:
                    try:
                        robot_speak(assistant_response)
                    except KeyboardInterrupt:
                        print("\nInterrupted during speech")
                        _shutdown_requested = True
                        break
                messages.append({"role": "assistant", "content": assistant_response})
        
        except KeyboardInterrupt:
            print("\n\nShutting down gracefully...")
            _shutdown_requested = True
            break
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            if not _shutdown_requested:
                print("LISA: I encountered an error. Please try again.")
                if ENABLE_SPEECH:
                    try:
                        robot_speak("I encountered an error. Please try again.")
                    except:
                        pass
        
        # Turn end is implicitly logged by terminal tee
    
    print("\n=== Session ended ===")
    print("Cleaning up and exiting...")
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n=== Interrupted by user ===")
        print("Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)


