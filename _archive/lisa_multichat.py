#!/usr/bin/env python3
import sys
import time
import datetime
import os
from ollama import chat, ChatResponse
from robot_functions import robot_speak, robot_listen, robot_take_pic



def main():
    """
    Main function to run the continuous chat with Ollama LLM.
    Uses the robot_speak and robot_listen functions from robot_functions.py.
    """
    MODEL_sys = "gemma3:4b"
    MODEL_app = "gemma3:12b"
    MAX_INTERACTIONS = 20

    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys_prompt_file_path = os.path.join(script_dir, "system_prompt.md")
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
    print(f"Using Ollama model: {MODEL_sys}")
    print("=======================================\n")

    welcome_message = "Hello! I'm your local intelligent safety assistant; or LISA for short. How can I help you today?"
    print(f"LISA: {welcome_message}")
    #robot_speak(welcome_message)

    # Main loop
    while True:
        user_input = robot_listen()
        #user_input = "Do a safety analysis"

        print(f"You: {user_input}")
        messages.append({"role": "user", "content": user_input})

        try:
            print("LISA is thinking...")
            response: ChatResponse = chat(
                model=MODEL_sys,
                messages=messages
            )
            assistant_response = response.message.content

            if "```tool_use```" in assistant_response:
                print("LISA: Calling tool: robot_take_pic")
                robot_take_pic()

                tool_confirmation = "Okay, I've taken a picture. Let me do a safety analysis for you."
                print(f"LISA: {tool_confirmation}")
                robot_speak(tool_confirmation)


                try:
                    # Open a new chat and analyze the image
                    print("LISA is analyzing the image...")
                    image_path = "/home/unitree/LISA_v2_demo/tmp/frame.jpg"#input("Enter image path: ")
                    response = chat(
                        model=MODEL_app,
                        messages=[
                            {
                                'role': 'user',
                                'content': application_prompt,
                                'images': [image_path],
                            }
                        ],
                        options={'temperature':0},
                    )

                    print(f"LISA: {response.message.content}")
                    robot_speak(response.message.content)
                    messages.append({"role": "assistant", "content": response.message.content})

                except Exception as e:
                    error_message = f"Error analyzing the image: {str(e)}"
                    print(f"Error: {error_message}")
                    robot_speak(error_message)

            else:
                messages.append({"role": "assistant", "content": assistant_response})
                print(f"LISA: {assistant_response}")
                robot_speak(assistant_response)

            # Trim chat history
            if len(messages) > (MAX_INTERACTIONS * 2 + 1):
                messages = [{"role": "system", "content": system_prompt}]
                print(f"Trimmed chat history to {MAX_INTERACTIONS} interactions")

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
