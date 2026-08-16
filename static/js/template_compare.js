/**
 * template_compare.js - Controller for r-pac Template Layout Comparison Tool
 */

let fileA = null;
let fileB = null;
let currentResults = null;
let activeModalTab = 'showFieldsA';

document.addEventListener('DOMContentLoaded', () => {
  setupFileUploads();
  setupSliders();
  setupActionButtons();
  setupModal();
  autoLoadDemoIfAvailable();
});

function setupSliders() {
  const tolSlider = document.getElementById('toleranceSlider');
  const tolVal = document.getElementById('toleranceValue');
  if (tolSlider && tolVal) {
    tolSlider.addEventListener('input', e => {
      tolVal.innerText = e.target.value;
    });
  }

  const blurSlider = document.getElementById('blurSlider');
  const blurVal = document.getElementById('blurValue');
  if (blurSlider && blurVal) {
    blurSlider.addEventListener('input', e => {
      blurVal.innerText = e.target.value;
    });
  }
}

function setupFileUploads() {
  const dzA = document.getElementById('dropZoneA');
  const dzB = document.getElementById('dropZoneB');
  const inpA = document.getElementById('fileInputA');
  const inpB = document.getElementById('fileInputB');

  // Drag & drop handlers
  [dzA, dzB].forEach((dz, idx) => {
    if (!dz) return;
    const inp = idx === 0 ? inpA : inpB;

    dz.addEventListener('click', (e) => {
      if (e.target.classList.contains('clear-file-btn')) {
        e.stopPropagation();
        if (idx === 0) {
          fileA = null;
          document.getElementById('fileNameA').innerHTML = '';
        } else {
          fileB = null;
          document.getElementById('fileNameB').innerHTML = '';
        }
        checkFilesReady();
        return;
      }
      if (inp) inp.click();
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      dz.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dz.style.borderColor = '#2563eb';
        dz.style.background = '#eff6ff';
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dz.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dz.style.borderColor = '#93c5fd';
        dz.style.background = '#f8fafc';
      });
    });

    dz.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files.length > 0 && files[0].type === 'application/pdf') {
        if (idx === 0) {
          fileA = files[0];
          displaySelectedFile('fileNameA', fileA);
        } else {
          fileB = files[0];
          displaySelectedFile('fileNameB', fileB);
        }
        checkFilesReady();
      }
    });
  });

  if (inpA) {
    inpA.addEventListener('change', e => {
      if (e.target.files.length > 0) {
        fileA = e.target.files[0];
        displaySelectedFile('fileNameA', fileA);
        checkFilesReady();
      }
    });
  }

  if (inpB) {
    inpB.addEventListener('change', e => {
      if (e.target.files.length > 0) {
        fileB = e.target.files[0];
        displaySelectedFile('fileNameB', fileB);
        checkFilesReady();
      }
    });
  }
}

function displaySelectedFile(elementId, file) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const sizeKb = file.size ? ` (${Math.round(file.size / 1024)} KB)` : '';
  el.innerHTML = `
    <span style="display:inline-flex; align-items:center; gap:6px; background:#dcfce7; color:#166534; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.85rem;">
      📄 ${file.name}${sizeKb}
      <button class="clear-file-btn" style="background:none; border:none; color:#dc2626; font-size:1rem; cursor:pointer; font-weight:bold; padding:0 4px;" title="Remove file">✕</button>
    </span>
  `;
}

function checkFilesReady() {
  const btnGLM = document.getElementById('btnGLM');
  const btnSSIM = document.getElementById('btnSSIM');
  const ready = (fileA !== null && fileB !== null);
  if (btnGLM) btnGLM.disabled = !ready;
  if (btnSSIM) btnSSIM.disabled = !ready;
}

function loadDemoPair(variant = 'pass') {
  fileA = 'DEMO_A';
  fileB = 'DEMO_B';
  window.demoVariant = variant;

  document.getElementById('fileNameA').innerHTML = `
    <span style="display:inline-flex; align-items:center; gap:6px; background:#dbeafe; color:#1e40af; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.85rem;">
      📄 artwork_signed_spec.pdf (Customer Spec Sheet)
      <button class="clear-file-btn" style="background:none; border:none; color:#dc2626; font-size:1rem; cursor:pointer; font-weight:bold; padding:0 4px;" title="Remove file">✕</button>
    </span>
  `;
  document.getElementById('fileNameB').innerHTML = `
    <span style="display:inline-flex; align-items:center; gap:6px; background:#dbeafe; color:#1e40af; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.85rem;">
      📄 ${variant === 'fail' ? 'layout_fail_font_sku2.pdf (Mismatched Output)' : 'layout_pass_sku1.pdf (Matched Output)'}
      <button class="clear-file-btn" style="background:none; border:none; color:#dc2626; font-size:1rem; cursor:pointer; font-weight:bold; padding:0 4px;" title="Remove file">✕</button>
    </span>
  `;
  checkFilesReady();
}

