#!/usr/bin/env python3
import sys
import time
import datetime
import os
import threading
import json
import re
from ollama import chat, ChatResponse
from robot_functions import robot_take_pic, robot_speak, robot_listen, robot_hello
from ros_functions import (
    navigate_to, 
    start_status_listener, 
    wait_for_goal_completion,
    navigate_to_with_feedback
)
from conversation_logger import ConversationLogger

# Models
# Text model for general chat; can be overridden via env
DEFAULT_CHAT_MODEL = os.environ.get("LISA_CHAT_MODEL", "gemma3n:e4b")
# Vision-capable model for image analysis; can be overridden via env
DEFAULT_VISION_MODEL = os.environ.get("LISA_VISION_MODEL", "gemma3n:e4b")

LAST_IMAGE_PATH = "/home/unitree/LISA_v3_nav/tmp/frame.jpg"

def load_prompt(file_path):
    """Load the entire prompt file content as a single system prompt string."""
    with open(file_path, 'r', encoding='utf-8') as prompt_file:
        return prompt_file.read().strip()

def determine_safety_involvement(user_request, chat_model):
    """
    Use LLM to determine if a user request involves safety considerations.
    
    Args:
        user_request: The user's input text
        chat_model: The model to use for analysis
    
    Returns:
        bool: True if safety is involved, False otherwise
    """
    safety_detection_prompt = f"""Analyze this user request and determine if it involves safety considerations, safety equipment, safety compliance, workplace safety, or safety violations.

User request: "{user_request}"

Consider these safety-related concepts:
- Safety equipment (hard hats, safety vests, goggles, gloves, boots)
- Safety compliance or violations
- Workplace safety inspections
- Safety protocols or procedures
- Personal protective equipment (PPE)
- Safety hazards or risks
- Safety reporting or documentation
- Worker safety or protection

Respond with only "YES" if the request involves any safety considerations, or "NO" if it does not involve safety."""

    try:
        messages = [{"role": "user", "content": safety_detection_prompt}]
        response: ChatResponse = chat(
            model=chat_model,
            messages=messages,
            options={'temperature': 0.1}  # Low temperature for consistent classification
        )
        
        result = response.message.content.strip().upper()
        return result == "YES"
        
    except Exception as e:
        print(f"Error determining safety involvement: {e}")
        # Default to False if there's an error
        return False

