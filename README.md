# r-pac Layout Analysis Tools — BarTender Layout QC Suite

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.0%2B-green.svg)](https://flask.palletsprojects.com)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

A comprehensive pre-production Quality Control (QC) web automation platform that validates BarTender-generated label layouts (Production Proof PDF or ZPL thermal print spool) against customer-signed artwork PDFs and live order data (Excel/CSV) **before** going to physical production.

---

## 🌟 Key Capabilities & Modules

- **Module 1 — Static Artwork vs Layout QC:** Field-by-field verification of font families, point sizes, PMS Black color disclaimer matching, X/Y placement bounding box tolerances, dielines (25x60mm), inlay specifications (R-BOOST M830), and Fixed vs Variable mandatory field checks.
- **Module 2 — Visual Difference Inspector:** Side-by-side visual diff overlay with an interactive split-screen swipe slider, layer opacity controls, and green/red anomaly bounding boxes.
- **Module 3 — Variable Data & Field Mapping QC:** Order Excel (`.xlsx`) and CSV parser, downloadable mapping Excel template, custom column mapping uploader, and per-record/per-field discrepancy detection (`Size`, `Article`, `Color`, `RPO`, `SKU`, `QTY`).
- **Module 4 — RFID & Serialization QC:** RFID vs Non-RFID mode, Serialized vs Non-Serialized mode, GS1 SGTIN-96 96-bit binary parser (Header 0x30, Filter, Partition, Prefix, Item Ref, Serial), duplicate EPC scanner, and sequence gap detector.
- **Module 5 — Thermal Spool Preview & 3-Way Cross-Check:** ZPL spool parsing (`^FO`, `^FD`, `^BC`, `^BQ`, `^RFW`, `^PW`, `^LL`), auto-detected dimensions badge, live Labelary cloud + local thermal rendering engine, and 3-way cross-check.
- **Module 6 — Batch Multi-Layout QC:** Simultaneous multi-SKU batch execution across all SKU layout files for an RPO with consolidated summary matrix.
- **Module 7 — Final AI QC Stage & 50% Quality Gate:**
  - Real-time sector score rollup.
  - **Score < 50% (Locked):** Blocks PDF report generation and displays an **Actionable Corrective Checklist** with specific guidance on how to fix the issue in BarTender before re-testing.
  - **Score ≥ 50% (Unlocked):** Unlocks the **Defect Screenshot Uploader** and generates downloadable **Executive PDF QC Reports** (ReportLab) with embedded screenshots, as well as Excel audit workbooks.
- **Module 8 — SQLite Audit History:** Searchable, persistent log of all QC runs, designer sign-offs, and batch statuses.

---

## 🚀 Quick Start Guide

### 1. Installation

Clone the repository and install required dependencies:

```bash
git clone https://github.com/rohitmali9860-web/QC_TOLL.git
cd QC_TOLL
pip install -r requirements.txt
```

### 2. Run Automated Verification Tests

Run the full automated test suite covering all 6 modules:

```bash
python test_qc_suite.py
```

### 3. Launch Web Application

Start the local Flask development server:

```bash
python app.py
```

Open your browser at: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 📁 Project Architecture

```
QC_TOLL/
├── app.py                      # Flask backend API & routing
├── database.py                 # SQLite schema & audit logging
├── requirements.txt            # Python dependencies
├── README.md                   # Documentation
├── test_qc_suite.py            # Automated 9-point verification suite
│
├── modules/
│   ├── static_qc.py            # Module 1: Layout & artwork analysis
│   ├── variable_qc.py          # Module 2: Order data & mapping engine
│   ├── serialization_qc.py     # Module 3: SGTIN-96 EPC & serial validator
│   ├── spool_qc.py             # Module 4: Thermal ZPL parser & renderer
│   ├── batch_qc.py             # Module 5: Multi-SKU batch executor
│   ├── scoring_report.py       # Module 6: Staged scoring & PDF/Excel generator
│   └── sample_data_generator.py # Test asset & demo data builder
│
├── static/
│   ├── css/
│   │   └── style.css           # r-pac Design System stylesheet
│   ├── js/
│   │   └── app.js              # State management & visual diff controller
│   └── img/                    # Static assets & placeholders
│
├── templates/
│   └── index.html              # Multi-tab r-pac Layout Analysis Suite UI
│
├── sample_data/                # Sample artwork PDFs, layouts, orders, ZPL
├── uploads/                    # Temporary uploaded files
└── generated_reports/          # Generated PDF & Excel certificates
```

---

## 📄 License & Attribution

© 2026 r-pac International Corp. All rights reserved. Powered by AI.
