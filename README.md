# 🏷️ r-pac Layout Analysis & BarTender QC Automation Suite

[![Build & Test CI](https://github.com/rohitmali9860-web/QC_TOLL/actions/workflows/qc_ci.yml/badge.svg)](https://github.com/rohitmali9860-web/QC_TOLL/actions/workflows/qc_ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![r-pac AI Powered](https://img.shields.io/badge/r--pac-AI%20Powered-00285e.svg)](https://layoutqc.r-pac.com/)

> **Industrial-grade Automated Quality Control (QC) & Template Comparison Suite** replicating the internal **r-pac Layout Analysis Suite** (`https://layoutqc.r-pac.com/`) with BarTender production extensions.

---

## 🌟 Key Application Pages

| Module | Route / Page | Description | Key Tech |
| :--- | :--- | :--- | :--- |
| 🏠 **Home Portal** | `/home.html` or `/` | Central multi-tool navigation hub with user badge & role management | HTML5, CSS Grid |
| 🔍 **Template Comparison** | `/template_compare.html` | Field-by-field position scoring ($\pm 0-15\text{pt}$ tolerance) & pixel density blur difference | PyMuPDF, OpenCV |
| 👁️ **Visual Diff** | `/compare.html` | Side-by-side visual difference overlay with layer opacity controls | OpenCV, Canvas |
| ✨ **Design AI QC** | `/design_ai_qc.html` | Full 6-module BarTender workflow with 50% pass gate & PDF certificate export | ReportLab, OpenPyXL |
| ⚡ **R-Print Performance** | `/design_ai_qc.html` | Thermal ZPL spool simulator and print engine throughput analytics | Regex, Pillow |

---

## 🚀 Quickstart Guide

### 1. Clone & Setup
```bash
git clone https://github.com/rohitmali9860-web/QC_TOLL.git
cd QC_TOLL
pip install -r requirements.txt
```

### 2. Launch Local Server
```bash
# Windows
run.bat

# Linux / macOS
chmod +x run.sh && ./run.sh

# Or directly with Python
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🧪 Testing & Verification

Run the comprehensive test suites:
```bash
# Run 9 core BarTender QC suites
python test_qc_suite.py

# Run Template Layout Comparison unit tests
python test_template_compare.py

# Run latency & throughput benchmarks
python scripts/benchmark_performance.py
```

---

## 🐳 Docker Deployment

```bash
docker-compose up -d --build
```
Access the application at `http://localhost:5000`.

---

## 📄 License & Attribution
Developed for **r-pac International** • *Bring Identity to Life™*
