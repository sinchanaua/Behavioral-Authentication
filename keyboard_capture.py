from pynput import keyboard
import pandas as pd
from datetime import datetime

# List to store key events
data = []

# When a key is pressed
def on_press(key):
    try:
        key_name = key.char
    except AttributeError:
        key_name = str(key)

    data.append({
        "Key": key_name,
        "Event": "Pressed",
        "Time": datetime.now()
    })

# When a key is released
def on_release(key):
    try:
        key_name = key.char
    except AttributeError:
        key_name = str(key)

    data.append({
        "Key": key_name,
        "Event": "Released",
        "Time": datetime.now()
    })

    # Stop recording when ESC is pressed
    if key == keyboard.Key.esc:
        df = pd.DataFrame(data)
        df.to_csv("data/keyboard_data.csv", index=False)
        print("\nData Saved Successfully!")
        return False

print("Keyboard recording started...")
print("Press ESC to stop and save.\n")

with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
    listener.join()