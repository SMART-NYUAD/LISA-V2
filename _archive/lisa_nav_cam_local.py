#!/usr/bin/env python3
import sys
import time
import datetime
import os
import threading
import json
from ollama import chat, ChatResponse
from robot_functions import robot_take_pic, robot_speak
from ros_functions import (
    navigate_to, 
    start_status_listener, 
    wait_for_goal_completion,
    navigate_to_with_feedback
)

def execute_compound_action(actions, model="gemma3:27b", messages=None):
    """
    Execute a sequence of actions and handle any follow-up analysis.
    
    Args:
        actions: List of action dictionaries with 'type' and 'params'
        model: The Ollama model to use for image analysis
        messages: Message history for LLM context (optional)
    
    Returns:
        tuple: (result_message, image_taken) - result message and whether an image was taken
    """
    # Initialize status listener (will only start one if not already running)
    start_status_listener()
    
    results = []
    image_taken = False
    
    for action in actions:
        action_type = action.get('type')
        params = action.get('params', {})
        
        if action_type == 'navigate_to':
            location = params.get('location')
            if location:
                try:
                    print(f"Navigating to {location}...")
                    robot_speak(f"Navigating to {location}")
                    
                    # Send goal and get goal_id for tracking
                    goal_id = navigate_to(location)
                    print(f"Goal sent with ID: {goal_id}")
                    
                    # Wait for navigation to complete with timeout
                    print("Waiting for navigation to complete...")
                    result = wait_for_goal_completion(goal_id, timeout=120.0)  # 2 minute timeout
                    
                    if result == "SUCCEEDED":
                        success_msg = f"Successfully reached {location}"
                        print(success_msg)
                        robot_speak(success_msg)
                        results.append(success_msg)
                    elif result == "CANCELED":
                        error_msg = f"Navigation to {location} was canceled"
                        print(error_msg)
                        robot_speak(error_msg)
                        results.append(error_msg)
                    elif result == "ABORTED":
                        error_msg = f"Navigation to {location} failed"
                        print(error_msg)
                        robot_speak(error_msg)
                        results.append(error_msg)
                    else:
                        error_msg = f"Navigation to {location} timed out"
                        print(error_msg)
                        robot_speak(error_msg)
                        results.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Navigation to {location} failed: {str(e)}"
                    print(error_msg)
                    robot_speak(error_msg)
                    results.append(error_msg)
                    
        elif action_type == 'take_picture':
            try:
                print("Taking a picture...")
                robot_speak("Taking a picture")
                success = robot_take_pic()
                if success:
                    success_msg = "Picture taken successfully"
                    print(success_msg)
                    robot_speak(success_msg)
                    results.append(success_msg)
                    image_taken = True
                else:
                    error_msg = "Failed to take picture"
                    print(error_msg)
                    robot_speak(error_msg)
                    results.append(error_msg)
            except Exception as e:
                error_msg = f"Picture taking failed: {str(e)}"
                print(error_msg)
                robot_speak(error_msg)
                results.append(error_msg)
                
        elif action_type == 'wait':
            wait_time = params.get('seconds', 1)
            print(f"Waiting for {wait_time} seconds...")
            robot_speak(f"Waiting {wait_time} seconds")
            time.sleep(wait_time)
            
        elif action_type == 'analyze_image':
            try:
                print("Analyzing the image...")
                robot_speak("Analyzing the image")
                image_path = "/home/unitree/LISA_v3_nav/tmp/frame.jpg"
                
                if os.path.exists(image_path):
                    # Add the image to the main conversation for analysis
                    messages.append({
                        "role": "user", 
                        "content": "Analyze this image and describe what you see.",
                        "images": [image_path]
                    })
                    
                    # Call local Ollama for analysis
                    print("LISA is analyzing the image...")
                    start_time = time.time()
                    
                    analysis_response: ChatResponse = chat(
                        model=model,
                        messages=messages,
                        options={'temperature': 0.3}
                    )
                    
                    end_time = time.time()
                    duration = end_time - start_time
                    print(f"LISA analyzed the image in {duration:.2f} seconds.")
                    
                    analysis_result = analysis_response.message.content
                    
                    # Try to parse as JSON first, if it fails, treat as plain text
                    try:
                        # Remove any potential markdown formatting
                        json_str = analysis_result.strip()
                        if json_str.startswith("```"):
                            json_str = json_str.split("```")[1]
                            if json_str.startswith("json"):
                                json_str = json_str[4:]
                        
                        response_data = json.loads(json_str)
                        # If it's JSON, extract the message
                        if "message" in response_data:
                            analysis_result = response_data["message"]
                            # If the message is about actions (like "I'll take a picture..."), 
                            # then the LLM didn't actually analyze the image
                            if "take a picture" in analysis_result.lower() or "analyze" in analysis_result.lower():
                                # The LLM responded with actions instead of analysis, treat as plain text
                                pass
                    except json.JSONDecodeError:
                        # If it's not JSON, use as-is
                        pass
                    
                    # Print and speak the analysis result
                    print(f"LISA: {analysis_result}")
                    robot_speak(analysis_result)
                    
                    # Add the analysis to message history
                    messages.append({"role": "assistant", "content": analysis_result})
                    
                    results.append("Image analyzed successfully")
                else:
                    error_msg = "No image found to analyze"
                    print(error_msg)
                    robot_speak(error_msg)
                    results.append(error_msg)
                    
            except Exception as e:
                error_msg = f"Image analysis failed: {str(e)}"
                print(error_msg)
                robot_speak(error_msg)
                results.append(error_msg)
    
    
    
    return " ".join(results), image_taken

