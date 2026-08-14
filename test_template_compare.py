"""
test_template_compare.py - Automated Unit Tests for Template Comparison Suite
Validates:
1. Element extraction (Text, Barcodes, Images, Vectors)
2. Position-based tolerance matching
3. Type filtering
4. Pixel density blur difference & heatmap generation
"""

import unittest
import os
import json
from modules.template_compare_engine import TemplateCompareEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'sample_data')

class TestTemplateCompareEngine(unittest.TestCase):
    def setUp(self):
        self.engine = TemplateCompareEngine()
        self.pdf_a = os.path.join(DATA_DIR, 'layout_pass_sku1.pdf')
        self.pdf_b_pass = os.path.join(DATA_DIR, 'layout_pass_sku1.pdf')
        self.pdf_b_fail = os.path.join(DATA_DIR, 'layout_fail_font_sku2.pdf')

    def test_01_element_extraction(self):
        elements = self.engine.extract_elements(self.pdf_a)
        self.assertGreater(len(elements), 0)
        first = elements[0]
        self.assertIn('type', first)
        self.assertIn('text', first)
        self.assertIn('bbox', first)

    def test_02_position_match_pass(self):
        res = self.engine.run_position_match(self.pdf_a, self.pdf_b_pass, tolerance_pt=5.0)
        self.assertEqual(res['score_value'], 1.0)
        self.assertEqual(res['score_percentage'], '100.0%')
        self.assertEqual(res['mismatched_count'], 0)

    def test_03_position_match_fail(self):
        res = self.engine.run_position_match(self.pdf_a, self.pdf_b_fail, tolerance_pt=5.0)
        self.assertLess(res['score_value'], 0.5)
        self.assertGreater(res['mismatched_count'], 0)

    def test_04_type_filters(self):
        # Only barcodes
        res = self.engine.run_position_match(
            self.pdf_a, self.pdf_b_pass,
            tolerance_pt=5.0,
            filter_types={'text': False, 'image': False, 'barcode': True, 'vector': False}
        )
        for field in res['fields_a']:
            self.assertEqual(field['type'], 'Barcode')

    def test_05_pixel_density_match(self):
        res = self.engine.run_pixel_density_match(self.pdf_a, self.pdf_b_pass, blur_amount=21)
        self.assertIn('diff_image_b64', res)
        self.assertTrue(res['diff_image_b64'].startswith('data:image/png;base64,'))
        self.assertEqual(res['score_value'], 1.0)

if __name__ == '__main__':
    unittest.main()
