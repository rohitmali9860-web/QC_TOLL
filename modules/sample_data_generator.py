"""
sample_data_generator.py - Generates rich, realistic sample test assets for all QC modules:
- Signed Customer Artwork PDF
- BarTender PP Layout PDFs (Pass, Font Mismatch, Placement Shift, Missing Field)
- Order Data (CSV and XLSX)
- Mapping Template (XLSX)
- Thermal RFID ZPL Spool
- Problem Screenshots
"""

import os
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from PIL import Image, ImageDraw, ImageFont

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sample_data')

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'screenshots'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'batch_layouts'), exist_ok=True)

def generate_signed_artwork():
    """Generates the Customer Signed Artwork PDF with spec block, dieline, colors, fonts, fixed/variable legend."""
    pdf_path = os.path.join(DATA_DIR, 'artwork_signed_spec.pdf')
    # Standard label 25mm x 60mm overall canvas with spec frame 90mm x 140mm
    c = canvas.Canvas(pdf_path, pagesize=(100 * mm, 140 * mm))
    
    # Title & Spec Header Block
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0d2363"))
    c.drawString(10 * mm, 130 * mm, "CUSTOMER SIGNED ARTWORK SPECIFICATION SHEET")
    
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.black)
    c.drawString(10 * mm, 125 * mm, "Brand: LOVESKIN APPAREL  |  Customer Ref: LS-SS26-PT  |  Revision: v3.2 (Approved)")
    c.drawString(10 * mm, 121 * mm, "Dieline Finished Size: 25.0mm x 60.0mm  |  Margins: 25.0mm x 8.0mm  |  Black Mark: 3x6mm")
    c.drawString(10 * mm, 117 * mm, "Inlay Spec: R-BOOST M830 (42x16mm / 128-bit EPC / ISO 18000-6C Gen2)")
    c.drawString(10 * mm, 113 * mm, "Color Disclaimer: PMS Black C (100% K)  |  Background: Untreated Thermal White")

    # Dieline Boundary Box (25mm x 60mm) centered at (37.5mm, 45mm)
    label_x = 37.5 * mm
    label_y = 45 * mm
    label_w = 25 * mm
    label_h = 60 * mm
    
    # Outer bleed and safe area
    c.setStrokeColor(colors.HexColor("#ef4444"))
    c.setLineWidth(0.5)
    c.setDash(2, 2)
    c.rect(label_x - 1*mm, label_y - 1*mm, label_w + 2*mm, label_h + 2*mm) # Bleed
    
    c.setStrokeColor(colors.HexColor("#0d2363"))
    c.setDash([])
    c.setLineWidth(1.0)
    c.rect(label_x, label_y, label_w, label_h) # Cut line
    
    # Artwork Label Content
    # 1. Brand Logo (Fixed)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(colors.black)
    c.drawCentredString(label_x + label_w/2, label_y + label_h - 7*mm, "LOVESKIN APPAREL")
    
    # 2. RFID Logo (Fixed)
    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(colors.HexColor("#1e40af"))
    c.drawString(label_x + 2*mm, label_y + label_h - 12*mm, "[((o))] RFID")
    
    # 3. Variable Fields Area (Arial Medium 5pt simulated with Helvetica 5pt)
    c.setFont("Helvetica", 5.2)
    c.setFillColor(colors.black)
    c.drawString(label_x + 2*mm, label_y + label_h - 17*mm, "Article: [VARIABLE_ARTICLE]")
    c.drawString(label_x + 2*mm, label_y + label_h - 21*mm, "Size: [VARIABLE_SIZE]")
    c.drawString(label_x + 2*mm, label_y + label_h - 25*mm, "Color: [VARIABLE_COLOR]")
    c.drawString(label_x + 2*mm, label_y + label_h - 29*mm, "RPO: [VARIABLE_RPO]")
    c.drawString(label_x + 2*mm, label_y + label_h - 33*mm, "SKU: [VARIABLE_SKU]")
    c.drawString(label_x + 2*mm, label_y + label_h - 37*mm, "QTY: [VARIABLE_QTY]")

    # 4. Barcode Simulation (Fixed position)
    c.setFillColor(colors.black)
    c.rect(label_x + 2*mm, label_y + 12*mm, 21*mm, 7*mm, fill=1, stroke=0)
    c.setFont("Helvetica", 4.5)
    c.drawCentredString(label_x + label_w/2, label_y + 9*mm, "*1000341139001*")

    # 5. QR Code Placeholder
    c.setLineWidth(0.5)
    c.rect(label_x + 8*mm, label_y + 2*mm, 9*mm, 6*mm, fill=0, stroke=1)
    c.setFont("Helvetica", 4)
    c.drawCentredString(label_x + label_w/2, label_y + 4.5*mm, "QR / GS1")

    # Specifications Table at Bottom
    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(colors.HexColor("#0d2363"))
    c.drawString(10 * mm, 38 * mm, "FIELD SPECIFICATION & TOLERANCE MATRIX:")
    
    headers = ["Field Name", "Type", "Font / Size", "Expected Value / Format", "Tol (X/Y)"]
    rows = [
        ["Brand Logo", "Mandatory/Fixed", "Helvetica-Bold 7.5pt", "LOVESKIN APPAREL", "±0.5mm"],
        ["RFID Logo", "Mandatory/Fixed", "Helvetica-Bold 6.0pt", "[((o))] RFID", "±0.5mm"],
        ["Article", "Mandatory/Variable", "Helvetica 5.2pt", "1000341139-PT (per Order)", "±0.5mm"],
        ["Size", "Mandatory/Variable", "Helvetica 5.2pt", "S, M, L, XL, 2XL", "±0.5mm"],
        ["Color", "Mandatory/Variable", "Helvetica 5.2pt", "Midnight Navy (per Order)", "±0.5mm"],
        ["RPO / SKU", "Mandatory/Variable", "Helvetica 5.2pt", "RPO: 1000341139 | SKU 1/3..3/3", "±0.5mm"],
        ["EPC Serial", "Mandatory/Variable", "OCR-B 6.0pt", "SGTIN-96 (Hex 24-char)", "Unique/Seq"],
        ["Dieline Box", "Finished Size", "N/A", "25.0mm x 60.0mm (PMS Black)", "±0.2mm"]
    ]
    
    y_table = 33 * mm
    c.setFont("Helvetica-Bold", 4.8)
    c.drawString(10 * mm, y_table, f"{'FIELD':<18} | {'TYPE':<20} | {'FONT':<20} | {'EXPECTED':<30} | {'TOL':<8}")
    c.line(10 * mm, y_table - 1*mm, 90 * mm, y_table - 1*mm)
    
    y_table -= 3.5 * mm
    c.setFont("Helvetica", 4.5)
    for r in rows:
        c.drawString(10 * mm, y_table, f"{r[0]:<18} | {r[1]:<20} | {r[2]:<20} | {r[3]:<30} | {r[4]:<8}")
        y_table -= 3.2 * mm
        
    c.save()
    return pdf_path

