#!/usr/bin/env python3
import sys
import time
import datetime
import os
import threading
import json
from ollama import chat, ChatResponse
from robot_functions import robot_speak, robot_listen
from ros_functions import navigate_to

# Helper function to delay the start of the robot action
def start_action_with_delay(delay, action_func):
    print(f"(Action '{action_func.__name__}' scheduled to start after {delay}s)")
    time.sleep(delay)
    print(f"(Starting delayed action: '{action_func.__name__}')")
    action_func()

def main():
    """
    Main function to run the continuous chat with Ollama LLM for navigation.
    Uses the robot_speak and robot_listen functions, plus navigation functions.
    """
    MODEL = "gemma3:12b-it-qat"
    MAX_INTERACTIONS = 20

    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys_prompt_file_path = os.path.join(script_dir, "demo_sys_prompt.md")
    nav_prompt_file_path = os.path.join(script_dir, "nav_app_prompt.md")

    # Read system prompt
    try:
        with open(sys_prompt_file_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        print(f"Error: System prompt file not found at {sys_prompt_file_path}")
        system_prompt = "You are a helpful assistant."
    except Exception as e:
        print(f"Error reading system prompt file: {e}")
        system_prompt = "You are a helpful assistant."

    # Read navigation application prompt
    try:
        with open(nav_prompt_file_path, 'r', encoding='utf-8') as f:
            application_prompt = f.read()
    except FileNotFoundError:
        print(f"Error: Navigation prompt file not found at {nav_prompt_file_path}")
        print("Please create the nav_app_prompt.md file with navigation instructions.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading application prompt file: {e}")
        sys.exit(1)

    # Initialize message history
    global messages
    messages = [
        {"role": "system", "content": application_prompt}
    ]

    # Welcome message
    print("\n=== LISA Navigation Assistant ===")
    print(f"Using Ollama model: {MODEL}")
    print("Available locations: station, workbench, dispenser")
    print("=======================================\n")

    welcome_message = "Hello! I'm LISA, your navigation assistant. I can help you navigate to the station, workbench, or dispenser. Where would you like to go?"
    print(f"LISA: {welcome_message}")
    #robot_speak(welcome_message)

    # Main loop
    while True:
        user_input = robot_listen()
        
        # Check for the clear chat signal
        if user_input == "CLEAR_CHAT":
            print("--- Clearing Chat History ---")
            # Reset messages to just the system prompt
            messages = [
                {"role": "system", "content": application_prompt}
            ]
            continue # Skip the rest of the loop and wait for new input
        
        # Handle case where listening failed or was cancelled
        if user_input is None:
            print("Listening cancelled or failed, waiting for next input.")
            continue # Skip the rest of the loop
            
        print(f"You: {user_input}")
        messages.append({"role": "user", "content": user_input})

        try:
            print("LISA is thinking...")
            start_time = time.time()  # Record start time
            response: ChatResponse = chat(
                model=MODEL,
                messages=messages, 
                options={'temperature':0.3}
            )
            end_time = time.time()  # Record end time
            duration = end_time - start_time  # Calculate duration
            print(f"LISA thought for {duration:.2f} seconds.")  # Print duration

            assistant_response = response.message.content

            # Try to parse the response as JSON for structured output
            try:
                # Clean the response - remove markdown code blocks if present
                cleaned_response = assistant_response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
                
                # Try to extract JSON from the cleaned response
                response_json = json.loads(cleaned_response)
                
                # Handle navigation action
                if response_json.get("action") == "navigate_to":
                    location = response_json.get("location")
                    message = response_json.get("message", f"Navigating to {location}...")
                    
                    print(f"LISA: {message}")
                    robot_speak(message)
                    
                    # Navigate to the specified location
                    try:
                        navigate_to(location)
                        success_message = f"Successfully sent navigation command to {location}."
                        print(f"LISA: {success_message}")
                        robot_speak(success_message)
                        
                        # Add only the original message to message history, not the success message
                        messages.append({"role": "assistant", "content": message})
                        
                    except ValueError as e:
                        error_message = f"Navigation error: {str(e)}"
                        print(f"Error: {error_message}")
                        robot_speak(error_message)
                        messages.append({"role": "assistant", "content": error_message})
                
                # Handle non-navigation responses
                elif response_json.get("action") == "none":
                    message = response_json.get("message", "I understand.")
                    print(f"LISA: {message}")
                    robot_speak(message)
                    messages.append({"role": "assistant", "content": message})
                
                # Handle unknown actions
                else:
                    print(f"LISA: Received unknown action: {response_json.get('action', 'none')}")
                    message = response_json.get("message", "I'm not sure how to handle that request.")
                    robot_speak(message)
                    messages.append({"role": "assistant", "content": message})
                    
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as a regular message
                print(f"LISA: {assistant_response}")
                robot_speak(assistant_response)
                messages.append({"role": "assistant", "content": assistant_response})

            # Trim chat history
            if len(messages) > (MAX_INTERACTIONS * 2 + 1):
                messages = messages[-(MAX_INTERACTIONS * 2):] # Keep the most recent interactions + system prompt
                messages.insert(0, {"role": "system", "content": application_prompt})
                print(f"Trimmed chat history to last {MAX_INTERACTIONS} interactions.")

        except Exception as e:
            error_message = f"Sorry, I encountered an error: {str(e)}"
            print(f"Error: {error_message}")
            robot_speak(error_message)

            if "connection" in str(e).lower():
                robot_speak("I'm having trouble connecting to the language model. Please check if Ollama is running.")
                retry = input("Would you like to retry? (y/n): ")
                if retry.lower() != 'y':
                    break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_logs")
        os.makedirs(log_dir, exist_ok=True)

        # Timestamped log file
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(log_dir, f"nav_chat_log_{timestamp}.json")

        # Dump messages
        try:
            import json
            with open(log_path, 'w', encoding='utf-8') as log_file:
                json.dump(messages, log_file, ensure_ascii=False, indent=2)
            print(f"\nNavigation chat log saved to {log_path}")
        except Exception as e:
            print(f"\nFailed to save chat log: {e}")
        
        print("Exiting gracefully.")
        sys.exit(0) 