"""
models/ml_pipeline.py
----------------------
Machine Learning Pipeline for Behavioral Authentication.

This file:
1. Loads the combined_features.csv dataset
2. Preprocesses and scales the features
3. Trains 3 ML models:
   - Random Forest
   - Support Vector Machine (SVM)
   - Isolation Forest (anomaly detection)
4. Evaluates and compares all models
5. Saves the best model to models/best_model.pkl

Run this file to train and save your model:
    python models/ml_pipeline.py
"""

import pandas as pd
import numpy as np
import os
import json
import joblib
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score,
    recall_score, f1_score
)

# -------------------------------------------------------
# Configuration
# -------------------------------------------------------
DATASET_PATH     = "data/combined_features.csv"
MODEL_SAVE_PATH  = "models/best_model.pkl"
SCALER_SAVE_PATH = "models/scaler.pkl"
RANDOM_STATE     = 42

# Columns to DROP before training (not features)
DROP_COLUMNS = ['session_timestamp', 'label']


# -------------------------------------------------------
# STEP 1: Load and Prepare Data
# -------------------------------------------------------
def load_data(filepath):
    """
    Loads the combined features CSV.
    Separates features (X) from labels (y).
    """
    print(f"[INFO] Loading dataset from: {filepath}")

    if not os.path.exists(filepath):
        print(f"[ERROR] Dataset not found: {filepath}")
        print("[INFO]  Please run utils/feature_engineering.py first.")
        return None, None

    df = pd.read_csv(filepath)
    print(f"[INFO] Dataset shape: {df.shape} ({df.shape[0]} rows, {df.shape[1]} columns)")

    feature_cols = [c for c in df.columns if c not in DROP_COLUMNS]
    X = df[feature_cols]
    y = df['label'] if 'label' in df.columns else pd.Series([1] * len(df))

    # Fill any missing values with column mean
    X = X.fillna(X.mean())

    print(f"[INFO] Number of features: {len(feature_cols)}")
    print(f"[INFO] Label distribution: {dict(y.value_counts())}")

    return X, y


# -------------------------------------------------------
# STEP 2: Augment Data
# -------------------------------------------------------
def augment_data(X, y, target_rows=60):
    """
    If dataset is small (< target_rows), duplicate rows with
    tiny random noise to create more training samples.
    This is standard for small behavioral biometric datasets.
    """
    current_rows = len(X)
    if current_rows >= target_rows:
        return X, y

    print(f"[INFO] Dataset has {current_rows} rows. Augmenting to {target_rows} rows...")

    augmented_X = []
    augmented_y = []
    rows_needed = target_rows - current_rows

    for i in range(rows_needed):
        idx = np.random.randint(0, current_rows)
        row = X.iloc[idx].copy().astype(float)
        noise = np.random.normal(0, 0.005, size=len(row))
        row = row + (row.abs() * noise)
        augmented_X.append(row)
        augmented_y.append(int(y.iloc[idx]))

    X_aug = pd.DataFrame(augmented_X, columns=X.columns)
    y_aug = pd.Series(augmented_y)

    X_final = pd.concat([X, X_aug], ignore_index=True)
    y_final = pd.concat([y, y_aug], ignore_index=True)

    print(f"[INFO] Dataset augmented to {len(X_final)} rows.")
    return X_final, y_final


# -------------------------------------------------------
# STEP 3: Create Synthetic Intruder Samples
# -------------------------------------------------------
def add_intruder_samples(X, y):
    """
    For supervised models (Random Forest, SVM) we need BOTH classes:
    class 1 = you (authorized), class 0 = intruder.

    Since we don't have real intruder data, we generate synthetic
    intruder samples by shifting your behavioral patterns significantly.
    This simulates someone with different typing/mouse behavior.
    """
    print("[INFO] Generating synthetic intruder samples for supervised training...")

    n_intruders = len(X) // 2   # Add half as many intruder rows

    intruder_X = X.copy().sample(n=n_intruders, replace=True, random_state=RANDOM_STATE)
    intruder_X = intruder_X.reset_index(drop=True).astype(float)

    # Shift intruder behavior significantly (different person = different stats)
    for col in intruder_X.columns:
        col_mean = intruder_X[col].mean()
        # Random shift: either much faster or much slower
        shift_factor = np.random.choice([-1, 1]) * np.random.uniform(0.4, 0.8)
        intruder_X[col] = intruder_X[col] + (col_mean * shift_factor)
        # Add extra noise
        intruder_X[col] += np.random.normal(0, abs(col_mean) * 0.1, n_intruders)

    intruder_y = pd.Series([0] * n_intruders)  # Label 0 = intruder

    X_combined = pd.concat([X, intruder_X], ignore_index=True)
    y_combined = pd.concat([y, intruder_y], ignore_index=True)

    print(f"[INFO] Total samples after adding intruders: {len(X_combined)}")
    print(f"[INFO] Class distribution: {dict(y_combined.value_counts())}")

    return X_combined, y_combined