async function autoLoadDemoIfAvailable() {
  loadDemoPair('pass');
}

function getFilterStates() {
  return {
    text: document.getElementById('filterText') ? document.getElementById('filterText').checked : true,
    image: document.getElementById('filterImage') ? document.getElementById('filterImage').checked : false,
    barcode: document.getElementById('filterBarcode') ? document.getElementById('filterBarcode').checked : true,
    vector: document.getElementById('filterVector') ? document.getElementById('filterVector').checked : false
  };
}

function setupActionButtons() {
  const btnGLM = document.getElementById('btnGLM');
  const btnSSIM = document.getElementById('btnSSIM');

  if (btnGLM) {
    btnGLM.addEventListener('click', async () => {
      await runPositionMatch();
    });
  }

  if (btnSSIM) {
    btnSSIM.addEventListener('click', async () => {
      await runPixelDensityMatch();
    });
  }
}

async function runPositionMatch() {
  showLoading(true);
  const tol = parseFloat(document.getElementById('toleranceSlider').value);
  const filters = getFilterStates();

  const formData = new FormData();
  formData.append('tolerance_pt', tol);
  formData.append('filters_json', JSON.stringify(filters));

  if (fileA === 'DEMO_A') {
    formData.append('use_demo', 'true');
    formData.append('demo_variant', window.demoVariant || 'pass');
  } else {
    formData.append('pdf_a', fileA);
    formData.append('pdf_b', fileB);
  }

  try {
    const resp = await fetch('/api/template-compare/position', {
      method: 'POST',
      body: formData
    });
    const data = await resp.json();

    if (data.status === 'success') {
      currentResults = data.result;
      displayResults(currentResults, 'position');
    } else {
      alert('Comparison failed: ' + (data.message || 'Error'));
    }
  } catch (err) {
    console.error('Position match error:', err);
    alert('Error running position match.');
  } finally {
    showLoading(false);
  }
}

async function runPixelDensityMatch() {
  showLoading(true);
  const blur = parseInt(document.getElementById('blurSlider').value);

  const formData = new FormData();
  formData.append('blur_amount', blur);

  if (fileA === 'DEMO_A') {
    formData.append('use_demo', 'true');
    formData.append('demo_variant', window.demoVariant || 'pass');
  } else {
    formData.append('pdf_a', fileA);
    formData.append('pdf_b', fileB);
  }

  try {
    const resp = await fetch('/api/template-compare/pixel-density', {
      method: 'POST',
      body: formData
    });
    const data = await resp.json();

    if (data.status === 'success') {
      currentResults = data.result;
      displayResults(currentResults, 'pixel_density');
    } else {
      alert('Pixel match failed: ' + (data.message || 'Error'));
    }
  } catch (err) {
    console.error('Pixel density match error:', err);
    alert('Error running pixel density match.');
  } finally {
    showLoading(false);
  }
}

function showLoading(show) {
  const el = document.getElementById('loading');
  if (el) el.hidden = !show;
}