def generate_layout_pdf(filename, variant='pass'):
    """Generates BarTender Production Proof (PP PDF) layout variants."""
    pdf_path = os.path.join(DATA_DIR, filename)
    c = canvas.Canvas(pdf_path, pagesize=(25 * mm, 60 * mm))
    
    # 25mm x 60mm label canvas
    w = 25 * mm
    h = 60 * mm
    
    # Cut box
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(0.2*mm, 0.2*mm, w - 0.4*mm, h - 0.4*mm)
    
    if variant == 'pass':
        # Brand Logo (Fixed, matching spec)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(colors.black)
        c.drawCentredString(w/2, h - 7*mm, "LOVESKIN APPAREL")
        
        # RFID Logo (Fixed, matching spec)
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(colors.HexColor("#1e40af"))
        c.drawString(2*mm, h - 12*mm, "[((o))] RFID")
        
        # Variable fields matching order SKU 1
        c.setFont("Helvetica", 5.2)
        c.setFillColor(colors.black)
        c.drawString(2*mm, h - 17*mm, "Article: 1000341139-PT")
        c.drawString(2*mm, h - 21*mm, "Size: M")
        c.drawString(2*mm, h - 25*mm, "Color: Midnight Navy")
        c.drawString(2*mm, h - 29*mm, "RPO: 1000341139")
        c.drawString(2*mm, h - 33*mm, "SKU: 1/3")
        c.drawString(2*mm, h - 37*mm, "QTY: 5")
        
        # Barcode
        c.setFillColor(colors.black)
        c.rect(2*mm, 12*mm, 21*mm, 7*mm, fill=1, stroke=0)
        c.setFont("Helvetica", 4.5)
        c.drawCentredString(w/2, 9*mm, "*1000341139001*")
        
        # QR
        c.setLineWidth(0.5)
        c.rect(8*mm, 2*mm, 9*mm, 6*mm, fill=0, stroke=1)
        c.setFont("Helvetica", 4)
        c.drawCentredString(w/2, 4.5*mm, "https://loveskin.com/auth")
        
    elif variant == 'fail_font_placement':
        # Brand Logo with wrong font and wrong placement
        c.setFont("Times-Roman", 9.0) # Font mismatch
        c.setFillColor(colors.black)
        c.drawCentredString(w/2 + 2*mm, h - 6*mm, "LOVESKIN APPAREL") # X/Y shifted
        
        # RFID Logo (Missing)
        # c.drawString(2*mm, h - 12*mm, "[((o))] RFID") -> OMITTED to trigger Mandatory Fixed missing check
        
        # Variable fields with wrong font and shifted positions
        c.setFont("Courier", 6.0) # Font mismatch
        c.setFillColor(colors.black)
        c.drawString(4.5*mm, h - 17*mm, "Article: 1000341139-PT") # Shifted
        c.drawString(4.5*mm, h - 21*mm, "Size: M")
        # Color field MISSING (Variable missing error)
        c.drawString(4.5*mm, h - 26*mm, "RPO: 1000341139")
        c.drawString(4.5*mm, h - 30*mm, "SKU: 1/3")
        c.drawString(4.5*mm, h - 34*mm, "QTY: 99") # Wrong QTY (Data mismatch)
        
        # Barcode shifted
        c.setFillColor(colors.black)
        c.rect(4*mm, 10*mm, 18*mm, 6*mm, fill=1, stroke=0)
        c.setFont("Courier", 4.0)
        c.drawCentredString(w/2, 7.5*mm, "*1000341139001*")
        
    elif variant == 'batch_sku2':
        # SKU 2 Pass
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(colors.black)
        c.drawCentredString(w/2, h - 7*mm, "LOVESKIN APPAREL")
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(colors.HexColor("#1e40af"))
        c.drawString(2*mm, h - 12*mm, "[((o))] RFID")
        c.setFont("Helvetica", 5.2)
        c.setFillColor(colors.black)
        c.drawString(2*mm, h - 17*mm, "Article: 1000341139-PT")
        c.drawString(2*mm, h - 21*mm, "Size: L")
        c.drawString(2*mm, h - 25*mm, "Color: Midnight Navy")
        c.drawString(2*mm, h - 29*mm, "RPO: 1000341139")
        c.drawString(2*mm, h - 33*mm, "SKU: 2/3")
        c.drawString(2*mm, h - 37*mm, "QTY: 5")
        c.setFillColor(colors.black)
        c.rect(2*mm, 12*mm, 21*mm, 7*mm, fill=1, stroke=0)
        c.setFont("Helvetica", 4.5)
        c.drawCentredString(w/2, 9*mm, "*1000341139002*")
        c.setLineWidth(0.5)
        c.rect(8*mm, 2*mm, 9*mm, 6*mm, fill=0, stroke=1)
        c.setFont("Helvetica", 4)
        c.drawCentredString(w/2, 4.5*mm, "https://loveskin.com/auth")

    elif variant == 'batch_sku3':
        # SKU 3 Pass
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(colors.black)
        c.drawCentredString(w/2, h - 7*mm, "LOVESKIN APPAREL")
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(colors.HexColor("#1e40af"))
        c.drawString(2*mm, h - 12*mm, "[((o))] RFID")
        c.setFont("Helvetica", 5.2)
        c.setFillColor(colors.black)
        c.drawString(2*mm, h - 17*mm, "Article: 1000341139-PT")
        c.drawString(2*mm, h - 21*mm, "Size: XL")
        c.drawString(2*mm, h - 25*mm, "Color: Midnight Navy")
        c.drawString(2*mm, h - 29*mm, "RPO: 1000341139")
        c.drawString(2*mm, h - 33*mm, "SKU: 3/3")
        c.drawString(2*mm, h - 37*mm, "QTY: 5")
        c.setFillColor(colors.black)
        c.rect(2*mm, 12*mm, 21*mm, 7*mm, fill=1, stroke=0)
        c.setFont("Helvetica", 4.5)
        c.drawCentredString(w/2, 9*mm, "*1000341139003*")
        c.setLineWidth(0.5)
        c.rect(8*mm, 2*mm, 9*mm, 6*mm, fill=0, stroke=1)
        c.setFont("Helvetica", 4)
        c.drawCentredString(w/2, 4.5*mm, "https://loveskin.com/auth")
        
    c.save()
    return pdf_path

