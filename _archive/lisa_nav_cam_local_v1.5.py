#!/usr/bin/env python3
import sys
import time
import datetime
import os
import threading
import json
import re
from ollama import chat, ChatResponse
from robot_functions import robot_take_pic, robot_speak
from ros_functions import (
    navigate_to, 
    start_status_listener, 
    wait_for_goal_completion,
    navigate_to_with_feedback
)
from conversation_logger import ConversationLogger

# Models
# Text model for general chat; can be overridden via env
DEFAULT_CHAT_MODEL = os.environ.get("LISA_CHAT_MODEL", "gemma3:12b")
# Vision-capable model for image analysis; can be overridden via env
DEFAULT_VISION_MODEL = os.environ.get("LISA_VISION_MODEL", "gemma3:12b")

LAST_IMAGE_PATH = "/home/unitree/LISA_v3_nav/tmp/frame.jpg"


# Let the LLM determine appropriate actions and analysis based on natural language understanding

def load_prompt(file_path):
    """Load the entire prompt file content as a single system prompt string."""
    with open(file_path, 'r', encoding='utf-8') as prompt_file:
        return prompt_file.read().strip()


def chat_with_local_ollama(model, messages, options=None):
    """
    Send a chat request to local Ollama.
    
    Args:
        model: The model name to use
        messages: List of message dictionaries
        options: Optional parameters like temperature
    
    Returns:
        ChatResponse: Response from local Ollama
    """
    try:
        response: ChatResponse = chat(
            model=model,
            messages=messages,
            options=options or {}
        )
        return response
    except Exception as e:
        raise Exception(f"Local Ollama request failed: {str(e)}")

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

