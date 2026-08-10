"""
app.py
------
Main Flask Application for Behavioral Authentication System.

Routes:
  GET/POST /register  → Registration page
  GET/POST /login     → Login page
  GET      /logout    → Logout + clear session
  GET      /          → Dashboard (protected - login required)
  GET      /api/status → Live authentication status (JSON)
  GET      /api/log   → Authentication history log (JSON)
"""

import os
import smtplib
import pandas as pd
from flask import (Flask, render_template, jsonify,
                   session, redirect, url_for, request, flash)
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from utils.auth_engine import AuthEngine, auth_state
from utils.database import (
    create_tables,
    register_user,
    login_user,
    log_login_attempt,
    fetch_login_history,
)

# -------------------------------------------------------
# Flask App Setup
# -------------------------------------------------------
app = Flask(__name__)
app.secret_key = "behavioral_auth_secret_key_2026"

# -------------------------------------------------------
# Email Alert Configuration
# -------------------------------------------------------
EMAIL_SENDER   = "4cb23ai104@gmail.com"       # ← Change this
EMAIL_PASSWORD = "nicf jbba yair tclm"     # ← Change this
EMAIL_RECEIVER = "4cb23ai104@gmail.com"       # ← Change this

# -------------------------------------------------------
# Initialize Database & Auth Engine on Startup
# -------------------------------------------------------
create_tables()   # Create users.db and users table if not exists

engine = AuthEngine()
engine.start()
print("[APP] Authentication engine started with Flask.")

alert_email_sent = False


# -------------------------------------------------------
# Helper: Login Required Decorator
# -------------------------------------------------------
def login_required(f):
    """
    Protects routes that need login.
    If user is not logged in → redirect to login page.
    """
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please login to access the dashboard.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# -------------------------------------------------------
# Helper: Send Email Alert
# -------------------------------------------------------
def send_email_alert(confidence, timestamp):
    global alert_email_sent
    if alert_email_sent:
        return
    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = "🚨 Security Alert - Unauthorized Access Detected!"
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER

        text = f"""
SECURITY ALERT - Behavioral Authentication System

An unauthorized user was detected on your system!

Details:
  Time       : {timestamp}
  Confidence : {confidence * 100:.1f}%
  Action     : Session terminated

Please check your system immediately.
        """

        html = f"""
<html>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
  <div style="background:white;border-radius:10px;padding:30px;max-width:500px;margin:auto;">
    <h2 style="color:#e74c3c;">🚨 Security Alert!</h2>
    <p>An <strong>unauthorized user</strong> was detected on your system.</p>
    <hr/>
    <table style="width:100%;">
      <tr><td style="color:#666;">🕐 Time</td><td><strong>{timestamp}</strong></td></tr>
      <tr><td style="color:#666;">📊 Confidence</td>
          <td><strong style="color:#e74c3c;">{confidence*100:.1f}%</strong></td></tr>
      <tr><td style="color:#666;">🔒 Action</td><td><strong>Session Terminated</strong></td></tr>
    </table>
    <hr/>
    <p style="color:#e74c3c;font-weight:bold;">Please check your system immediately!</p>
  </div>
</body>
</html>
        """
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

        alert_email_sent = True
        print(f"[APP] 📧 Alert email sent to {EMAIL_RECEIVER}")

    except Exception as e:
        print(f"[APP] Email failed: {e}")


# -------------------------------------------------------
# Helper: Log Intrusion
# -------------------------------------------------------
def log_intrusion(confidence, timestamp):
    log_path = "data/intrusion_log.csv"
    row = pd.DataFrame([{
        'timestamp':  timestamp,
        'confidence': confidence,
        'action':     'session_terminated',
        'email_sent': alert_email_sent
    }])
    if os.path.exists(log_path):
        row.to_csv(log_path, mode='a', header=False, index=False)
    else:
        row.to_csv(log_path, index=False)
    print(f"[APP] Intrusion logged.")


# ═══════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════

# -------------------------------------------------------
# REGISTER PAGE
# -------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """
    GET  → Show registration form
    POST → Process registration form
    """
    # If already logged in → go to dashboard
    if session.get("logged_in"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username         = request.form.get("username", "").strip()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Check passwords match
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "error")
            return redirect(url_for("register"))

        # Try to register
        success, message = register_user(username, password)

        if success:
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for("login"))
        else:
            flash(message, "error")
            return redirect(url_for("register"))

    return render_template("register.html")


# -------------------------------------------------------
# LOGIN PAGE
# -------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    GET  → Show login form
    POST → Process login form
    """
    # If already logged in → go to dashboard
    if session.get("logged_in"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        success, message = login_user(username, password)
        ip_address = request.remote_addr
        log_login_attempt(username, success, message, ip_address)

        if success:
            # Save user info in session
            session["logged_in"] = True
            session["username"]  = username
            flash(f"Welcome back, {username}! 👋", "success")
            return redirect(url_for("home"))
        else:
            flash(message, "error")
            return redirect(url_for("login"))

    return render_template("login.html")


# -------------------------------------------------------
# LOGOUT
# -------------------------------------------------------
@app.route("/logout")
def logout():
    """Clears session and redirects to login page."""
    username = session.get("username", "User")
    session.clear()
    flash(f"You have been logged out, {username}.", "success")
    return redirect(url_for("login"))


# -------------------------------------------------------
# FORCE LOGOUT (called when intruder detected)
# -------------------------------------------------------
@app.route("/force-logout")
def force_logout():
    """
    Called automatically when intruder is detected.
    Shows a security warning page and clears session.
    """
    session.clear()
    return render_template("logout_alert.html")


# -------------------------------------------------------
# DASHBOARD (protected)
# -------------------------------------------------------
@app.route("/")
@login_required
def home():
    """Main dashboard — only accessible after login."""
    return render_template("dashboard.html",
                           username=session.get("username", "User"))


# -------------------------------------------------------
# ADMIN: Login Audit View
# -------------------------------------------------------
@app.route("/admin")
@login_required
def admin():
    history = fetch_login_history(limit=50)
    return render_template("admin.html", history=history)


# -------------------------------------------------------
# API: Live Authentication Status
# -------------------------------------------------------
@app.route("/api/status")
@login_required
def api_status():
    """
    Returns live auth status as JSON.
    Dashboard calls this every 3 seconds.
    """
    global alert_email_sent

    status    = engine.get_status()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    status_text = status.get("status", "").lower()
    is_unauthenticated = "unauth" in status_text or "intruder" in status_text

    if status.get("is_alert") and status.get("intruder_count", 0) > 0:
        if not session.get("alert_triggered"):
            session["alert_triggered"] = True
            alert_email_sent           = False
            confidence                 = status.get("confidence", 0)
            send_email_alert(confidence, timestamp)
            log_intrusion(confidence, timestamp)

        status["force_logout"] = True
    elif is_unauthenticated:
        status["force_logout"] = True
    else:
        status["force_logout"] = False
        if status.get("status") == "Authenticated ✓":
            session.pop("alert_triggered", None)
            alert_email_sent = False

    return jsonify(status)


# -------------------------------------------------------
# API: Authentication Log History
# -------------------------------------------------------
@app.route("/api/log")
@login_required
def api_log():
    """Returns last 20 authentication log entries."""
    log_path = "data/auth_log.csv"
    if not os.path.exists(log_path):
        return jsonify([])
    try:
        df = pd.read_csv(log_path)
        df = df.tail(20).iloc[::-1]
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)})


# ═══════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  BEHAVIORAL AUTHENTICATION SYSTEM")
    print("  Flask App Starting...")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=False, use_reloader=False)