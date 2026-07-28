import pandas as pd
import numpy as np
import os

def load_raw_data(filepath):
    """
    Load the raw keyboard CSV file.
    Expected columns: Key, Event, Time
    """
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()  # Remove accidental spaces
    df['Time'] = pd.to_datetime(df['Time'])  # Convert string to datetime
    df = df.sort_values('Time').reset_index(drop=True)  # Sort by time
    return df


def calculate_hold_times(df):
    """
    Hold Time = Time of Release - Time of Press for the same key.
    This tells us how long each key was physically held down.
    """
    hold_times = []

    press_events = df[df['Event'] == 'Pressed'].copy()
    release_events = df[df['Event'] == 'Released'].copy()

    for _, press_row in press_events.iterrows():
        key = press_row['Key']
        press_time = press_row['Time']

        # Find the matching release event AFTER this press
        matching_releases = release_events[
            (release_events['Key'] == key) &
            (release_events['Time'] > press_time)
        ]

        if not matching_releases.empty:
            release_time = matching_releases.iloc[0]['Time']
            hold_time = (release_time - press_time).total_seconds() * 1000  # in milliseconds
            hold_times.append({
                'Key': key,
                'Hold_Time_ms': round(hold_time, 4)
            })

    return pd.DataFrame(hold_times)


def calculate_flight_times(df):
    """
    Flight Time = Time of next key Press - Time of previous key Release.
    This is the gap between finishing one key and starting the next.
    """
    flight_times = []

    release_events = df[df['Event'] == 'Released'].sort_values('Time').reset_index(drop=True)
    press_events = df[df['Event'] == 'Pressed'].sort_values('Time').reset_index(drop=True)

    for i, release_row in release_events.iterrows():
        release_time = release_row['Time']

        # Find the very next press after this release
        next_presses = press_events[press_events['Time'] > release_time]

        if not next_presses.empty:
            next_press_time = next_presses.iloc[0]['Time']
            flight_time = (next_press_time - release_time).total_seconds() * 1000  # ms
            flight_times.append({
                'From_Key': release_row['Key'],
                'Flight_Time_ms': round(flight_time, 4)
            })

    return pd.DataFrame(flight_times)


def calculate_typing_speed(df):
    """
    Typing Speed = Total key presses / Total time in seconds.
    Returns keys per second.
    """
    press_events = df[df['Event'] == 'Pressed']

    if len(press_events) < 2:
        return 0.0

    total_time_seconds = (
        press_events['Time'].max() - press_events['Time'].min()
    ).total_seconds()

    if total_time_seconds == 0:
        return 0.0

    speed = len(press_events) / total_time_seconds
    return round(speed, 4)


def calculate_key_press_frequency(df):
    """
    Key Press Frequency = Total key presses / Total session duration.
    Similar to typing speed but includes all events in the time window.
    """
    press_events = df[df['Event'] == 'Pressed']

    total_time_seconds = (df['Time'].max() - df['Time'].min()).total_seconds()

    if total_time_seconds == 0:
        return 0.0

    frequency = len(press_events) / total_time_seconds
    return round(frequency, 4)


def calculate_error_rate(df):
    """
    Error Rate = Number of Backspace presses / Total key presses.
    Backspace usage is a proxy for typing errors.
    """
    press_events = df[df['Event'] == 'Pressed']
    total_presses = len(press_events)

    if total_presses == 0:
        return 0.0

    backspace_presses = press_events[
        press_events['Key'].str.lower().str.contains('backspace', na=False)
    ]

    error_rate = len(backspace_presses) / total_presses
    return round(error_rate, 4)


def process_keyboard_data(input_filepath, output_filepath):
    """
    Main function: loads raw data, computes all features,
    saves a summary feature row to CSV.
    """
    print(f"[INFO] Loading raw keyboard data from: {input_filepath}")
    df = load_raw_data(input_filepath)
    print(f"[INFO] Total events loaded: {len(df)}")

    # --- Calculate features ---
    print("[INFO] Calculating Hold Times...")
    hold_df = calculate_hold_times(df)
    avg_hold_time = round(hold_df['Hold_Time_ms'].mean(), 4) if not hold_df.empty else 0.0
    std_hold_time = round(hold_df['Hold_Time_ms'].std(), 4) if not hold_df.empty else 0.0

    print("[INFO] Calculating Flight Times...")
    flight_df = calculate_flight_times(df)
    avg_flight_time = round(flight_df['Flight_Time_ms'].mean(), 4) if not flight_df.empty else 0.0
    std_flight_time = round(flight_df['Flight_Time_ms'].std(), 4) if not flight_df.empty else 0.0

    print("[INFO] Calculating Typing Speed...")
    typing_speed = calculate_typing_speed(df)

    print("[INFO] Calculating Key Press Frequency...")
    key_frequency = calculate_key_press_frequency(df)

    print("[INFO] Calculating Error Rate...")
    error_rate = calculate_error_rate(df)

    # --- Build feature summary row ---
    features = {
        'avg_hold_time_ms':    avg_hold_time,
        'std_hold_time_ms':    std_hold_time,
        'avg_flight_time_ms':  avg_flight_time,
        'std_flight_time_ms':  std_flight_time,
        'typing_speed_kps':    typing_speed,
        'key_press_frequency': key_frequency,
        'error_rate':          error_rate,
        'total_keystrokes':    len(df[df['Event'] == 'Pressed'])
    }

    features_df = pd.DataFrame([features])

    # --- Save to output CSV ---
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    if os.path.exists(output_filepath):
        # Append new row to existing file
        features_df.to_csv(output_filepath, mode='a', header=False, index=False)
        print(f"[INFO] Features appended to: {output_filepath}")
    else:
        # Create new file with header
        features_df.to_csv(output_filepath, index=False)
        print(f"[INFO] Features saved to: {output_filepath}")

    # --- Print summary to console ---
    print("\n========== KEYBOARD FEATURES SUMMARY ==========")
    print(f"  Avg Hold Time     : {avg_hold_time} ms")
    print(f"  Std Hold Time     : {std_hold_time} ms")
    print(f"  Avg Flight Time   : {avg_flight_time} ms")
    print(f"  Std Flight Time   : {std_flight_time} ms")
    print(f"  Typing Speed      : {typing_speed} keys/sec")
    print(f"  Key Frequency     : {key_frequency} keys/sec")
    print(f"  Error Rate        : {error_rate} (backspace ratio)")
    print(f"  Total Keystrokes  : {features['total_keystrokes']}")
    print("================================================\n")

    return features


# -------------------------------------------------------
# Run this file directly to test it
# -------------------------------------------------------
if __name__ == "__main__":
    INPUT_FILE  = "data/keyboard_data.csv"
    OUTPUT_FILE = "data/keyboard_features.csv"
    process_keyboard_data(INPUT_FILE, OUTPUT_FILE)