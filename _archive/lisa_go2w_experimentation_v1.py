#!/usr/bin/env python3
import sys
import time
import datetime
import os
import threading
import json
import re
from ollama import chat, ChatResponse
from robot_functions import robot_speak, robot_take_pic, robot_hello, initialize_sdk
from ros_functions import (
    navigate_to, 
    start_status_listener, 
    wait_for_goal_completion,
    navigate_to_with_feedback
)

# Enhanced system prompt for experimental scenarios
EXPERIMENTATION_SYSTEM_PROMPT = """You are LISA, an AI assistant integrated with a robot that can navigate to locations, take pictures, and make decisions based on what it sees.

## Your Capabilities:
1. **Navigation**: Move to predefined locations (station, workbench, dispenser)
2. **Photography**: Take pictures using the robot's camera
3. **Image Analysis**: Analyze pictures and describe what you see
4. **Timing Control**: Wait for specified durations between actions
5. **Decision Making**: Make decisions based on image analysis results
6. **Conditional Actions**: Execute different actions based on what you observe

## Available Actions:
- `navigate_to`: Navigate to a location
  - Parameters: `location` (must be one of: 'station', 'workbench', 'dispenser')
- `take_picture`: Take a picture with the robot's camera
  - Parameters: none
- `analyze_image`: Analyze the last taken picture and describe it
  - Parameters: none
- `wait`: Wait for a specified number of seconds
  - Parameters: `seconds` (number)
- `conditional_action`: Execute actions based on analysis results
  - Parameters: `condition` (string describing what to look for), `if_true` (actions if condition met), `if_false` (actions if condition not met)

## Experimental Scenarios:
1. **Work Area Inspection**: "inspect work area" → navigate to workbench, take picture, analyze, return to station and report
2. **PPE Check**: "check my gear" → take picture, analyze for PPE, give safety advice
3. **Equipment Delivery**: "check equipment" → navigate to dispenser, check for missing items, navigate to worker if needed
4. **Safety Patrol**: "patrol area" → visit all locations, take pictures, report findings

## Response Format:
You MUST respond with valid JSON (no markdown formatting) in this structure:
{
  "actions": [
    {"type": "action_name", "params": {param_dict}}
  ],
  "message": "Your friendly response to the user",
  "scenario": "scenario_name" (optional, for tracking experiment type)
}

## Decision Making:
When analyzing images, look for:
- PPE items: helmet, safety vest, gloves, safety glasses
- Safety hazards: spills, obstacles, unsafe conditions
- Missing equipment: tools, materials, safety gear
- Worker presence: people in the area

## Examples:

User: "inspect work area"
Response:
{
  "actions": [
    {"type": "navigate_to", "params": {"location": "workbench"}},
    {"type": "take_picture", "params": {}},
    {"type": "analyze_image", "params": {}},
    {"type": "navigate_to", "params": {"location": "station"}}
  ],
  "message": "I'll inspect the work area by going to the workbench, taking a picture, analyzing it, and returning to report my findings.",
  "scenario": "work_area_inspection"
}

User: "check my gear"
Response:
{
  "actions": [
    {"type": "take_picture", "params": {}},
    {"type": "analyze_image", "params": {}}
  ],
  "message": "I'll take a picture and check if you're wearing the proper safety gear.",
  "scenario": "ppe_check"
}

User: "check equipment"
Response:
{
  "actions": [
    {"type": "navigate_to", "params": {"location": "dispenser"}},
    {"type": "take_picture", "params": {}},
    {"type": "analyze_image", "params": {}}
  ],
  "message": "I'll check the equipment at the dispenser and see if anything is missing.",
  "scenario": "equipment_check"
}

## Important Notes:
- NEVER use markdown code blocks in your JSON response
- Always validate location names (only 'station', 'workbench', 'dispenser' are valid)
- Include friendly, conversational messages
- For safety scenarios, be thorough in your analysis
- If a command is unclear, ask for clarification instead of guessing
"""

