#!/usr/bin/env python3
"""
LISA - AI-Powered Robot Navigation & Safety Assistant (API + Keyboard Mode)

This script runs LISA with a remote Ollama API backend and keyboard text input.
Suitable for testing with more powerful models on a remote server.

Key Features:
- Remote Ollama API for LLM inference
- Keyboard text input for commands
- Robot navigation via ROS 2
- Camera control and vision analysis
- Safety monitoring with PPE detection
- Text-to-speech announcements

Usage:
    python lisa_api_kb.py

Environment Variables:
    LISA_CHAT_MODEL: Chat model name (default: gemma3:27b)
    LISA_VISION_MODEL: Vision model name (default: gemma3:27b)
    UNITREE_SDK_PATH: Path to Unitree SDK (default: /home/unitree/unitree_sdk2_python)

Author: [Your team/organization]
Version: 2.0
"""
import sys
import time
import datetime
import os
import json
import requests
import re
import base64

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from robot_functions import robot_take_pic, robot_speak, preload_tts_model
from ros_functions import (
    navigate_to, 
    start_status_listener, 
    wait_for_goal_completion
)
 

# Enable speech
ENABLE_SPEECH = True

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

# Ollama API configuration
OLLAMA_API_BASE = "http://192.168.50.103:11434"
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_API_BASE}/api/chat"

# Models
DEFAULT_CHAT_MODEL = os.environ.get("LISA_CHAT_MODEL", "gemma3:27b")
DEFAULT_VISION_MODEL = os.environ.get("LISA_VISION_MODEL", "gemma3:27b")

# Path to last captured image (relative to script directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_IMAGE_PATH = os.path.join(SCRIPT_DIR, "tmp", "frame.jpg")

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
        if function_name == "navigate_to":
            location = params.get("location")
            if not location:
                return "Error: No location specified for navigation"
            
            print(f"Navigating to {location}...")
            goal_id = navigate_to(location)
            result = wait_for_goal_completion(goal_id, timeout=120.0)
            
            if result == "SUCCEEDED":
                success_msg = f"Successfully reached {location}"
                print(success_msg)
                return success_msg
            else:
                error_msg = f"Navigation to {location} failed: {result}"
                print(error_msg)
                return error_msg
                
        elif function_name == "take_picture":
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
            
            
            return f"Image analysis: {analysis_result}"
            
        elif function_name == "speak":
            message = params.get("message")
            if not message:
                return "Error: No message specified for speak function"
            
            print(f"LISA: {message}")
            if ENABLE_SPEECH:
                robot_speak(message)
            
            
            return f"Announced: {message}"
            
        elif function_name == "activate_safety_protocol":
            return load_safety_protocol(messages)
            
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


def load_safety_protocol(messages):
    """Load the safety protocol into the conversation."""
    print("🚨 Safety violation detected - loading safety compliance protocol")
    
    # Load safety prompt
    script_dir = os.path.dirname(os.path.abspath(__file__))
    safety_prompt_path = os.path.join(script_dir, "..", "prompts", "side_prompt.md")
    
    if os.path.exists(safety_prompt_path):
        safety_prompt = load_prompt(safety_prompt_path)
        # Add safety prompt as system message
        messages.append({
            "role": "system", 
            "content": f"SAFETY PROTOCOL ACTIVATED:\n\n{safety_prompt}"
        })
        messages.append({
            "role": "user",
            "content": "Safety protocol has been loaded. You must now begin STEP 1 of the safety workflow: Confirm the safety violation with the worker, ask for their name and ask if they want you to fetch a hard hat."
        })
        print("🔒 Safety compliance protocol loaded")
        return "Safety protocol loaded and activated - beginning safety workflow"
    else:
        print("⚠️ Safety prompt file not found")
        return "Error: Safety prompt file not found"

def main():
    """Main function to run the simplified navigation and camera assistant."""
    chat_model = DEFAULT_CHAT_MODEL
    vision_model = DEFAULT_VISION_MODEL
    
    # Tee terminal output to file
    setup_terminal_log("../logs/api")
    
    # Initialize status listener
    start_status_listener()
    
    # Initialize message history
    messages = []
    
    # Welcome message
    print("\n=== LISA - Navigation & Camera Assistant (V2 Simplified) ===")
    print(f"Using Ollama chat model: {chat_model}")
    print(f"Using Ollama vision model: {vision_model}")
    print(f"API endpoint: {OLLAMA_API_BASE}")
    print("Type 'quit' or 'exit' to end the session")
    print("Type 'clear' to clear chat history")
    print("==========================================\n")
    
    # Preload TTS model to eliminate first-call latency
    preload_tts_model()
    
    welcome_message = "Hello! I'm LISA, your navigation and camera assistant. I can go to different locations, take pictures, and analyze what I see. What would you like me to do?"
    print(f"LISA: {welcome_message}")
    
    # Main conversation loop
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
            break
        
        # Check for exit commands
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        # Check for clear chat signal
        if user_input.lower() == 'clear':
            print("--- Clearing Chat History ---")
            messages = []
            continue
        
        # Handle empty input
        if not user_input:
            continue
        
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
            # Error already printed; nothing else to do
        
        # Turn end is implicitly logged by terminal tee
    
    print("Session ended.")

if __name__ == "__main__":
    main()