def generate_order_files():
    """Generates realistic order CSV and XLSX files."""
    headers = [
        "RPO_NO", "SKU_INDEX", "SKU_TOTAL", "SKU_STRING", "ARTICLE_NO",
        "COLOR_NAME", "SIZE_LABEL", "ORDER_QTY", "EPC_HEADER_HEX",
        "COMPANY_PREFIX", "ITEM_REF", "SERIAL_START", "SERIAL_END",
        "SAMPLE_EPC_HEX", "QR_AUTH_URL"
    ]
    
    rows = [
        [
            "1000341139", 1, 3, "1/3", "1000341139-PT",
            "Midnight Navy", "M", 5, "30",
            "0843210", "100341", 1001, 1005,
            "3034027780000000000003E9", "https://loveskin.com/auth/1000341139001"
        ],
        [
            "1000341139", 2, 3, "2/3", "1000341139-PT",
            "Midnight Navy", "L", 5, "30",
            "0843210", "100341", 1006, 1010,
            "3034027780000000000003EE", "https://loveskin.com/auth/1000341139002"
        ],
        [
            "1000341139", 3, 3, "3/3", "1000341139-PT",
            "Midnight Navy", "XL", 5, "30",
            "0843210", "100341", 1011, 1015,
            "3034027780000000000003F3", "https://loveskin.com/auth/1000341139003"
        ]
    ]
    
    # 1. CSV
    csv_path = os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
        
    # 2. XLSX
    xlsx_path = os.path.join(DATA_DIR, '1000341139_Loveskin-PT_001.xlsx')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Order Data"
    
    # Styling
    header_fill = PatternFill(start_color="0D2363", end_color="0D2363", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    for r in rows:
        ws.append(r)
        
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    wb.save(xlsx_path)
    return csv_path, xlsx_path

def generate_mapping_template():
    """Generates standard BarTender layout field mapping Excel template."""
    xlsx_path = os.path.join(DATA_DIR, 'mapping_template_standard.xlsx')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Field Mapping"
    
    headers = ["Template Field Name", "Field Type", "Order File Column", "Is Mandatory", "Validation Rule / Regex", "Sample Output"]
    mappings = [
        ["Brand_Logo", "Fixed Text", "N/A (Fixed)", "YES", "Exact Match: LOVESKIN APPAREL", "LOVESKIN APPAREL"],
        ["RFID_Logo", "Fixed Icon", "N/A (Fixed)", "YES", "Exact Match: [((o))] RFID", "[((o))] RFID"],
        ["Article_No", "Variable Text", "ARTICLE_NO", "YES", "^[0-9]{10}-[A-Z]{2}$", "1000341139-PT"],
        ["Size_Label", "Variable Text", "SIZE_LABEL", "YES", "^(XS|S|M|L|XL|2XL|3XL|[0-9]{1,2})$", "M"],
        ["Color_Name", "Variable Text", "COLOR_NAME", "YES", "^[A-Za-z ]+$", "Midnight Navy"],
        ["RPO_Number", "Variable Text", "RPO_NO", "YES", "^[0-9]{10}$", "1000341139"],
        ["SKU_Sequence", "Variable Text", "SKU_STRING", "YES", "^[0-9]+/[0-9]+$", "1/3"],
        ["Order_Quantity", "Variable Text", "ORDER_QTY", "YES", "^[0-9]+$", "5"],
        ["EPC_Serial_Hex", "RFID Hex", "SAMPLE_EPC_HEX", "YES", "^30[0-9A-Fa-f]{22}$", "3034027780000000000003E9"],
        ["QR_Code_URL", "2D Barcode", "QR_AUTH_URL", "YES", "^https?://.+$", "https://loveskin.com/auth/1000341139001"]
    ]
    
    header_fill = PatternFill(start_color="0D2363", end_color="0D2363", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    for m in mappings:
        ws.append(m)
        
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
        
    wb.save(xlsx_path)
    return xlsx_path

def generate_sample_zpl():
    """Generates sample RFID ZPL spool output."""
    zpl_path = os.path.join(DATA_DIR, 'sample_rfid_spool.zpl')
    zpl_content = """^XA
^PW400
^LL600
^PON
^LH0,0
^RS8,,,1
^RFW,H,,,^FD3034027780000000000003E9^FS
^FO60,40^A0N,28,28^FDLOVESKIN APPAREL^FS
^FO40,80^A0N,22,22^FD[((o))] RFID^FS
^FO40,120^A0N,18,18^FDArticle: 1000341139-PT^FS
^FO40,150^A0N,18,18^FDSize: M^FS
^FO40,180^A0N,18,18^FDColor: Midnight Navy^FS
^FO40,210^A0N,18,18^FDRPO: 1000341139^FS
^FO40,240^A0N,18,18^FDSKU: 1/3^FS
^FO40,270^A0N,18,18^FDQTY: 5^FS
^FO40,320^BY2,3,60^BCN,60,Y,N,N^FD1000341139001^FS
^FO140,420^BQN,2,4^FDQA,https://loveskin.com/auth/1000341139001^FS
^XZ
"""
    with open(zpl_path, 'w', encoding='utf-8') as f:
        f.write(zpl_content.strip())
    return zpl_path

def generate_sample_screenshots():
    """Generates sample defect screenshots for problem attachment demo."""
    screenshot_path1 = os.path.join(DATA_DIR, 'screenshots', 'defect_font_mismatch.png')
    img = Image.new('RGB', (600, 400), color='#f8fafc')
    draw = ImageDraw.Draw(img)
    
    # Draw simulated label fragment
    draw.rectangle([50, 50, 550, 350], fill='#ffffff', outline='#cbd5e1', width=2)
    draw.text((70, 70), "BarTender Layout Inspection - Problem Annotation", fill='#0f172a')
    draw.text((70, 110), "Brand Header: LOVESKIN APPAREL (Font: Times-Roman 9pt)", fill='#334155')
    draw.text((70, 150), "Expected Spec: Arial-Bold 7.5pt per Artwork", fill='#64748b')
    draw.text((70, 190), "Discrepancy: Mismatched font family & sizing exceeds ±0.5pt", fill='#dc2626')
    draw.text((70, 230), "Field X-Offset: 4.5mm (Spec: 2.0mm ±0.5mm)", fill='#dc2626')
    
    # Red circle callout
    draw.ellipse([60, 100, 500, 180], outline='#ef4444', width=3)
    draw.text((380, 80), "DEFECT #1: FONT MISMATCH", fill='#ef4444')
    
    img.save(screenshot_path1)
    return screenshot_path1

def build_all_sample_assets():
    ensure_dirs()
    p1 = generate_signed_artwork()
    p2 = generate_layout_pdf('layout_pass_sku1.pdf', 'pass')
    p3 = generate_layout_pdf('layout_fail_font_sku2.pdf', 'fail_font_placement')
    p4 = generate_layout_pdf(os.path.join('batch_layouts', '1000341139_SKU1_M.pdf'), 'pass')
    p5 = generate_layout_pdf(os.path.join('batch_layouts', '1000341139_SKU2_L.pdf'), 'batch_sku2')
    p6 = generate_layout_pdf(os.path.join('batch_layouts', '1000341139_SKU3_XL.pdf'), 'batch_sku3')
    c1, x1 = generate_order_files()
    m1 = generate_mapping_template()
    z1 = generate_sample_zpl()
    s1 = generate_sample_screenshots()
    print("All sample test assets generated successfully.")

if __name__ == '__main__':
    build_all_sample_assets()