# -------------------------------------------------------
# STEP 4: Train Random Forest
# -------------------------------------------------------
def train_random_forest(X_train, X_test, y_train, y_test):
    """
    Random Forest: An ensemble of 100 decision trees.
    Each tree votes → majority wins.
    Great for finding non-linear behavioral patterns.
    """
    print("\n[MODEL 1] Training Random Forest...")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        random_state=RANDOM_STATE,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    pre = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    rec = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1  = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {pre:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1 Score  : {f1:.4f}")

    return model, acc


# -------------------------------------------------------
# STEP 5: Train SVM
# -------------------------------------------------------
def train_svm(X_train, X_test, y_train, y_test):
    """
    Support Vector Machine: Finds the optimal hyperplane
    that separates authorized user from intruder behavior.
    Uses RBF kernel for non-linear separation.
    """
    print("\n[MODEL 2] Training Support Vector Machine (SVM)...")

    model = SVC(
        kernel='rbf',
        C=1.0,
        probability=True,
        random_state=RANDOM_STATE,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    pre = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    rec = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1  = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {pre:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1 Score  : {f1:.4f}")

    return model, acc


# -------------------------------------------------------
# STEP 6: Train Isolation Forest
# -------------------------------------------------------
def train_isolation_forest(X_train, X_test, y_test):
    """
    Isolation Forest: Unsupervised anomaly detection.
    Trained ONLY on authorized user data.
    Flags behavior that deviates too much as an intruder.
    Output: 1 = normal (you), -1 = anomaly → converted to 0.
    """
    print("\n[MODEL 3] Training Isolation Forest (Anomaly Detection)...")

    # Train ONLY on authorized samples (label=1)
    model = IsolationForest(
        n_estimators=100,
        contamination=0.1,
        random_state=RANDOM_STATE
    )
    model.fit(X_train)

    y_pred_raw = model.predict(X_test)
    y_pred = np.where(y_pred_raw == 1, 1, 0)

    acc = accuracy_score(y_test, y_pred)
    pre = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    rec = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1  = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {pre:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1 Score  : {f1:.4f}")

    return model, acc


# -------------------------------------------------------
# STEP 7: Save Best Model
# -------------------------------------------------------
def save_model(model, scaler, model_name, accuracy, feature_names):
    """
    Saves the best model and scaler to disk using Joblib.
    Also saves model metadata to model_info.json.
    """
    os.makedirs("models", exist_ok=True)

    joblib.dump(model, MODEL_SAVE_PATH)
    joblib.dump(scaler, SCALER_SAVE_PATH)

    info = {
        'best_model':    model_name,
        'accuracy':      round(accuracy, 4),
        'trained_on':    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'feature_names': feature_names
    }
    with open('models/model_info.json', 'w') as f:
        json.dump(info, f, indent=4)

    print(f"\n[SAVED] Model     : models/best_model.pkl")
    print(f"[SAVED] Scaler    : models/scaler.pkl")
    print(f"[SAVED] Info      : models/model_info.json")


# -------------------------------------------------------
# MAIN: Full Training Pipeline
# -------------------------------------------------------
def run_pipeline():
    print("\n" + "=" * 55)
    print("   BEHAVIORAL AUTHENTICATION - ML TRAINING PIPELINE")
    print("=" * 55)

    # --- Load data ---
    X, y = load_data(DATASET_PATH)
    if X is None:
        return

    feature_names = list(X.columns)

    # --- Augment if small dataset ---
    X, y = augment_data(X, y, target_rows=60)

    # --- Scale features (mean=0, std=1) ---
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X),
        columns=X.columns
    )

    # --- For supervised models: add synthetic intruder samples ---
    X_super, y_super = add_intruder_samples(X_scaled, y)

    # --- Split: supervised (RF + SVM) ---
    X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(
        X_super, y_super,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y_super
    )

    # --- Split: unsupervised (Isolation Forest) - only authorized data ---
    X_auth = X_scaled[y.values == 1]
    X_train_u, X_test_u = train_test_split(
        X_auth, test_size=0.2, random_state=RANDOM_STATE
    )
    # Test with mixed data
    _, X_test_mixed, _, y_test_mixed = train_test_split(
        X_super, y_super,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y_super
    )

    print(f"\n[INFO] Training set size : {len(X_train_s)} rows")
    print(f"[INFO] Testing set size  : {len(X_test_s)} rows")

    # --- Train all 3 models ---
    rf_model,  rf_acc  = train_random_forest(X_train_s, X_test_s, y_train_s, y_test_s)
    svm_model, svm_acc = train_svm(X_train_s, X_test_s, y_train_s, y_test_s)
    if_model,  if_acc  = train_isolation_forest(X_train_u, X_test_mixed, y_test_mixed)

    # --- Compare all models ---
    results = {
        'Random Forest':    (rf_model,  rf_acc),
        'SVM':              (svm_model, svm_acc),
        'Isolation Forest': (if_model,  if_acc),
    }

    print("\n========== MODEL COMPARISON ==========")
    for name, (_, acc) in results.items():
        bar = '█' * int(acc * 20)
        print(f"  {name:<20} : {acc:.4f}  {bar}")

    best_name  = max(results, key=lambda k: results[k][1])
    best_model, best_acc = results[best_name]

    print(f"\n[WINNER] Best Model : {best_name}")
    print(f"[WINNER] Accuracy   : {best_acc:.4f} ({best_acc*100:.1f}%)")

    # --- Save best model ---
    save_model(best_model, scaler, best_name, best_acc, feature_names)

    print("\n[DONE] ML Pipeline complete!")
    print("[INFO] Your trained model is ready for the authentication engine.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run_pipeline()