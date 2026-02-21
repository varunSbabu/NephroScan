"""
CKD Prediction System - Database Layer
SQLite-backed storage for users, patients, and predictions.
"""

import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "ckd_clinical.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Create all tables and seed default users."""
    conn = get_connection()
    c = conn.cursor()

    # ── Users table ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,          -- SHA-256 hash
            full_name   TEXT,
            role        TEXT    DEFAULT 'doctor',  -- admin | doctor | nurse
            email       TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Patients table ───────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id        TEXT    UNIQUE NOT NULL,
            mrn               TEXT,
            first_name        TEXT    NOT NULL,
            last_name         TEXT    NOT NULL,
            date_of_birth     TEXT,
            age               INTEGER,
            gender            TEXT,
            blood_group       TEXT,
            phone             TEXT,
            email             TEXT,
            address           TEXT,
            city              TEXT,
            state             TEXT,
            physician         TEXT,
            department        TEXT,
            registered_by     TEXT,   -- username of the registering provider
            registration_date TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Predictions table ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      TEXT    NOT NULL,
            prediction_date TEXT    DEFAULT (datetime('now')),
            ensemble_result TEXT,
            ensemble_conf   REAL,
            ckd_detected    INTEGER,   -- 1 = CKD, 0 = No CKD
            model_results   TEXT,      -- JSON blob of all 9 model results
            medical_params  TEXT,      -- JSON blob of input parameters
            performed_by    TEXT       -- username
        )
    """)

    conn.commit()

    # ── Seed default users (only if table is empty) ──────────────────────────
    count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        default_users = [
            ("admin",  hash_password("admin123"),  "System Administrator", "admin",  "admin@ckd-clinic.com"),
            ("doctor", hash_password("doctor123"), "Dr. Alex Johnson",     "doctor", "doctor@ckd-clinic.com"),
            ("nurse",  hash_password("nurse123"),  "Nurse Patricia Lee",   "nurse",  "nurse@ckd-clinic.com"),
        ]
        c.executemany(
            "INSERT INTO users (username, password, full_name, role, email) VALUES (?,?,?,?,?)",
            default_users
        )
        conn.commit()

    conn.close()


# ── User operations ─────────────────────────────────────────────────────────

def authenticate_user(username: str, password: str):
    """Return user row on success, None on failure."""
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, hash_password(password))
    ).fetchone()
    conn.close()
    return dict(user) if user else None


def get_all_users():
    conn = get_connection()
    rows = conn.execute("SELECT id, username, full_name, role, email, created_at FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_user(username, password, full_name, role, email):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, full_name, role, email) VALUES (?,?,?,?,?)",
            (username, hash_password(password), full_name, role, email)
        )
        conn.commit()
        return True, "User created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def change_password(username, old_password, new_password):
    conn = get_connection()
    user = conn.execute(
        "SELECT id FROM users WHERE username = ? AND password = ?",
        (username, hash_password(old_password))
    ).fetchone()
    if not user:
        conn.close()
        return False, "Current password is incorrect."
    conn.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (hash_password(new_password), username)
    )
    conn.commit()
    conn.close()
    return True, "Password changed successfully."


# ── Patient operations ───────────────────────────────────────────────────────

def save_patient(data: dict, registered_by: str):
    """Insert a patient record. Returns (True, patient_id) or (False, error_msg)."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO patients
              (patient_id, mrn, first_name, last_name, date_of_birth, age, gender,
               blood_group, phone, email, address, city, state, physician,
               department, registered_by)
            VALUES
              (:patient_id, :mrn, :first_name, :last_name, :date_of_birth, :age, :gender,
               :blood_group, :phone, :email, :address, :city, :state, :physician,
               :department, :registered_by)
        """, {**data, "registered_by": registered_by})
        conn.commit()
        return True, data["patient_id"]
    except sqlite3.IntegrityError:
        return False, f"Patient ID '{data['patient_id']}' already exists."
    finally:
        conn.close()


def get_patient(patient_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_patients():
    conn = get_connection()
    rows = conn.execute(
        "SELECT patient_id, first_name, last_name, age, gender, physician, registration_date FROM patients ORDER BY registration_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_patient(patient_id: str, data: dict):
    """Update editable fields for an existing patient. Admin only."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE patients SET
                first_name=:first_name, last_name=:last_name, age=:age,
                gender=:gender, blood_group=:blood_group, phone=:phone,
                email=:email, address=:address, city=:city, state=:state,
                physician=:physician, department=:department
            WHERE patient_id=:patient_id
        """, {**data, "patient_id": patient_id})
        conn.commit()
        return True, "Patient updated successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_patient(patient_id: str):
    """Delete patient and all associated predictions. Admin only."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM predictions WHERE patient_id=?", (patient_id,))
        conn.execute("DELETE FROM patients WHERE patient_id=?", (patient_id,))
        conn.commit()
        return True, "Patient and all associated records deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_user(username: str):
    """Delete a user account. Admin only; cannot delete own account."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        return True, f"User '{username}' deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def update_user(username: str, full_name: str, role: str, email: str):
    """Update user details. Admin only."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET full_name=?, role=?, email=? WHERE username=?",
            (full_name, role, email, username)
        )
        conn.commit()
        return True, "User updated successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# ── Prediction operations ───────────────────────────────────────────────────

def save_prediction(patient_id, ensemble_result, ensemble_conf, ckd_detected,
                    model_results_json, medical_params_json, performed_by):
    import json
    conn = get_connection()
    conn.execute("""
        INSERT INTO predictions
          (patient_id, ensemble_result, ensemble_conf, ckd_detected,
           model_results, medical_params, performed_by)
        VALUES (?,?,?,?,?,?,?)
    """, (patient_id, ensemble_result, ensemble_conf, ckd_detected,
          model_results_json, medical_params_json, performed_by))
    conn.commit()
    conn.close()


def get_patient_predictions(patient_id: str):
    import json
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM predictions WHERE patient_id = ? ORDER BY prediction_date DESC",
        (patient_id,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["model_results"] = json.loads(d["model_results"])
            d["medical_params"] = json.loads(d["medical_params"])
        except Exception:
            pass
        results.append(d)
    return results


def get_summary_stats():
    """Return quick stats for the dashboard."""
    conn = get_connection()
    total_patients  = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    total_preds     = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    ckd_positive    = conn.execute("SELECT COUNT(*) FROM predictions WHERE ckd_detected=1").fetchone()[0]
    total_users     = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return {
        "total_patients": total_patients,
        "total_predictions": total_preds,
        "ckd_positive": ckd_positive,
        "total_users": total_users,
    }


# Initialise on import
init_db()