def main():
    """
    Main function to run the simplified navigation and camera assistant.
    """
    MODEL = "gemma3n:e2b"  # "gpt-oss:20b" #"mistral-small3.2:latest" #"gemma3:27b" #"qwen2.5vl:7b" 
    
    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys_prompt_file_path = os.path.join(script_dir, "nav_cam_sys_prompt.md")
    
    # Read system prompt
    try:
        with open(sys_prompt_file_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        print(f"System prompt not found, using default")
        system_prompt = """You are LISA, an AI assistant that can navigate and take pictures.

When users give you compound commands like "go to X and take a picture", you should:
1. Parse the command to identify all actions
2. Return a JSON response with the sequence of actions

When an image is included in the conversation context, you can analyze and describe what you see in your response.

IMPORTANT: Use the analyze_image action when the user's request implies they want to know what you see. For example:
- "go to workbench and tell me what's there" → navigate_to + take_picture + analyze_image
- "inspect the dispenser" → navigate_to + take_picture + analyze_image  
- "take a picture" → just take_picture (no analysis needed)

Use your judgment to determine if the user wants to know what you see or just wants a picture taken.

Available actions:
- navigate_to: Navigate to 'station', 'workbench', or 'dispenser'
- take_picture: Take a picture with the robot's camera
- analyze_image: Analyze the last taken picture and describe what you see
- wait: Wait for specified seconds

Respond with JSON in this format:
{
  "actions": [
    {"type": "navigate_to", "params": {"location": "dispenser"}},
    {"type": "take_picture", "params": {}}
  ],
  "message": "Your response to the user"
}

If no actions are needed, use:
{
  "actions": [],
  "message": "Your response"
}

Examples:
- "Go to the dispenser and take a picture" → navigate_to + take_picture
- "Take a picture and tell me what you see" → take_picture + analyze_image
- "Go to the workbench, wait 5 seconds, then take a picture and describe it" → navigate_to + wait + take_picture + analyze_image

Always respond with valid JSON without markdown formatting."""
    
    # Initialize message history
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Welcome message
    print("\n=== LISA - Navigation & Camera Assistant (Local Ollama Version) ===")
    print(f"Using Ollama model: {MODEL}")
    print("Type 'quit' or 'exit' to end the session")
    print("Type 'clear' to clear chat history")
    print("==========================================\n")
    
    welcome_message = "Hello! I'm LISA, your navigation and camera assistant. I can go to different locations, take pictures, and analyze what I see. What would you like me to do?"
    print(f"LISA: {welcome_message}")
    #robot_speak(welcome_message)
    
    # Main loop
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
        
        # Check for the clear chat signal
        if user_input.lower() == 'clear':
            print("--- Clearing Chat History ---")
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            continue
        
        # Handle empty input
        if not user_input:
            continue
            
        messages.append({"role": "user", "content": user_input})
        
        try:
            print("LISA is thinking...")
            start_time = time.time()
            
            response: ChatResponse = chat(
                model=MODEL,
                messages=messages,
                options={'temperature': 0.3}
            )
            
            end_time = time.time()
            duration = end_time - start_time
            print(f"LISA thought for {duration:.2f} seconds.")
            
            assistant_response = response.message.content
            
            # Debug: Print the raw LLM response
            print(f"DEBUG: Raw LLM response: {assistant_response}")
            
            # Try to parse JSON response
            try:
                # Remove any potential markdown formatting
                json_str = assistant_response.strip()
                if json_str.startswith("```"):
                    json_str = json_str.split("```")[1]
                    if json_str.startswith("json"):
                        json_str = json_str[4:]
                
                print(f"DEBUG: Parsed JSON string: {json_str}")
                response_data = json.loads(json_str)
                
                actions = response_data.get("actions", [])
                message = response_data.get("message", "")
                
                
                
                # Print and speak the initial message
                if message:
                    print(f"LISA: {message}")
                    robot_speak(message)
                
                # Execute actions if any
                if actions:
                    print(f"Executing {len(actions)} actions...")
                    
                    # Execute actions directly (no threading needed for terminal version)
                    result, image_taken = execute_compound_action(actions, MODEL, messages)
                    
                    
                
            except json.JSONDecodeError:
                # Fallback to plain text response
                print(f"LISA: {assistant_response}")
                robot_speak(assistant_response)
            
            # Add response to message history
            messages.append({"role": "assistant", "content": assistant_response})
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            robot_speak("I encountered an error. Please try again.")
            
    print("Session ended.")

if __name__ == "__main__":
    main() 