function displayResults(res, mode) {
  const panel = document.getElementById('resultsPanel');
  panel.hidden = false;

  document.getElementById('scoreValue').innerText = res.score_value;
  document.getElementById('scorePercentage').innerText = res.score_percentage;

  const methodInfo = document.getElementById('methodInfo');
  const specBanner = document.getElementById('specHeaderBanner');
  const specMatrixSec = document.getElementById('specMatrixSection');
  const specTbody = document.getElementById('specMatrixTableBody');
  const metaPills = document.getElementById('specMetaPills');

  if (mode === 'position') {
    if (res.is_spec_sheet) {
      methodInfo.innerHTML = `
        <strong>Method:</strong> Artwork Specification Matrix & Typography Match<br>
        <strong>Rules Verified:</strong> ${res.matched_count} of ${res.total_fields_a} mandatory rules passed (Font & Placement)<br>
        <strong>Dieline / Tag:</strong> ${res.spec_header ? res.spec_header.size_finished : '25x60mm'}
      `;

      // Show Spec Header Banner
      if (specBanner && res.spec_header) {
        specBanner.style.display = 'block';
        metaPills.innerHTML = `
          <span>🏢 <strong>Customer:</strong> ${res.spec_header.customer}</span>
          <span>🏷️ <strong>Item Ref:</strong> ${res.spec_header.item_ref}</span>
          <span>📐 <strong>Finished Size:</strong> ${res.spec_header.size_finished}</span>
          <span>📡 <strong>RFID Inlay:</strong> ${res.spec_header.rfid_inlay}</span>
          <span>📅 <strong>Spec Date:</strong> ${res.spec_header.date}</span>
        `;
      }

      // Render 10-Row Spec Matrix Table
      if (specMatrixSec && res.spec_matrix) {
        specMatrixSec.style.display = 'block';
        specTbody.innerHTML = '';
        res.spec_matrix.forEach(row => {
          const tr = document.createElement('tr');
          const isFontPass = (row.font_status === 'PASS');
          const isRowPass = (row.status === 'MATCHED');

          tr.innerHTML = `
            <td><strong>${row.id}</strong></td>
            <td><strong>${row.description}</strong></td>
            <td><code>${row.required_font}</code></td>
            <td><span class="type-badge" style="background:${row.field_info.includes('Fixed') ? '#eff6ff' : '#fef3c7'}; color:${row.field_info.includes('Fixed') ? '#1e40af' : '#b45309'};">${row.field_info}</span></td>
            <td>${row.layout_text}</td>
            <td>
              <span class="type-badge" style="background:${isFontPass ? '#dcfce7' : '#fee2e2'}; color:${isFontPass ? '#166534' : '#991b1b'};">
                ${isFontPass ? '✓ ' + row.font_details : '✗ ' + row.font_details}
              </span>
            </td>
            <td>
              <span class="${isRowPass ? 'badge-matched' : 'badge-mismatched'}">${row.status}</span>
            </td>
          `;
          specTbody.appendChild(tr);
        });
      }
    } else {
      if (specBanner) specBanner.style.display = 'none';
      if (specMatrixSec) specMatrixSec.style.display = 'none';
      methodInfo.innerHTML = `
        <strong>Method:</strong> Position-Based Alignment Match<br>
        <strong>Tolerance:</strong> ±${res.tolerance_pt} pt<br>
        <strong>Summary:</strong> ${res.matched_count} of ${res.total_fields_a} fields matched within tolerance.
      `;
    }

    // Details boxes
    const detailsSection = document.getElementById('detailsSection');
    detailsSection.innerHTML = `
      <div class="detail-box">
        <div class="detail-label">Spec Required Rules</div>
        <div class="detail-value">${res.total_fields_a}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Layout Elements Tested</div>
        <div class="detail-value">${res.total_fields_b}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label" style="color:#16a34a;">Passed Rules</div>
        <div class="detail-value" style="color:#16a34a;">${res.matched_count}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label" style="color:#dc2626;">Discrepancies / Gaps</div>
        <div class="detail-value" style="color:#dc2626;">${res.mismatched_count}</div>
      </div>
    `;

    // Show Visual Inspection Canvas
    const visSection = document.getElementById('visualSection');
    if (visSection) visSection.hidden = false;
    const diffImg = document.getElementById('diffImage');
    if (diffImg) {
      diffImg.src = res.side_by_side_b64 || res.diff_image_b64 || res.roi_preview_b64 || '';
    }
    switchVisualTab('side_by_side');

    document.getElementById('fieldDetailsActions').hidden = false;
  } else {
    if (specBanner) specBanner.style.display = 'none';
    if (specMatrixSec) specMatrixSec.style.display = 'none';
    methodInfo.innerHTML = `
      <strong>Method:</strong> Pixel Density / SSIM Gaussian Blur Difference<br>
      <strong>Kernel Blur:</strong> ${res.blur_amount}px<br>
      <strong>Difference Clusters:</strong> ${res.difference_regions_count} discrepancy region(s) detected.
    `;

    const detailsSection = document.getElementById('detailsSection');
    detailsSection.innerHTML = `
      <div class="detail-box">
        <div class="detail-label">Density Similarity</div>
        <div class="detail-value" style="color:#16a34a;">${res.score_percentage}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Blur Filter Kernel</div>
        <div class="detail-value">${res.blur_amount} px</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Anomaly Regions</div>
        <div class="detail-value" style="color:${res.difference_regions_count > 0 ? '#dc2626' : '#16a34a'};">${res.difference_regions_count}</div>
      </div>
    `;

    const visSection = document.getElementById('visualSection');
    if (visSection) visSection.hidden = false;
    const diffImg = document.getElementById('diffImage');
    if (diffImg) {
      diffImg.src = res.diff_image_b64 || res.overlay_diff_b64 || '';
    }
    switchVisualTab('overlay_diff');

    document.getElementById('fieldDetailsActions').hidden = true;
  }
}

function switchVisualTab(tabKey) {
  if (!currentResults) return;

  const btnSide = document.getElementById('tabSideBySide');
  const btnOver = document.getElementById('tabOverlayDiff');
  const btnCrop = document.getElementById('tabSpecCrop');
  const diffImg = document.getElementById('diffImage');

  [btnSide, btnOver, btnCrop].forEach(b => { if (b) b.classList.remove('active'); });

  if (tabKey === 'side_by_side') {
    if (btnSide) btnSide.classList.add('active');
    if (diffImg) diffImg.src = currentResults.side_by_side_b64 || currentResults.diff_image_b64 || '';
  } else if (tabKey === 'overlay_diff') {
    if (btnOver) btnOver.classList.add('active');
    if (diffImg) diffImg.src = currentResults.overlay_diff_b64 || currentResults.diff_image_b64 || '';
  } else if (tabKey === 'spec_crop') {
    if (btnCrop) btnCrop.classList.add('active');
    if (diffImg) diffImg.src = currentResults.roi_preview_b64 || currentResults.diff_image_b64 || '';
  }
}

