"""
database.py - SQLite Database Management for BarTender Layout QC Suite
Handles audit trails, sector scores, field findings, mapping templates, and settings.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'bartender_qc.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if not already present."""
    conn = get_db()
    cursor = conn.cursor()

    # QC Runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qc_runs (
            id TEXT PRIMARY KEY,
            designer_name TEXT NOT NULL,
            rpo_number TEXT NOT NULL,
            item_code TEXT NOT NULL,
            is_rfid INTEGER DEFAULT 1,
            is_serialized INTEGER DEFAULT 1,
            overall_score REAL DEFAULT 0.0,
            status TEXT DEFAULT 'IN_PROGRESS',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            notes TEXT
        )
    ''')

    # Sector Scores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sector_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            sector_name TEXT NOT NULL,
            score REAL NOT NULL,
            total_checks INTEGER NOT NULL,
            passed_checks INTEGER NOT NULL,
            failed_checks INTEGER NOT NULL,
            status TEXT NOT NULL,
            details_json TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES qc_runs(id)
        )
    ''')

    # QC Findings / Issues table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qc_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            sector_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            check_type TEXT NOT NULL,
            expected_val TEXT,
            actual_val TEXT,
            status TEXT NOT NULL,
            severity TEXT DEFAULT 'HIGH',
            correction_instruction TEXT,
            is_fixed INTEGER DEFAULT 0,
            FOREIGN KEY (run_id) REFERENCES qc_runs(id)
        )
    ''')

    # Mapping Templates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mapping_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            mapping_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # Screenshot Attachments for Problem Areas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screenshot_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            finding_id INTEGER,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            caption TEXT,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES qc_runs(id)
        )
    ''')

    # Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Set default settings if not exists
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('pass_threshold', '50')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('company_name', 'r-pac International')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('xy_tolerance_mm', '0.5')")

    conn.commit()
    conn.close()

def log_qc_run(run_id, designer_name, rpo_number, item_code, is_rfid, is_serialized, overall_score, status, notes=""):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT OR REPLACE INTO qc_runs (id, designer_name, rpo_number, item_code, is_rfid, is_serialized, overall_score, status, created_at, completed_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM qc_runs WHERE id=?), ?), ?, ?)
    ''', (run_id, designer_name, rpo_number, item_code, 1 if is_rfid else 0, 1 if is_serialized else 0, overall_score, status, run_id, now, now, notes))
    conn.commit()
    conn.close()

def save_sector_score(run_id, sector_name, score, total_checks, passed_checks, failed_checks, status, details=None):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details_json = json.dumps(details or {})
    
    cursor.execute('DELETE FROM sector_scores WHERE run_id = ? AND sector_name = ?', (run_id, sector_name))
    cursor.execute('''
        INSERT INTO sector_scores (run_id, sector_name, score, total_checks, passed_checks, failed_checks, status, details_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, sector_name, score, total_checks, passed_checks, failed_checks, status, details_json, now))
    conn.commit()
    conn.close()

def save_finding(run_id, sector_name, field_name, check_type, expected_val, actual_val, status, severity='HIGH', instruction=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO qc_findings (run_id, sector_name, field_name, check_type, expected_val, actual_val, status, severity, correction_instruction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, sector_name, field_name, check_type, str(expected_val), str(actual_val), status, severity, instruction))
    conn.commit()
    conn.close()

def get_run_summary(run_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM qc_runs WHERE id = ?', (run_id,))
    run = cursor.fetchone()
    
    cursor.execute('SELECT * FROM sector_scores WHERE run_id = ?', (run_id,))
    sectors = cursor.fetchall()
    
    cursor.execute('SELECT * FROM qc_findings WHERE run_id = ?', (run_id,))
    findings = cursor.fetchall()
    
    cursor.execute('SELECT * FROM screenshot_attachments WHERE run_id = ?', (run_id,))
    screenshots = cursor.fetchall()
    
    conn.close()
    
    return {
        'run': dict(run) if run else None,
        'sectors': [dict(s) for s in sectors],
        'findings': [dict(f) for f in findings],
        'screenshots': [dict(s) for s in screenshots]
    }

def get_all_runs(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM qc_runs ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_setting(key, default=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()
