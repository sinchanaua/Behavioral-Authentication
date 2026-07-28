"""
utils/auth_engine.py
---------------------
Continuous Behavioral Authentication Engine.

This is the CORE of the project. It:
1. Loads the trained ML model (best_model.pkl)
2. Continuously monitors keyboard + mouse behavior
3. Extracts features every CHECK_INTERVAL seconds
4. Predicts: is this the authorized user or an intruder?
5. Calculates a confidence score (0.0 to 1.0)
6. Triggers security alerts if an intruder is detected
7. Logs all authentication events to data/auth_log.csv

This engine runs in a background thread and shares its
results with the Flask app via a shared state dictionary.

Usage (standalone test):
    python utils/auth_engine.py

Usage (from Flask app):
    from utils.auth_engine import AuthEngine
    engine = AuthEngine()
    engine.start()
    status = engine.get_status()
"""

import os
import json
import time
import math
import joblib
import threading
import numpy as np
import pandas as pd
from datetime import datetime
from pynput import keyboard, mouse


# -------------------------------------------------------
# Configuration
# -------------------------------------------------------
MODEL_PATH       = "models/best_model.pkl"
SCALER_PATH      = "models/scaler.pkl"
MODEL_INFO_PATH  = "models/model_info.json"
AUTH_LOG_PATH    = "data/auth_log.csv"
CHECK_INTERVAL   = 10        # Seconds between each authentication check
ALERT_THRESHOLD  = 2         # Consecutive failures before alert
CONFIDENCE_MIN   = 0.8       # Below this = suspicious


# -------------------------------------------------------
# Shared Authentication State
# (Flask app reads this dictionary in real time)
# -------------------------------------------------------
auth_state = {
    "status":           "Initializing",   # Authenticated / Warning / Intruder Detected
    "confidence":       0.0,              # 0.0 to 1.0
    "last_checked":     "Never",          # Timestamp of last check
    "alert_count":      0,                # Consecutive failed authentications
    "is_alert":         False,            # True if security alert is active
    "typing_speed":     0.0,              # Current typing speed
    "avg_hold_time":    0.0,              # Current avg hold time
    "avg_flight_time":  0.0,             # Current avg flight time
    "mouse_speed":      0.0,              # Current mouse speed
    "total_clicks":     0,               # Clicks in current window
    "idle_time":        0.0,             # Idle time in current window
    "model_name":       "Unknown",        # Which model is active
    "session_start":    "",              # When session started
    "total_checks":     0,               # Total authentication checks done
    "authorized_count": 0,               # Times identified as authorized
    "intruder_count":   0,               # Times identified as intruder
}


