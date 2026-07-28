"""
utils/feature_engineering.py
-----------------------------
Combines keyboard and mouse behavioral features into one
unified dataset ready for Machine Learning.

Input  : data/keyboard_features.csv  (from keyboard_processor.py)
         data/mouse_data.csv          (from mouse_capture.py)
Output : data/combined_features.csv  (ML-ready dataset)

Each row in combined_features.csv = one complete user session.
The ML model will train on this file.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

# -------------------------------------------------------
# Configuration
# -------------------------------------------------------
KEYBOARD_FEATURES_FILE = "data/keyboard_features.csv"
MOUSE_DATA_FILE        = "data/mouse_data.csv"
OUTPUT_FILE            = "data/combined_features.csv"


# -------------------------------------------------------
# PART 1: Load Keyboard Features
# -------------------------------------------------------
def load_keyboard_features(filepath):
    """
    Loads the already-processed keyboard features.
    These were calculated in keyboard_processor.py.
    Returns a dictionary of keyboard features.
    """
    if not os.path.exists(filepath):
        print(f"[ERROR] Keyboard features file not found: {filepath}")
        print("[INFO]  Please run utils/keyboard_processor.py first.")
        return None

    df = pd.read_csv(filepath)

    if df.empty:
        print("[ERROR] Keyboard features file is empty.")
        return None

    # Use the LAST row (most recent session)
    latest = df.iloc[-1]

    features = {
        'avg_hold_time_ms':    latest.get('avg_hold_time_ms', 0),
        'std_hold_time_ms':    latest.get('std_hold_time_ms', 0),
        'avg_flight_time_ms':  latest.get('avg_flight_time_ms', 0),
        'std_flight_time_ms':  latest.get('std_flight_time_ms', 0),
        'typing_speed_kps':    latest.get('typing_speed_kps', 0),
        'key_press_frequency': latest.get('key_press_frequency', 0),
        'error_rate':          latest.get('error_rate', 0),
        'total_keystrokes':    latest.get('total_keystrokes', 0),
    }

    print("[INFO] Keyboard features loaded successfully.")
    return features


# -------------------------------------------------------
# PART 2: Extract Mouse Features from Raw Mouse Data
# -------------------------------------------------------
def extract_mouse_features(filepath):
    """
    Reads the raw mouse_data.csv and calculates
    behavioral features from it.
    Returns a dictionary of mouse features.
    """
    if not os.path.exists(filepath):
        print(f"[ERROR] Mouse data file not found: {filepath}")
        print("[INFO]  Please run utils/mouse_capture.py first.")
        return None

    df = pd.read_csv(filepath)

    if df.empty:
        print("[ERROR] Mouse data file is empty.")
        return None

    print(f"[INFO] Mouse data loaded: {len(df)} events")

    # --- Separate event types ---
    movements = df[df['event_type'] == 'movement']
    clicks    = df[df['event_type'] == 'click']
    scrolls   = df[df['event_type'] == 'scroll']
    idles     = df[df['event_type'] == 'idle']

    # --- Feature 1: Mouse Speed Statistics ---
    speeds = movements['speed_px_s'].dropna()
    avg_mouse_speed = round(speeds.mean(), 4) if not speeds.empty else 0.0
    std_mouse_speed = round(speeds.std(), 4)  if not speeds.empty else 0.0
    max_mouse_speed = round(speeds.max(), 4)  if not speeds.empty else 0.0

    # --- Feature 2: Click Behavior ---
    total_clicks = len(clicks)
    left_clicks  = len(clicks[clicks['button'] == 'left'])
    right_clicks = len(clicks[clicks['button'] == 'right'])

    # Click frequency = clicks per second of session
    click_frequency = 0.0
    if total_clicks > 0 and not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        session_duration = (
            df['timestamp'].max() - df['timestamp'].min()
        ).total_seconds()
        if session_duration > 0:
            click_frequency = round(total_clicks / session_duration, 4)

    # --- Feature 3: Scroll Behavior ---
    total_scrolls  = len(scrolls)
    scroll_up      = len(scrolls[scrolls['action'] == 'scrolled_up'])
    scroll_down    = len(scrolls[scrolls['action'] == 'scrolled_down'])

    # --- Feature 4: Idle Time ---
    idle_end_events = idles[idles['action'] == 'idle_end']
    total_idle_time = round(idle_end_events['idle_time_s'].sum(), 4) \
                      if not idle_end_events.empty else 0.0
    avg_idle_time   = round(idle_end_events['idle_time_s'].mean(), 4) \
                      if not idle_end_events.empty else 0.0
    idle_count      = len(idle_end_events)

    # --- Feature 5: Movement Area (how much of screen was used) ---
    if not movements.empty:
        x_range = round(movements['x'].max() - movements['x'].min(), 2)
        y_range = round(movements['y'].max() - movements['y'].min(), 2)
    else:
        x_range = 0.0
        y_range = 0.0

    features = {
        # Speed features
        'avg_mouse_speed':    avg_mouse_speed,
        'std_mouse_speed':    std_mouse_speed,
        'max_mouse_speed':    max_mouse_speed,
        # Click features
        'total_clicks':       total_clicks,
        'left_clicks':        left_clicks,
        'right_clicks':       right_clicks,
        'click_frequency':    click_frequency,
        # Scroll features
        'total_scrolls':      total_scrolls,
        'scroll_up_count':    scroll_up,
        'scroll_down_count':  scroll_down,
        # Idle features
        'total_idle_time_s':  total_idle_time,
        'avg_idle_time_s':    avg_idle_time,
        'idle_count':         idle_count,
        # Movement area
        'mouse_x_range':      x_range,
        'mouse_y_range':      y_range,
    }

    print("[INFO] Mouse features extracted successfully.")
    return features


# -------------------------------------------------------
# PART 3: Combine and Save
# -------------------------------------------------------
def combine_and_save(keyboard_features, mouse_features, output_filepath, label=1):
    """
    Combines keyboard + mouse features into one row.
    Adds a label column:
        1 = legitimate user (authorized)
        0 = intruder (unauthorized)
    During training, we always use label=1 (your own data).
    Saves to combined_features.csv.
    """

    # Merge both feature dictionaries
    combined = {}
    combined.update(keyboard_features)
    combined.update(mouse_features)

    # Add session metadata
    combined['session_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    combined['label'] = label   # 1 = you (authorized), 0 = intruder

    combined_df = pd.DataFrame([combined])

    # Save: append if file exists, create if not
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    if os.path.exists(output_filepath):
        combined_df.to_csv(output_filepath, mode='a', header=False, index=False)
        print(f"[INFO] Features appended to: {output_filepath}")
    else:
        combined_df.to_csv(output_filepath, index=False)
        print(f"[INFO] Combined features saved to: {output_filepath}")

    return combined


# -------------------------------------------------------
# PART 4: Print Summary
# -------------------------------------------------------
def print_summary(combined):
    """
    Prints a clean summary of all features to the console.
    """
    print("\n========== COMBINED FEATURE SUMMARY ==========")
    print("--- Keyboard Features ---")
    print(f"  Avg Hold Time      : {combined.get('avg_hold_time_ms', 0)} ms")
    print(f"  Std Hold Time      : {combined.get('std_hold_time_ms', 0)} ms")
    print(f"  Avg Flight Time    : {combined.get('avg_flight_time_ms', 0)} ms")
    print(f"  Typing Speed       : {combined.get('typing_speed_kps', 0)} keys/sec")
    print(f"  Error Rate         : {combined.get('error_rate', 0)}")
    print(f"  Total Keystrokes   : {combined.get('total_keystrokes', 0)}")
    print("--- Mouse Features ---")
    print(f"  Avg Mouse Speed    : {combined.get('avg_mouse_speed', 0)} px/s")
    print(f"  Total Clicks       : {combined.get('total_clicks', 0)}")
    print(f"  Click Frequency    : {combined.get('click_frequency', 0)} clicks/sec")
    print(f"  Total Scrolls      : {combined.get('total_scrolls', 0)}")
    print(f"  Total Idle Time    : {combined.get('total_idle_time_s', 0)} sec")
    print(f"  Idle Count         : {combined.get('idle_count', 0)}")
    print(f"  Mouse X Range      : {combined.get('mouse_x_range', 0)} px")
    print(f"  Mouse Y Range      : {combined.get('mouse_y_range', 0)} px")
    print("--- Session Info ---")
    print(f"  Label              : {combined.get('label', 1)} (1=You, 0=Intruder)")
    print(f"  Timestamp          : {combined.get('session_timestamp', '')}")
    print("===============================================\n")


# -------------------------------------------------------
# Main: Run the full pipeline
# -------------------------------------------------------
if __name__ == "__main__":
    print("\n[START] Feature Engineering Pipeline")
    print("=" * 50)

    # Step 1: Load keyboard features
    keyboard_features = load_keyboard_features(KEYBOARD_FEATURES_FILE)
    if keyboard_features is None:
        exit(1)

    # Step 2: Extract mouse features
    mouse_features = extract_mouse_features(MOUSE_DATA_FILE)
    if mouse_features is None:
        exit(1)

    # Step 3: Combine and save
    combined = combine_and_save(keyboard_features, mouse_features, OUTPUT_FILE, label=1)

    # Step 4: Print summary
    print_summary(combined)

    print("[DONE] Feature engineering complete!")
    print(f"[INFO] Your ML dataset is ready at: {OUTPUT_FILE}")
    print("[INFO] Run this script after every typing+mouse session")
    print("[INFO] to build up more training data rows.\n")