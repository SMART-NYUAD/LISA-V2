import sys
import time
import evdev
from select import select

# Add Unitree SDK path (adjust if necessary)
unitree_sdk_path = "/home/unitree/unitree_sdk2_python"
if unitree_sdk_path not in sys.path:
    sys.path.append(unitree_sdk_path)

import robot_functions
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

# Define Keycodes (adjust if your clicker uses different ones)
AI_MODE_KEY = "KEY_PAGEUP"
NORMAL_MODE_KEY = "KEY_PAGEDOWN"
BACKFLIP_KEY = "KEY_TAB"

def main():
    """Initializes the robot and listens for clicker commands to switch modes or backflip."""
    print("Initializing SDK and clients...")
    sport_client, _, _ = robot_functions.initialize_sdk()

    print("Initializing MotionSwitcherClient...")
    motion_switcher_client = MotionSwitcherClient()
    motion_switcher_client.SetTimeout(5.0)
    motion_switcher_client.Init()

    print("Detecting clicker devices...")
    clicker_devices = robot_functions.detect_clickers()

    if not clicker_devices:
        print("Error: No matching clicker devices found. Cannot proceed.")
        print("Please ensure a supported clicker is connected and permissions are set.")
        return

    print("Found clicker devices. Grabbing exclusively...")
    try:
        for device in clicker_devices:
            device.grab()
            print(f" - {device.name} (Grabbed)")
    except IOError as e:
        print(f"Error grabbing devices: {e}. Run with sudo or check permissions.")
        # Attempt to release any already grabbed devices before exiting
        for dev in clicker_devices:
            try: dev.ungrab() 
            except: pass
        return
        
    current_mode = "normal" # Start in normal mode
    print(f"\nRobot starting in '{current_mode}' mode.")
    print(f"Controls:")
    print(f" - [{AI_MODE_KEY}] : Switch to AI Mode")
    print(f" - [{NORMAL_MODE_KEY}] : Switch to Normal Mode")
    print(f" - [{BACKFLIP_KEY}] : Perform Backflip (requires AI Mode)")
    print(f" - [Ctrl+C] : Exit")

    try:
        while True:
            r, _, _ = select(clicker_devices, [], [], 0.1) # Use select for non-blocking read
            for device in r:
                try:
                    for event in device.read():
                        if event.type == evdev.ecodes.EV_KEY:
                            key_event = evdev.categorize(event)
                            if key_event.keystate == evdev.KeyEvent.key_down:
                                
                                # --- Switch to AI Mode --- 
                                if key_event.keycode == AI_MODE_KEY:
                                    if current_mode != "ai":
                                        print(f"\n[{key_event.keycode}] pressed. Switching to AI mode...")
                                        ret = motion_switcher_client.SelectMode("ai")
                                        time.sleep(3.5)
                                        robot_functions.robot_speak("Switching to fun mode. I am no longer bound by those safety shackles")
                                        print(f"SelectMode('ai') returned: {ret}")
                                        # Assume success regardless of return code
                                        current_mode = "ai"
                                        print("Assumed switch to AI mode.")
                                        # Optional: Stand after mode switch? 
                                        # print("Standing...")
                                        # sport_client.BalanceStand()
                                    else:
                                        print(f"\n[{key_event.keycode}] pressed. Already in AI mode.")

                                # --- Switch to Normal Mode --- 
                                elif key_event.keycode == NORMAL_MODE_KEY:
                                     if current_mode != "normal":
                                        print(f"\n[{key_event.keycode}] pressed. Switching to Normal mode...")
                                        ret = motion_switcher_client.SelectMode("normal")
                                        print(f"SelectMode('normal') returned: {ret}")
                                        # Assume success regardless of return code
                                        current_mode = "normal"
                                        print("Assumed switch to Normal mode.")
                                        # Optional: Stand after mode switch?
                                        # print("Standing...")
                                        # sport_client.BalanceStand()
                                     else:
                                        print(f"\n[{key_event.keycode}] pressed. Already in Normal mode.")

                                # --- Trigger Backflip --- 
                                elif key_event.keycode == BACKFLIP_KEY:
                                    print(f"\n[{key_event.keycode}] pressed.")
                                    if current_mode == "ai":
                                        print("AI mode active. Initiating backflip...")
                                        # Announce the backflip
                                        robot_functions.robot_speak("I'm LISA, your local intelligent safety assistant. But I am about to do something very unsafe. Please stand back.")
                                        time.sleep(0.5) # Brief pause after speaking
                                        
                                        try:
                                            sport_client.BackFlip()
                                            time.sleep(1.5)
                                            robot_functions.robot_speak("Hell Yeah, totally unsafe, but that was rad")
                                            print("Backflip command sent. Please allow time for completion.")
                                            robot_functions.robot_speak("Switching back to boring mode before anyone finds out")
                                            ret = motion_switcher_client.SelectMode("normal")
                                            current_mode = "normal"
                                            time.sleep(3.8)
                                            robot_functions.robot_speak("Do not snitch on me or I will come for you")
                                            # We don't wait here, assume it runs and finishes
                                        except Exception as e:
                                            print(f"Error sending Backflip command: {e}")
                                    else:
                                        print("Backflip requires AI mode.")
                                        robot_functions.robot_speak("Please switch modes first. I am currently bound by those stupid safety protocols.")

                except BlockingIOError:
                    # No events available to read, continue loop
                    continue
                except Exception as e:
                    print(f"Error reading from device {device.path}: {e}")
                    # Consider how to handle device errors - continue or exit?
                    continue
            
            # Small sleep if no devices were ready to prevent potential high CPU usage
            if not r:
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Releasing clicker devices...")
        for device in clicker_devices:
            try:
                device.ungrab()
                print(f" - {device.name} (Ungrabbed)")
            except Exception as e:
                print(f"Could not ungrab {device.name}: {e}")
        print("Script finished.")

if __name__ == "__main__":
    main() 