import evdev
from select import select

def detect_clickers():
    """
    Scan for input devices and return a list of devices that match the two clicker names.
    """
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    selected_devices = []
    for device in devices:
        #print(f"Device: {device.name}, Path: {device.path}")
        # Match the two specific device names.
        if device.name in [
            "Wireless Present Wireless Present Keyboard",
            "KNORVAY Knorvay Wireless Presenter Keyboard"
        ]:
            selected_devices.append(device)
    return selected_devices

def listen_for_clickers(devices):
    """
    Listen for key events from a list of devices concurrently using select.
    """
    print("Listening for events from the following devices:")
    for device in devices:
        print(f" - {device.name}")
        
    while True:
        # Use select to wait until one (or more) devices are ready for reading.
        r, _, _ = select(devices, [], [])
        for device in r:
            # Read all available events from the ready device.
            for event in device.read():
                if event.type == evdev.ecodes.EV_KEY:
                    key_event = evdev.categorize(event)
                    # We check for key-down events.
                    if key_event.keystate == evdev.KeyEvent.key_down:
                        print(f"Detected key press from {device.name}: {key_event.keycode}")

if __name__ == "__main__":
    clicker_devices = detect_clickers()
    if clicker_devices:
        listen_for_clickers(clicker_devices)
    else:
        print("No matching clicker devices found.")

