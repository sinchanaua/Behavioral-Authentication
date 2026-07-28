"""
app.py
------
Main Flask Application for Behavioral Authentication System.

Routes:
  GET  /              → Dashboard page
  GET  /api/status    → Live authentication status (JSON)
  GET  /api/log       → Authentication history log (JSON)
  GET  /logout        → Force logout (called when intruder detected)
  POST /api/send-alert → Sends email alert to owner

Run:
    python app.py
"""

import os
import smtplib
import pandas as pd
from flask import Flask, render_template, jsonify, session, redirect, url_for
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from utils.auth_engine import AuthEngine, auth_state

# -------------------------------------------------------
# Flask App Setup
# -------------------------------------------------------
app = Flask(__name__)
app.secret_key = "behavioral_auth_secret_key_2026"

# -------------------------------------------------------
# Email Alert Configuration
# !! IMPORTANT: Fill in your Gmail address and App Password
# !! To get App Password:
# !! 1. Go to Google Account → Security
# !! 2. Enable 2-Step Verification
# !! 3. Search "App Passwords" → Generate one for "Mail"
# -------------------------------------------------------
EMAIL_SENDER   = "4cb23ai104@gmail.com"       # ← Change this
EMAIL_PASSWORD = "nicf jbba yair tclm"     # ← Change this (App Password)
EMAIL_RECEIVER = "4cb23ai104@gmail.com"       # ← Change this (who gets the alert)

# -------------------------------------------------------
# Start Authentication Engine
# -------------------------------------------------------
engine = AuthEngine()
engine.start()
print("[APP] Authentication engine started with Flask.")

# Track if alert email was already sent (avoid spam)
alert_email_sent = False


