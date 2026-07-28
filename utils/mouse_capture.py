"""
utils/mouse_capture.py
----------------------
Captures mouse / touchpad behavioral data including:
- Movement (x, y coordinates + timestamp)
- Mouse speed (pixels per second)
- Click events (left/right, pressed/released)
- Scroll events (direction + amount)
- Idle time (when mouse stops moving)

All data is saved to data/mouse_data.csv
Run this file directly to start capturing. Press Ctrl+C to stop.
"""

import csv
import os
import time
import math
from datetime import datetime
from pynput import mouse

# -------------------------------------------------------
# Configuration
# -------------------------------------------------------
OUTPUT_FILE = "data/mouse_data.csv"          # Where to save data
IDLE_THRESHOLD = 1.5                          # Seconds before marking as idle
MOVEMENT_SAMPLE_RATE = 0.05                   # Save movement every 50ms (avoids huge files)

# -------------------------------------------------------
# Global State Variables
# -------------------------------------------------------
last_x = None                  # Last known x position
last_y = None                  # Last known y position
last_move_time = None          # Time of last movement
last_sample_time = 0           # For controlling sample rate
is_idle = False                # Whether mouse is currently idle
idle_start_time = None         # When idle period started
csv_writer = None              # CSV writer object
csv_file = None                # File handle


# -------------------------------------------------------
# CSV Setup
# -------------------------------------------------------
def setup_csv(filepath):
    """
    Creates the CSV file with headers if it doesn't exist.
    Returns the file handle and writer object.
    """
    global csv_writer, csv_file

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    file_exists = os.path.exists(filepath)
    csv_file = open(filepath, mode='a', newline='')
    csv_writer = csv.writer(csv_file)

    # Write header only if file is new
    if not file_exists:
        csv_writer.writerow([
            'event_type',   # movement / click / scroll / idle
            'x',            # x coordinate
            'y',            # y coordinate
            'button',       # left / right / none
            'action',       # pressed / released / moved / scrolled / idle_start / idle_end
            'scroll_dx',    # horizontal scroll amount
            'scroll_dy',    # vertical scroll amount
            'speed_px_s',   # mouse speed in pixels per second
            'idle_time_s',  # how long mouse was idle (seconds)
            'timestamp'     # exact time of event
        ])
        print(f"[INFO] Created new CSV file: {filepath}")
    else:
        print(f"[INFO] Appending to existing CSV file: {filepath}")

    return csv_file, csv_writer


def write_row(event_type, x=0, y=0, button='none', action='none',
              scroll_dx=0, scroll_dy=0, speed=0.0, idle_time=0.0):
    """
    Writes a single event row to the CSV file.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    csv_writer.writerow([
        event_type,
        round(x, 2),
        round(y, 2),
        button,
        action,
        scroll_dx,
        scroll_dy,
        round(speed, 4),
        round(idle_time, 4),
        timestamp
    ])
    csv_file.flush()  # Write immediately to disk


# -------------------------------------------------------
# Speed Calculator
# -------------------------------------------------------
def calculate_speed(x1, y1, x2, y2, time1, time2):
    """
    Calculates mouse speed in pixels per second.
    Speed = Distance / Time
    Distance = sqrt((x2-x1)^2 + (y2-y1)^2)  [Euclidean distance]
    """
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    time_diff = time2 - time1

    if time_diff <= 0:
        return 0.0

    return distance / time_diff


# -------------------------------------------------------
# Event Handlers
# -------------------------------------------------------
def on_move(x, y):
    """
    Called every time the mouse/touchpad moves.
    Calculates speed and checks for idle recovery.
    """
    global last_x, last_y, last_move_time, last_sample_time, is_idle, idle_start_time

    current_time = time.time()

    # --- Check if mouse was idle and just moved again ---
    if is_idle:
        idle_duration = current_time - idle_start_time
        write_row(
            event_type='idle',
            x=x, y=y,
            action='idle_end',
            idle_time=round(idle_duration, 4)
        )
        print(f"[IDLE END] Idle for {round(idle_duration, 2)}s")
        is_idle = False
        idle_start_time = None

    # --- Control sample rate (avoid saving every tiny movement) ---
    if current_time - last_sample_time < MOVEMENT_SAMPLE_RATE:
        last_x = x
        last_y = y
        last_move_time = current_time
        return

    # --- Calculate speed ---
    speed = 0.0
    if last_x is not None and last_move_time is not None:
        speed = calculate_speed(last_x, last_y, x, y, last_move_time, current_time)

    # --- Write movement event ---
    write_row(
        event_type='movement',
        x=x, y=y,
        action='moved',
        speed=speed
    )

    # --- Update state ---
    last_x = x
    last_y = y
    last_move_time = current_time
    last_sample_time = current_time


def on_click(x, y, button, pressed):
    """
    Called every time a mouse button or touchpad tap is clicked.
    """
    action = 'pressed' if pressed else 'released'
    button_name = 'left' if 'left' in str(button).lower() else 'right'

    write_row(
        event_type='click',
        x=x, y=y,
        button=button_name,
        action=action
    )
    print(f"[CLICK] {button_name} {action} at ({x}, {y})")


def on_scroll(x, y, dx, dy):
    """
    Called every time the mouse wheel or two-finger scroll is used.
    dx = horizontal scroll, dy = vertical scroll
    """
    direction = 'up' if dy > 0 else 'down'

    write_row(
        event_type='scroll',
        x=x, y=y,
        action=f'scrolled_{direction}',
        scroll_dx=dx,
        scroll_dy=dy
    )
    print(f"[SCROLL] {direction} at ({x}, {y}) | dy={dy}")


# -------------------------------------------------------
# Idle Detection (runs in background using a checker)
# -------------------------------------------------------
def check_idle():
    """
    Checks if the mouse has been still for longer than IDLE_THRESHOLD.
    This runs in a loop in a separate thread.
    """
    global is_idle, idle_start_time, last_move_time

    while True:
        time.sleep(0.5)  # Check every 500ms

        if last_move_time is None:
            continue

        time_since_move = time.time() - last_move_time

        # If mouse stopped moving and not already marked idle
        if time_since_move >= IDLE_THRESHOLD and not is_idle:
            is_idle = True
            idle_start_time = time.time()
            write_row(
                event_type='idle',
                x=last_x or 0,
                y=last_y or 0,
                action='idle_start'
            )
            print(f"[IDLE START] Mouse idle at ({last_x}, {last_y})")


# -------------------------------------------------------
# Main: Start Capturing
# -------------------------------------------------------
if __name__ == "__main__":
    import threading

    print("=" * 50)
    print("  Mouse / Touchpad Capture Started")
    print("  Move your touchpad, click, or scroll")
    print("  Press Ctrl+C to stop capturing")
    print("=" * 50)

    # Setup CSV file
    setup_csv(OUTPUT_FILE)

    # Start idle detection in background thread
    idle_thread = threading.Thread(target=check_idle, daemon=True)
    idle_thread.start()

    # Start mouse listener
    try:
        with mouse.Listener(
            on_move=on_move,
            on_click=on_click,
            on_scroll=on_scroll
        ) as listener:
            listener.join()

    except KeyboardInterrupt:
        print("\n[INFO] Capture stopped by user.")

    finally:
        if csv_file:
            csv_file.close()
        print(f"[INFO] Data saved to: {OUTPUT_FILE}")
        print("[INFO] Mouse capture session ended.")