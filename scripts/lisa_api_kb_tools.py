#!/usr/bin/env python3
"""
LISA - AI-Powered Robot Navigation & Safety Assistant (Ollama Tools + Keyboard Mode)

This script runs LISA with a remote Ollama API backend using native tool calling
and keyboard text input. This version uses the Ollama Python library's built-in
tools feature instead of manual JSON parsing.

Key Features:
- Remote Ollama API with native tool calling
- Keyboard text input for commands
- Robot navigation via ROS 2
- Camera control and vision analysis
- Safety monitoring with PPE detection
- Text-to-speech announcements

Usage:
    python lisa_api_kb_tools.py

Environment Variables:
    LISA_CHAT_MODEL: Chat model name (default: gemma3:27b)
    LISA_VISION_MODEL: Vision model name (default: gemma3:27b)
    UNITREE_SDK_PATH: Path to Unitree SDK (default: /home/unitree/unitree_sdk2_python)

Author: [Your team/organization]
Version: 2.0 (Ollama Tools)
"""
import sys
import time
import datetime
import os
import base64
import ollama

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import config
from robot_functions import robot_take_pic, robot_speak, preload_tts_model
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

def define_tools():
    """Define the tools available to LISA in Ollama's native format."""
    return [
        {
            'type': 'function',
            'function': {
                'name': 'navigate_to',
                'description': 'Navigate the robot to a specific location',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'location': {
                            'type': 'string',
                            'description': 'Destination location: station, storage_area, or work_area'
                        },
                        'speak': {
                            'type': 'string',
                            'description': 'Optional message to announce while navigating'
                        }
                    },
                    'required': ['location']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'take_picture',
                'description': 'Take a photo with the robot\'s camera',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'speak': {
                            'type': 'string',
                            'description': 'Optional message to announce while taking the picture'
                        }
                    },
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'analyze_image',
                'description': 'Analyze the most recently taken image with the robot\'s camera',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'prompt': {
                            'type': 'string',
                            'description': 'What to analyze or look for in the image'
                        }
                    },
                    'required': ['prompt']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'speak',
                'description': 'Announce a message to people in the area using text-to-speech',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'The message to speak out loud'
                        }
                    },
                    'required': ['message']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'activate_safety_protocol',
                'description': 'Activate the safety compliance protocol when safety violations are detected',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'wait_for_response',
                'description': 'Signal that you are waiting for human input and need to pause the workflow',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'Optional description of what you are waiting for'
                        }
                    },
                    'required': []
                }
            }
        }
    ]

def execute_function(tool_call, chat_model, vision_model, messages, client):
    """Execute a function call from Ollama's tool calling format and return the result."""
    function_name = tool_call.function.name
    params = tool_call.function.arguments
    
    # Handle optional speak parameter
    speak_message = params.get("speak")
    
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
            
            # Create clean analysis messages (no system prompt to avoid confusion)
            analysis_messages = [{
                "role": "user",
                "content": full_prompt + "\n\nRespond with plain text analysis only.",
                "images": [image_data]
            }]
            
            response = client.chat(
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
    """Main function to run the navigation and camera assistant with Ollama tools."""
    chat_model = DEFAULT_CHAT_MODEL
    vision_model = DEFAULT_VISION_MODEL
    
    # Initialize Ollama client with remote API
    client = ollama.Client(host=OLLAMA_API_BASE)
    
    # Tee terminal output to file
    setup_terminal_log("../logs/api")
    
    # Initialize status listener
    start_status_listener()
    
    # Initialize message history
    messages = []
    
    # Welcome message
    print("\n=== LISA - Navigation & Camera Assistant (V2 Ollama Tools) ===")
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
    
    # Define available tools
    tools = define_tools()
    
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
                prompt_path = os.path.join(script_dir, "..", "prompts", "main_prompt_tools.md")
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
            
            # Get LLM response with tools
            response = client.chat(
                model=chat_model,
                messages=messages,
                tools=tools,
                options={'temperature': 0.3}
            )
            
            duration = time.time() - start_time
            print(f"LISA thought for {duration:.2f} seconds.")
            
            # Check if response contains tool calls
            if hasattr(response.message, 'tool_calls') and response.message.tool_calls:
                # Add assistant's message to history
                messages.append({
                    "role": "assistant",
                    "content": response.message.content or ""
                })
                
                # Execute each tool call
                for tool_call in response.message.tool_calls:
                    print(f"DEBUG: Executing function: {tool_call.function.name}")
                    result = execute_function(tool_call, chat_model, vision_model, messages, client)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": result
                    })
                    
                    # Check if we should wait for user input
                    if result == "WAIT_FOR_USER_INPUT":
                        print("LISA is waiting for your response...")
                        break
                
                # If we're not waiting for user input, continue the workflow
                if result != "WAIT_FOR_USER_INPUT":
                    # Ask the LLM what to do next after function execution
                    while True:
                        print("LISA is deciding what to do next...")
                        followup_start = time.time()
                        
                        next_response = client.chat(
                            model=chat_model,
                            messages=messages,
                            tools=tools,
                            options={'temperature': 0.3}
                        )
                        
                        followup_duration = time.time() - followup_start
                        print(f"LISA decided next action in {followup_duration:.2f} seconds.")
                        
                        # Check if the next response has tool calls
                        if hasattr(next_response.message, 'tool_calls') and next_response.message.tool_calls:
                            # Add assistant's message
                            messages.append({
                                "role": "assistant",
                                "content": next_response.message.content or ""
                            })
                            
                            # Execute the next tool calls
                            for next_tool_call in next_response.message.tool_calls:
                                print(f"DEBUG: Continuing with next function: {next_tool_call.function.name}")
                                next_result = execute_function(next_tool_call, chat_model, vision_model, messages, client)
                                
                                messages.append({
                                    "role": "tool",
                                    "content": next_result
                                })
                                
                                # Check if we should wait for user input
                                if next_result == "WAIT_FOR_USER_INPUT":
                                    print("LISA is waiting for your response...")
                                    break
                            
                            # If waiting for input, break the loop
                            if next_result == "WAIT_FOR_USER_INPUT":
                                break
                        else:
                            # Regular response - end the workflow
                            assistant_text = next_response.message.content.strip()
                            print(f"LISA: {assistant_text}")
                            if ENABLE_SPEECH:
                                robot_speak(assistant_text)
                            messages.append({"role": "assistant", "content": assistant_text})
                            break
                
            else:
                # Regular conversational response (no tool calls)
                assistant_response = response.message.content.strip()
                print(f"LISA: {assistant_response}")
                if ENABLE_SPEECH:
                    robot_speak(assistant_response)
                messages.append({"role": "assistant", "content": assistant_response})
        
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            print("LISA: I encountered an error. Please try again.")
        
        # Turn end is implicitly logged by terminal tee
    
    print("Session ended.")

if __name__ == "__main__":
    main()

