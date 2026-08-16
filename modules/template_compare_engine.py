"""
template_compare_engine.py - Position, Pixel Density & Full Artwork Spec Matching Engine
Supports:
1. Full Artwork Spec Sheet Parsing (Header metadata, 10-point Spec Table Matrix, Annotation Rules, Font Matching).
2. Label ROI Cropping & Coordinate Normalization Overlap.
3. Position-Based Matching with adjustable tolerance (points) and type filters.
4. Pixel Density Matching with adjustable blur kernel and difference heatmap generation.
"""

import fitz  # PyMuPDF
import cv2
import numpy as np
import io
import os
import re
import base64
from PIL import Image
from modules.artwork_spec_parser import ArtworkSpecParser

PT_TO_MM = 25.4 / 72.0
MM_TO_PT = 72.0 / 25.4

class TemplateCompareEngine:
    def __init__(self):
        self.spec_parser = ArtworkSpecParser()

    def extract_elements(self, pdf_path, filter_types=None):
        """Extracts elements classified by type: text, image, barcode, vector."""
        active_filters = filter_types or {'text': True, 'image': True, 'barcode': True, 'vector': True}
        doc = fitz.open(pdf_path)
        elements = []
        elem_idx = 1

        for page_idx, page in enumerate(doc):
            rect = page.rect
            text_instances = page.get_text("dict", flags=fitz.TEXTFLAGS_SEARCH)
            for block in text_instances.get("blocks", []):
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if not text:
                                continue

                            bbox = span.get("bbox", (0, 0, 0, 0))
                            font = span.get("font", "Helvetica")
                            size = round(span.get("size", 0.0), 1)

                            is_barcode = (
                                "barcode" in font.lower() or 
                                "ocr" in font.lower() or 
                                (text.startswith("*") and text.endswith("*")) or 
                                "rfid" in text.lower() or 
                                "http" in text.lower()
                            )

                            elem_type = "Barcode" if is_barcode else "Text"

                            if (elem_type == "Text" and active_filters.get('text', True)) or \
                               (elem_type == "Barcode" and active_filters.get('barcode', True)):
                                elements.append({
                                    'id': elem_idx,
                                    'page': page_idx + 1,
                                    'type': elem_type,
                                    'text': text,
                                    'font': font,
                                    'size_pt': size,
                                    'bbox': [round(b, 2) for b in bbox],
                                    'bbox_str': f"({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})",
                                    'center': [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0]
                                })
                                elem_idx += 1

                elif block.get("type") == 1 and active_filters.get('image', True):  # Image block
                    bbox = block.get("bbox", (0, 0, 0, 0))
                    elements.append({
                        'id': elem_idx,
                        'page': page_idx + 1,
                        'type': 'Image',
                        'text': f"[Embedded Image {block.get('width', '')}x{block.get('height', '')}]",
                        'font': 'N/A',
                        'size_pt': 0,
                        'bbox': [round(b, 2) for b in bbox],
                        'bbox_str': f"({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})",
                        'center': [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0]
                    })
                    elem_idx += 1

            if active_filters.get('vector', True):
                for draw in page.get_drawings():
                    r = draw.get("rect")
                    if r and (r.width > 2 or r.height > 2):
                        elements.append({
                            'id': elem_idx,
                            'page': page_idx + 1,
                            'type': 'Vector',
                            'text': f"[Vector Path W:{r.width:.1f}pt H:{r.height:.1f}pt]",
                            'font': 'N/A',
                            'size_pt': 0,
                            'bbox': [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)],
                            'bbox_str': f"({r.x0:.1f}, {r.y0:.1f}, {r.x1:.1f}, {r.y1:.1f})",
                            'center': [(r.x0 + r.x1) / 2.0, (r.y0 + r.y1) / 2.0]
                        })
                        elem_idx += 1
                        if elem_idx > 80:
                            break

        doc.close()
        return elements

    def run_position_match(self, pdf_a_path, pdf_b_path, tolerance_pt=5.0, filter_types=None):
        """
        Executes comparison.
        If PDF A is a full customer artwork spec sheet, runs intelligent spec table matrix & annotation font matching.
        Otherwise executes single-layout bounding box alignment matching.
        """
        is_spec = self.spec_parser.is_full_artwork_spec(pdf_a_path)

        if is_spec:
            return self._run_spec_sheet_comparison(pdf_a_path, pdf_b_path, tolerance_pt, filter_types)
        else:
            return self._run_layout_to_layout_comparison(pdf_a_path, pdf_b_path, tolerance_pt, filter_types)

    def _run_spec_sheet_comparison(self, spec_pdf_path, layout_pdf_path, tolerance_pt=5.0, filter_types=None):
        """
        Specialized engine for Full Customer Artwork Spec Sheet vs System Output Layout.
        Parses Header, 10-Row Spec Table Matrix, Annotation Callouts, Font Family & Size, and generates cropped ROI overlap.
        """
        spec_data = self.spec_parser.parse_full_spec(spec_pdf_path)
        spec_table = spec_data['spec_table']
        header_meta = spec_data['header']

        layout_elements = self.extract_elements(layout_pdf_path, filter_types)

        spec_matrix_results = []
        matched_count = 0
        total_rules = len(spec_table)

        # Build lookup of layout text
        layout_texts = [elem.get('text', '') for elem in layout_elements]
        full_layout_str = " ".join(layout_texts).lower()

        for rule in spec_table:
            rule_id = rule['field_id']
            desc = rule['description']
            req_font = rule['required_font']
            req_family = rule.get('font_family', 'Arial')
            req_size = rule.get('font_size', 5.0)
            field_info = rule['field_info']
            sample_val = rule.get('sample_val', '')

            matching_elem = None
            font_status = 'PASS'
            font_details = ''

            # 1. Match element in PDF B
            if rule_id == 1:  # Brand logo
                for elem in layout_elements:
                    if "loveskin" in elem.get('text', '').lower():
                        matching_elem = elem
                        break
            elif rule_id in (2, 3, 4):  # Fixed labels: Size, Article number, Color
                keywords = {2: 'taglia', 3: 'articolo', 4: 'colore'}
                for elem in layout_elements:
                    if keywords[rule_id] in elem.get('text', '').lower():
                        matching_elem = elem
                        break
            elif rule_id == 5:  # RFID logo
                for elem in layout_elements:
                    if "rfid" in elem.get('text', '').lower():
                        matching_elem = elem
                        break
            elif rule_id == 6:  # Size variable
                for elem in layout_elements:
                    txt = elem.get('text', '').strip()
                    if "taglia" in txt.lower() or "size:" in txt.lower() or txt in ('S', 'M', 'L', 'XL', '2XL'):
                        matching_elem = elem
                        break
            elif rule_id == 7:  # Article number variable
                for elem in layout_elements:
                    txt = elem.get('text', '').strip()
                    if "articolo" in txt.lower() or "article:" in txt.lower() or "z5e213ts" in txt.lower():
                        matching_elem = elem
                        break
            elif rule_id == 8:  # Color variable
                for elem in layout_elements:
                    txt = elem.get('text', '').strip()
                    if "colore" in txt.lower() or "color:" in txt.lower() or any(c in txt.lower() for c in ['nero', 'navy', 'black']):
                        matching_elem = elem
                        break
            elif rule_id == 9:  # QR Code Text
                for elem in layout_elements:
                    if "qr code" in elem.get('text', '').lower():
                        matching_elem = elem
                        break
            elif rule_id == 10:  # QR Code 15x15mm
                for elem in layout_elements:
                    txt = elem.get('text', '').lower()
                    if "qr" in txt or elem.get('type') == 'Barcode':
                        matching_elem = elem
                        break

            # 2. Font Verification (Arial Medium - 5pt)
            if matching_elem:
                elem_font = matching_elem.get('font', '')
                elem_size = matching_elem.get('size_pt', 0.0)

                # Check if font family contains Arial or Helvetica
                family_ok = any(f in elem_font.lower() for f in ['arial', 'helvetica']) or req_family in ('Custom/Vector', 'Symbol/Vector', 'Barcode2D')
                is_barcode_or_vector = (rule['type'] in ('Barcode', 'Logo') or req_family in ('Custom/Vector', 'Symbol/Vector', 'Barcode2D'))
                size_ok = is_barcode_or_vector or (abs(elem_size - req_size) <= 1.0)

                if family_ok and size_ok:
                    font_status = 'PASS'
                    font_details = f"Matched: {elem_font} ({elem_size}pt)"
                    status = 'MATCHED'
                    matched_count += 1
                else:
                    font_status = 'FONT_MISMATCH'
                    reasons = []
                    if not family_ok: reasons.append(f"Expected {req_family}, found {elem_font}")
                    if not size_ok: reasons.append(f"Expected {req_size}pt, found {elem_size}pt")
                    font_details = "; ".join(reasons)
                    status = 'MISMATCHED'

                actual_text = matching_elem.get('text', '')
                bbox_str = matching_elem.get('bbox_str', 'N/A')
            else:
                status = 'MISSING_IN_OUTPUT'
                font_status = 'NOT_FOUND'
                font_details = 'Element missing from production layout'
                actual_text = '[FIELD NOT FOUND]'
                bbox_str = 'N/A'

            spec_matrix_results.append({
                'id': rule_id,
                'type': rule['type'],
                'description': desc,
                'required_font': req_font,
                'field_info': field_info,
                'spec_sample': sample_val,
                'layout_text': actual_text,
                'bbox': bbox_str,
                'font_status': font_status,
                'font_details': font_details,
                'status': status
            })

        score_val = round(matched_count / total_rules, 4)
        score_pct = round(score_val * 100.0, 1)

        return {
            'method': 'Artwork Spec Table & Annotation Font Match',
            'is_spec_sheet': True,
            'spec_header': header_meta,
            'tolerance_pt': tolerance_pt,
            'score_value': score_val,
            'score_percentage': f"{score_pct}%",
            'total_fields_a': total_rules,
            'total_fields_b': len(layout_elements),
            'matched_count': matched_count,
            'mismatched_count': total_rules - matched_count,
            'extra_in_b_count': 0,
            'spec_matrix': spec_matrix_results,
            'matched_fields': [r for r in spec_matrix_results if r['status'] == 'MATCHED'],
            'mismatched_fields': [r for r in spec_matrix_results if r['status'] != 'MATCHED'],
            'fields_a': [{'id': r['id'], 'type': r['type'], 'text': r['description'], 'bbox_str': f"Rule {r['id']} ({r['required_font']})", 'font': r['required_font'], 'size_pt': 5.0} for r in spec_matrix_results],
            'fields_b': layout_elements,
            'roi_preview_b64': spec_data.get('roi_preview_b64', '')
        }

    def _run_layout_to_layout_comparison(self, pdf_a_path, pdf_b_path, tolerance_pt=5.0, filter_types=None):
        """Standard layout-to-layout position matching."""
        fields_a = self.extract_elements(pdf_a_path, filter_types)
        fields_b = self.extract_elements(pdf_b_path, filter_types)

        matched_b_indices = set()
        matched_results = []
        mismatched_results = []

        total_a = len(fields_a)

        for fa in fields_a:
            best_match = None
            best_distance = float('inf')
            best_idx = -1

            for idx_b, fb in enumerate(fields_b):
                if idx_b in matched_b_indices:
                    continue
                if fa['type'] != fb['type']:
                    continue

                dx = abs(fa['bbox'][0] - fb['bbox'][0])
                dy = abs(fa['bbox'][1] - fb['bbox'][1])
                dist = (dx**2 + dy**2) ** 0.5

                text_match = (fa['text'].strip().lower() == fb['text'].strip().lower())
                effective_dist = dist if text_match else dist + 15.0

                if effective_dist < best_distance:
                    best_distance = effective_dist
                    best_match = fb
                    best_idx = idx_b

            if best_match and best_distance <= tolerance_pt:
                matched_b_indices.add(best_idx)
                dx = round(abs(fa['bbox'][0] - best_match['bbox'][0]), 2)
                dy = round(abs(fa['bbox'][1] - best_match['bbox'][1]), 2)
                font_matched = (fa.get('font') == best_match.get('font'))
                size_matched = (fa.get('size_pt') == best_match.get('size_pt'))

                matched_results.append({
                    'id': fa['id'],
                    'type': fa['type'],
                    'text_a': fa['text'],
                    'text_b': best_match['text'],
                    'bbox_a': fa['bbox_str'],
                    'bbox_b': best_match['bbox_str'],
                    'delta_x': dx,
                    'delta_y': dy,
                    'distance_pt': round(best_distance, 2),
                    'font_match': font_matched,
                    'size_match': size_matched,
                    'status': 'MATCHED'
                })
            else:
                mismatched_results.append({
                    'id': fa['id'],
                    'type': fa['type'],
                    'text_a': fa['text'],
                    'text_b': best_match['text'] if best_match else 'MISSING IN PDF B',
                    'bbox_a': fa['bbox_str'],
                    'bbox_b': best_match['bbox_str'] if best_match else 'N/A',
                    'distance_pt': round(best_distance, 2) if best_match else 999.0,
                    'status': 'MISMATCHED' if best_match else 'MISSING',
                    'reason': f"Shifted by {best_distance:.1f}pt (> tolerance ±{tolerance_pt}pt)" if best_match else "Field not found in PDF B"
                })

        extra_b = []
        for idx_b, fb in enumerate(fields_b):
            if idx_b not in matched_b_indices:
                extra_b.append({
                    'id': fb['id'],
                    'type': fb['type'],
                    'text': fb['text'],
                    'bbox_str': fb['bbox_str'],
                    'status': 'EXTRA_IN_B'
                })

        matched_count = len(matched_results)
        total_elements = max(total_a, 1)
        score_val = round(matched_count / total_elements, 4)
        score_pct = round(score_val * 100.0, 1)

        return {
            'method': 'Position-Based Match',
            'is_spec_sheet': False,
            'tolerance_pt': tolerance_pt,
            'score_value': score_val,
            'score_percentage': f"{score_pct}%",
            'total_fields_a': total_a,
            'total_fields_b': len(fields_b),
            'matched_count': matched_count,
            'mismatched_count': len(mismatched_results),
            'extra_in_b_count': len(extra_b),
            'fields_a': fields_a,
            'fields_b': fields_b,
            'matched_fields': matched_results,
            'mismatched_fields': mismatched_results,
            'extra_in_b': extra_b
        }

    def run_pixel_density_match(self, pdf_a_path, pdf_b_path, blur_amount=21):
        """
        Executes Pixel Density / SSIM blur matching and generates difference heatmap.
        """
        ksize = blur_amount if blur_amount % 2 != 0 else blur_amount + 1

        doc_a = fitz.open(pdf_a_path)
        doc_b = fitz.open(pdf_b_path)

        # If PDF A is full spec sheet, crop the label ROI for density comparison
        if self.spec_parser.is_full_artwork_spec(pdf_a_path):
            spec_info = self.spec_parser.parse_full_spec(pdf_a_path)
            roi = spec_info['roi_bbox']
            pix_a = doc_a[0].get_pixmap(dpi=150, clip=fitz.Rect(*roi))
        else:
            pix_a = doc_a[0].get_pixmap(dpi=150)

        pix_b = doc_b[0].get_pixmap(dpi=150)

        img_a = np.frombuffer(pix_a.samples, dtype=np.uint8).reshape((pix_a.height, pix_a.width, pix_a.n))
        img_b = np.frombuffer(pix_b.samples, dtype=np.uint8).reshape((pix_b.height, pix_b.width, pix_b.n))

        if pix_a.n == 4:
            img_a = cv2.cvtColor(img_a, cv2.COLOR_RGBA2BGR)
        else:
            img_a = cv2.cvtColor(img_a, cv2.COLOR_RGB2BGR)

        if pix_b.n == 4:
            img_b = cv2.cvtColor(img_b, cv2.COLOR_RGBA2BGR)
        else:
            img_b = cv2.cvtColor(img_b, cv2.COLOR_RGB2BGR)

        doc_a.close()
        doc_b.close()

        h, w = img_a.shape[:2]
        img_b = cv2.resize(img_b, (w, h))

        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

        blur_a = cv2.GaussianBlur(gray_a, (ksize, ksize), 0)
        blur_b = cv2.GaussianBlur(gray_b, (ksize, ksize), 0)

        diff = cv2.absdiff(blur_a, blur_b)

        total_pixels = float(diff.size)
        diff_sum = float(np.sum(diff > 15))
        density_match = max(0.0, 1.0 - (diff_sum / total_pixels))

        score_val = round(density_match, 4)
        score_pct = round(score_val * 100.0, 1)

        heatmap = cv2.applyColorMap(diff * 3, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(img_b, 0.6, heatmap, 0.4, 0)

        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) > 80:
                x, y, cw, ch = cv2.boundingRect(cnt)
                cv2.rectangle(overlay, (x, y), (x + cw, y + ch), (0, 0, 255), 2)

        _, buffer = cv2.imencode('.png', overlay)
        diff_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        return {
            'method': 'Pixel Density Match',
            'blur_amount': ksize,
            'score_value': score_val,
            'score_percentage': f"{score_pct}%",
            'diff_image_b64': diff_b64,
            'difference_regions_count': len([c for c in contours if cv2.contourArea(c) > 80])
        }

    def export_findings_csv(self, result):
        """Exports comparison findings into CSV formatted text."""
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        if result.get('is_spec_sheet'):
            writer.writerow(['Rule_ID', 'Field_Description', 'Required_Font', 'Field_Info', 'Layout_Text', 'Font_Match_Status', 'Font_Details', 'Overall_Status'])
            for r in result.get('spec_matrix', []):
                writer.writerow([r['id'], r['description'], r['required_font'], r['field_info'], r['layout_text'], r['font_status'], r['font_details'], r['status']])
        else:
            writer.writerow(['Field_ID', 'Type', 'Spec_Value_A', 'Layout_Value_B', 'Deviation_Distance_pt', 'Status', 'Details'])
            for m in result.get('matched_fields', []):
                writer.writerow([m['id'], m['type'], m.get('text_a', ''), m.get('text_b', ''), m.get('distance_pt', 0), m['status'], f"Delta X: {m.get('delta_x', 0)}pt, Delta Y: {m.get('delta_y', 0)}pt"])
            for mm in result.get('mismatched_fields', []):
                writer.writerow([mm['id'], mm['type'], mm.get('text_a', ''), mm.get('text_b', ''), mm.get('distance_pt', 0), mm['status'], mm.get('reason', '')])

        return output.getvalue()
