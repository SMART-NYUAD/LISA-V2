#!/usr/bin/env python3
import sys
import time
import datetime
import os
import threading
from ollama import chat, ChatResponse
from robot_functions import robot_speak, robot_listen, robot_take_pic, robot_hello

# Helper function to delay the start of the robot action
def start_action_with_delay(delay, action_func):
    print(f"(Action '{action_func.__name__}' scheduled to start after {delay}s)")
    time.sleep(delay)
    print(f"(Starting delayed action: '{action_func.__name__}')")
    action_func()

def main():
    """
    Main function to run the continuous chat with Ollama LLM.
    Uses the robot_speak and robot_listen functions from robot_functions.py.
    """
    MODEL = "gemma3:4b-it-qat"
    MAX_INTERACTIONS = 20

    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys_prompt_file_path = os.path.join(script_dir, "demo_sys_prompt.md")
    app_prompt_file_path = os.path.join(script_dir, "simple_app_prompt.md")

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

    # Read application prompt
    try:
        with open(app_prompt_file_path, 'r', encoding='utf-8') as f:
            application_prompt = f.read()
    except Exception as e:
        print(f"Error reading application prompt file: {e}")
        application_prompt = ""

    # Initialize message history
    global messages
    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # Welcome message
    print("\n=== LISA - AI Assistant Interface ===")
    print(f"Using Ollama model: {MODEL}")
    print("=======================================\n")

    welcome_message = "Hello! I'm your local intelligent safety assistant; or LISA for short. How can I help you today?"
    print(f"LISA: {welcome_message}")
    robot_speak(welcome_message)

    # Main loop
    while True:
        user_input = robot_listen()
        #user_input = "Do a safety analysis for me"
        #user_input = "Say hello" # Add this for testing hello
        
        # Check for the clear chat signal
        if user_input == "CLEAR_CHAT":
            print("--- Clearing Chat History ---")
            # Reset messages to just the system prompt
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            # Play a confirmation sound or message? (Optional)
            # robot_speak("Chat history cleared.") 
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

            # Check for tool use indication
            tool_call_prefix = "```tool_use:"
            tool_call_suffix = "```"
            
            tool_name = None
            follow_up_message = None

            # Find the tool tag anywhere in the response
            prefix_index = assistant_response.find(tool_call_prefix)

            if prefix_index != -1 and tool_call_suffix in assistant_response[prefix_index:]:
                try:
                    # Find suffix *after* the prefix
                    suffix_index = assistant_response.find(tool_call_suffix, prefix_index + len(tool_call_prefix))
                    
                    if suffix_index != -1:
                        # Extract tool name between prefix and suffix
                        tool_name = assistant_response[prefix_index + len(tool_call_prefix):suffix_index].strip()
                        # Capture any text *after* the suffix, stripping whitespace
                        follow_up_message = assistant_response[suffix_index + len(tool_call_suffix):].strip()
                        print(f"(Found tool tag '{tool_name}')")
                        # Text before the prefix is ignored implicitly by how we extract tool_name and follow_up
                    else: 
                        # If suffix isn't found after prefix, treat as normal message
                        print("(Tool prefix found, but suffix missing or misplaced. Treating as normal message.)")
                        pass 
                except Exception as e:
                    print(f"Error parsing tool call: {e}")
                    # Treat as normal message on error
                    tool_name = None
                    follow_up_message = None
            
            # Execute tool if name was extracted
            if tool_name == "robot_take_pic":
                print(f"LISA: Calling tool: {tool_name}")
                # 1. Take the picture (blocking)
                robot_take_pic()

                # 2. Define confirmation message
                tool_confirmation = "I've taken a picture. Let me analyze that for you. Just wait a sec."
                print(f"LISA: {tool_confirmation}")
                
                # 3. Start speaking the confirmation in a background thread
                print("(Starting confirmation speech in background...)")
                speak_thread = threading.Thread(target=robot_speak, args=(tool_confirmation,))
                speak_thread.start()

                # 4. Immediately proceed with preparing for image analysis
                image_path = "/home/unitree/LISA_v2_demo/tmp/frame.jpg"
                messages.append({
                    "role": "user",
                    "content": "here is the picture, do an analysis. no need to call any tool right now",
                    "images": [image_path]
                })
                
                # 5. Call LLM for analysis (this will now happen while confirmation speech is playing)
                try:
                    print("LISA is analyzing the image...")
                    start_time = time.time()  # Record start time
                    
                    response: ChatResponse = chat(
                        model=MODEL,
                        messages=messages,
                        options={'temperature':0.3}
                    )
                    end_time = time.time()  # Record end time
                    duration = end_time - start_time  # Calculate duration
                    print(f"LISA analyzed the image in {duration:.2f} seconds.")  # Print duration
                    
                    analysis_response = response.message.content # Use a different variable name
                    messages.append({"role": "assistant", "content": analysis_response})

                    #messages = [{"role": "system", "content": system_prompt}] #reset chat

                    # 6. Speak the final analysis (blocking, or could also be threaded if needed)
                    print(f"LISA: {analysis_response}")
                    robot_speak(analysis_response)

                except Exception as e:
                    error_message = f"Error analyzing the image: {str(e)}"
                    print(f"Error: {error_message}")
                    # Consider threading this error speech too if it's long
                    robot_speak(error_message)

            elif tool_name == "robot_hello":
                print(f"LISA: Handling tool: {tool_name}")
                # Use the follow-up message from the LLM for speaking
                message_to_speak = follow_up_message
                
                # Fallback if LLM didn't provide a follow-up message after the tag
                if not message_to_speak:
                    message_to_speak = "Hello there! LISA is here." # Default greeting
                    print(f"(LLM didn't provide follow-up message, using default: '{message_to_speak}')")
                
                # Define the delay before starting the robot action (e.g., 0.75 seconds)
                action_start_delay = 5

                # 1. Print and start Speak message in the main thread.
                print(f"LISA: {message_to_speak}") 
                # We assume robot_speak might block here.
                
                # 2. Start a separate thread that will wait, then call robot_hello.
                # This thread starts *immediately* but waits internally.
                timer_thread = threading.Thread(
                    target=start_action_with_delay, 
                    args=(action_start_delay, robot_hello)
                )
                timer_thread.start()

                # 3. Call robot_speak. If it blocks, timer_thread continues waiting/
                #    running in the background.
                robot_speak(message_to_speak) 
                
                # 4. Append the *spoken* message to history after speaking finishes.
                messages.append({"role": "assistant", "content": message_to_speak})
                
        

            # Handle cases where no tool was called, or an unknown tool was specified
            else:
                # Use the original assistant_response if no valid tool detected, 
                # or potentially use follow_up_message if an unknown tool was specified?
                # For now, just use the original response if tool_name is None.
                final_response = assistant_response
                if tool_name: # If a tool was detected but wasn't 'robot_take_pic' or 'robot_hello'
                     print(f"LISA: Received unknown tool call: {tool_name}")
                     # Decide whether to use the original full response or just the follow-up
                     final_response = follow_up_message if follow_up_message else f"I received an unknown tool command: {tool_name}" 
                
                # Append the final response to messages only if it's not empty
                if final_response:
                    messages.append({"role": "assistant", "content": final_response})
                    print(f"LISA: {final_response}")
                    robot_speak(final_response)
                elif not tool_name: # Handle case where original response was empty or only whitespace
                    print("LISA: Received empty response.")
                    # Optionally speak a generic message like "I didn't get that." or remain silent.

            # Trim chat history - Moved outside the specific tool logic
            if len(messages) > (MAX_INTERACTIONS * 2 + 1):
                messages = messages[-(MAX_INTERACTIONS * 2):] # Keep the most recent interactions + system prompt
                messages.insert(0, {"role": "system", "content": system_prompt})
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
        log_path = os.path.join(log_dir, f"chat_log_{timestamp}.json")

        # Dump messages
        try:
            import json
            with open(log_path, 'w', encoding='utf-8') as log_file:
                json.dump(messages, log_file, ensure_ascii=False, indent=2)
            print(f"\nChat log saved to {log_path}")
        except Exception as e:
            print(f"\nFailed to save chat log: {e}")
        
        print("Exiting gracefully.")
        sys.exit(0)