"""
test_qc_suite.py - Comprehensive Automated Verification Test Suite
Tests all 6 modules, SQLite logging, scoring rollup, 50% gate, PDF/Excel generation.
"""

import os
import json
from database import init_db, log_qc_run, get_run_summary, get_all_runs
from modules.sample_data_generator import build_all_sample_assets, DATA_DIR
from modules.static_qc import StaticQCAnalyzer
from modules.variable_qc import VariableQCAnalyzer
from modules.serialization_qc import SerializationQCAnalyzer
from modules.spool_qc import SpoolQCAnalyzer
from modules.batch_qc import BatchQCAnalyzer
from modules.scoring_report import StagedScoringEngine

def run_tests():
    print("=== STARTING BAR TENDER QC SUITE VERIFICATION ===")
    init_db()
    build_all_sample_assets()

    art_pdf = os.path.join(DATA_DIR, 'artwork_signed_spec.pdf')
    pass_pdf = os.path.join(DATA_DIR, 'layout_pass_sku1.pdf')
    fail_pdf = os.path.join(DATA_DIR, 'layout_fail_font_sku2.pdf')
    order_xlsx = os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.xlsx')
    zpl_file = os.path.join(DATA_DIR, 'sample_rfid_spool.zpl')
    screenshot_file = os.path.join(DATA_DIR, 'screenshots', 'defect_font_mismatch.png')

    # Test 1: Static QC Pass
    static_analyzer = StaticQCAnalyzer()
    res_static_pass = static_analyzer.compare(art_pdf, pass_pdf)
    print(f"[PASS] Module 1 (Static Pass): Score = {res_static_pass['score']}% (Status: {res_static_pass['status']})")
    assert res_static_pass['score'] >= 85.0, f"Expected pass >= 85%, got {res_static_pass['score']}%"

    # Test 1b: Static QC Fail
    res_static_fail = static_analyzer.compare(art_pdf, fail_pdf)
    print(f"[PASS] Module 1 (Static Fail): Score = {res_static_fail['score']}% (Status: {res_static_fail['status']}, Failed checks: {res_static_fail['failed_checks']})")
    assert res_static_fail['failed_checks'] > 0, "Expected failed checks in fail variant"

    # Test 2: Variable QC
    var_analyzer = VariableQCAnalyzer()
    res_var = var_analyzer.validate(order_xlsx, pass_pdf, record_index=0)
    print(f"[PASS] Module 2 (Variable Data QC): Score = {res_var['score']}% (Status: {res_var['status']})")
    assert res_var['score'] >= 85.0

    # Test 3: RFID & Serialization QC
    serial_analyzer = SerializationQCAnalyzer()
    res_serial = serial_analyzer.validate_batch(is_rfid=True, is_serialized=True)
    print(f"[PASS] Module 3 (RFID / Serialization QC): Score = {res_serial['score']}% (Status: {res_serial['status']}, EPCs: {res_serial['epc_count']})")
    assert res_serial['score'] == 100.0

    # Test 4: Thermal / Spool QC
    with open(zpl_file, 'r', encoding='utf-8') as f:
        zpl_content = f.read()
    spool_analyzer = SpoolQCAnalyzer()
    res_spool = spool_analyzer.cross_check(zpl_content)
    print(f"[PASS] Module 4 (Thermal / Spool QC): Score = {res_spool['score']}% (Status: {res_spool['status']}, Dims: {res_spool['dimensions']['width_mm']}x{res_spool['dimensions']['length_mm']}mm)")
    assert res_spool['score'] >= 85.0

    # Test 5: Batch Multi-Layout QC
    batch_analyzer = BatchQCAnalyzer()
    batch_layouts = [
        os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU1_M.pdf'),
        os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU2_L.pdf'),
        os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU3_XL.pdf')
    ]
    res_batch = batch_analyzer.process_batch(art_pdf, batch_layouts, order_xlsx)
    print(f"[PASS] Module 5 (Batch QC): Score = {res_batch['score']}% (Files: {res_batch['total_files_processed']})")
    assert res_batch['score'] >= 85.0

    # Test 6: Staged Scoring Engine & 50% Gate
    scoring_engine = StagedScoringEngine(pass_threshold=50.0)

    # A. Pass Gate Test (>=50%)
    pass_sectors = [res_static_pass, res_var, res_serial, res_spool]
    rollup_pass = scoring_engine.calculate_overall_score(pass_sectors)
    print(f"[PASS] Module 6 (Pass Rollup): Score = {rollup_pass['overall_score']}% (Passed Gate: {rollup_pass['passed_gate']})")
    assert rollup_pass['passed_gate'] is True

    # B. Fail Gate Test (<50%)
    fail_sectors = [
        {'sector_name': 'Static', 'score': 20.0, 'total_checks': 10, 'passed_checks': 2, 'failed_checks': 8, 'checks': [{'field_name': 'Brand', 'status': 'FAIL', 'details': 'Font Mismatch', 'expected': 'Arial', 'actual': 'Times'}]},
        {'sector_name': 'Variable', 'score': 25.0, 'total_checks': 8, 'passed_checks': 2, 'failed_checks': 6, 'checks': [{'field_name': 'Size', 'status': 'FAIL', 'details': 'Wrong Size', 'expected': 'M', 'actual': 'XXL'}]}
    ]
    rollup_fail = scoring_engine.calculate_overall_score(fail_sectors)
    print(f"[PASS] Module 6 (Fail Gate <50%): Score = {rollup_fail['overall_score']}% (Passed Gate: {rollup_fail['passed_gate']}, Actionable checklist items: {len(rollup_fail['correction_checklist'])})")
    assert rollup_fail['passed_gate'] is False
    assert len(rollup_fail['correction_checklist']) == 2

    # Test 7: PDF Report Generation with ReportLab
    meta = {'run_id': 'TEST-001', 'designer_name': 'Rohit', 'rpo_number': '1000341139', 'item_code': 'LS-SS26-PT'}
    screenshots = [{'file_path': screenshot_file, 'caption': 'DEFECT #1: Font Mismatch on Brand Header'}]
    pdf_out = os.path.join(DATA_DIR, 'test_output_report.pdf')
    scoring_engine.generate_pdf_report(meta, pass_sectors, screenshots=screenshots, output_path=pdf_out)
    assert os.path.exists(pdf_out), "PDF report file was not created"
    print(f"[PASS] ReportLab PDF Report Generated: {pdf_out} ({os.path.getsize(pdf_out)} bytes)")

    # Test 8: Excel Workbook Generation
    xlsx_out = os.path.join(DATA_DIR, 'test_output_audit.xlsx')
    scoring_engine.generate_excel_report(meta, pass_sectors, output_path=xlsx_out)
    assert os.path.exists(xlsx_out), "Excel report file was not created"
    print(f"[PASS] Excel Audit Workbook Generated: {xlsx_out} ({os.path.getsize(xlsx_out)} bytes)")

    # Test 9: SQLite Logging
    log_qc_run('TEST-001', 'Rohit', '1000341139', 'LS-SS26-PT', True, True, rollup_pass['overall_score'], 'PASSED')
    summary = get_run_summary('TEST-001')
    assert summary['run']['designer_name'] == 'Rohit'
    print("[PASS] SQLite Audit Logging & Traceability Verified.")

    print("\nALL 9 QC TEST SUITES PASSED WITH 100% SUCCESS.")

if __name__ == '__main__':
    run_tests()