def load_system_prompts(user_request, chat_model):
    """
    Load appropriate system prompts based on user request analysis.
    
    Args:
        user_request: The user's input text
        chat_model: The model to use for prompt selection
        
    Returns:
        str: Combined system prompt content
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Always load the demo prompt
    demo_prompt_path = os.path.join(script_dir, "prompt_demo.md")
    if not os.path.exists(demo_prompt_path):
        raise FileNotFoundError(f"Demo prompt file not found at {demo_prompt_path}")
    
    system_prompt = load_prompt(demo_prompt_path)
    
    # Check if safety is involved using LLM
    is_safety_related = determine_safety_involvement(user_request, chat_model)
    
    if is_safety_related:
        safety_prompt_path = os.path.join(script_dir, "safety_prompt.md")
        if os.path.exists(safety_prompt_path):
            safety_prompt = load_prompt(safety_prompt_path)
            # Combine prompts with clear separation
            system_prompt = f"{system_prompt}\n\n---\n\n{safety_prompt}"
            print("🔒 Safety mode activated - Additional safety protocols loaded")
        else:
            print("⚠️ Safety involvement detected but safety_prompt.md not found")
    
    return system_prompt

def chat_with_ollama(model, messages, options=None):
    """
    Send a chat request to the local Ollama instance.
    
    Args:
        model: The model name to use
        messages: List of message dictionaries
        options: Optional parameters like temperature
    
    Returns:
        ChatResponse: Response from Ollama
    """
    try:
        response: ChatResponse = chat(
            model=model,
            messages=messages,
            options=options or {}
        )
        return response
    except Exception as e:
        raise Exception(f"Ollama chat failed: {str(e)}")

def remove_markdown_code_blocks(text):
    """Remove all fenced markdown code blocks from the given text."""
    cleaned_text = text
    while "```" in cleaned_text:
        start_index = cleaned_text.find("```")
        end_index = cleaned_text.find("```", start_index + 3)
        if end_index == -1:
            # Remove everything from the first fence to the end
            cleaned_text = cleaned_text[:start_index].rstrip()
            break
        cleaned_text = (cleaned_text[:start_index] + cleaned_text[end_index + 3:]).strip()
    return cleaned_text

def remove_json_plan_blocks(text):
    """
    If any JSON blocks that look like plans are embedded in the text, remove them
    by truncating text before the first such block. A plan is detected if the
    JSON contains an "actions" key.
    """
    # Find the first JSON-like block
    for match in re.finditer(r"\{[\s\S]*?\}", text):
        candidate = match.group(0)
        if '"actions"' in candidate:
            return text[:match.start()].rstrip()
    return text

def get_last_user_text(prior_messages):
    """Return the most recent user text message that does not include images."""
    for msg in reversed(prior_messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str) and not msg.get("images"):
            return msg.get("content", "").strip()
    return ""

def handle_unknown_action(action_type, params, messages, chat_model):
    """
    Attempt to handle unknown action types intelligently.
    Returns a result message if handled, None if it needs LLM intervention.
    """
    try:
        # Check if it's a communication/speech action
        if action_type.lower() in ['talk', 'speak', 'announce', 'say', 'tell', 'communicate', 'broadcast', 'alert', 'warn']:
            message = params.get('message', '') or params.get('text', '') or params.get('content', '')
            if message:
                print(f"LISA: {message}")
                robot_speak(message)
                return f"Announced: {message}"
            else:
                return "No message provided for communication action"
        
        # Check if it's a movement/navigation action
        elif action_type.lower() in ['move', 'go', 'travel', 'head']:
            location = params.get('location', '') or params.get('destination', '') or params.get('target', '')
            if location:
                # Try to use the existing navigation system
                try:
                    goal_id = navigate_to(location)
                    result = wait_for_goal_completion(goal_id, timeout=120.0)
                    if result == "SUCCEEDED":
                        return f"Successfully reached {location}"
                    else:
                        return f"Navigation to {location} failed: {result}"
                except Exception as e:
                    return f"Navigation failed: {str(e)}"
            else:
                return "No location specified for movement action"
        
        # Check if it's a sensing/observation action
        elif action_type.lower() in ['look', 'observe', 'see', 'check', 'inspect', 'examine', 'scan']:
            # For now, treat as take_picture
            try:
                success = robot_take_pic()
                if success:
                    return "Picture taken for observation"
                else:
                    return "Failed to take observation picture"
            except Exception as e:
                return f"Observation failed: {str(e)}"
        
        # If we don't recognize the action, return None to trigger LLM intervention
        return None
        
    except Exception as e:
        return f"Error handling unknown action '{action_type}': {str(e)}"

def handle_safety_violation_if_detected(analysis_text, messages, chat_model, logger=None):
    """
    Check for safety violations in analysis text and handle them automatically.
    Returns (violation_detected, should_continue_processing, updated_assistant_response)
    """
    safety_violation_detected = (
        "not wearing a hard hat" in analysis_text.lower() or
        "no hard hat" in analysis_text.lower() or
        "without a hard hat" in analysis_text.lower() or
        "missing hard hat" in analysis_text.lower()
    )
    
    if not safety_violation_detected:
        return False, False, None
    
    # Safety violation detected - initiate protocol
    print("🚨 Safety violation detected - initiating safety protocol")
    observation = f"Safety violation detected: {analysis_text}. Continue with mandatory safety protocol."
    messages.append({"role": "user", "content": observation})
    
    try:
        # Ask the model for the next step in the safety protocol
        followup_response = chat_with_ollama(
            model=chat_model,
            messages=messages,
            options={'temperature': 0.1}
        )
        next_text = followup_response.message.content.strip()
        print(f"DEBUG: Safety protocol next step: {next_text}")
        
        # Check if it's a stepwise response
        is_stepwise = ('"type"' in next_text) and ('"ACT"' in next_text or '"TALK"' in next_text)
        
        return True, is_stepwise, next_text
        
    except Exception as e:
        print(f"Error initiating safety protocol: {e}")
        if logger:
            logger.log_error(str(e), "safety_protocol")
        return True, False, None

def get_llm_alternative_for_unknown_action(action_type, params, messages, chat_model):
    """
    Ask the LLM to provide an alternative approach when we can't handle an unknown action.
    """
    try:
        # Get the original user request for context
        last_user_request = get_last_user_text(messages)
        
        # Create a prompt asking for an alternative
        alternative_prompt = f"""I was asked to perform an action called '{action_type}' with parameters {params}, but I don't have that capability built in. 

