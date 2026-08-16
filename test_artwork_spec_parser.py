"""
test_artwork_spec_parser.py - Automated Tests for Full Artwork Spec Parser & Font Matcher
"""

import unittest
import os
from modules.template_compare_engine import TemplateCompareEngine
from modules.artwork_spec_parser import ArtworkSpecParser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'sample_data')

class TestArtworkSpecParser(unittest.TestCase):
    def setUp(self):
        self.parser = ArtworkSpecParser()
        self.engine = TemplateCompareEngine()
        self.pdf_spec = os.path.join(DATA_DIR, 'artwork_signed_spec.pdf')
        self.pdf_pass = os.path.join(DATA_DIR, 'layout_pass_sku1.pdf')
        self.pdf_fail = os.path.join(DATA_DIR, 'layout_fail_font_sku2.pdf')

    def test_01_detect_full_spec(self):
        self.assertTrue(self.parser.is_full_artwork_spec(self.pdf_spec))
        self.assertFalse(self.parser.is_full_artwork_spec(self.pdf_pass))

    def test_02_parse_spec_metadata(self):
        spec_data = self.parser.parse_full_spec(self.pdf_spec)
        header = spec_data['header']
        self.assertEqual(header['customer'], 'LOVESKIN')
        self.assertEqual(header['item_ref'], 'LOVESKIN-PT')
        self.assertIn('25 mm x 60 mm', header['size_finished'])
        self.assertEqual(len(spec_data['spec_table']), 10)

    def test_03_compare_spec_with_pass_layout(self):
        res = self.engine.run_position_match(self.pdf_spec, self.pdf_pass)
        self.assertTrue(res['is_spec_sheet'])
        self.assertEqual(res['score_percentage'], '100.0%')
        self.assertEqual(res['matched_count'], 10)
        self.assertEqual(res['mismatched_count'], 0)

    def test_04_compare_spec_with_fail_layout(self):
        res = self.engine.run_position_match(self.pdf_spec, self.pdf_fail)
        self.assertTrue(res['is_spec_sheet'])
        self.assertLess(res['score_value'], 0.5)
        self.assertGreater(res['mismatched_count'], 0)

    def test_05_csv_export(self):
        res = self.engine.run_position_match(self.pdf_spec, self.pdf_pass)
        csv_out = self.engine.export_findings_csv(res)
        self.assertIn('Rule_ID', csv_out)
        self.assertIn('Brand logo', csv_out)

if __name__ == '__main__':
    unittest.main()
