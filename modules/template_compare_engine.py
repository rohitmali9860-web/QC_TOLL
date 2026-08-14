"""
template_compare_engine.py - Position & Pixel Density Matching Engine
Replicates the r-pac Template Comparison algorithms:
1. Position-Based Matching with adjustable tolerance (points) and type filters (Text, Image, Barcode, Vector).
2. Pixel Density Matching with adjustable blur kernel and difference heatmap generation.
3. Detailed Field Breakdown (PDF A fields, PDF B fields, Matched fields, Mismatched fields).
"""

import fitz  # PyMuPDF
import cv2
import numpy as np
import io
import os
import base64
from PIL import Image

PT_TO_MM = 25.4 / 72.0

class TemplateCompareEngine:
    def __init__(self):
        pass

    def extract_elements(self, pdf_path, filter_types=None):
        """Extracts elements classified by type: text, image, barcode, vector."""
        active_filters = filter_types or {'text': True, 'image': True, 'barcode': True, 'vector': True}
        doc = fitz.open(pdf_path)
        elements = []
        elem_idx = 1

        for page_idx, page in enumerate(doc):
            rect = page.rect
            page_w = rect.width
            page_h = rect.height

            # 1. Text & Barcodes
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

                            # Heuristic classification for Barcode / QR vs Text
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

            # 2. Vector Drawings (Rectangles, Borders, Dielines)
            if active_filters.get('vector', True):
                for draw in page.get_drawings():
                    r = draw.get("rect")
                    if r and (r.width > 2 or r.height > 2):
                        # Filter out tiny artefacts
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
                        if elem_idx > 80:  # Cap vector elements to prevent clutter
                            break

        doc.close()
        return elements

    def run_position_match(self, pdf_a_path, pdf_b_path, tolerance_pt=5.0, filter_types=None):
        """
        Executes Position-Based matching with specified tolerance and type filters.
        """
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

            # Find closest candidate in B with same type and content/context
            for idx_b, fb in enumerate(fields_b):
                if idx_b in matched_b_indices:
                    continue
                if fa['type'] != fb['type']:
                    continue

                # Compute Euclidean distance between top-left coordinates
                dx = abs(fa['bbox'][0] - fb['bbox'][0])
                dy = abs(fa['bbox'][1] - fb['bbox'][1])
                dist = (dx**2 + dy**2) ** 0.5

                # Boost match if text is identical
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

        # Extra items in B
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
        # Ensure blur is odd
        ksize = blur_amount if blur_amount % 2 != 0 else blur_amount + 1

        # Render PDF pages to OpenCV BGR images
        doc_a = fitz.open(pdf_a_path)
        doc_b = fitz.open(pdf_b_path)

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

        # Resize B to match A
        h, w = img_a.shape[:2]
        img_b = cv2.resize(img_b, (w, h))

        # Convert to grayscale
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian Blur per slider
        blur_a = cv2.GaussianBlur(gray_a, (ksize, ksize), 0)
        blur_b = cv2.GaussianBlur(gray_b, (ksize, ksize), 0)

        # Compute Absolute Pixel Difference
        diff = cv2.absdiff(blur_a, blur_b)

        # Calculate density match score
        total_pixels = float(diff.size)
        diff_sum = float(np.sum(diff > 15))
        density_match = max(0.0, 1.0 - (diff_sum / total_pixels))

        score_val = round(density_match, 4)
        score_pct = round(score_val * 100.0, 1)

        # Create Visual Heatmap Overlay
        heatmap = cv2.applyColorMap(diff * 3, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(img_b, 0.6, heatmap, 0.4, 0)

        # Draw red bounding boxes around regions with high difference
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) > 80:
                x, y, cw, ch = cv2.boundingRect(cnt)
                cv2.rectangle(overlay, (x, y), (x + cw, y + ch), (0, 0, 255), 2)

        # Encode overlay image to base64
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
        writer.writerow(['Field_ID', 'Type', 'Spec_Value_A', 'Layout_Value_B', 'Deviation_Distance_pt', 'Status', 'Details'])

        for m in result.get('matched_fields', []):
            writer.writerow([m['id'], m['type'], m['text_a'], m['text_b'], m['distance_pt'], m['status'], f"Delta X: {m['delta_x']}pt, Delta Y: {m['delta_y']}pt"])

        for mm in result.get('mismatched_fields', []):
            writer.writerow([mm['id'], mm['type'], mm['text_a'], mm['text_b'], mm['distance_pt'], mm['status'], mm.get('reason', '')])

        for ex in result.get('extra_in_b', []):
            writer.writerow([ex['id'], ex['type'], 'N/A', ex['text'], 'N/A', ex['status'], 'Unexpected field in output'])

        return output.getvalue()