The original user request was: "{last_user_request}"

Given my available capabilities (navigate to locations, take pictures, speak messages), how should I handle this request? Please provide a brief, natural response that either:
1. Explains what I can do instead, or 
2. Provides the announcement/message directly if this was meant to be a speaking action

Keep your response conversational and under 2 sentences."""

        # Add the alternative request to messages
        alt_messages = messages + [{"role": "user", "content": alternative_prompt}]
        
        # Get LLM response
        response = chat_with_ollama(
            model=chat_model,
            messages=alt_messages,
            options={'temperature': 0.3}
        )
        
        alternative_text = response.message.content.strip()
        alternative_text = remove_markdown_code_blocks(alternative_text)
        alternative_text = remove_json_plan_blocks(alternative_text)
        
        return alternative_text
        
    except Exception as e:
        print(f"Error getting LLM alternative: {e}")
        return None

def execute_compound_action(actions, chat_model=DEFAULT_CHAT_MODEL, vision_model=DEFAULT_VISION_MODEL, messages=None, logger=None):
    """
    Execute a sequence of actions and handle any follow-up analysis.
    
    Args:
        actions: List of action dictionaries with 'type' and 'params'
        model: The Ollama model to use for image analysis
        messages: Message history for LLM context (optional)
        logger: ConversationLogger instance for logging actions
    
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
                action_start_time = time.time()
                try:
                    print(f"Navigating to {location}...")
                    
                    # Send goal and get goal_id for tracking
                    goal_id = navigate_to(location)
                    print(f"Goal sent with ID: {goal_id}")
                    
                    # Wait for navigation to complete with timeout
                    print("Waiting for navigation to complete...")
                    result = wait_for_goal_completion(goal_id, timeout=120.0)  # 2 minute timeout
                    
                    action_duration = time.time() - action_start_time
                    
                    if result == "SUCCEEDED":
                        success_msg = f"Successfully reached {location}"
                        print(success_msg)
                        robot_speak(success_msg)  # Speak the confirmation, provides natural delay
                        results.append(success_msg)
                        if logger:
                            logger.log_action_executed("navigate_to", params, success_msg, action_duration)
                    elif result == "CANCELED":
                        error_msg = f"Navigation to {location} was canceled"
                        print(error_msg)
                        results.append(error_msg)
                        if logger:
                            logger.log_action_executed("navigate_to", params, error_msg, action_duration)
                    elif result == "ABORTED":
                        error_msg = f"Navigation to {location} failed"
                        print(error_msg)
                        results.append(error_msg)
                        if logger:
                            logger.log_action_executed("navigate_to", params, error_msg, action_duration)
                    else:
                        error_msg = f"Navigation to {location} timed out"
                        print(error_msg)
                        results.append(error_msg)
                        if logger:
                            logger.log_action_executed("navigate_to", params, error_msg, action_duration)
                        
                except Exception as e:
                    action_duration = time.time() - action_start_time
                    error_msg = f"Navigation to {location} failed: {str(e)}"
                    print(error_msg)
                    results.append(error_msg)
                    if logger:
                        logger.log_error(str(e), "navigation")
                        logger.log_action_executed("navigate_to", params, error_msg, action_duration)
                    
        elif action_type == 'take_picture':
            action_start_time = time.time()
            try:
                print("Taking a picture...")
                success = robot_take_pic()
                action_duration = time.time() - action_start_time
                
                if success:
                    success_msg = "Picture taken successfully"
                    print(success_msg)
                    results.append(success_msg)
                    image_taken = True
                    if logger:
                        logger.log_action_executed("take_picture", params, success_msg, action_duration)
                else:
                    error_msg = "Failed to take picture"
                    print(error_msg)
                    results.append(error_msg)
                    if logger:
                        logger.log_action_executed("take_picture", params, error_msg, action_duration)
            except Exception as e:
                action_duration = time.time() - action_start_time
                error_msg = f"Picture taking failed: {str(e)}"
                print(error_msg)
                results.append(error_msg)
                if logger:
                    logger.log_error(str(e), "camera")
                    logger.log_action_executed("take_picture", params, error_msg, action_duration)
                
        elif action_type == 'talk' or action_type == 'speak' or action_type == 'announce':
            action_start_time = time.time()
            try:
                message = params.get('message', '')
                if message:
                    print(f"LISA: {message}")
                    robot_speak(message)
                    action_duration = time.time() - action_start_time
                    success_msg = f"Announced: {message}"
                    results.append(success_msg)
                    if logger:
                        logger.log_action_executed(action_type, params, success_msg, action_duration)
                else:
                    action_duration = time.time() - action_start_time
                    error_msg = "No message provided for talk action"
                    print(error_msg)
                    results.append(error_msg)
                    if logger:
                        logger.log_action_executed(action_type, params, error_msg, action_duration)
            except Exception as e:
                action_duration = time.time() - action_start_time
                error_msg = f"Talk action failed: {str(e)}"
                print(error_msg)
                results.append(error_msg)
                if logger:
                    logger.log_error(str(e), "speech")
                    logger.log_action_executed(action_type, params, error_msg, action_duration)
                
        # 'wait' action removed as unnecessary; any received 'wait' will be ignored
        
        elif action_type == 'analyze_image':
            try:
                print("Analyzing the image...")
                image_path = LAST_IMAGE_PATH
                
                if os.path.exists(image_path):
                    # Keep analysis inside the same session: append an image + brief instruction
                    last_request_text = get_last_user_text(messages)
                    analysis_prompt = f"Analyze this image based on the user's request: '{last_request_text}'. Describe what you see in 1-3 sentences. Plain text only."
                    messages.append({
                        "role": "user",
                        "content": analysis_prompt,
                        "images": [image_path]
                    })

                    # Call LLM for analysis
                    print("LISA is analyzing the image...")
                    start_time = time.time()
                    
                    analysis_response = chat_with_ollama(
                        model=vision_model or chat_model,
                        messages=messages,
                        options={'temperature': 0.2}
                    )
                    
                    end_time = time.time()
                    duration = end_time - start_time
                    print(f"LISA analyzed the image in {duration:.2f} seconds.")
                    
                    analysis_result = analysis_response.message.content

                    # Strip fenced code blocks and any embedded JSON plan blocks
                    analysis_result = remove_markdown_code_blocks(analysis_result)
                    analysis_result = remove_json_plan_blocks(analysis_result)
                    
                    # Print and speak the analysis result
                    print(f"LISA: {analysis_result}")
                    robot_speak(analysis_result)
                    
                    # Log the image analysis
                    if logger:
                        logger.log_image_analysis(analysis_prompt, analysis_result, duration)
                    
                    # Add the analysis to message history
                    messages.append({"role": "assistant", "content": analysis_result})
                    
                    results.append("Image analyzed successfully")
                else:
                    error_msg = "No image found to analyze"
                    print(error_msg)
                    results.append(error_msg)
                    if logger:
                        logger.log_error(error_msg, "image_analysis")
                    
            except Exception as e:
                error_msg = f"Image analysis failed: {str(e)}"
                print(error_msg)
                results.append(error_msg)
                if logger:
                    logger.log_error(str(e), "image_analysis")
        
        else:
            # Handle unknown action types adaptively
            if action_type:
                print(f"Attempting to handle unknown action: {action_type}")
                handled = handle_unknown_action(action_type, params, messages, chat_model)
                if handled:
                    results.append(handled)
                else:
                    # Ask LLM to find an alternative approach
                    print(f"Unknown action '{action_type}' - asking LLM for alternative approach")
                    alternative_msg = get_llm_alternative_for_unknown_action(action_type, params, messages, chat_model)
                    if alternative_msg:
                        print(f"LISA: {alternative_msg}")
                        robot_speak(alternative_msg)
                        results.append(f"Alternative approach: {alternative_msg}")
                    else:
                        fallback_msg = f"I'm not sure how to '{action_type}', but I've completed the other actions."
                        print(f"LISA: {fallback_msg}")
                        results.append(fallback_msg)
    
    return " ".join(results), image_taken

