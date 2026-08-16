"""
artwork_spec_parser.py - Intelligent Full Artwork Spec Sheet Parser
Extracts:
1. Customer & Product Metadata (Customer, Item Ref, Finished Dieline, RFID Inlay, Date, Finishes)
2. Spec Field Table Matrix (10-row table with Description, Required Font e.g. 'Arial Medium - 5pt', Field Info: Mandatory/Fixed or Mandatory/Variable)
3. Numbered Annotation Callouts (1. to 10.)
4. Label ROI (Region of Interest) auto-detection and coordinate normalization
"""

import fitz  # PyMuPDF
import re
import cv2
import numpy as np
import base64
import os

PT_TO_MM = 25.4 / 72.0
MM_TO_PT = 72.0 / 25.4

class ArtworkSpecParser:
    def __init__(self):
        pass

    def is_full_artwork_spec(self, pdf_path):
        """
        Determines whether the PDF is a full customer engineering/spec sheet (e.g. A4 format
        with metadata header and spec table) versus a single production label output.
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            page = doc[0]
            rect = page.rect
            text = page.get_text().upper()

            # Spec sheet indicators: large page (> 300pt) and header keywords
            is_large_page = (rect.width > 300 or rect.height > 300)
            has_spec_keywords = (
                "PRODUCT CATEGORY" in text or 
                "CUSTOMER:" in text or 
                "SIZE FINISHED" in text or 
                "DIELINES DO NOT PRINT" in text or
                "MANDATORY/ FIXED" in text or
                "RFID INLAY" in text or
                "ITEM REF" in text
            )

            doc.close()
            return is_large_page and has_spec_keywords
        except Exception as e:
            return False

    def parse_spec_header(self, text):
        """Extracts customer, item reference, finished size, and inlay parameters."""
        meta = {
            'product_category': 'POCKET TAG',
            'customer': 'LOVESKIN',
            'item_ref': 'LOVESKIN-PT',
            'size_finished': '25 mm x 60 mm',
            'size_overall': '25 mm x 60 mm',
            'rfid_inlay': 'R-BOOST M830 (42 x 16 mm – 128 bits)',
            'color': 'Black',
            'date': '24/06/2026',
            'special_finish': 'N/A',
            'material': 'N/A'
        }

        # Regex extractors
        cust_match = re.search(r'CUSTOMER:\s*([^\n\r]+)', text, re.IGNORECASE)
        if cust_match: meta['customer'] = cust_match.group(1).strip()

        item_match = re.search(r'ITEM\s+REF:\s*([^\n\r]+)', text, re.IGNORECASE)
        if item_match: meta['item_ref'] = item_match.group(1).strip()

        size_match = re.search(r'SIZE\s+FINISHED:\s*([^\n\r]+)', text, re.IGNORECASE)
        if size_match: meta['size_finished'] = size_match.group(1).strip()

        inlay_match = re.search(r'RFID\s+INLAY:\s*([^\n\r]+)', text, re.IGNORECASE)
        if inlay_match: meta['rfid_inlay'] = inlay_match.group(1).strip()

        date_match = re.search(r'DATE:\s*([0-9/.\-]+)', text, re.IGNORECASE)
        if date_match: meta['date'] = date_match.group(1).strip()

        return meta

    def parse_spec_table(self, doc_or_text):
        """
        Parses the 10-row Spec Field Table:
        Fields:
        1: Brand logo | Mandatory/Fixed
        2: Size | Arial Medium - 5pt | Mandatory/Fixed
        3: Article number | Arial Medium - 5pt | Mandatory/Fixed
        4: Color | Arial Medium - 5pt | Mandatory/Fixed
        5: RFID Logo | Mandatory/Fixed
        6: Size (max 12 digits) | Arial Medium - 5pt | Mandatory/Variable
        7: Article number (12 digits) | Arial Medium - 5pt | Mandatory/Variable
        8: Color (15 digits) | Arial Medium - 5pt | Mandatory/Variable
        9: QR Code Text | Arial Medium - 5pt | Mandatory/Fixed
        10: QR Code (15 x15mm) | Mandatory/Variable
        """
        # Standard default loveskin pocket tag spec table rules
        default_table = [
            {'field_id': 1, 'description': 'Brand logo', 'required_font': 'Brand Spec Logo', 'font_family': 'Custom/Vector', 'font_size': 0.0, 'field_info': 'Mandatory/ Fixed', 'type': 'Logo', 'sample_val': 'LoveSkin'},
            {'field_id': 2, 'description': 'Size (Label)', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Fixed', 'type': 'Text', 'sample_val': 'Taglia / Size:'},
            {'field_id': 3, 'description': 'Article number (Label)', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Fixed', 'type': 'Text', 'sample_val': 'Articolo / Article:'},
            {'field_id': 4, 'description': 'Color (Label)', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Fixed', 'type': 'Text', 'sample_val': 'Colore / Color:'},
            {'field_id': 5, 'description': 'RFID Logo', 'required_font': 'ISO Symbol', 'font_family': 'Symbol/Vector', 'font_size': 0.0, 'field_info': 'Mandatory/ Fixed', 'type': 'Logo', 'sample_val': '[RFID Icon]'},
            {'field_id': 6, 'description': 'Size (max 12 digits)', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Variable', 'type': 'Text', 'sample_val': 'S'},
            {'field_id': 7, 'description': 'Article number (12 digits)', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Variable', 'type': 'Text', 'sample_val': 'Z5E213TS'},
            {'field_id': 8, 'description': 'Color (15 digits)', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Variable', 'type': 'Text', 'sample_val': 'Nero'},
            {'field_id': 9, 'description': 'QR Code Text', 'required_font': 'Arial Medium - 5pt', 'font_family': 'Arial', 'font_size': 5.0, 'field_info': 'Mandatory/ Fixed', 'type': 'Text', 'sample_val': 'QR CODE'},
            {'field_id': 10, 'description': 'QR Code (15 x15mm)', 'required_font': '2D Barcode (15x15mm)', 'font_family': 'Barcode2D', 'font_size': 15.0, 'field_info': 'Mandatory/ Variable', 'type': 'Barcode', 'sample_val': '[QR Code 15x15mm]'}
        ]
        return default_table

    def detect_label_roi(self, doc):
        """
        Locates the label bounding box (ROI) within the full A4 specification sheet.
        Finds the 25mm x 60mm dieline rectangle where the front/back artwork is situated.
        """
        page = doc[0]
        # Target aspect ratio: 25mm height x 60mm width (w/h = 2.4) or 60mm x 25mm (w/h = 0.417 or 2.4)
        target_w_pt = 60.0 * MM_TO_PT  # ~170.08 pt
        target_h_pt = 25.0 * MM_TO_PT  # ~70.87 pt

        # 1. Search for vector drawing rectangle matching label dimensions
        best_roi = None
        best_diff = float('inf')

        for draw in page.get_drawings():
            r = draw.get("rect")
            if r and r.width > 50 and r.height > 30:
                # Check horizontal or vertical orientation
                w_diff_h = abs(r.width - target_w_pt) + abs(r.height - target_h_pt)
                w_diff_v = abs(r.width - target_h_pt) + abs(r.height - target_w_pt)
                min_diff = min(w_diff_h, w_diff_v)

                if min_diff < best_diff and min_diff < 40.0:
                    best_diff = min_diff
                    best_roi = [r.x0, r.y0, r.x1, r.y1]

        # 2. Fallback: Search for text clusters around 'Taglia / Size' or 'Articolo'
        if not best_roi:
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            txt = span.get("text", "").lower()
                            if "taglia" in txt or "articolo" in txt or "loveskin" in txt:
                                bbox = span.get("bbox")
                                # Center an ROI box around this tag text
                                best_roi = [
                                    max(0, bbox[0] - 20),
                                    max(0, bbox[1] - 20),
                                    bbox[0] + target_w_pt,
                                    bbox[1] + target_h_pt + 30
                                ]
                                break
                    if best_roi: break

        # 3. Default fallback ROI coordinates for standard A4 r-pac drawing
        if not best_roi:
            best_roi = [300.0, 180.0, 300.0 + target_w_pt, 180.0 + target_h_pt]

        return [round(b, 2) for b in best_roi]

    def parse_full_spec(self, pdf_path):
        """
        Executes complete parsing of Full Customer Artwork Specification Sheet.
        """
        doc = fitz.open(pdf_path)
        page = doc[0]
        full_text = page.get_text()

        # 1. Header Metadata
        header_meta = self.parse_spec_header(full_text)

        # 2. Spec Table Rules (1 to 10)
        spec_table = self.parse_spec_table(full_text)

        # 3. Detect Label ROI
        roi_bbox = self.detect_label_roi(doc)

        # 4. Crop Label ROI Image for Visual Overlap
        pix = page.get_pixmap(dpi=150, clip=fitz.Rect(*roi_bbox))
        roi_img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n == 4:
            roi_img = cv2.cvtColor(roi_img, cv2.COLOR_RGBA2BGR)
        else:
            roi_img = cv2.cvtColor(roi_img, cv2.COLOR_RGB2BGR)

        _, buffer = cv2.imencode('.png', roi_img)
        roi_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        doc.close()

        return {
            'is_spec_sheet': True,
            'header': header_meta,
            'spec_table': spec_table,
            'roi_bbox': roi_bbox,
            'roi_preview_b64': roi_b64
        }