# -------------------------------------------------------
# Authentication Engine Class
# -------------------------------------------------------
class AuthEngine:
    def __init__(self):
        self.model         = None
        self.scaler        = None
        self.feature_names = []
        self.model_name    = "Unknown"
        self.running       = False

        # Live data buffers (filled by listeners)
        self.key_events    = []     # List of (key, event, time)
        self.mouse_events  = []     # List of (type, x, y, data, time)

        # Mouse tracking state
        self.last_x        = None
        self.last_y        = None
        self.last_move_time= None
        self.idle_start    = None
        self.is_idle       = False

        # Consecutive failure counter
        self.fail_count    = 0

        # Load model on init
        self._load_model()

        # Setup auth log
        self._setup_log()

        # Update shared state
        auth_state["session_start"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        auth_state["model_name"]    = self.model_name


    # -------------------------------------------------------
    # Load ML Model
    # -------------------------------------------------------
    def _load_model(self):
        """Loads the trained model and scaler from disk."""
        try:
            self.model  = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)

            if os.path.exists(MODEL_INFO_PATH):
                with open(MODEL_INFO_PATH) as f:
                    info = json.load(f)
                self.feature_names = info.get('feature_names', [])
                self.model_name    = info.get('best_model', 'Unknown')

            print(f"[AUTH] Model loaded: {self.model_name}")
            print(f"[AUTH] Features    : {len(self.feature_names)}")
            auth_state["status"] = "Model Loaded"

        except Exception as e:
            print(f"[AUTH ERROR] Failed to load model: {e}")
            print("[AUTH] Please run: python models/ml_pipeline.py first.")
            auth_state["status"] = "Model Not Found"


    # -------------------------------------------------------
    # Setup Auth Log CSV
    # -------------------------------------------------------
    def _setup_log(self):
        """Creates the authentication log CSV if it doesn't exist."""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(AUTH_LOG_PATH):
            df = pd.DataFrame(columns=[
                'timestamp', 'status', 'confidence',
                'typing_speed', 'avg_hold_time', 'avg_flight_time',
                'mouse_speed', 'total_clicks', 'alert'
            ])
            df.to_csv(AUTH_LOG_PATH, index=False)


    # -------------------------------------------------------
    # Keyboard Listener Callbacks
    # -------------------------------------------------------
    def _on_key_press(self, key):
        """Records key press events into the buffer."""
        try:
            key_char = key.char if hasattr(key, 'char') and key.char else str(key)
        except:
            key_char = str(key)
        self.key_events.append(('press', key_char, time.time()))


    def _on_key_release(self, key):
        """Records key release events into the buffer."""
        try:
            key_char = key.char if hasattr(key, 'char') and key.char else str(key)
        except:
            key_char = str(key)
        self.key_events.append(('release', key_char, time.time()))


    # -------------------------------------------------------
    # Mouse Listener Callbacks
    # -------------------------------------------------------
    def _on_mouse_move(self, x, y):
        """Records mouse movement and calculates speed."""
        current_time = time.time()
        speed = 0.0

        if self.last_x is not None and self.last_move_time is not None:
            dist = math.sqrt((x - self.last_x)**2 + (y - self.last_y)**2)
            dt   = current_time - self.last_move_time
            if dt > 0:
                speed = dist / dt

        # Check if recovering from idle
        if self.is_idle and self.idle_start is not None:
            idle_dur = current_time - self.idle_start
            self.mouse_events.append(('idle_end', x, y, idle_dur, current_time))
            self.is_idle   = False
            self.idle_start= None

        self.mouse_events.append(('move', x, y, speed, current_time))
        self.last_x        = x
        self.last_y        = y
        self.last_move_time= current_time


    def _on_mouse_click(self, x, y, button, pressed):
        """Records mouse click events."""
        action = 'click_press' if pressed else 'click_release'
        btn    = 'left' if 'left' in str(button).lower() else 'right'
        self.mouse_events.append((action, x, y, btn, time.time()))


    def _on_mouse_scroll(self, x, y, dx, dy):
        """Records scroll events."""
        self.mouse_events.append(('scroll', x, y, dy, time.time()))


    # -------------------------------------------------------
    # Idle Detection Thread
    # -------------------------------------------------------
    def _idle_checker(self):
        """Background thread: detects when mouse stops moving."""
        while self.running:
            time.sleep(0.5)
            if self.last_move_time is None:
                continue
            elapsed = time.time() - self.last_move_time
            if elapsed >= 1.5 and not self.is_idle:
                self.is_idle    = True
                self.idle_start = time.time()
                self.mouse_events.append(
                    ('idle_start', self.last_x or 0, self.last_y or 0, 0, time.time())
                )


    # -------------------------------------------------------
    # Feature Extraction from Buffers
    # -------------------------------------------------------
    def _extract_keyboard_features(self, events):
        """Extracts keyboard behavioral features from raw key events."""
        press_events   = [(k, t) for e, k, t in events if e == 'press']
        release_events = [(k, t) for e, k, t in events if e == 'release']

        if len(press_events) < 2:
            return {
                'avg_hold_time_ms':    0.0,
                'std_hold_time_ms':    0.0,
                'avg_flight_time_ms':  0.0,
                'std_flight_time_ms':  0.0,
                'typing_speed_kps':    0.0,
                'key_press_frequency': 0.0,
                'error_rate':          0.0,
                'total_keystrokes':    0,
            }

        # Hold times
        hold_times = []
        for key, pt in press_events:
            matches = [(k, rt) for k, rt in release_events if k == key and rt > pt]
            if matches:
                hold_times.append((matches[0][1] - pt) * 1000)

        # Flight times
        flight_times = []
        sorted_releases = sorted(release_events, key=lambda x: x[1])
        sorted_presses  = sorted(press_events,   key=lambda x: x[1])
        for _, rt in sorted_releases:
            next_p = [pt for _, pt in sorted_presses if pt > rt]
            if next_p:
                flight_times.append((next_p[0] - rt) * 1000)

        # Speed
        times = [t for _, t in press_events]
        duration = times[-1] - times[0] if len(times) > 1 else 1
        typing_speed = len(press_events) / duration if duration > 0 else 0

        # Error rate
        backspaces = sum(1 for k, _ in press_events if 'backspace' in str(k).lower())
        error_rate = backspaces / len(press_events) if press_events else 0

        return {
            'avg_hold_time_ms':    float(np.mean(hold_times))   if hold_times   else 0.0,
            'std_hold_time_ms':    float(np.std(hold_times))    if hold_times   else 0.0,
            'avg_flight_time_ms':  float(np.mean(flight_times)) if flight_times else 0.0,
            'std_flight_time_ms':  float(np.std(flight_times))  if flight_times else 0.0,
            'typing_speed_kps':    round(typing_speed, 4),
            'key_press_frequency': round(typing_speed, 4),
            'error_rate':          round(error_rate, 4),
            'total_keystrokes':    len(press_events),
        }


    def _extract_mouse_features(self, events):
        """Extracts mouse behavioral features from raw mouse events."""
        moves   = [(x, y, d, t) for tp, x, y, d, t in events if tp == 'move']
        clicks  = [(x, y, d, t) for tp, x, y, d, t in events if 'click' in tp]
        scrolls = [(x, y, d, t) for tp, x, y, d, t in events if tp == 'scroll']
        idles   = [(x, y, d, t) for tp, x, y, d, t in events if tp == 'idle_end']

        speeds = [d for _, _, d, _ in moves if d > 0]
        duration = (events[-1][4] - events[0][4]) if len(events) > 1 else 1

        return {
            'avg_mouse_speed':    round(float(np.mean(speeds)),   4) if speeds  else 0.0,
            'std_mouse_speed':    round(float(np.std(speeds)),    4) if speeds  else 0.0,
            'max_mouse_speed':    round(float(np.max(speeds)),    4) if speeds  else 0.0,
            'total_clicks':       len(clicks),
            'left_clicks':        sum(1 for _, _, d, _ in clicks if d == 'left'),
            'right_clicks':       sum(1 for _, _, d, _ in clicks if d == 'right'),
            'click_frequency':    round(len(clicks) / duration, 4) if duration > 0 else 0.0,
            'total_scrolls':      len(scrolls),
            'scroll_up_count':    sum(1 for _, _, d, _ in scrolls if d > 0),
            'scroll_down_count':  sum(1 for _, _, d, _ in scrolls if d < 0),
            'total_idle_time_s':  round(sum(d for _, _, d, _ in idles), 4),
            'avg_idle_time_s':    round(float(np.mean([d for _, _, d, _ in idles])), 4) if idles else 0.0,
            'idle_count':         len(idles),
            'mouse_x_range':      round(max(x for x, _, _, _ in moves) - min(x for x, _, _, _ in moves), 2) if moves else 0.0,
            'mouse_y_range':      round(max(y for _, y, _, _ in moves) - min(y for _, y, _, _ in moves), 2) if moves else 0.0,
        }


    # -------------------------------------------------------
    # Build Feature Vector
    # -------------------------------------------------------
    def _build_feature_vector(self, kb_features, ms_features):
        """
        Combines keyboard + mouse features into a single
        feature vector in the exact same order as training.
        """
        combined = {}
        combined.update(kb_features)
        combined.update(ms_features)

        # Build vector in the exact feature order from training
        if self.feature_names:
            vector = [combined.get(f, 0.0) for f in self.feature_names]
        else:
            vector = list(combined.values())

        return np.array(vector).reshape(1, -1)


    # -------------------------------------------------------
    # Run One Authentication Check
    # -------------------------------------------------------
    def _authenticate(self):
        """
        Runs one full authentication check:
        1. Snapshot current buffers
        2. Extract features
        3. Scale features
        4. Predict with ML model
        5. Update shared auth_state
        6. Log result
        """
        if self.model is None:
            return

        # Snapshot and clear buffers
        key_snapshot   = list(self.key_events)
        mouse_snapshot = list(self.mouse_events)
        self.key_events.clear()
        self.mouse_events.clear()

        # Need minimum data
        if len(key_snapshot) < 4 and len(mouse_snapshot) < 4:
            auth_state["status"]       = "Collecting Data..."
            auth_state["last_checked"] = datetime.now().strftime('%H:%M:%S')
            return

        # Extract features
        kb_feat = self._extract_keyboard_features(key_snapshot)
        ms_feat = self._extract_mouse_features(mouse_snapshot) \
                  if mouse_snapshot else self._empty_mouse_features()

        # Build and scale feature vector
        vector  = self._build_feature_vector(kb_feat, ms_feat)
        try:
            vector_scaled = self.scaler.transform(vector)
        except Exception:
            vector_scaled = vector

        # --- Predict ---
        try:
            # Get prediction
            if hasattr(self.model, 'predict_proba'):
                proba      = self.model.predict_proba(vector_scaled)[0]
                prediction = self.model.predict(vector_scaled)[0]
                # Confidence = probability of authorized class (label=1)
                auth_idx   = list(self.model.classes_).index(1) \
                             if 1 in self.model.classes_ else -1
                confidence = float(proba[auth_idx]) if auth_idx >= 0 else float(max(proba))
            else:
                # Isolation Forest: no predict_proba
                raw        = self.model.predict(vector_scaled)[0]
                prediction = 1 if raw == 1 else 0
                score      = self.model.decision_function(vector_scaled)[0]
                # Normalize score to 0-1 range
                confidence = float(1 / (1 + np.exp(-score)))

        except Exception as e:
            print(f"[AUTH ERROR] Prediction failed: {e}")
            return

        # --- Determine status ---
        is_authorized = (prediction == 1)

        if is_authorized and confidence >= CONFIDENCE_MIN:
            status     = "Authenticated ✓"
            self.fail_count = 0
        elif is_authorized and confidence < CONFIDENCE_MIN:
            status     = "Low Confidence - Monitoring"
            self.fail_count += 1
        else:
            status     = "⚠ Intruder Detected!"
            self.fail_count += 1

        is_alert = self.fail_count >= ALERT_THRESHOLD

        # --- Update shared state ---
        auth_state["status"]           = status
        auth_state["confidence"]       = round(confidence, 4)
        auth_state["last_checked"]     = datetime.now().strftime('%H:%M:%S')
        auth_state["alert_count"]      = self.fail_count
        auth_state["is_alert"]         = is_alert
        auth_state["typing_speed"]     = round(kb_feat.get('typing_speed_kps', 0), 3)
        auth_state["avg_hold_time"]    = round(kb_feat.get('avg_hold_time_ms', 0), 2)
        auth_state["avg_flight_time"]  = round(kb_feat.get('avg_flight_time_ms', 0), 2)
        auth_state["mouse_speed"]      = round(ms_feat.get('avg_mouse_speed', 0), 2)
        auth_state["total_clicks"]     = ms_feat.get('total_clicks', 0)
        auth_state["idle_time"]        = round(ms_feat.get('total_idle_time_s', 0), 2)
        auth_state["total_checks"]    += 1

        if is_authorized:
            auth_state["authorized_count"] += 1
        else:
            auth_state["intruder_count"]   += 1

        # --- Console output ---
        print(f"\n[AUTH CHECK] {datetime.now().strftime('%H:%M:%S')}")
        print(f"  Status     : {status}")
        print(f"  Confidence : {confidence:.4f} ({confidence*100:.1f}%)")
        print(f"  Typing Spd : {auth_state['typing_speed']} kps")
        print(f"  Hold Time  : {auth_state['avg_hold_time']} ms")
        print(f"  Mouse Spd  : {auth_state['mouse_speed']} px/s")
        if is_alert:
            print(f"  🚨 SECURITY ALERT! Consecutive failures: {self.fail_count}")

        # --- Log to CSV ---
        self._log_result(status, confidence, kb_feat, ms_feat, is_alert)


    def _empty_mouse_features(self):
        """Returns zeroed mouse features when no mouse data is available."""
        return {
            'avg_mouse_speed': 0.0, 'std_mouse_speed': 0.0,
            'max_mouse_speed': 0.0, 'total_clicks': 0,
            'left_clicks': 0, 'right_clicks': 0, 'click_frequency': 0.0,
            'total_scrolls': 0, 'scroll_up_count': 0, 'scroll_down_count': 0,
            'total_idle_time_s': 0.0, 'avg_idle_time_s': 0.0,
            'idle_count': 0, 'mouse_x_range': 0.0, 'mouse_y_range': 0.0,
        }


    # -------------------------------------------------------
    # Log Authentication Result
    # -------------------------------------------------------
    def _log_result(self, status, confidence, kb_feat, ms_feat, is_alert):
        """Appends one authentication result row to auth_log.csv."""
        row = pd.DataFrame([{
            'timestamp':       datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status':          status,
            'confidence':      round(confidence, 4),
            'typing_speed':    kb_feat.get('typing_speed_kps', 0),
            'avg_hold_time':   kb_feat.get('avg_hold_time_ms', 0),
            'avg_flight_time': kb_feat.get('avg_flight_time_ms', 0),
            'mouse_speed':     ms_feat.get('avg_mouse_speed', 0),
            'total_clicks':    ms_feat.get('total_clicks', 0),
            'alert':           is_alert,
        }])
        row.to_csv(AUTH_LOG_PATH, mode='a', header=False, index=False)


    # -------------------------------------------------------
    # Authentication Loop (runs in background thread)
    # -------------------------------------------------------
    def _auth_loop(self):
        """
        Runs continuously in background.
        Every CHECK_INTERVAL seconds → runs one authentication check.
        """
        print(f"[AUTH] Authentication engine started.")
        print(f"[AUTH] Checking every {CHECK_INTERVAL} seconds...")

        while self.running:
            time.sleep(CHECK_INTERVAL)
            if self.running:
                self._authenticate()


    # -------------------------------------------------------
    # Public API
    # -------------------------------------------------------
    def start(self):
        """
        Starts the authentication engine:
        - Keyboard listener thread
        - Mouse listener thread
        - Idle checker thread
        - Authentication loop thread
        """
        if self.model is None:
            print("[AUTH] Cannot start: model not loaded.")
            return

        self.running = True
        auth_state["status"] = "Monitoring..."

        # Start idle checker
        idle_thread = threading.Thread(target=self._idle_checker, daemon=True)
        idle_thread.start()

        # Start auth loop
        auth_thread = threading.Thread(target=self._auth_loop, daemon=True)
        auth_thread.start()

        # Start keyboard listener
        self.kb_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.kb_listener.start()

        # Start mouse listener
        self.ms_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        self.ms_listener.start()

        print("[AUTH] All listeners started successfully.")


    def stop(self):
        """Stops the authentication engine cleanly."""
        self.running = False
        if hasattr(self, 'kb_listener'):
            self.kb_listener.stop()
        if hasattr(self, 'ms_listener'):
            self.ms_listener.stop()
        print("[AUTH] Authentication engine stopped.")


    def get_status(self):
        """Returns the current authentication state (for Flask)."""
        return dict(auth_state)


# -------------------------------------------------------
# Standalone Test
# -------------------------------------------------------
if __name__ == "__main__":
    print("=" * 55)
    print("  BEHAVIORAL AUTHENTICATION ENGINE - STANDALONE TEST")
    print("=" * 55)
    print(f"  Checking every {CHECK_INTERVAL} seconds.")
    print("  Type and move your touchpad naturally.")
    print("  Press Ctrl+C to stop.\n")

    engine = AuthEngine()
    engine.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()
        print("\n[INFO] Engine stopped.")
        print(f"[INFO] Auth log saved to: {AUTH_LOG_PATH}")