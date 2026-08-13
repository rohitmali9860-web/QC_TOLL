"""
app.py - BarTender Layout QC Automation Tool (r-pac Style)
Main Flask backend providing RESTful endpoints for all 6 QC modules,
database tracking, PDF/Excel generation, and live interactive UI serving.
"""

import os
import io
import uuid
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename

from database import init_db, log_qc_run, save_sector_score, save_finding, get_run_summary, get_all_runs, get_setting, set_setting
from modules.static_qc import StaticQCAnalyzer
from modules.variable_qc import VariableQCAnalyzer
from modules.serialization_qc import SerializationQCAnalyzer
from modules.spool_qc import SpoolQCAnalyzer
from modules.batch_qc import BatchQCAnalyzer
from modules.scoring_report import StagedScoringEngine
from modules.sample_data_generator import build_all_sample_assets, DATA_DIR

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
REPORTS_DIR = os.path.join(BASE_DIR, 'generated_reports')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload

# Initialize database and ensure sample fixtures exist
init_db()
if not os.path.exists(os.path.join(DATA_DIR, 'artwork_signed_spec.pdf')):
    build_all_sample_assets()

# Instantiate Analyzers
static_analyzer = StaticQCAnalyzer()
variable_analyzer = VariableQCAnalyzer()
serialization_analyzer = SerializationQCAnalyzer()
spool_analyzer = SpoolQCAnalyzer()
batch_analyzer = BatchQCAnalyzer()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/demo-data', methods=['GET'])
def get_demo_data():
    """Returns sample file references and default metadata for one-click testing."""
    return jsonify({
        'status': 'success',
        'active_rpo': '1000341139',
        'designer_name': 'Rohit',
        'item_code': 'LS-SS26-PT',
        'artwork_file': os.path.join(DATA_DIR, 'artwork_signed_spec.pdf'),
        'layout_pass_file': os.path.join(DATA_DIR, 'layout_pass_sku1.pdf'),
        'layout_fail_file': os.path.join(DATA_DIR, 'layout_fail_font_sku2.pdf'),
        'order_csv_file': os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.csv'),
        'order_xlsx_file': os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.xlsx'),
        'mapping_xlsx_file': os.path.join(DATA_DIR, 'mapping_template_standard.xlsx'),
        'zpl_spool_file': os.path.join(DATA_DIR, 'sample_rfid_spool.zpl'),
        'sample_screenshot': os.path.join(DATA_DIR, 'screenshots', 'defect_font_mismatch.png'),
        'batch_layouts': [
            os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU1_M.pdf'),
            os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU2_L.pdf'),
            os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU3_XL.pdf')
        ]
    })

