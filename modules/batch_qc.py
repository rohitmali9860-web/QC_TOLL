"""
batch_qc.py - Module 5: Batch / Multi-Layout QC
Processes multiple generated layout PDF files simultaneously (e.g. all SKUs for an RPO),
running automated static, variable, and serialization validation per file,
and aggregating results into a consolidated batch matrix report.
"""

import os
from .static_qc import StaticQCAnalyzer
from .variable_qc import VariableQCAnalyzer
from .serialization_qc import SerializationQCAnalyzer

class BatchQCAnalyzer:
    def __init__(self):
        self.static_analyzer = StaticQCAnalyzer()
        self.variable_analyzer = VariableQCAnalyzer()
        self.serialization_analyzer = SerializationQCAnalyzer()

    def process_batch(self, artwork_pdf_path, layout_pdf_paths, order_file_path, is_rfid=True, is_serialized=True):
        """
        Executes QC across a batch of layout files against the artwork and order records.
        """
        order_data = self.variable_analyzer.parse_order_file(order_file_path)
        records = order_data['records']

        batch_results = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        extracted_skus = []
        extracted_epcs = []

        for idx, layout_path in enumerate(layout_pdf_paths):
            file_name = os.path.basename(layout_path)
            record_idx = min(idx, len(records) - 1) if records else 0
            order_record = records[record_idx] if records else {}

            if 'SKU_STRING' in order_record:
                extracted_skus.append(order_record['SKU_STRING'])
            if 'SAMPLE_EPC_HEX' in order_record:
                extracted_epcs.append(order_record['SAMPLE_EPC_HEX'])

            # 1. Run Static QC on this layout
            static_res = self.static_analyzer.compare(artwork_pdf_path, layout_path)

            # 2. Run Variable QC on this layout
            var_res = self.variable_analyzer.validate(order_file_path, layout_path, record_index=record_idx)

            # Aggregate scores for this SKU
            file_total = static_res['total_checks'] + var_res['total_checks']
            file_passed = static_res['passed_checks'] + var_res['passed_checks']
            file_score = round((file_passed / max(file_total, 1)) * 100.0, 1)

            total_checks += file_total
            passed_checks += file_passed
            failed_checks += (file_total - file_passed)

            batch_results.append({
                'index': idx + 1,
                'file_name': file_name,
                'file_path': layout_path,
                'sku_string': order_record.get('SKU_STRING', f"SKU {idx+1}"),
                'size_label': order_record.get('SIZE_LABEL', 'N/A'),
                'order_qty': order_record.get('ORDER_QTY', 'N/A'),
                'static_score': static_res['score'],
                'variable_score': var_res['score'],
                'overall_score': file_score,
                'status': 'PASS' if file_score >= 85.0 else 'FAIL',
                'static_checks': static_res['checks'],
                'variable_checks': var_res['checks'],
                'visual_diff': static_res['visual_diff']
            })

        # 3. Run Serialization validation across batch
        serial_res = self.serialization_analyzer.validate_batch(
            is_rfid=is_rfid,
            is_serialized=is_serialized,
            order_records=records,
            epc_list=extracted_epcs,
            sku_sequences=extracted_skus
        )

        total_checks += serial_res['total_checks']
        passed_checks += serial_res['passed_checks']
        failed_checks += serial_res['failed_checks']

        batch_score = round((passed_checks / max(total_checks, 1)) * 100.0, 1)

        return {
            'sector_name': 'Batch Multi-Layout QC',
            'score': batch_score,
            'status': 'PASS' if batch_score >= 85.0 else 'FAIL',
            'total_files_processed': len(layout_pdf_paths),
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': failed_checks,
            'files': batch_results,
            'serialization_summary': serial_res
        }