def main():
    """
    Main function to run the LISA navigation and camera assistant demo with ASR and clicker support.
    """
    chat_model = DEFAULT_CHAT_MODEL
    vision_model = DEFAULT_VISION_MODEL

    # Initialize conversation logger
    logger = ConversationLogger()

    # Initialize message history with placeholder - will be updated with first user input
    messages = []
    
    # Welcome message
    print("\n=== LISA - Navigation & Camera Assistant (Demo Version) ===")
    print(f"Using Ollama chat model: {chat_model}")
    print(f"Using Ollama vision model: {vision_model}")
    print("Using local Ollama instance")
    print("Uses clicker for input and ASR for speech recognition")
    print("==========================================\n")
    
    welcome_message = "Hello! I'm LISA, your Local Intelligent Safety Assistant. I was developed by the SMART Construction Research Group at New York University Abu Dhabi. I can navigate to different locations, take pictures, and analyze what I see for safety compliance. How can I help you today?"
    print(f"LISA: {welcome_message}")
    robot_speak(welcome_message)
    
    # Log session initialization
    logger.log_system_message(f"Demo session started with local Ollama - Chat: {chat_model}, Vision: {vision_model}", "info")
    
    # Main loop using ASR and clicker
    while True:
        try:
            # Use robot_listen for ASR with clicker input
            user_input = robot_listen()
            
            # Handle case where listening failed or was cancelled
            if user_input is None:
                print("Listening cancelled or failed, waiting for next input.")
                continue
                
            # Check for the clear chat signal
            if user_input == "CLEAR_CHAT":
                print("--- Clearing Chat History ---")
                messages = []
                logger.log_system_message("Chat history cleared", "info")
                continue
                
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
            break
        
        # Handle empty input
        if not user_input or not user_input.strip():
            continue
            
        print(f"You: {user_input}")
        
        # Start logging this user turn
        logger.start_user_turn(user_input, "speech")
        
        # Load appropriate system prompts if this is the first interaction or messages were cleared
        if not messages:
            try:
                print("🧠 Analyzing request to determine appropriate protocols...")
                system_prompt = load_system_prompts(user_input, chat_model)
                messages.append({"role": "system", "content": system_prompt})
            except Exception as e:
                print(f"Error loading system prompts: {e}")
                # Fallback to demo prompt only
                script_dir = os.path.dirname(os.path.abspath(__file__))
                demo_prompt_path = os.path.join(script_dir, "prompt_demo.md")
                if os.path.exists(demo_prompt_path):
                    system_prompt = load_prompt(demo_prompt_path)
                    messages.append({"role": "system", "content": system_prompt})
                else:
                    print("Error: Demo prompt file not found!")
                    continue
            
        # Append the user's raw text
        messages.append({"role": "user", "content": user_input})
        
        try:
            print("LISA is thinking...")
            logger.log_llm_thinking_start()
            start_time = time.time()
            
            # Let the LLM decide naturally if it needs to reference the last image
            # The prompt will guide it to understand when to use existing vs new images
            turn_model = chat_model

            # Add brevity reminder for demo
            messages_with_reminder = messages + [{"role": "system", "content": "Remember: Keep your response very brief (1-2 sentences max) for this demo."}]
            
            ollama_response = chat_with_ollama(
                model=turn_model,
                messages=messages_with_reminder,
                options={'temperature': 0.2}  # Lower temperature for more concise responses
            )
            
            end_time = time.time()
            duration = end_time - start_time
            print(f"LISA thought for {duration:.2f} seconds.")
            
            assistant_response = ollama_response.message.content
            
            # Log the LLM response
            logger.log_llm_response(assistant_response, duration)

            # Debug: Print the raw LLM response
            print(f"DEBUG: Raw LLM response: {assistant_response}")

            # Decide whether to treat as a JSON action plan, a stepwise ACT/TALK, image analysis request, or plain text
            raw_text = assistant_response.strip()
            
            # Check if LLM is requesting to analyze the current image
            if raw_text.startswith("ANALYZE_CURRENT_IMAGE") and os.path.exists(LAST_IMAGE_PATH):
                try:
                    image_analysis_prompt = raw_text.replace("ANALYZE_CURRENT_IMAGE", "").strip()
                    if not image_analysis_prompt:
                        image_analysis_prompt = f"Answer the user's question: '{user_input}'"
                    
                    messages.append({
                        "role": "user", 
                        "content": f"{image_analysis_prompt}. Ground your answer strictly in what you can see in this image.",
                        "images": [LAST_IMAGE_PATH]
                    })
                    
                    analysis_start_time = time.time()
                    vision_response = chat_with_ollama(
                        model=vision_model or chat_model,
                        messages=messages,
                        options={'temperature': 0.2}
                    )
                    analysis_duration = time.time() - analysis_start_time
                    
                    analysis_result = vision_response.message.content
                    analysis_result = remove_markdown_code_blocks(analysis_result)
                    analysis_result = remove_json_plan_blocks(analysis_result)
                    
                    print(f"LISA: {analysis_result}")
                    robot_speak(analysis_result)
                    
                    # Log the image analysis
                    logger.log_image_analysis(image_analysis_prompt, analysis_result, analysis_duration)
                    
                    messages.append({"role": "assistant", "content": analysis_result})
                    
                    # Check for safety violations and handle automatically
                    violation_detected, is_stepwise, next_response = handle_safety_violation_if_detected(
                        analysis_result, messages, chat_model, logger
                    )
                    
                    if violation_detected:
                        if is_stepwise and next_response:
                            # Stepwise response - process it as a stepwise action
                            assistant_response = next_response
                            # Don't add to messages yet - let it fall through to stepwise processing
                            raw_text = next_response
                            # Re-evaluate as stepwise
                            looks_like_step = ('"type"' in raw_text) and ('"ACT"' in raw_text or '"TALK"' in raw_text) and ('{' in raw_text)
                            if looks_like_step:
                                # Process as stepwise - don't continue, fall through to stepwise handler
                                pass
                            else:
                                # Not stepwise, treat as plain text
                                print(f"LISA: {next_response}")
                                robot_speak(next_response)
                                messages.append({"role": "assistant", "content": next_response})
                                continue
                        elif next_response:
                            # Plain text response
                            print(f"LISA: {next_response}")
                            robot_speak(next_response)
                            messages.append({"role": "assistant", "content": next_response})
                            continue
                        else:
                            # Error in safety protocol - continue normally
                            continue
                    else:
                        # No safety violation - normal completion
                        continue
                except Exception as e:
                    print(f"Error analyzing image: {e}")
                    
            # Check for JSON structures anywhere in the response
            looks_like_plan = ('"actions"' in raw_text) and ('{' in raw_text)
            looks_like_step = ('"type"' in raw_text) and ('"ACT"' in raw_text or '"TALK"' in raw_text) and ('{' in raw_text)

            if looks_like_plan:
                try:
                    # Extract JSON from response (could be wrapped in markdown or mixed with text)
                    json_str = raw_text
                    
                    # Handle markdown fences
                    if "```" in json_str:
                        parts = json_str.split("```")
                        for i, part in enumerate(parts):
                            if part.strip().startswith("json"):
                                part = part.strip()[4:]  # Remove "json" prefix
                            if '{' in part and '"actions"' in part:
                                json_str = part.strip()
                                break
                    
                    # If no markdown fences, find the JSON object
                    elif not json_str.strip().startswith('{'):
                        # Find the first JSON object in the text
                        start = json_str.find('{')
                        if start != -1:
                            # Find the matching closing brace
                            brace_count = 0
                            end = start
                            for i in range(start, len(json_str)):
                                if json_str[i] == '{':
                                    brace_count += 1
                                elif json_str[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end = i + 1
                                        break
                            json_str = json_str[start:end]
                    
                    json_str = json_str.strip()

                    print(f"DEBUG: Parsed JSON string: {json_str}")
                    
                    # Try to fix common JSON syntax errors
                    try:
                        response_data = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"DEBUG: JSON parse error: {e}")
                        # Try to fix common errors like missing quotes on keys
                        fixed_json = json_str
                        # Fix "params: {}" -> "params": {}
                        fixed_json = re.sub(r'"(\w+):\s*([{[])', r'"\1": \2', fixed_json)
                        print(f"DEBUG: Attempting to fix JSON: {fixed_json}")
                        try:
                            response_data = json.loads(fixed_json)
                            print("DEBUG: JSON repair successful")
                        except json.JSONDecodeError:
                            print("DEBUG: JSON repair failed, falling back to plain text")
                            raise  # Re-raise the original exception

                    actions = response_data.get("actions", [])
                    message = response_data.get("message", "")

                    # Print and speak the initial message
                    if message:
                        print(f"LISA: {message}")
                        robot_speak(message)

                    # Execute actions if any
                    if actions:
                        print(f"Executing {len(actions)} actions...")
                        result, image_taken = execute_compound_action(actions, chat_model, vision_model, messages, logger)

                        # Let the LLM decide naturally when to provide follow-up analysis
                        # by adding an observation about the completed actions
                        action_summary = []
                        for action in actions:
                            if action.get('type') == 'navigate_to':
                                location = action.get('params', {}).get('location', 'unknown location')
                                action_summary.append(f"navigated to {location}")
                            elif action.get('type') == 'take_picture':
                                action_summary.append("took a picture")
                        
                        if action_summary:
                            actions_completed = ", then ".join(action_summary)
                            observation = f"Actions completed: {actions_completed}. {result}"
                            messages.append({"role": "user", "content": observation})
                            
                            # Get LLM's follow-up response
                            print("LISA is preparing follow-up...")
                            followup_response = chat_with_ollama(
                                model=chat_model,
                                messages=messages,
                                options={'temperature': 0.1}  # Lower temperature to reduce hallucinations
                            )
                            
                            followup_text = followup_response.message.content.strip()
                            print(f"DEBUG: Follow-up response: {followup_text}")
                            
                            # Check if this is a status report vs something to announce
                            # Don't speak status reports that mention completing actions
                            is_status_report = any(phrase in followup_text.lower() for phrase in [
                                "i've", "i have", "completed", "accomplished", "finished", 
                                "navigated to", "announced", "taken a picture", "reached"
                            ])
                            
                            # Check if it's an ANALYZE_CURRENT_IMAGE request
                            if followup_text.startswith("ANALYZE_CURRENT_IMAGE") and os.path.exists(LAST_IMAGE_PATH):
                                try:
                                    image_analysis_prompt = followup_text.replace("ANALYZE_CURRENT_IMAGE", "").strip()
                                    if not image_analysis_prompt:
                                        last_user_text = get_last_user_text(messages)
                                        image_analysis_prompt = f"Provide a report based on the user's request: '{last_user_text}'"
                                    
                                    messages.append({
                                        "role": "user", 
                                        "content": f"{image_analysis_prompt}. Ground your answer strictly in what you can see in this image.",
                                        "images": [LAST_IMAGE_PATH]
                                    })
                                    
                                    analysis_start_time = time.time()
                                    vision_response = chat_with_ollama(
                                        model=vision_model or chat_model,
                                        messages=messages,
                                        options={'temperature': 0.2}
                                    )
                                    analysis_duration = time.time() - analysis_start_time
                                    
                                    analysis_result = vision_response.message.content
                                    analysis_result = remove_markdown_code_blocks(analysis_result)
                                    analysis_result = remove_json_plan_blocks(analysis_result)
                                    
                                    print(f"LISA: {analysis_result}")
                                    robot_speak(analysis_result)
                                    
                                    # Log the image analysis
                                    logger.log_image_analysis(image_analysis_prompt, analysis_result, analysis_duration)
                                    
                                    messages.append({"role": "assistant", "content": analysis_result})
                                except Exception as e:
                                    print(f"Error analyzing image: {e}")
                            else:
                                # Regular conversational response
                                print(f"LISA: {followup_text}")
                                # Only speak if it's not a status report
                                if not is_status_report:
                                    robot_speak(followup_text)
                                messages.append({"role": "assistant", "content": followup_text})
                except json.JSONDecodeError:
                    # Treat as plain text if parsing fails
                    print(f"LISA: {assistant_response}")
                    robot_speak(assistant_response)
            elif looks_like_step:
                # Handle stepwise responses similar to the original implementation
                # ... (stepwise handling code would be here, similar to original)
                print(f"LISA: {assistant_response}")
                robot_speak(assistant_response)
            else:
                # Plain conversational reply
                print(f"LISA: {assistant_response}")
                robot_speak(assistant_response)
            
            # Add response to message history
            messages.append({"role": "assistant", "content": assistant_response})
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            error_speech = "I encountered an error. Please try again."
            print(f"LISA: {error_speech}")
            robot_speak(error_speech)
            logger.log_error(str(e), "general")
        
        # End the current turn logging
        logger.end_turn()
            
    print("Session ended.")
    logger.log_session_end()

if __name__ == "__main__":
    main()