# -------------------------------------------------------
# Helper: Send Email Alert
# -------------------------------------------------------
def send_email_alert(confidence, timestamp):
    """
    Sends an email alert to the owner when an intruder is detected.
    Uses Gmail SMTP with App Password.
    """
    global alert_email_sent

    # Don't send duplicate emails
    if alert_email_sent:
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚨 Security Alert - Unauthorized Access Detected!"
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER

        # Plain text version
        text = f"""
SECURITY ALERT - Behavioral Authentication System

An unauthorized user was detected on your system!

Details:
  Time           : {timestamp}
  Confidence     : {confidence * 100:.1f}% (too low - not you!)
  Action Taken   : Session terminated / Logout triggered

Please check your system immediately.

- Behavioral Authentication System
        """

        # HTML version (looks better in email)
        html = f"""
<html>
<body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px;">
  <div style="background: white; border-radius: 10px; padding: 30px; max-width: 500px; margin: auto;">
    <h2 style="color: #e74c3c;">🚨 Security Alert!</h2>
    <p style="color: #333;">An <strong>unauthorized user</strong> was detected on your system.</p>
    <hr/>
    <table style="width:100%; border-collapse: collapse;">
      <tr>
        <td style="padding: 8px; color: #666;">🕐 Time</td>
        <td style="padding: 8px;"><strong>{timestamp}</strong></td>
      </tr>
      <tr style="background:#f9f9f9;">
        <td style="padding: 8px; color: #666;">📊 Confidence</td>
        <td style="padding: 8px;"><strong style="color:#e74c3c;">{confidence*100:.1f}%</strong></td>
      </tr>
      <tr>
        <td style="padding: 8px; color: #666;">🔒 Action</td>
        <td style="padding: 8px;"><strong>Session Terminated</strong></td>
      </tr>
    </table>
    <hr/>
    <p style="color: #e74c3c; font-weight: bold;">Please check your system immediately!</p>
    <p style="color: #999; font-size: 12px;">— Behavioral Authentication System</p>
  </div>
</body>
</html>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

        alert_email_sent = True
        print(f"[APP] 📧 Alert email sent to {EMAIL_RECEIVER}")

    except Exception as e:
        print(f"[APP] Email failed: {e}")
        print("[APP] Tip: Make sure EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER are set.")


# -------------------------------------------------------
# Helper: Log Intrusion Event
# -------------------------------------------------------
def log_intrusion(confidence, timestamp):
    """
    Logs a detailed intrusion event to data/intrusion_log.csv
    """
    log_path = "data/intrusion_log.csv"
    row = pd.DataFrame([{
        'timestamp':   timestamp,
        'confidence':  confidence,
        'action':      'session_terminated',
        'email_sent':  alert_email_sent
    }])

    if os.path.exists(log_path):
        row.to_csv(log_path, mode='a', header=False, index=False)
    else:
        row.to_csv(log_path, index=False)

    print(f"[APP] Intrusion event logged to {log_path}")


# -------------------------------------------------------
# Routes
# -------------------------------------------------------

@app.route("/")
def home():
    """
    Main dashboard page.
    If session is marked as logged out → redirect to logout page.
    """
    if session.get("force_logout"):
        return redirect(url_for("logout"))

    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    """
    Returns current authentication status as JSON.
    The dashboard calls this every 3 seconds via JavaScript.

    Also checks if intruder is detected → triggers email + logout.
    """
    global alert_email_sent

    status = engine.get_status()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # --- Check if intruder detected → trigger actions ---
    if status.get("is_alert") and status.get("intruder_count", 0) > 0:

        # Reset alert email flag if new session
        if not session.get("alert_triggered"):
            session["alert_triggered"] = True
            session["force_logout"]    = True
            alert_email_sent           = False

            confidence = status.get("confidence", 0)

            # Send email alert
            send_email_alert(confidence, timestamp)

            # Log intrusion
            log_intrusion(confidence, timestamp)

        # Tell dashboard to force logout
        status["force_logout"] = True

    else:
        status["force_logout"] = False
        # Reset alert flags when authenticated again
        if status.get("status") == "Authenticated ✓":
            session.pop("alert_triggered", None)
            session.pop("force_logout", None)
            alert_email_sent = False

    return jsonify(status)


@app.route("/api/log")
def api_log():
    """
    Returns the last 20 authentication log entries as JSON.
    Displayed in the dashboard's history table.
    """
    log_path = "data/auth_log.csv"

    if not os.path.exists(log_path):
        return jsonify([])

    try:
        df = pd.read_csv(log_path)
        # Return last 20 rows, newest first
        df = df.tail(20).iloc[::-1]
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/logout")
def logout():
    """
    Force logout page.
    Shown when an intruder is detected.
    Clears the session.
    """
    session.clear()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Session Terminated</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: Arial, sans-serif;
                background: #1a1a2e;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                color: white;
            }
            .box {
                text-align: center;
                background: #16213e;
                padding: 50px;
                border-radius: 15px;
                border: 2px solid #e74c3c;
                max-width: 500px;
            }
            .icon  { font-size: 64px; margin-bottom: 20px; }
            h1     { color: #e74c3c; margin-bottom: 15px; }
            p      { color: #aaa; margin-bottom: 25px; line-height: 1.6; }
            a {
                background: #e74c3c;
                color: white;
                padding: 12px 30px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: bold;
            }
            a:hover { background: #c0392b; }
        </style>
    </head>
    <body>
        <div class="box">
            <div class="icon">🔒</div>
            <h1>Session Terminated</h1>
            <p>
                An unauthorized user was detected by the
                Behavioral Authentication System.<br><br>
                Your session has been terminated for security.
                The system owner has been notified via email.
            </p>
            <a href="/">Return to Login</a>
        </div>
    </body>
    </html>
    """


# -------------------------------------------------------
# Run Flask App
# -------------------------------------------------------
if __name__ == "__main__":
    print("=" * 55)
    print("  BEHAVIORAL AUTHENTICATION SYSTEM")
    print("  Flask App Starting...")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=False, use_reloader=False)