# --- MODULE 1: STATIC ARTWORK QC ---
@app.route('/api/qc/static', methods=['POST'])
def qc_static():
    try:
        run_id = request.form.get('run_id', str(uuid.uuid4())[:8])
        artwork_file = request.files.get('artwork_pdf')
        layout_file = request.files.get('layout_pdf')
        use_demo = request.form.get('use_demo') == 'true'
        fail_variant = request.form.get('fail_variant') == 'true'

        if use_demo:
            art_path = os.path.join(DATA_DIR, 'artwork_signed_spec.pdf')
            lay_path = os.path.join(DATA_DIR, 'layout_fail_font_sku2.pdf' if fail_variant else 'layout_pass_sku1.pdf')
        else:
            if not artwork_file or not layout_file:
                return jsonify({'status': 'error', 'message': 'Artwork PDF and Layout PDF are required.'}), 400
            art_path = os.path.join(UPLOAD_DIR, f"{run_id}_art_{secure_filename(artwork_file.filename)}")
            lay_path = os.path.join(UPLOAD_DIR, f"{run_id}_lay_{secure_filename(layout_file.filename)}")
            artwork_file.save(art_path)
            layout_file.save(lay_path)

        result = static_analyzer.compare(art_path, lay_path)
        
        # Save to DB
        save_sector_score(
            run_id, 'Static Artwork QC', result['score'],
            result['total_checks'], result['passed_checks'], result['failed_checks'],
            result['status'], result
        )

        return jsonify({'status': 'success', 'run_id': run_id, 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- MODULE 2: VARIABLE DATA & MAPPING QC ---
@app.route('/api/qc/variable', methods=['POST'])
def qc_variable():
    try:
        run_id = request.form.get('run_id', str(uuid.uuid4())[:8])
        order_file = request.files.get('order_file')
        layout_file = request.files.get('layout_pdf')
        mapping_file = request.files.get('mapping_file')
        mapping_json_str = request.form.get('mapping_json')
        record_idx = int(request.form.get('record_index', 0))
        use_demo = request.form.get('use_demo') == 'true'
        fail_variant = request.form.get('fail_variant') == 'true'

        if use_demo:
            order_path = os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.xlsx')
            lay_path = os.path.join(DATA_DIR, 'layout_fail_font_sku2.pdf' if fail_variant else 'layout_pass_sku1.pdf')
            custom_map = None
        else:
            if not order_file or not layout_file:
                return jsonify({'status': 'error', 'message': 'Order file (CSV/XLSX) and Layout PDF are required.'}), 400
            order_path = os.path.join(UPLOAD_DIR, f"{run_id}_order_{secure_filename(order_file.filename)}")
            lay_path = os.path.join(UPLOAD_DIR, f"{run_id}_lay_var_{secure_filename(layout_file.filename)}")
            order_file.save(order_path)
            layout_file.save(lay_path)

            custom_map = None
            if mapping_file:
                map_path = os.path.join(UPLOAD_DIR, f"{run_id}_map_{secure_filename(mapping_file.filename)}")
                mapping_file.save(map_path)
                custom_map = variable_analyzer.parse_mapping_file(map_path)
            elif mapping_json_str:
                custom_map = json.loads(mapping_json_str)

        result = variable_analyzer.validate(order_path, lay_path, mapping=custom_map, record_index=record_idx)

        # Save to DB
        save_sector_score(
            run_id, 'Variable Data & Mapping QC', result['score'],
            result['total_checks'], result['passed_checks'], result['failed_checks'],
            result['status'], result
        )

        return jsonify({'status': 'success', 'run_id': run_id, 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/qc/mapping/template', methods=['GET'])
def download_mapping_template():
    buf = variable_analyzer.generate_mapping_excel(None)
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='bartender_field_mapping_template.xlsx'
    )

# --- MODULE 3: RFID & SERIALIZATION QC ---
@app.route('/api/qc/rfid', methods=['POST'])
def qc_rfid():
    try:
        run_id = request.form.get('run_id', str(uuid.uuid4())[:8])
        is_rfid = request.form.get('is_rfid', 'true') == 'true'
        is_serialized = request.form.get('is_serialized', 'true') == 'true'
        epcs_raw = request.form.get('epcs_json')
        skus_raw = request.form.get('skus_json')
        has_errors = request.form.get('simulate_errors') == 'true'

        epc_list = json.loads(epcs_raw) if epcs_raw else None
        sku_list = json.loads(skus_raw) if skus_raw else None

        if has_errors:
            # Simulate gap & duplicate error
            epc_list = [
                "3034027780000000000003E9",  # 1001
                "3034027780000000000003E9",  # 1001 Duplicate!
                "3034027780000000000003EB",  # 1003 (Gap: 1002 missing)
                "3034027780000000000003ED"   # 1005 (Gap: 1004 missing)
            ]
            sku_list = ["1/3", "3/3"] # Missing 2/3

        result = serialization_analyzer.validate_batch(
            is_rfid=is_rfid,
            is_serialized=is_serialized,
            epc_list=epc_list,
            sku_sequences=sku_list
        )

        save_sector_score(
            run_id, 'RFID & Serialization QC', result['score'],
            result['total_checks'], result['passed_checks'], result['failed_checks'],
            result['status'], result
        )

        return jsonify({'status': 'success', 'run_id': run_id, 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- MODULE 4: THERMAL / SPOOL PREVIEW QC ---
@app.route('/api/qc/spool', methods=['POST'])
def qc_spool():
    try:
        run_id = request.form.get('run_id', str(uuid.uuid4())[:8])
        zpl_file = request.files.get('zpl_file')
        zpl_text = request.form.get('zpl_text')
        use_demo = request.form.get('use_demo') == 'true'

        if use_demo:
            with open(os.path.join(DATA_DIR, 'sample_rfid_spool.zpl'), 'r', encoding='utf-8') as f:
                zpl_content = f.read()
        elif zpl_file:
            zpl_content = zpl_file.read().decode('utf-8', errors='replace')
        elif zpl_text:
            zpl_content = zpl_text
        else:
            return jsonify({'status': 'error', 'message': 'ZPL spool file or text content is required.'}), 400

        result = spool_analyzer.cross_check(zpl_content)

        save_sector_score(
            run_id, 'Thermal / Spool Preview QC', result['score'],
            result['total_checks'], result['passed_checks'], result['failed_checks'],
            result['status'], result
        )

        return jsonify({'status': 'success', 'run_id': run_id, 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- MODULE 5: BATCH MULTI-LAYOUT QC ---
@app.route('/api/qc/batch', methods=['POST'])
def qc_batch():
    try:
        run_id = request.form.get('run_id', str(uuid.uuid4())[:8])
        use_demo = request.form.get('use_demo') == 'true'

        if use_demo:
            art_path = os.path.join(DATA_DIR, 'artwork_signed_spec.pdf')
            order_path = os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.xlsx')
            layout_paths = [
                os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU1_M.pdf'),
                os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU2_L.pdf'),
                os.path.join(DATA_DIR, 'batch_layouts', '1000341139_SKU3_XL.pdf')
            ]
        else:
            artwork_file = request.files.get('artwork_pdf')
            order_file = request.files.get('order_file')
            layout_files = request.files.getlist('layout_pdfs')

            if not artwork_file or not order_file or not layout_files:
                return jsonify({'status': 'error', 'message': 'Artwork, Order file, and batch Layout PDFs are required.'}), 400

            art_path = os.path.join(UPLOAD_DIR, f"{run_id}_batch_art_{secure_filename(artwork_file.filename)}")
            order_path = os.path.join(UPLOAD_DIR, f"{run_id}_batch_order_{secure_filename(order_file.filename)}")
            artwork_file.save(art_path)
            order_file.save(order_path)

            layout_paths = []
            for lf in layout_files:
                lp = os.path.join(UPLOAD_DIR, f"{run_id}_batch_lay_{secure_filename(lf.filename)}")
                lf.save(lp)
                layout_paths.append(lp)

        result = batch_analyzer.process_batch(art_path, layout_paths, order_path)

        save_sector_score(
            run_id, 'Batch Multi-Layout QC', result['score'],
            result['total_checks'], result['passed_checks'], result['failed_checks'],
            result['status'], result
        )

        return jsonify({'status': 'success', 'run_id': run_id, 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- MODULE 6: STAGED SCORING & REPORT GATE ---
@app.route('/api/qc/score', methods=['POST'])
def calculate_score():
    try:
        data = request.get_json() or {}
        run_id = data.get('run_id', 'RUN-001')
        sector_results = data.get('sectors', [])
        pass_threshold = float(get_setting('pass_threshold', 50.0))

        scoring_engine = StagedScoringEngine(pass_threshold=pass_threshold)
        rollup = scoring_engine.calculate_overall_score(sector_results)

        # Log run
        log_qc_run(
            run_id=run_id,
            designer_name=data.get('designer_name', 'Rohit'),
            rpo_number=data.get('rpo_number', '1000341139'),
            item_code=data.get('item_code', 'LS-SS26-PT'),
            is_rfid=data.get('is_rfid', True),
            is_serialized=data.get('is_serialized', True),
            overall_score=rollup['overall_score'],
            status=rollup['status']
        )

        return jsonify({'status': 'success', 'rollup': rollup})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/qc/screenshots/upload', methods=['POST'])
def upload_screenshot():
    try:
        run_id = request.form.get('run_id', 'RUN-001')
        caption = request.form.get('caption', 'Problem area annotation')
        img_file = request.files.get('screenshot')

        if not img_file:
            return jsonify({'status': 'error', 'message': 'No image file uploaded.'}), 400

        filename = f"{run_id}_{secure_filename(img_file.filename)}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        img_file.save(file_path)

        # Save to DB
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO screenshot_attachments (run_id, file_name, file_path, caption, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (run_id, filename, file_path, caption, now))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'file_path': file_path, 'caption': caption})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/qc/report/pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json() or {}
        run_metadata = {
            'run_id': data.get('run_id', 'RUN-001'),
            'designer_name': data.get('designer_name', 'Rohit'),
            'rpo_number': data.get('rpo_number', '1000341139'),
            'item_code': data.get('item_code', 'LS-SS26-PT'),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        sector_results = data.get('sectors', [])
        screenshots = data.get('screenshots', [])

        pass_threshold = float(get_setting('pass_threshold', 50.0))
        scoring_engine = StagedScoringEngine(pass_threshold=pass_threshold)

        # Check gate
        rollup = scoring_engine.calculate_overall_score(sector_results)
        if not rollup['passed_gate']:
            return jsonify({
                'status': 'locked',
                'message': f"QC Score {rollup['overall_score']}% is below required {pass_threshold}% threshold. Report generation is locked.",
                'correction_checklist': rollup['correction_checklist']
            }), 403

        pdf_filename = f"QC_Report_{run_metadata['rpo_number']}_{run_metadata['run_id']}.pdf"
        pdf_path = os.path.join(REPORTS_DIR, pdf_filename)
        scoring_engine.generate_pdf_report(run_metadata, sector_results, screenshots=screenshots, output_path=pdf_path)

        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=pdf_filename
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/qc/report/excel', methods=['POST'])
def generate_excel():
    try:
        data = request.get_json() or {}
        run_metadata = {
            'run_id': data.get('run_id', 'RUN-001'),
            'designer_name': data.get('designer_name', 'Rohit'),
            'rpo_number': data.get('rpo_number', '1000341139'),
            'item_code': data.get('item_code', 'LS-SS26-PT')
        }
        sector_results = data.get('sectors', [])
        scoring_engine = StagedScoringEngine()

        xlsx_filename = f"QC_Audit_{run_metadata['rpo_number']}_{run_metadata['run_id']}.xlsx"
        xlsx_path = os.path.join(REPORTS_DIR, xlsx_filename)
        scoring_engine.generate_excel_report(run_metadata, sector_results, output_path=xlsx_path)

        return send_file(
            xlsx_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=xlsx_filename
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- AUDIT & SETTINGS ---
@app.route('/api/history', methods=['GET'])
def get_history():
    runs = get_all_runs(limit=100)
    return jsonify({'status': 'success', 'runs': runs})

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.get_json() or {}
        for k, v in data.items():
            set_setting(k, v)
        return jsonify({'status': 'success', 'message': 'Settings updated.'})
    else:
        return jsonify({
            'pass_threshold': get_setting('pass_threshold', '50'),
            'company_name': get_setting('company_name', 'r-pac International'),
            'xy_tolerance_mm': get_setting('xy_tolerance_mm', '0.5')
        })

if __name__ == '__main__':
    print("Starting r-pac BarTender Layout QC Suite on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