async function downloadCSVReport() {
  if (!currentResults) return;
  try {
    const resp = await fetch('/api/template-compare/export/csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result: currentResults })
    });
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `QC_Spec_Comparison_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    console.error('CSV download error:', err);
    alert('Error exporting CSV.');
  }
}

// ============================================================================
// Field Details Modal
// ============================================================================
function setupModal() {
  const btnView = document.getElementById('btnViewFields');
  const modal = document.getElementById('fieldDetailsModal');
  const closeBtn = document.getElementById('closeModal');

  function openModal() {
    if (!modal) return;
    modal.hidden = false;
    modal.style.display = 'flex';
    modal.classList.add('active');
    renderModalTable(activeModalTab);
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    modal.style.display = 'none';
    modal.classList.remove('active');
  }

  if (btnView) {
    btnView.addEventListener('click', openModal);
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', closeModal);
  }

  // Close when clicking dark backdrop outside modal-content
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });
  }

  // Close on Escape key press
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && !modal.hidden) {
      closeModal();
    }
  });

  // Modal Tab switching
  ['showFieldsA', 'showFieldsB', 'showMatched', 'showMismatched'].forEach(tabId => {
    const tabBtn = document.getElementById(tabId);
    if (tabBtn) {
      tabBtn.addEventListener('click', () => {
        document.querySelectorAll('.pdf-tab').forEach(b => b.classList.remove('active'));
        tabBtn.classList.add('active');
        activeModalTab = tabId;
        renderModalTable(tabId);
      });
    }
  });
}

function renderModalTable(tabId) {
  if (!currentResults) return;

  const thead = document.getElementById('fieldsTableHead');
  const tbody = document.getElementById('fieldsTableBody');
  tbody.innerHTML = '';

  if (tabId === 'showFieldsA') {
    thead.innerHTML = `<tr><th>#</th><th>Type</th><th>Text / Value</th><th>Coordinates (x0, y0, x1, y1)</th><th>Font & Size</th></tr>`;
    (currentResults.fields_a || []).forEach(f => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${f.id}</td><td><span class="type-badge type-${f.type.toLowerCase()}">${f.type}</span></td><td><strong>${f.text}</strong></td><td><code>${f.bbox_str}</code></td><td>${f.font || 'N/A'} (${f.size_pt}pt)</td>`;
      tbody.appendChild(tr);
    });
  } else if (tabId === 'showFieldsB') {
    thead.innerHTML = `<tr><th>#</th><th>Type</th><th>Text / Value</th><th>Coordinates (x0, y0, x1, y1)</th><th>Font & Size</th></tr>`;
    (currentResults.fields_b || []).forEach(f => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${f.id}</td><td><span class="type-badge type-${f.type.toLowerCase()}">${f.type}</span></td><td><strong>${f.text}</strong></td><td><code>${f.bbox_str}</code></td><td>${f.font || 'N/A'} (${f.size_pt}pt)</td>`;
      tbody.appendChild(tr);
    });
  } else if (tabId === 'showMatched') {
    thead.innerHTML = `<tr><th>#</th><th>Type</th><th>PDF A Value</th><th>PDF B Value</th><th>Deviation Distance</th><th>Status</th></tr>`;
    (currentResults.matched_fields || []).forEach(f => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${f.id}</td><td><span class="type-badge type-${f.type.toLowerCase()}">${f.type}</span></td><td>${f.text_a}</td><td><strong>${f.text_b}</strong></td><td>ΔX: ${f.delta_x}pt, ΔY: ${f.delta_y}pt (Dist: ${f.distance_pt}pt)</td><td><span class="badge-matched">MATCHED</span></td>`;
      tbody.appendChild(tr);
    });
  } else if (tabId === 'showMismatched') {
    thead.innerHTML = `<tr><th>#</th><th>Type</th><th>Expected Spec (A)</th><th>Layout Finding (B)</th><th>Discrepancy Reason</th><th>Status</th></tr>`;
    (currentResults.mismatched_fields || []).forEach(f => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${f.id}</td><td><span class="type-badge type-${f.type.toLowerCase()}">${f.type}</span></td><td>${f.text_a}</td><td style="color:#dc2626;"><strong>${f.text_b}</strong></td><td>${f.reason}</td><td><span class="badge-mismatched">MISMATCH</span></td>`;
      tbody.appendChild(tr);
    });
  }
}
