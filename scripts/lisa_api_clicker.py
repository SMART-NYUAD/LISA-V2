#!/usr/bin/env python3
"""
LISA - AI-Powered PPE Compliance Robot (API + Clicker/ASR Mode)

This script runs LISA with a remote Ollama API backend and hands-free voice input
via wireless presenter clicker and Whisper ASR. Focused on PPE detection demo.

Key Features:
- Remote Ollama API for LLM inference
- Clicker-triggered voice input (hands-free)
- Automatic speech recognition (Whisper)
- Camera control and vision analysis
- PPE compliance detection for construction activities
- Text-to-speech announcements

Usage:
    python lisa_api_clicker.py

Controls:
    TAB key: Start/stop audio recording
    VOLUMEDOWN key: Clear conversation history
    Ctrl+C: Exit program

Supported Clicker Devices:
    - Wireless Present Wireless Present Keyboard
    - KNORVAY Knorvay Wireless Presenter Keyboard

Version: 2.1 (PPE Demo)
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
from robot_functions import robot_take_pic, robot_speak, robot_listen, preload_tts_model
# Navigation imports removed - not needed for PPE demo
# from ros_functions import navigate_to, start_status_listener, wait_for_goal_completion


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
    
    # Announce what we're doing if specified
    if speak_message:
        print(f"LISA: {speak_message}")
        if ENABLE_SPEECH:
            robot_speak(speak_message)
    
    start_time = time.time()
    
    try:
        if function_name == "take_picture":
            print("Taking a picture...")
            success = robot_take_pic()
            
            if success:
                success_msg = "Picture taken successfully"
                print(success_msg)
                
                # Automatically trigger image analysis for demo flow
                print("Auto-triggering image analysis...")
                
                # We need to construct a "fake" analysis function call to pass to ourselves recursively
                # This simulates the LLM deciding to analyze the image immediately
                analysis_call = {
                    "function": "analyze_image",
                    "params": {"prompt": "Describe what you see with attention to safety"},
                    "speak": "Analyzing the image now."
                }
                
                # Recursively call execute_function for the analysis
                analysis_result = execute_function(analysis_call, chat_model, vision_model, messages, logger)
                
                # Signal that we are done with this chain and want to wait for user input
                return "WAIT_FOR_USER_INPUT"
                
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
            
            # Load visual prompt template from file and inject analysis prompt
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                visual_prompt_path = os.path.join(script_dir, "..", "prompts", "visual_prompt.md")
                visual_prompt_template = load_prompt(visual_prompt_path)
                full_prompt = visual_prompt_template.replace("{{ANALYSIS_PROMPT}}", analysis_prompt)
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
            
            # Directly speak the analysis result instead of returning it to the conversation
            if ENABLE_SPEECH:
                robot_speak(analysis_result)
            
            # Return a summary so the LLM knows it's done, but doesn't need to re-speak it
            return f"Image analysis completed and spoken to user: {analysis_result[:50]}..."
            
        elif function_name == "speak":
            message = params.get("message")
            if not message:
                return "Error: No message specified for speak function"
            
            print(f"LISA: {message}")
            if ENABLE_SPEECH:
                robot_speak(message)
            
            
            return f"Announced: {message}"
            
        elif function_name == "wait_for_response":
            # Signal that we're waiting for human input - don't continue workflow
            message = params.get("message", "Waiting for response...")
            return "WAIT_FOR_USER_INPUT"  # Special signal to break the function loop
            
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
    chat_model = DEFAULT_CHAT_MODEL
    vision_model = DEFAULT_VISION_MODEL
    
    # Tee terminal output to file
    setup_terminal_log("../logs/api")
    
    # Navigation status listener removed - not needed for PPE demo
    
    # Initialize message history
    messages = []
    
    # Welcome message
    print("\n=== LISA - PPE Compliance Assistant (Demo V2.1, API) ===")
    print(f"Using Ollama chat model: {chat_model}")
    print(f"Using Ollama vision model: {vision_model}")
    print(f"API endpoint: {OLLAMA_API_BASE}")
    print("Uses clicker for input and ASR for speech recognition")
    print("==========================================\n")
    
    # Preload TTS model to eliminate first-call latency
    preload_tts_model()
    
    welcome_message = "Hello! I'm LISA, your PPE compliance assistant. I can take pictures and check if workers are wearing the right safety equipment for their tasks. How can I help you today?"
    print(f"LISA: {welcome_message}")
    #if ENABLE_SPEECH:
        #robot_speak(welcome_message)
    
    # Install graceful Ctrl+C handler
    signal.signal(signal.SIGINT, _handle_sigint)

    # Main conversation loop via ASR/clicker
    while not _shutdown_requested:
        try:
            user_input = robot_listen(
                check_stop_func=lambda: _shutdown_requested,
                clear_key="KEY_VOLUMEDOWN"
            )
            
            # Handle case where listening failed or was cancelled
            if user_input is None:
                print("Listening cancelled or failed, waiting for next input.")
                continue
            
            # Check for the clear chat signal
            if user_input == "CLEAR_CHAT":
                print("--- Clearing Chat History ---")
                messages = []
                continue
            
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
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
            print("LISA is thinking...")
            start_time = time.time()
            
            # Get LLM response
            api_response = chat_with_api(
                model=chat_model,
                messages=messages,
                options={'temperature': 0.3}
            )
            
            duration = time.time() - start_time
            print(f"LISA thought for {duration:.2f} seconds.")
            
            assistant_response = api_response['message']['content'].strip()
            
            # Check if response contains a function call
            function_call = extract_function_call(assistant_response)
            
            if function_call:
                # Execute the function
                print(f"DEBUG: Executing function: {function_call}")
                result = execute_function(function_call, chat_model, vision_model, messages, None)
                
                # Check for special break signals immediately
                if result == "WAIT_FOR_USER_INPUT":
                    print("Workflow completed, waiting for user input...")
                    # We still append the result to history so the LLM knows what happened
                    messages.append({"role": "assistant", "content": assistant_response})
                    messages.append({"role": "user", "content": "Function execution completed successfully."})
                    continue

                # Add assistant response and function result to messages
                messages.append({"role": "assistant", "content": assistant_response})
                messages.append({"role": "user", "content": f"Function result: {result}"})
                
                # Always ask the LLM what to do next after a function execution
                # Trust the LLM to naturally conclude workflows
                while True:
                    print("LISA is deciding what to do next...")
                    followup_start = time.time()
                    next_response = chat_with_api(
                        model=chat_model,
                        messages=messages,
                        options={'temperature': 0.3}
                    )
                    
                    followup_duration = time.time() - followup_start
                    print(f"LISA decided next action in {followup_duration:.2f} seconds.")
                    
                    next_text = next_response['message']['content'].strip()
                    
                    # Check if the next response is another function call
                    next_function = extract_function_call(next_text)
                    
                    if next_function:
                        print(f"DEBUG: Continuing with next function: {next_function}")
                        next_result = execute_function(next_function, chat_model, vision_model, messages, None)
                        messages.append({"role": "assistant", "content": next_text})
                        messages.append({"role": "user", "content": f"Function result: {next_result}"})
                        
                        # Check if we should wait for user input
                        if next_result == "WAIT_FOR_USER_INPUT":
                            print("LISA is waiting for your response...")
                            break
                    else:
                        # Regular response - end the workflow
                        print(f"LISA: {next_text}")
                        if ENABLE_SPEECH:
                            robot_speak(next_text)
                        messages.append({"role": "assistant", "content": next_text})
                        break
                
            else:
                # Regular conversational response
                print(f"LISA: {assistant_response}")
                if ENABLE_SPEECH:
                    robot_speak(assistant_response)
                messages.append({"role": "assistant", "content": assistant_response})
        
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            print("LISA: I encountered an error. Please try again.")
            if ENABLE_SPEECH:
                robot_speak("I encountered an error. Please try again.")
            # Error already printed; nothing else to do
        
        # Turn end is implicitly logged by terminal tee
    
    print("Session ended.")

if __name__ == "__main__":
    main()


