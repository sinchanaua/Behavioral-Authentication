# 🔐 Closing the Security Gap: Continuous Behavioral Authentication Beyond Login

> A Final Year Engineering Project — 2026

---

## 📌 Project Overview

Traditional authentication systems verify a user's identity **only at login**.
Once logged in, there is no further verification — leaving systems vulnerable
to session hijacking, unauthorized access, and insider threats.

This project solves that problem by implementing a **Continuous Behavioral
Authentication System** that monitors the user's behavior **throughout the
entire session** using:

- ⌨️ **Keystroke Dynamics** — Hold Time, Flight Time, Typing Speed
- 🖱️ **Mouse/Touchpad Behavior** — Speed, Clicks, Scrolls, Idle Time
- 🤖 **Machine Learning** — Random Forest, SVM, Isolation Forest
- 🚨 **Real-time Alerts** — Email notification + automatic session logout

---

## 🎯 Objective

Detect unauthorized users **during an active session** by continuously
analyzing behavioral biometrics and comparing them against the enrolled
user's behavioral profile using machine learning.

---

## 🏗️ Project Architecture

```
Raw Data Collection
       │
       ▼
Data Preprocessing & Feature Engineering
       │
       ▼
Machine Learning Pipeline (Train & Save Model)
       │
       ▼
Continuous Authentication Engine (Background Thread)
       │
       ▼
Flask Web Application + Live Dashboard
       │
       ▼
Alert System (Email + Force Logout)
```

---

## 📁 Project Structure

```
Behavioral_Authentication/
│
├── data/                          # All CSV data files
│   ├── keyboard_data.csv          # Raw keystroke events
│   ├── keyboard_features.csv      # Processed keyboard features
│   ├── mouse_data.csv             # Raw mouse/touchpad events
│   ├── combined_features.csv      # ML-ready combined dataset
│   ├── auth_log.csv               # Authentication history log
│   └── intrusion_log.csv          # Intrusion event log
│
├── models/                        # ML model files
│   ├── ml_pipeline.py             # Train & save ML models
│   ├── best_model.pkl             # Saved best ML model
│   ├── scaler.pkl                 # Saved feature scaler
│   └── model_info.json            # Model metadata
│
├── utils/                         # Utility modules
│   ├── __init__.py
│   ├── keyboard_processor.py      # Extract keyboard features
│   ├── mouse_capture.py           # Capture mouse/touchpad data
│   ├── feature_engineering.py     # Combine features for ML
│   └── auth_engine.py             # Continuous auth engine
│
├── templates/                     # Flask HTML templates
│   └── dashboard.html             # Live dashboard UI
│
├── static/                        # Static assets (CSS, JS, images)
│
├── app.py                         # Main Flask application
├── keyboard_capture.py            # Raw keystroke capture
├── requirements.txt               # Python dependencies
└── README.md                      # Project documentation
```

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/Behavioral_Authentication.git
cd Behavioral_Authentication
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Email Alerts
Open `app.py` and update these lines:
```python
EMAIL_SENDER   = "your_email@gmail.com"
EMAIL_PASSWORD = "your_16_digit_app_password"
EMAIL_RECEIVER = "your_email@gmail.com"
```

> To get a Gmail App Password:
> Google Account → Security → 2-Step Verification → App Passwords → Generate

---

## 🚀 How to Run

### Phase 1 — Collect Training Data (repeat 15-20 times)

```bash
# Step 1: Capture keystrokes (type naturally for 1-2 mins, then Ctrl+C)
python keyboard_capture.py

# Step 2: Process keyboard features
python utils/keyboard_processor.py

# Step 3: Capture mouse/touchpad (use for 1-2 mins, then Ctrl+C)
python utils/mouse_capture.py

# Step 4: Combine features into dataset
python utils/feature_engineering.py
```

### Phase 2 — Train ML Model

```bash
python models/ml_pipeline.py
```

### Phase 3 — Run the Application

```bash
python app.py
```

Open browser → `http://127.0.0.1:5000`

---

## 📊 Behavioral Features

### Keystroke Dynamics
| Feature | Description |
|---|---|
| Hold Time | Duration a key is held down (ms) |
| Flight Time | Gap between releasing one key and pressing next (ms) |
| Typing Speed | Keys typed per second |
| Key Press Frequency | Keypresses per second of session |
| Error Rate | Ratio of backspace usage |

### Mouse / Touchpad Behavior
| Feature | Description |
|---|---|
| Mouse Speed | Average cursor speed (pixels/sec) |
| Total Clicks | Number of click events |
| Click Frequency | Clicks per second |
| Scroll Events | Up/down scroll count |
| Idle Time | Duration of no movement |
| Movement Range | Screen area covered (X and Y range) |

---

## 🤖 Machine Learning Models

| Model | Type | Purpose |
|---|---|---|
| **Random Forest** | Supervised | Ensemble of 100 decision trees |
| **SVM** | Supervised | Finds optimal behavioral boundary |
| **Isolation Forest** | Unsupervised | Anomaly/intruder detection |

The best performing model is automatically selected and saved as `best_model.pkl`.

---

## 🖥️ Dashboard Features

- 🟢 **Live Authentication Status** — Authenticated / Warning / Intruder
- 📊 **Confidence Score** — Real-time percentage with animated bar
- ⌨️ **Typing Metrics** — Speed, Hold Time, Flight Time
- 🖱️ **Mouse Metrics** — Speed, Clicks, Idle Time
- 📋 **Authentication History** — Last 20 checks with timestamps
- 🚨 **Security Alert** — Red popup + email + force logout

---

## 🔐 Security Features

- ✅ Continuous monitoring every 10 seconds
- ✅ Confidence threshold: 60% minimum
- ✅ 2 consecutive failures trigger security alert
- ✅ Automatic session termination
- ✅ Email notification to system owner
- ✅ Complete audit log in `data/auth_log.csv`

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python 3.x | Core programming language |
| Flask | Web framework |
| Scikit-learn | Machine learning |
| Pandas & NumPy | Data processing |
| Pynput | Keyboard & mouse monitoring |
| Joblib | Model serialization |
| HTML/CSS/JavaScript | Dashboard frontend |

---

## 👩‍💻 How It Works (Simple Explanation)

1. **Enrollment Phase** — You use your laptop normally for 15-20 sessions.
   The system records your unique typing and mouse behavior patterns.

2. **Training Phase** — A machine learning model learns what YOUR behavior
   looks like and creates a behavioral profile.

3. **Authentication Phase** — Every 10 seconds, the system compares the
   current behavior against your profile. If it matches → Authenticated.
   If it doesn't → Alert triggered!

4. **Alert Phase** — If an intruder is detected:
   - Dashboard shows red warning
   - Email sent to owner
   - Session automatically terminated

---

## 📈 Results

- ✅ Authentication Accuracy: ~90-96% (Real User)
- ✅ Best Model: Random Forest
- ✅ Check Interval: Every 10 seconds
- ✅ Confidence Threshold: 60%

---

## 🎓 Project Information

- **Project Title:** Closing the Security Gap: Continuous Behavioral Authentication Beyond Login
- **Domain:** Cybersecurity / Biometrics / Machine Learning
- **Academic Year:** 2025-2026
- **Technology Stack:** Python, Flask, Scikit-learn, HTML/CSS/JS

---

## 📜 License

This project is developed for academic purposes as a Final Year Engineering Project.

---

*Built with ❤️ — Behavioral Authentication System 2026*