def execute_enhanced_action(actions, model="gemma3:4b-it-qat", scenario=None):
    """
    Execute a sequence of actions with enhanced decision-making capabilities.
    
    Args:
        actions: List of action dictionaries with 'type' and 'params'
        model: The Ollama model to use for image analysis
        scenario: Optional scenario name for tracking
    
    Returns:
        dict: Results including messages, analysis results, and decisions made
    """
    # Initialize status listener if not already started
    try:
        start_status_listener()
    except:
        pass  # Already started
    
    results = {
        'messages': [],
        'analysis_results': [],
        'decisions': [],
        'scenario': scenario,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    image_taken = False
    last_analysis = None
    
    for i, action in enumerate(actions):
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
                        results['messages'].append(success_msg)
                    elif result == "CANCELED":
                        error_msg = f"Navigation to {location} was canceled"
                        print(error_msg)
                        robot_speak(error_msg)
                        results['messages'].append(error_msg)
                    elif result == "ABORTED":
                        error_msg = f"Navigation to {location} failed"
                        print(error_msg)
                        robot_speak(error_msg)
                        results['messages'].append(error_msg)
                    else:
                        error_msg = f"Navigation to {location} timed out"
                        print(error_msg)
                        robot_speak(error_msg)
                        results['messages'].append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Navigation to {location} failed: {str(e)}"
                    print(error_msg)
                    robot_speak(error_msg)
                    results['messages'].append(error_msg)
                    
        elif action_type == 'take_picture':
            try:
                print("Taking a picture...")
                robot_speak("Taking a picture")
                success = robot_take_pic()
                if success:
                    success_msg = "Picture taken successfully"
                    print(success_msg)
                    robot_speak(success_msg)
                    results['messages'].append(success_msg)
                    image_taken = True
                else:
                    error_msg = "Failed to take picture"
                    print(error_msg)
                    robot_speak(error_msg)
                    results['messages'].append(error_msg)
            except Exception as e:
                error_msg = f"Picture taking failed: {str(e)}"
                print(error_msg)
                robot_speak(error_msg)
                results['messages'].append(error_msg)
                
        elif action_type == 'wait':
            wait_time = params.get('seconds', 1)
            print(f"Waiting for {wait_time} seconds...")
            robot_speak(f"Waiting {wait_time} seconds")
            time.sleep(wait_time)
    
    # If an image was taken and analysis is requested, perform it
    if image_taken and any(action.get('type') == 'analyze_image' for action in actions):
        try:
            print("Analyzing the image...")
            robot_speak("Analyzing the image")
            image_path = "/home/unitree/LISA_v3_nav/tmp/frame.jpg"
            
            # Enhanced analysis prompt for experimental scenarios
            analysis_prompt = """Analyze this image and provide a detailed description. Focus on:

1. **Safety Assessment**: Look for PPE (helmet, vest, gloves, safety glasses), safety hazards, or unsafe conditions
2. **Equipment Status**: Check for missing tools, materials, or safety equipment
3. **Worker Status**: Note if people are present and their safety compliance
4. **Environmental Conditions**: Identify any spills, obstacles, or environmental hazards

Provide a structured response with:
- Overall safety assessment
- Specific items or conditions observed
- Recommendations if safety issues are found
- Compliments if proper safety practices are observed

Be thorough but concise, and include a touch of humor if appropriate."""
            
            # Prepare messages for image analysis
            analysis_messages = [
                {"role": "system", "content": "You are LISA, a safety-focused assistant that analyzes images for safety compliance and provides helpful advice."},
                {
                    "role": "user",
                    "content": analysis_prompt,
                    "images": [image_path]
                }
            ]
            
            # Call LLM for analysis
            response = chat(
                model=model,
                messages=analysis_messages,
                options={'temperature': 0.3}
            )
            
            analysis_result = response.message.content
            results['analysis_results'].append(analysis_result)
            last_analysis = analysis_result
            
            # Speak the analysis result
            print(f"LISA: {analysis_result}")
            robot_speak(analysis_result)
            
            # Make decisions based on analysis for experimental scenarios
            if scenario:
                decision = make_decision_based_on_analysis(analysis_result, scenario)
                if decision:
                    results['decisions'].append(decision)
                    execute_decision(decision, model)
            
        except Exception as e:
            error_msg = f"Image analysis failed: {str(e)}"
            print(error_msg)
            results['messages'].append(error_msg)
    
    return results

def make_decision_based_on_analysis(analysis_result, scenario):
    """
    Make decisions based on image analysis results for different scenarios.
    
    Args:
        analysis_result: The analysis text from the LLM
        scenario: The scenario being executed
    
    Returns:
        dict: Decision to execute, or None if no decision needed
    """
    analysis_lower = analysis_result.lower()
    
    if scenario == "work_area_inspection":
        # Check for safety issues that require immediate attention
        if any(keyword in analysis_lower for keyword in ['hazard', 'unsafe', 'missing ppe', 'spill', 'obstacle']):
            return {
                'type': 'safety_alert',
                'message': 'Safety issues detected during inspection. Immediate attention required.',
                'actions': [
                    {'type': 'navigate_to', 'params': {'location': 'station'}},
                    {'type': 'wait', 'params': {'seconds': 2}}
                ]
            }
        else:
            return {
                'type': 'all_clear',
                'message': 'Work area inspection complete. No immediate safety concerns detected.',
                'actions': [
                    {'type': 'navigate_to', 'params': {'location': 'station'}},
                    {'type': 'wait', 'params': {'seconds': 2}}
                ]
            }
    
    elif scenario == "equipment_check":
        # Check for missing equipment
        if any(keyword in analysis_lower for keyword in ['missing', 'not present', 'empty', 'no equipment']):
            return {
                'type': 'equipment_missing',
                'message': 'Missing equipment detected. Delivering to worker location.',
                'actions': [
                    {'type': 'navigate_to', 'params': {'location': 'workbench'}},
                    {'type': 'wait', 'params': {'seconds': 3}},
                    {'type': 'navigate_to', 'params': {'location': 'station'}}
                ]
            }
        else:
            return {
                'type': 'equipment_available',
                'message': 'Equipment check complete. All items appear to be available.',
                'actions': [
                    {'type': 'navigate_to', 'params': {'location': 'station'}},
                    {'type': 'wait', 'params': {'seconds': 2}}
                ]
            }
    
    elif scenario == "ppe_check":
        # Check for PPE compliance
        if any(keyword in analysis_lower for keyword in ['missing', 'not wearing', 'no helmet', 'no vest']):
            return {
                'type': 'ppe_violation',
                'message': 'PPE compliance issue detected. Please ensure proper safety gear is worn.',
                'actions': []
            }
        else:
            return {
                'type': 'ppe_compliant',
                'message': 'PPE check complete. Proper safety gear is being worn.',
                'actions': []
            }
    
    return None

def execute_decision(decision, model):
    """
    Execute a decision made based on analysis results.
    
    Args:
        decision: The decision dictionary with actions to execute
        model: The Ollama model to use
    """
    print(f"Executing decision: {decision['type']}")
    robot_speak(decision['message'])
    
    if 'actions' in decision and decision['actions']:
        print("Executing decision actions...")
        execute_enhanced_action(decision['actions'], model)

def generate_experiment_report(results):
    """
    Generate a structured report for experimental scenarios.
    
    Args:
        results: The results dictionary from execute_enhanced_action
    
    Returns:
        str: Formatted report
    """
    report = f"""
=== LISA Experiment Report ===
Scenario: {results.get('scenario', 'Unknown')}
Timestamp: {results.get('timestamp', 'Unknown')}

Messages:
{chr(10).join(f"- {msg}" for msg in results.get('messages', []))}

Analysis Results:
{chr(10).join(f"- {analysis}" for analysis in results.get('analysis_results', []))}

Decisions Made:
{chr(10).join(f"- {decision['type']}: {decision['message']}" for decision in results.get('decisions', []))}

=== End Report ===
"""
    return report

def main():
    """
    Main function to run the enhanced experimentation assistant.
    """
    MODEL = "gemma3:4b-it-qat"
    
    # Initialize SDK
    initialize_sdk()
    
    # Welcome message
    print("\n=== LISA Enhanced Experimentation Assistant ===")
    print(f"Using Ollama model: {MODEL}")
    print("Available experimental scenarios:")
    print("1. 'inspect work area' - Work area safety inspection")
    print("2. 'check my gear' - PPE compliance check")
    print("3. 'check equipment' - Equipment availability check")
    print("4. 'patrol area' - Multi-location safety patrol")
    print("5. Custom compound commands (e.g., 'go to workbench and take picture')")
    print("===============================================\n")
    
    welcome_message = "Hello! I'm LISA, your enhanced experimentation assistant. I can perform safety inspections, check equipment, and make decisions based on what I see. What would you like me to do?"
    print(f"LISA: {welcome_message}")
    robot_speak(welcome_message)
    
    # Main interaction loop
    while True:
        try:
            # Get user input
            user_input = input("You: ")
            
            if user_input is None:
                print("Listening cancelled or failed, waiting for next input.")
                continue
            
            print(f"You: {user_input}")
            
            # Check for exit command
            if user_input.lower() in ['exit', 'quit', 'stop', 'goodbye']:
                robot_speak("Goodbye! Thank you for using LISA.")
                break
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": EXPERIMENTATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ]
            
            # Get response from LLM
            print("LISA is thinking...")
            start_time = time.time()
            
            response: ChatResponse = chat(
                model=MODEL,
                messages=messages,
                options={'temperature': 0.3}
            )
            
            end_time = time.time()
            print(f"LISA thought for {end_time - start_time:.2f} seconds.")
            
            assistant_response = response.message.content
            print(f"LISA: {assistant_response}")
            
            # Parse JSON response
            try:
                # Extract JSON from response (handle potential markdown formatting)
                json_match = re.search(r'\{.*\}', assistant_response, re.DOTALL)
                if json_match:
                    response_data = json.loads(json_match.group())
                else:
                    # If no JSON found, treat as simple response
                                    robot_speak("I'm sorry, I had trouble understanding that command. Could you please try again?")
                continue
                
                actions = response_data.get('actions', [])
                message = response_data.get('message', '')
                scenario = response_data.get('scenario', None)
                
                # Speak the response message
                if message:
                    print(f"LISA: {message}")
                    robot_speak(message)
                
                # Execute actions if any
                if actions:
                    print(f"Executing {len(actions)} actions...")
                    results = execute_enhanced_action(actions, MODEL, scenario)
                    
                    # Generate and save report
                    report = generate_experiment_report(results)
                    print(report)
                    
                    # Save report to file
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    report_filename = f"experiment_report_{timestamp}.txt"
                    report_path = os.path.join("/home/unitree/LISA_v3_nav/tmp", report_filename)
                    
                    os.makedirs("/home/unitree/LISA_v3_nav/tmp", exist_ok=True)
                    with open(report_path, 'w') as f:
                        f.write(report)
                    
                    print(f"Experiment report saved to: {report_path}")
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Raw response: {assistant_response}")
                robot_speak("I'm sorry, I had trouble understanding that command. Could you please try again?")
            
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            robot_speak("Goodbye!")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            robot_speak("I encountered an error. Please try again.")

if __name__ == "__main__":
    main() 