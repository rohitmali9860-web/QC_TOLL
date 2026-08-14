# r-pac Layout Analysis & QC Tools — REST API Specification

## 1. Overview
This document specifies all endpoints provided by the Flask QC backend for template layout matching, static artwork verification, variable data mapping, RFID serialization, and thermal spool simulation.

---

## 2. Authentication & User Endpoints

### `GET /auth/me`
Returns the currently logged-in user profile, role, and permission flags.
- **Response `200 OK`**:
```json
{
  "display_name": "Rohit Mali",
  "email": "rohit.mali@r-pac.com",
  "role": "user",
  "permissions": [
    "pdf_analyzer",
    "template_comparison",
    "visual_comparison",
    "ai_comparison",
    "design_ai_qc",
    "rprint_performance"
  ]
}
```

---

## 3. Template Comparison Endpoints

### `POST /api/template-compare/position`
Performs field-by-field geometric alignment check using bounding box Euclidean distance against a configurable tolerance.
- **Form Data Parameters**:
  - `pdf_a` *(File, optional if `use_demo=true`)*: Reference PDF
  - `pdf_b` *(File, optional if `use_demo=true`)*: Target PDF
  - `tolerance_pt` *(Float, default: 5.0)*: Distance threshold in points
  - `filters_json` *(JSON String)*: `{"text": true, "image": false, "barcode": true, "vector": false}`
  - `use_demo` *(Boolean)*: `true` or `false`
  - `demo_variant` *(String)*: `pass` or `fail`
- **Response `200 OK`**:
```json
{
  "status": "success",
  "result": {
    "method": "Position-Based Match",
    "tolerance_pt": 5.0,
    "score_value": 1.0,
    "score_percentage": "100.0%",
    "matched_count": 10,
    "mismatched_count": 0,
    "fields_a": [...],
    "matched_fields": [...]
  }
}
```

### `POST /api/template-compare/pixel-density`
Executes pixel-level visual difference analysis using Gaussian blur filtering and OpenCV absolute difference heatmap generation.
- **Form Data Parameters**:
  - `blur_amount` *(Integer, default: 21)*: Kernel size (odd integer)
  - `use_demo` *(Boolean)*
  - `demo_variant` *(String)*
- **Response `200 OK`**:
```json
{
  "status": "success",
  "result": {
    "method": "Pixel Density Match",
    "blur_amount": 21,
    "score_value": 1.0,
    "score_percentage": "100.0%",
    "diff_image_b64": "data:image/png;base64,...",
    "difference_regions_count": 0
  }
}
```

---

## 4. BarTender Design AI QC Endpoints

### `POST /api/qc/static`
Static artwork & dieline verification.

### `POST /api/qc/variable`
Validates variable order CSV/Excel field mapping.

### `POST /api/qc/rfid`
GS1 SGTIN-96 binary EPC header, company prefix, and duplicate serialization detector.

### `POST /api/qc/spool`
Thermal ZPL printer spool parser and label preview.

### `POST /api/qc/batch`
Multi-SKU batch execution across sizes and items.

### `POST /api/qc/score`
Rollup scoring engine calculating total quality score and enforcing 50% pass threshold.

### `POST /api/qc/report/pdf`
Generates PDF QC Certificate with embedded defect screenshots.
