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

        # Flexible Matcher
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

            # 1. Flexible Heuristic Matching
            if rule_id == 1:  # Brand logo
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if "loveskin" in t or "brand" in t or (elem.get('id') == 1 and len(t) > 2):
                        matching_elem = elem; break
            elif rule_id == 2:  # Size Label
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if any(k in t for k in ['taglia', 'size:', 'size :', 'sz:', 'size']):
                        matching_elem = elem; break
            elif rule_id == 3:  # Article Label
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if any(k in t for k in ['articolo', 'article', 'item:', 'item ref', 'style:', 'ref:']):
                        matching_elem = elem; break
            elif rule_id == 4:  # Color Label
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if any(k in t for k in ['colore', 'color:', 'color :', 'colour:', 'color']):
                        matching_elem = elem; break
            elif rule_id == 5:  # RFID logo
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if "rfid" in t or "epc" in t or elem.get('type') == 'Barcode':
                        matching_elem = elem; break
            elif rule_id == 6:  # Size value
                for elem in layout_elements:
                    t = elem.get('text', '').strip()
                    if any(k in t.lower() for k in ['taglia', 'size:', 'size :']) or t in ('S', 'M', 'L', 'XL', '2XL', '32', '34', '36', '38', '40', '42', 'Small', 'Medium', 'Large'):
                        matching_elem = elem; break
            elif rule_id == 7:  # Article value
                for elem in layout_elements:
                    t = elem.get('text', '').strip()
                    if any(a in t.lower() for a in ['z5e213ts', '1000341139', 'loveskin-pt', 'pt', 'style']) or re.search(r'[A-Z0-9]{5,}', t):
                        matching_elem = elem; break
            elif rule_id == 8:  # Color value
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if any(c in t for c in ['nero', 'navy', 'black', 'white', 'midnight', 'blue', 'grey', 'red', 'beige']):
                        matching_elem = elem; break
            elif rule_id == 9:  # QR Code Text
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if "qr" in t or "code" in t or "barcode" in t:
                        matching_elem = elem; break
            elif rule_id == 10:  # QR Code Barcode
                for elem in layout_elements:
                    t = elem.get('text', '').lower()
                    if "qr" in t or elem.get('type') in ('Barcode', 'Image', 'Vector'):
                        matching_elem = elem; break

            # 2. Font Verification (Arial / Helvetica 5pt)
            if matching_elem:
                elem_font = matching_elem.get('font', '')
                elem_size = matching_elem.get('size_pt', 0.0)

                family_ok = any(f in elem_font.lower() for f in ['arial', 'helvetica']) or req_family in ('Custom/Vector', 'Symbol/Vector', 'Barcode2D')
                is_barcode_or_vector = (rule['type'] in ('Barcode', 'Logo') or req_family in ('Custom/Vector', 'Symbol/Vector', 'Barcode2D'))
                size_ok = is_barcode_or_vector or (abs(elem_size - req_size) <= 1.5)

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

        # 3. Generate Visual Side-by-Side & Overlay Diff Images
        doc_spec = fitz.open(spec_pdf_path)
        doc_lay = fitz.open(layout_pdf_path)

        roi = spec_data.get('roi_bbox', [300, 180, 470, 250])
        pix_spec = doc_spec[0].get_pixmap(dpi=150, clip=fitz.Rect(*roi))
        pix_lay = doc_lay[0].get_pixmap(dpi=150)

        img_spec = np.frombuffer(pix_spec.samples, dtype=np.uint8).reshape((pix_spec.height, pix_spec.width, pix_spec.n))
        img_lay = np.frombuffer(pix_lay.samples, dtype=np.uint8).reshape((pix_lay.height, pix_lay.width, pix_lay.n))

        if pix_spec.n == 4: img_spec = cv2.cvtColor(img_spec, cv2.COLOR_RGBA2BGR)
        else: img_spec = cv2.cvtColor(img_spec, cv2.COLOR_RGB2BGR)

        if pix_lay.n == 4: img_lay = cv2.cvtColor(img_lay, cv2.COLOR_RGBA2BGR)
        else: img_lay = cv2.cvtColor(img_lay, cv2.COLOR_RGB2BGR)

        doc_spec.close()
        doc_lay.close()

        # Resize layout to match spec crop height
        target_h, target_w = img_spec.shape[:2]
        img_lay_resized = cv2.resize(img_lay, (target_w, target_h))

        # A. Side-by-Side Canvas
        divider = np.zeros((target_h, 6, 3), dtype=np.uint8) + np.array([220, 150, 40], dtype=np.uint8)
        side_by_side = np.hstack([img_spec, divider, img_lay_resized])

        # Add Title Banners to Side-by-Side
        banner_h = 30
        canvas_w = side_by_side.shape[1]
        annotated_canvas = np.zeros((target_h + banner_h, canvas_w, 3), dtype=np.uint8) + 255
        annotated_canvas[banner_h:, :] = side_by_side

        cv2.putText(annotated_canvas, "MASTER SPEC ARTWORK (CROPPED)", (15, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 40, 0), 2)
        cv2.putText(annotated_canvas, "SYSTEM OUTPUT (BARTENDER PP)", (target_w + 20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 20), 2)

        # Draw green bounding boxes for matched items on layout
        for elem in layout_elements:
            if 'bbox' in elem and len(elem['bbox']) == 4:
                b = elem['bbox']
                # Scale bbox to resized dimensions
                bx0 = int((b[0] / max(pix_lay.width, 1)) * target_w) + target_w + 6
                by0 = int((b[1] / max(pix_lay.height, 1)) * target_h) + banner_h
                bx1 = int((b[2] / max(pix_lay.width, 1)) * target_w) + target_w + 6
                by1 = int((b[3] / max(pix_lay.height, 1)) * target_h) + banner_h
                cv2.rectangle(annotated_canvas, (bx0, by0), (bx1, by1), (0, 180, 0), 1)

        # B. Alpha Blended Overlay
        overlay_blend = cv2.addWeighted(img_spec, 0.5, img_lay_resized, 0.5, 0)
        gray_s = cv2.cvtColor(img_spec, cv2.COLOR_BGR2GRAY)
        gray_l = cv2.cvtColor(img_lay_resized, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(cv2.GaussianBlur(gray_s, (21, 21), 0), cv2.GaussianBlur(gray_l, (21, 21), 0))
        heatmap = cv2.applyColorMap(diff * 3, cv2.COLORMAP_JET)
        overlay_diff = cv2.addWeighted(overlay_blend, 0.6, heatmap, 0.4, 0)

        # Encode images to base64
        _, buf_side = cv2.imencode('.png', annotated_canvas)
        side_b64 = "data:image/png;base64," + base64.b64encode(buf_side).decode('utf-8')

        _, buf_over = cv2.imencode('.png', overlay_diff)
        over_b64 = "data:image/png;base64," + base64.b64encode(buf_over).decode('utf-8')

        _, buf_spec = cv2.imencode('.png', img_spec)
        spec_b64 = "data:image/png;base64," + base64.b64encode(buf_spec).decode('utf-8')

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
            'side_by_side_b64': side_b64,
            'overlay_diff_b64': over_b64,
            'diff_image_b64': over_b64,
            'roi_preview_b64': spec_b64
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

        # Generate Visual Side-by-Side & Overlay Diff Images
        try:
            doc_a = fitz.open(pdf_a_path)
            doc_b = fitz.open(pdf_b_path)
            pix_a = doc_a[0].get_pixmap(dpi=150)
            pix_b = doc_b[0].get_pixmap(dpi=150)

            img_a = np.frombuffer(pix_a.samples, dtype=np.uint8).reshape((pix_a.height, pix_a.width, pix_a.n))
            img_b = np.frombuffer(pix_b.samples, dtype=np.uint8).reshape((pix_b.height, pix_b.width, pix_b.n))

            if pix_a.n == 4: img_a = cv2.cvtColor(img_a, cv2.COLOR_RGBA2BGR)
            else: img_a = cv2.cvtColor(img_a, cv2.COLOR_RGB2BGR)

            if pix_b.n == 4: img_b = cv2.cvtColor(img_b, cv2.COLOR_RGBA2BGR)
            else: img_b = cv2.cvtColor(img_b, cv2.COLOR_RGB2BGR)

            doc_a.close()
            doc_b.close()

            th, tw = img_a.shape[:2]
            img_b_res = cv2.resize(img_b, (tw, th))
            div = np.zeros((th, 6, 3), dtype=np.uint8) + np.array([220, 150, 40], dtype=np.uint8)
            sbs = np.hstack([img_a, div, img_b_res])

            b_h = 30
            c_w = sbs.shape[1]
            ann_c = np.zeros((th + b_h, c_w, 3), dtype=np.uint8) + 255
            ann_c[b_h:, :] = sbs
            cv2.putText(ann_c, "PDF A (REFERENCE SPEC)", (15, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 40, 0), 2)
            cv2.putText(ann_c, "PDF B (SYSTEM OUTPUT)", (tw + 20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 20), 2)

            _, buf_s = cv2.imencode('.png', ann_c)
            side_b64 = "data:image/png;base64," + base64.b64encode(buf_s).decode('utf-8')

            # Diff
            gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
            gray_b = cv2.cvtColor(img_b_res, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(cv2.GaussianBlur(gray_a, (21, 21), 0), cv2.GaussianBlur(gray_b, (21, 21), 0))
            hmap = cv2.applyColorMap(diff * 3, cv2.COLORMAP_JET)
            over = cv2.addWeighted(cv2.addWeighted(img_a, 0.5, img_b_res, 0.5, 0), 0.6, hmap, 0.4, 0)
            _, buf_o = cv2.imencode('.png', over)
            over_b64 = "data:image/png;base64," + base64.b64encode(buf_o).decode('utf-8')
        except Exception as e:
            side_b64 = ''
            over_b64 = ''

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
            'extra_in_b': extra_b,
            'side_by_side_b64': side_b64,
            'overlay_diff_b64': over_b64,
            'diff_image_b64': over_b64,
            'roi_preview_b64': side_b64
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