def check_for_safety_violation_with_llm(analysis_text, messages, chat_model, logger=None):
    """
    Use LLM to determine if the image analysis indicates a safety violation.
    Returns (violation_detected, should_continue_processing, updated_assistant_response)
    """
    # Check if we're already in a safety protocol workflow
    # Look for recent safety protocol messages in the conversation
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    for msg in recent_messages:
        if msg.get("role") == "system" and "SAFETY PROTOCOL ACTIVATED" in msg.get("content", ""):
            print("DEBUG: Already in safety protocol workflow - skipping safety check")
            return False, False, None
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # Only skip if there are actual safety protocol ACTIONS, not just analysis mentions
            if any(phrase in content.lower() for phrase in [
                "stop work immediately", "fetch a hard hat", "safety compliance protocol",
                "initiating hard hat safety", "personal safety assistant", "navigate to station"
            ]):
                print("DEBUG: Recent safety protocol activity detected - skipping safety check")
                return False, False, None
    
    print("DEBUG: Asking LLM to check for safety violations...")
    print(f"DEBUG: Analysis text being checked: '{analysis_text}'")
    
    safety_check_prompt = f"""Based on this image analysis, determine if there is a hard hat safety violation:

Image analysis: "{analysis_text}"

Rules:
- A safety violation exists if there is a PERSON/WORKER visible who is NOT wearing a hard hat
- If no people are visible, there is NO violation
- If people are visible and wearing hard hats, there is NO violation  
- Only respond with "VIOLATION" if you can clearly identify a person without a hard hat
- Otherwise respond with "NO_VIOLATION"

Response (one word only):"""

    try:
        safety_messages = [{"role": "user", "content": safety_check_prompt}]
        response = chat_with_local_ollama(
            model=chat_model,
            messages=safety_messages,
            options={'temperature': 0.1}  # Low temperature for consistent classification
        )
        
        result = response.message.content.strip().upper()
        print(f"DEBUG: LLM safety check result: {result}")
        
        if result == "VIOLATION":
            # Safety violation detected - initiate protocol
            print("🚨 Safety violation detected by LLM - initiating safety protocol")
            print("🔒 Loading safety compliance protocols...")
            
            # Load the safety prompt and add it to the conversation
            script_dir = os.path.dirname(os.path.abspath(__file__))
            safety_prompt_path = os.path.join(script_dir, "safety_prompt.md")
            
            if os.path.exists(safety_prompt_path):
                safety_prompt = load_prompt(safety_prompt_path)
                # Add safety prompt as a system message
                messages.append({"role": "system", "content": f"SAFETY PROTOCOL ACTIVATED:\n\n{safety_prompt}"})
            else:
                print("⚠️ Safety prompt file not found, using basic safety response")
            
            observation = f"Safety violation detected: {analysis_text}. You must now follow the safety compliance protocol."
            messages.append({"role": "user", "content": observation})
            
            # Ask the model for the next step in the safety protocol
            followup_response = chat_with_local_ollama(
                model=chat_model,
                messages=messages,
                options={'temperature': 0.1}
            )
            next_text = followup_response.message.content.strip()
            print(f"DEBUG: Safety protocol next step: {next_text}")
            
            # Check if it's a stepwise response
            is_stepwise = ('"type"' in next_text) and ('"ACT"' in next_text or '"TALK"' in next_text)
            
            return True, is_stepwise, next_text
        else:
            print("DEBUG: No safety violation detected by LLM")
            return False, False, None
        
    except Exception as e:
        print(f"Error checking safety violation: {e}")
        if logger:
            logger.log_error(str(e), "safety_check")
        return False, False, None

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
        response = chat_with_local_ollama(
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
        
        elif action_type == 'analyze_image' or action_type == 'analyze_current_image':
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

                    # Call local Ollama for analysis
                    print("LISA is analyzing the image...")
                    start_time = time.time()
                    
                    response = chat_with_local_ollama(
                        model=vision_model or chat_model,
                        messages=messages,
                        options={'temperature': 0.2}
                    )
                    
                    end_time = time.time()
                    duration = end_time - start_time
                    print(f"LISA analyzed the image in {duration:.2f} seconds.")
                    
                    analysis_result = response.message.content

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
                    robot_speak(error_msg)
                    results.append(error_msg)
                    if logger:
                        logger.log_error(error_msg, "image_analysis")
                    
            except Exception as e:
                error_msg = f"Image analysis failed: {str(e)}"
                print(error_msg)
                robot_speak(error_msg)
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
    Main function to run the simplified navigation and camera assistant.
    """
    chat_model = DEFAULT_CHAT_MODEL
    vision_model = DEFAULT_VISION_MODEL

    # Initialize conversation logger
    logger = ConversationLogger()

    # Initialize message history with placeholder - will be updated with first user input
    messages = []
    
    # Welcome message
    print("\n=== LISA - Navigation & Camera Assistant (Local Ollama Version) ===")
    print(f"Using Ollama chat model: {chat_model}")
    print(f"Using Ollama vision model: {vision_model}")
    print("Type 'quit' or 'exit' to end the session")
    print("Type 'clear' to clear chat history")
    print("==========================================\n")
    
    welcome_message = "Hello! I'm LISA, your navigation and camera assistant. I can go to different locations, take pictures, and analyze what I see. What would you like me to do?"
    print(f"LISA: {welcome_message}")
    
    # Log session initialization
    logger.log_system_message(f"Session started with local Ollama models - Chat: {chat_model}, Vision: {vision_model}", "info")
    
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
            logger.log_session_end()
            break
        
        # Check for the clear chat signal
        if user_input.lower() == 'clear':
            print("--- Clearing Chat History ---")
            messages = []
            logger.log_system_message("Chat history cleared", "info")
            continue
        
        # Handle empty input
        if not user_input:
            continue
            
        # Start logging this user turn
        logger.start_user_turn(user_input, "text")
        
        # Load default system prompt if this is the first interaction or messages were cleared
        if not messages:
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                default_prompt_path = os.path.join(script_dir, "prompt.md")
                if os.path.exists(default_prompt_path):
                    system_prompt = load_prompt(default_prompt_path)
                    messages.append({"role": "system", "content": system_prompt})
                else:
                    print("Error: Default prompt file not found!")
                    continue
            except Exception as e:
                print(f"Error loading system prompt: {e}")
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

            response = chat_with_local_ollama(
                model=turn_model,
                messages=messages,
                options={'temperature': 0.2 if turn_model == vision_model else 0.3}
            )
            
            end_time = time.time()
            duration = end_time - start_time
            print(f"LISA thought for {duration:.2f} seconds.")
            
            assistant_response = response.message.content
            
            # Log the LLM response
            logger.log_llm_response(assistant_response, duration)

            # Debug: Print the raw LLM response
            print(f"DEBUG: Raw LLM response: {assistant_response}")

            # Decide whether to treat as a JSON action plan, a stepwise ACT/TALK, image analysis request, or plain text
            raw_text = assistant_response.strip()
            
            # This section is now handled by the stepwise JSON processing below
            # The LLM should respond with stepwise JSON format for image analysis
                    
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
                            
                            # Check if the original user request included analysis/inspection keywords
                            original_request = get_last_user_text(messages[:-1])  # Get user request before the observation
                            analysis_keywords = ['inspect', 'check', 'examine', 'report', 'analyze', 'look at', 'see what', 'find out']
                            should_analyze = any(keyword in original_request.lower() for keyword in analysis_keywords)
                            
                            if should_analyze and "took a picture" in actions_completed:
                                observation = f"Actions completed: {actions_completed}. {result}\n\nSince the user requested inspection/analysis, please analyze the image you just took using this JSON format: {{\"type\": \"ACT\", \"tool\": \"analyze_current_image\", \"params\": {{\"prompt\": \"describe what you see\"}}}}"
                            else:
                                observation = f"Actions completed: {actions_completed}. {result}"
                            
                            messages.append({"role": "user", "content": observation})
                            
                            # Get LLM's follow-up response
                            print("LISA is preparing follow-up...")
                            followup_response = chat_with_local_ollama(
                                model=chat_model,
                                messages=messages,
                                options={'temperature': 0.1}  # Lower temperature to reduce hallucinations
                            )
                            
                            followup_text = followup_response.message.content.strip()
                            print(f"DEBUG: Follow-up response: {followup_text}")
                            
                            # Clean the followup text of markdown code blocks and JSON
                            clean_followup_text = remove_markdown_code_blocks(followup_text)
                            clean_followup_text = remove_json_plan_blocks(clean_followup_text)
                            
                            # Check if this is a status report vs something to announce
                            # Don't speak status reports that mention completing actions
                            is_status_report = any(phrase in clean_followup_text.lower() for phrase in [
                                "i've", "i have", "completed", "accomplished", "finished", 
                                "navigated to", "announced", "taken a picture", "reached"
                            ])
                            
                            # Check if it's a stepwise JSON request (including analyze_current_image)
                            if ('"type"' in followup_text) and ('"ACT"' in followup_text or '"TALK"' in followup_text) and ('{' in followup_text):
                                # Process the stepwise JSON immediately
                                try:
                                    # Parse the stepwise JSON
                                    json_str = followup_text.strip()
                                    if "```" in json_str:
                                        parts = json_str.split("```")
                                        for part in parts:
                                            if part.strip().startswith("json"):
                                                part = part.strip()[4:]  # Remove "json" prefix
                                            if '{' in part and '"type"' in part:
                                                json_str = part.strip()
                                                break
                                    
                                    step = json.loads(json_str)
                                    step_type = (step.get("type") or "").upper()
                                    step_tool = step.get("tool")
                                    step_params = step.get("params", {})
                                    step_msg = step.get("message", "")
                                    
                                    if step_msg:
                                        print(f"DEBUG: Internal step message: {step_msg}")
                                    
                                    # Add the stepwise response to messages
                                    messages.append({"role": "assistant", "content": followup_text})
                                    
                                    # Execute the stepwise action
                                    if step_type == "ACT" and step_tool and (step_tool == 'analyze_image' or step_tool == 'analyze_current_image'):
                                        # Handle image analysis
                                        if os.path.exists(LAST_IMAGE_PATH):
                                            last_user_text = get_last_user_text(messages)
                                            analysis_prompt = step_params.get('prompt', f"Answer the user's request: '{last_user_text}'")
                                            
                                            messages.append({
                                                "role": "user",
                                                "content": f"{analysis_prompt}. Ground your answer strictly in what you can see in this image.",
                                                "images": [LAST_IMAGE_PATH]
                                            })
                                            
                                            analysis_start_time = time.time()
                                            vision_response = chat_with_local_ollama(
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
                                            if logger:
                                                logger.log_image_analysis(analysis_prompt, analysis_result, analysis_duration)
                                            
                                            messages.append({"role": "assistant", "content": analysis_result})
                                            
                                            # Check for safety violations
                                            violation_detected, is_stepwise, next_response = check_for_safety_violation_with_llm(
                                                analysis_result, messages, chat_model, logger
                                            )
                                            
                                            if violation_detected and next_response:
                                                print(f"LISA: {next_response}")
                                                robot_speak(next_response)
                                                messages.append({"role": "assistant", "content": next_response})
                                        else:
                                            print("LISA: I don't have a recent image to analyze.")
                                    else:
                                        # Handle other stepwise actions if needed
                                        print(f"LISA: {clean_followup_text}")
                                        if not is_status_report:
                                            robot_speak(clean_followup_text)
                                
                                except json.JSONDecodeError:
                                    # If JSON parsing fails, treat as regular response
                                    print(f"LISA: {clean_followup_text}")
                                    if not is_status_report:
                                        robot_speak(clean_followup_text)
                                    messages.append({"role": "assistant", "content": followup_text})
                            else:
                                # Regular conversational response
                                print(f"LISA: {clean_followup_text}")
                                # Only speak if it's not a status report
                                if not is_status_report:
                                    robot_speak(clean_followup_text)
                                messages.append({"role": "assistant", "content": followup_text})
                except json.JSONDecodeError:
                    # Treat as plain text if parsing fails
                    print(f"LISA: {assistant_response}")
                    robot_speak(assistant_response)
            elif looks_like_step:
                try:
                    # Extract JSON from response (could be wrapped in markdown or mixed with text)
                    json_str = raw_text
                    
                    # Handle markdown fences
                    if "```" in json_str:
                        parts = json_str.split("```")
                        for i, part in enumerate(parts):
                            if part.strip().startswith("json"):
                                part = part.strip()[4:]  # Remove "json" prefix
                            if '{' in part and '"type"' in part:
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

                    print(f"DEBUG: Parsed STEP string: {json_str}")
                    
                    # Try to fix common JSON syntax errors
                    try:
                        step = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"DEBUG: JSON parse error: {e}")
                        # Try to fix common errors like missing quotes on keys
                        fixed_json = json_str
                        # Fix "params: {}" -> "params": {}
                        fixed_json = re.sub(r'"(\w+):\s*([{[])', r'"\1": \2', fixed_json)
                        print(f"DEBUG: Attempting to fix JSON: {fixed_json}")
                        try:
                            step = json.loads(fixed_json)
                            print("DEBUG: JSON repair successful")
                        except json.JSONDecodeError:
                            print("DEBUG: JSON repair failed, falling back to plain text")
                            raise  # Re-raise the original exception

                    # Append model output to history (only if not already added by safety handler)
                    if not any(msg.get("content") == assistant_response for msg in messages[-2:]):
                        messages.append({"role": "assistant", "content": assistant_response})

                    step_type = (step.get("type") or "").upper()
                    step_tool = step.get("tool")
                    step_params = step.get("params", {})
                    step_msg = step.get("message", "")

                    # Only print the internal message for debugging, don't speak it
                    if step_msg:
                        print(f"DEBUG: Internal step message: {step_msg}")

                    max_internal_steps = 8  # Increased for safety protocol workflow
                    steps_taken = 0
                    continue_loop = True
                    while continue_loop and steps_taken < max_internal_steps:
                        if step_type == "ACT" and step_tool:
                            if step_tool == 'analyze_image' or step_tool == 'analyze_current_image':
                                # Handle image analysis in ACT mode
                                if os.path.exists(LAST_IMAGE_PATH):
                                    # Use the LLM's requested prompt, or fall back to default
                                    last_user_text = get_last_user_text(messages)
                                    analysis_instruction = step_params.get('prompt', f"Answer my last request grounded strictly in this image. Question: '{last_user_text}'. If something is not visible or unclear, say so. Keep it concise.")
                                    messages.append({
                                        "role": "user",
                                        "content": f"{analysis_instruction}. Ground your answer strictly in what you can see in this image.",
                                        "images": [LAST_IMAGE_PATH]
                                    })
                                    response = chat_with_local_ollama(
                                        model=vision_model or chat_model,
                                        messages=messages,
                                        options={'temperature': 0.2}
                                    )
                                    analysis_text = response.message.content.strip()
                                    analysis_text = remove_markdown_code_blocks(analysis_text)
                                    analysis_text = remove_json_plan_blocks(analysis_text)
                                    print(f"LISA: {analysis_text}")
                                    robot_speak(analysis_text)
                                    
                                    # Add the analysis to message history
                                    messages.append({"role": "assistant", "content": analysis_text})
                                    
                                    # Check for safety violations and handle automatically
                                    violation_detected, is_stepwise, next_response = check_for_safety_violation_with_llm(
                                        analysis_text, messages, chat_model, logger
                                    )
                                    
                                    if violation_detected:
                                        steps_taken += 1
                                        if is_stepwise and next_response:
                                            # Parse the stepwise response and continue
                                            try:
                                                messages.append({"role": "assistant", "content": next_response})
                                                next_step = json.loads(next_response.strip('`').replace('json\n', '').strip())
                                                step_type = (next_step.get("type") or "").upper()
                                                step_tool = next_step.get("tool")
                                                step_params = next_step.get("params", {})
                                                step_msg = next_step.get("message", "")
                                                if step_msg:
                                                    print(f"DEBUG: Internal step message: {step_msg}")
                                            except json.JSONDecodeError:
                                                # Treat as plain text response
                                                print(f"LISA: {next_response}")
                                                robot_speak(next_response)
                                                continue_loop = False
                                        elif next_response:
                                            # Plain text response
                                            print(f"LISA: {next_response}")
                                            robot_speak(next_response)
                                            messages.append({"role": "assistant", "content": next_response})
                                        # Continue the loop to process the next step
                                    else:
                                        # No safety violation - end the stepwise process
                                        continue_loop = False
                                        break
                                else:
                                    print("LISA: I don't have a recent image to analyze.")
                                    continue_loop = False
                                    break
                            elif step_tool in ['talk', 'speak', 'announce']:
                                # Handle talk/speak/announce actions
                                message = step_params.get('message', '')
                                if message:
                                    print(f"LISA: {message}")
                                    robot_speak(message)
                                else:
                                    print("LISA: No message provided for talk action.")
                                
                                # End the loop after talk actions - let user respond
                                continue_loop = False
                                break
                            else:
                                print("Executing 1 action (stepwise)...")
                                result, image_taken = execute_compound_action([
                                    {"type": step_tool, "params": step_params}
                                ], chat_model, vision_model, messages, logger)

                                # Summarize observation
                                observation = f"Observation: {result}"
                                messages.append({"role": "user", "content": observation})
                                steps_taken += 1

                                # Simplified continuation logic - no automatic safety protocol continuation
                                messages.append({"role": "user", "content": "If the user's original request is now complete, respond with 'TALK' to end the task. Only continue with more actions if the user explicitly requested multiple steps."})
                                
                                followup_response = chat_with_local_ollama(
                                    model=chat_model,
                                    messages=messages,
                                    options={'temperature': 0.1}  # Lower temperature for more conservative behavior
                                )
                                next_text = followup_response.message.content.strip()
                                print(f"DEBUG: Raw LLM response: {next_text}")
                                messages.append({"role": "assistant", "content": next_text})

                                # Check if it's a stepwise JSON request (this will be handled by the main stepwise loop)
                                if ('"type"' in next_text) and ('"ACT"' in next_text or '"TALK"' in next_text) and ('{' in next_text):
                                    # Parse and continue with the stepwise processing
                                    try:
                                        next_step = json.loads(next_text.strip('`').replace('json\n', '').strip())
                                        step_type = (next_step.get("type") or "").upper()
                                        step_tool = next_step.get("tool")
                                        step_params = next_step.get("params", {})
                                        step_msg = next_step.get("message", "")
                                        if step_msg:
                                            print(f"DEBUG: Internal step message: {step_msg}")
                                        continue  # Continue the loop with the new step
                                    except json.JSONDecodeError:
                                        print("DEBUG: Failed to parse stepwise JSON, treating as plain text")
                                        print(f"LISA: {next_text}")
                                        robot_speak(next_text)
                                        continue_loop = False

                                # Parse next step decision
                                if next_text.startswith("```"):
                                    parts = next_text.split("```")
                                    if len(parts) >= 2:
                                        next_text = parts[1]
                                    if next_text.startswith("json"):
                                        next_text = next_text[4:]
                                next_text = next_text.strip()

                                # Detect step or treat as talk
                                if next_text.upper().strip() == "TALK":
                                    # LLM is signaling to end the task - don't output anything
                                    continue_loop = False
                                elif ('"type"' in next_text) and ('"ACT"' in next_text or '"TALK"' in next_text):
                                    try:
                                        next_step = json.loads(next_text)
                                    except json.JSONDecodeError as e:
                                        print(f"DEBUG: JSON parse error: {e}")
                                        # Try to fix common errors like missing quotes on keys
                                        fixed_json = next_text
                                        # Fix "params: {}" -> "params": {}
                                        import re
                                        fixed_json = re.sub(r'"(\w+):\s*([{[])', r'"\1": \2', fixed_json)
                                        print(f"DEBUG: Attempting to fix JSON: {fixed_json}")
                                        try:
                                            next_step = json.loads(fixed_json)
                                            print("DEBUG: JSON repair successful")
                                        except json.JSONDecodeError:
                                            print("DEBUG: JSON repair failed, falling back to plain text")
                                            raise  # Re-raise the original exception
                                    
                                    try:
                                        step_type = (next_step.get("type") or "").upper()
                                        step_tool = next_step.get("tool")
                                        step_params = next_step.get("params", {})
                                        step_msg = next_step.get("message", "")
                                        # Remove the conversion logic - let analyze_current_image be handled by the main stepwise loop
                                        if step_msg:
                                            print(f"DEBUG: Internal step message: {step_msg}")
                                        if step_type == "TALK":
                                            continue_loop = False
                                    except json.JSONDecodeError:
                                        # Not a valid step; treat as final talk
                                        print(f"LISA: {next_text}")
                                        robot_speak(next_text)
                                        continue_loop = False
                                else:
                                    # Plain conversational reply; end loop
                                    print(f"LISA: {next_text}")
                                    robot_speak(next_text)
                                    continue_loop = False
                        elif step_type == "TALK" and step_tool in ['talk', 'speak', 'announce']:
                            # Handle TALK actions
                            message = step_params.get('message', '')
                            if message:
                                print(f"LISA: {message}")
                                robot_speak(message)
                            else:
                                print("LISA: No message provided for talk action.")
                            
                            # End the loop after talk actions - let user respond
                            continue_loop = False
                            break
                        else:
                            # Invalid tool; end
                            continue_loop = False
                except json.JSONDecodeError:
                    if assistant_response is not None:
                        print(f"LISA: {assistant_response}")
                        robot_speak(assistant_response)
            else:
                # Plain conversational reply
                if assistant_response is not None:
                    print(f"LISA: {assistant_response}")
                    robot_speak(assistant_response)
            
            # Add response to message history (only if not already added)
            if assistant_response is not None:
                messages.append({"role": "assistant", "content": assistant_response})
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            print("LISA: I encountered an error. Please try again.")
            logger.log_error(str(e), "general")
        
        # End the current turn logging
        logger.end_turn()
            
    print("Session ended.")

if __name__ == "__main__":
    main() 