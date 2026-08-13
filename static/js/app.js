/**
 * app.js - Client-Side Controller for r-pac BarTender Layout QC Suite
 * Manages modular navigation, staged scoring, visual diff swipe slider,
 * defect screenshots, and PDF/Excel report triggers.
 */

// Application State
const state = {
  activeTab: 'tab-static',
  isDemo: true,
  demoVariant: 'pass', // 'pass' or 'fail'
  runId: 'RUN-' + Math.random().toString(36).substring(2, 8).toUpperCase(),
  designer: 'Rohit',
  rpo: '1000341139',
  itemCode: 'LS-SS26-PT',
  sectors: {
    static: null,
    variable: null,
    rfid: null,
    spool: null,
    batch: null
  },
  screenshots: []
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  initSwipeSlider();
  loadDemoDataset('pass');
  loadAuditHistory();
});

// ============================================================================
// Tab & Navigation Switching
// ============================================================================
function switchTab(tabId) {
  state.activeTab = tabId;

  // Update Top Modular Cards
  document.querySelectorAll('.portal-card').forEach(card => {
    if (card.getAttribute('data-tab') === tabId) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }
  });

  // Update Tab Content Sections
  document.querySelectorAll('.qc-tab-content').forEach(content => {
    if (content.id === tabId) {
      content.classList.add('active');
    } else {
      content.classList.remove('active');
    }
  });
}

// ============================================================================
// Demo Dataset Loader (Pass vs Fail Mode)
// ============================================================================
async function loadDemoDataset(variant = 'pass') {
  state.isDemo = true;
  state.demoVariant = variant;

  const resp = await fetch('/api/demo-data');
  const data = await resp.json();

  document.getElementById('meta-designer').innerText = data.designer_name;
  document.getElementById('meta-rpo').innerText = data.active_rpo;
  document.getElementById('meta-item').innerText = data.item_code;

  // Show badges
  document.getElementById('badge-art').style.display = 'inline-block';
  document.getElementById('badge-lay').style.display = 'inline-block';
  document.getElementById('badge-order').style.display = 'inline-block';
  document.getElementById('badge-zpl').style.display = 'inline-block';
  document.getElementById('badge-batch').style.display = 'inline-block';

  // Automatically execute all modules to populate initial state
  await runStaticQC();
  await runVariableQC();
  await runSerializationQC();
  await runSpoolQC();
  await runBatchQC();
  await recalculateFinalScore();
}

function handleFileSelected(input, badgeId) {
  state.isDemo = false;
  if (input.files && input.files.length > 0) {
    const badge = document.getElementById(badgeId);
    badge.innerText = `✓ ${input.files.length} File(s) Selected`;
    badge.style.display = 'inline-block';
  }
}

// ============================================================================
// MODULE 1: STATIC ARTWORK QC & VISUAL DIFF
// ============================================================================
async function runStaticQC() {
  const formData = new FormData();
  formData.append('run_id', state.runId);
  formData.append('use_demo', state.isDemo ? 'true' : 'false');
  formData.append('fail_variant', state.demoVariant === 'fail' ? 'true' : 'false');

  const artFile = document.getElementById('file-artwork').files[0];
  const layFile = document.getElementById('file-layout').files[0];
  if (artFile) formData.append('artwork_pdf', artFile);
  if (layFile) formData.append('layout_pdf', layFile);

  try {
    const resp = await fetch('/api/qc/static', { method: 'POST', body: formData });
    const json = await resp.json();

    if (json.status === 'success') {
      const res = json.result;
      state.sectors.static = res;

      // Render Static QC Table
      const tbody = document.querySelector('#static-checks-table tbody');
      tbody.innerHTML = '';

      res.checks.forEach(chk => {
        const tr = document.createElement('tr');
        const isPass = chk.status === 'PASS';
        tr.innerHTML = `
          <td><strong>${chk.field_name}</strong></td>
          <td>${chk.category || 'General'}</td>
          <td style="color:#0284c7;">${chk.expected}</td>
          <td>${chk.actual}</td>
          <td><span class="badge-status ${isPass ? 'badge-pass' : 'badge-fail'}">${chk.status}</span></td>
          <td style="font-size:0.8rem; color:${isPass ? '#475569' : '#dc2626'}">${chk.details}</td>
        `;
        tbody.appendChild(tr);
      });

      // Update score badge
      const scoreBadge = document.getElementById('static-score-badge');
      scoreBadge.innerText = `Score: ${res.score}% (${res.status})`;
      scoreBadge.className = `badge-status ${res.status === 'PASS' ? 'badge-pass' : 'badge-fail'}`;
      document.getElementById('static-results-container').style.display = 'block';

      // Update Visual Diff Images
      if (res.visual_diff) {
        if (res.visual_diff.artwork_img_b64) {
          document.getElementById('swipe-art-img').src = res.visual_diff.artwork_img_b64;
        }
        if (res.visual_diff.layout_img_b64) {
          document.getElementById('swipe-lay-img').src = res.visual_diff.layout_img_b64;
        }
        if (res.visual_diff.annotated_img_b64) {
          document.getElementById('annotated-diff-img').src = res.visual_diff.annotated_img_b64;
        }
      }
    }
  } catch (err) {
    console.error('Static QC Error:', err);
  }
}

// ============================================================================
// MODULE 2: VARIABLE DATA & MAPPING QC
// ============================================================================
async function runVariableQC() {
  const formData = new FormData();
  formData.append('run_id', state.runId);
  formData.append('use_demo', state.isDemo ? 'true' : 'false');
  formData.append('fail_variant', state.demoVariant === 'fail' ? 'true' : 'false');
  formData.append('record_index', document.getElementById('select-order-record').value);

  const orderFile = document.getElementById('file-order').files[0];
  const layFile = document.getElementById('file-layout').files[0];
  const mapFile = document.getElementById('file-mapping').files[0];

  if (orderFile) formData.append('order_file', orderFile);
  if (layFile) formData.append('layout_pdf', layFile);
  if (mapFile) formData.append('mapping_file', mapFile);

  try {
    const resp = await fetch('/api/qc/variable', { method: 'POST', body: formData });
    const json = await resp.json();

    if (json.status === 'success') {
      const res = json.result;
      state.sectors.variable = res;

      const tbody = document.querySelector('#variable-checks-table tbody');
      tbody.innerHTML = '';

      res.checks.forEach(chk => {
        const tr = document.createElement('tr');
        const isPass = chk.status === 'PASS';
        tr.innerHTML = `
          <td><strong>${chk.field_name}</strong></td>
          <td><code style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px;">${chk.order_column}</code></td>
          <td style="color:#0284c7;">${chk.expected}</td>
          <td><strong>${chk.actual}</strong></td>
          <td><span class="badge-status ${isPass ? 'badge-pass' : 'badge-fail'}">${chk.status}</span></td>
          <td style="font-size:0.8rem; color:${isPass ? '#475569' : '#dc2626'}">${chk.details}</td>
        `;
        tbody.appendChild(tr);
      });

      const scoreBadge = document.getElementById('var-score-badge');
      scoreBadge.innerText = `Score: ${res.score}% (${res.status})`;
      scoreBadge.className = `badge-status ${res.status === 'PASS' ? 'badge-pass' : 'badge-fail'}`;
      document.getElementById('var-results-container').style.display = 'block';
    }
  } catch (err) {
    console.error('Variable QC Error:', err);
  }
}

// ============================================================================
// MODULE 3: RFID & SERIALIZATION QC
// ============================================================================
async function runSerializationQC() {
  const isRFID = document.querySelector('input[name="radio-rfid"]:checked').value === 'true';
  const isSerialized = document.querySelector('input[name="radio-serialized"]:checked').value === 'true';

  const formData = new FormData();
  formData.append('run_id', state.runId);
  formData.append('is_rfid', isRFID ? 'true' : 'false');
  formData.append('is_serialized', isSerialized ? 'true' : 'false');
  formData.append('simulate_errors', state.demoVariant === 'fail' ? 'true' : 'false');

  try {
    const resp = await fetch('/api/qc/rfid', { method: 'POST', body: formData });
    const json = await resp.json();

    if (json.status === 'success') {
      const res = json.result;
      state.sectors.rfid = res;

      const tbody = document.querySelector('#serial-checks-table tbody');
      tbody.innerHTML = '';

      res.checks.forEach(chk => {
        const tr = document.createElement('tr');
        const isPass = chk.status === 'PASS';
        tr.innerHTML = `
          <td><strong>${chk.field_name}</strong></td>
          <td style="color:#0284c7;">${chk.expected}</td>
          <td><strong>${chk.actual}</strong></td>
          <td><span class="badge-status ${isPass ? 'badge-pass' : 'badge-fail'}">${chk.status}</span></td>
          <td style="font-size:0.8rem; color:${isPass ? '#475569' : '#dc2626'}">${chk.details}</td>
        `;
        tbody.appendChild(tr);
      });

      const scoreBadge = document.getElementById('serial-score-badge');
      scoreBadge.innerText = `Score: ${res.score}% (${res.status})`;
      scoreBadge.className = `badge-status ${res.status === 'PASS' ? 'badge-pass' : 'badge-fail'}`;
      document.getElementById('serial-results-container').style.display = 'block';
    }
  } catch (err) {
    console.error('Serialization QC Error:', err);
  }
}

function toggleRFIDMode() {
  const isRFID = document.querySelector('input[name="radio-rfid"]:checked').value === 'true';
  document.getElementById('rfid-inspector-card').style.display = isRFID ? 'block' : 'none';
  runSerializationQC();
}

// ============================================================================
// MODULE 4: THERMAL / ZPL SPOOL PREVIEW QC
// ============================================================================
async function runSpoolQC() {
  const formData = new FormData();
  formData.append('run_id', state.runId);
  formData.append('use_demo', state.isDemo ? 'true' : 'false');

  const zplFile = document.getElementById('file-zpl').files[0];
  const zplText = document.getElementById('zpl-text-input').value;

  if (zplFile) formData.append('zpl_file', zplFile);
  if (zplText) formData.append('zpl_text', zplText);

  try {
    const resp = await fetch('/api/qc/spool', { method: 'POST', body: formData });
    const json = await resp.json();

    if (json.status === 'success') {
      const res = json.result;
      state.sectors.spool = res;

      // Update Preview Image
      if (res.preview_image_b64) {
        document.getElementById('spool-preview-img').src = res.preview_image_b64;
      }
      if (res.dimensions) {
        document.getElementById('spool-dims-badge').innerText =
          `${res.dimensions.width_dots}x${res.dimensions.length_dots} dots (${res.dimensions.width_mm}mm x ${res.dimensions.length_mm}mm) @ ${res.dimensions.dpmm}dpmm`;
      }
      if (res.preview_source) {
        document.getElementById('spool-source-badge').innerText = `Renderer: ${res.preview_source}`;
      }

      // Populate Cross Check Table
      const tbody = document.querySelector('#spool-checks-table tbody');
      tbody.innerHTML = '';

      res.checks.forEach(chk => {
        const tr = document.createElement('tr');
        const isPass = chk.status === 'PASS';
        tr.innerHTML = `
          <td><strong>${chk.field_name}</strong></td>
          <td style="color:#0284c7;">${chk.expected}</td>
          <td><strong>${chk.actual}</strong></td>
          <td><span class="badge-status ${isPass ? 'badge-pass' : 'badge-fail'}">${chk.status}</span></td>
          <td style="font-size:0.8rem; color:${isPass ? '#475569' : '#dc2626'}">${chk.details}</td>
        `;
        tbody.appendChild(tr);
      });

      const scoreBadge = document.getElementById('spool-score-badge');
      scoreBadge.innerText = `Score: ${res.score}% (${res.status})`;
      scoreBadge.className = `badge-status ${res.status === 'PASS' ? 'badge-pass' : 'badge-fail'}`;
      document.getElementById('spool-results-container').style.display = 'block';
    }
  } catch (err) {
    console.error('Spool QC Error:', err);
  }
}

// ============================================================================
// MODULE 5: BATCH MULTI-LAYOUT QC
// ============================================================================
async function runBatchQC() {
  const formData = new FormData();
  formData.append('run_id', state.runId);
  formData.append('use_demo', state.isDemo ? 'true' : 'false');

  try {
    const resp = await fetch('/api/qc/batch', { method: 'POST', body: formData });
    const json = await resp.json();

    if (json.status === 'success') {
      const res = json.result;
      state.sectors.batch = res;

      const tbody = document.querySelector('#batch-matrix-table tbody');
      tbody.innerHTML = '';

      res.files.forEach(f => {
        const tr = document.createElement('tr');
        const isPass = f.status === 'PASS';
        tr.innerHTML = `
          <td>${f.index}</td>
          <td><strong>${f.file_name}</strong></td>
          <td><span style="background:#f1f5f9; padding:2px 8px; border-radius:4px; font-weight:600;">${f.sku_string} (${f.size_label})</span></td>
          <td>${f.static_score}%</td>
          <td>${f.variable_score}%</td>
          <td><strong>${f.overall_score}%</strong></td>
          <td><span class="badge-status ${isPass ? 'badge-pass' : 'badge-fail'}">${f.status}</span></td>
        `;
        tbody.appendChild(tr);
      });

      const scoreBadge = document.getElementById('batch-score-badge');
      scoreBadge.innerText = `Batch Score: ${res.score}% (${res.status})`;
      scoreBadge.className = `badge-status ${res.status === 'PASS' ? 'badge-pass' : 'badge-fail'}`;
      document.getElementById('batch-results-container').style.display = 'block';
    }
  } catch (err) {
    console.error('Batch QC Error:', err);
  }
}

// ============================================================================
// MODULE 6: STAGED SCORING & FINAL QUALITY GATE (<50% vs >=50%)
// ============================================================================
async function recalculateFinalScore() {
  const completedSectors = Object.values(state.sectors).filter(s => s !== null);

  const payload = {
    run_id: state.runId,
    designer_name: state.designer,
    rpo_number: state.rpo,
    item_code: state.itemCode,
    sectors: completedSectors
  };

  try {
    const resp = await fetch('/api/qc/score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await resp.json();

    if (json.status === 'success') {
      const rollup = json.rollup;
      const score = rollup.overall_score;
      const passedGate = rollup.passed_gate;

      // 1. Update Gauge & Bars
      const gauge = document.getElementById('overall-gauge');
      gauge.style.setProperty('--score-pct', score);
      document.getElementById('gauge-score-num').innerText = `${score}%`;
      document.getElementById('gauge-status-label').innerText = passedGate ? 'PASSED' : 'FAILED - QC LOCKED';

      if (passedGate) {
        gauge.classList.remove('fail');
      } else {
        gauge.classList.add('fail');
      }

      // Sector Bars
      if (state.sectors.static) {
        document.getElementById('bar-static-pct').innerText = `${state.sectors.static.score}%`;
        document.getElementById('bar-static-fill').style.width = `${state.sectors.static.score}%`;
      }
      if (state.sectors.variable) {
        document.getElementById('bar-var-pct').innerText = `${state.sectors.variable.score}%`;
        document.getElementById('bar-var-fill').style.width = `${state.sectors.variable.score}%`;
      }
      if (state.sectors.rfid) {
        document.getElementById('bar-rfid-pct').innerText = `${state.sectors.rfid.score}%`;
        document.getElementById('bar-rfid-fill').style.width = `${state.sectors.rfid.score}%`;
      }
      if (state.sectors.spool) {
        document.getElementById('bar-spool-pct').innerText = `${state.sectors.spool.score}%`;
        document.getElementById('bar-spool-fill').style.width = `${state.sectors.spool.score}%`;
      }

      // 2. Gate Alert Box Enforcement
      const gateBox = document.getElementById('gate-alert-box');
      const btnPDF = document.getElementById('btn-download-pdf');

      if (passedGate) {
        gateBox.className = 'gate-alert gate-alert-pass';
        gateBox.innerHTML = `
          <div style="font-size:1.25rem;">✓</div>
          <div>
            <strong>QC Score Threshold Satisfied (${score}% ≥ 50%)</strong>
            <p style="font-size:0.75rem; margin-top:2px;">Pre-production layout certified. Report generation unlocked.</p>
          </div>
        `;
        btnPDF.disabled = false;
        btnPDF.classList.remove('btn-disabled');
        btnPDF.innerHTML = '📄 Download Final QC Report (PDF)';
      } else {
        gateBox.className = 'gate-alert gate-alert-fail';
        gateBox.innerHTML = `
          <div style="font-size:1.25rem;">⚠️</div>
          <div>
            <strong>QC Threshold Not Met (${score}% < 50%) — QC REPORT LOCKED</strong>
            <p style="font-size:0.75rem; margin-top:2px;">Correct the errors below in BarTender and re-test before production sign-off.</p>
          </div>
        `;
        btnPDF.disabled = true;
        btnPDF.classList.add('btn-disabled');
        btnPDF.innerHTML = '🔒 Report Locked (<50% Score)';
      }

      // 3. Actionable Checklist
      const checklistContainer = document.getElementById('checklist-items-container');
      const failCountBadge = document.getElementById('fail-count-badge');
      checklistContainer.innerHTML = '';

      if (rollup.correction_checklist.length === 0) {
        failCountBadge.innerText = '0 Issues';
        failCountBadge.style.background = '#dcfce7';
        failCountBadge.style.color = '#166534';
        checklistContainer.innerHTML = `<p style="color:#16a34a; font-size:0.85rem; padding:1rem; text-align:center;">✨ All verified fields passed specifications. No corrections required.</p>`;
      } else {
        failCountBadge.innerText = `${rollup.correction_checklist.length} Issues`;
        failCountBadge.style.background = '#fee2e2';
        failCountBadge.style.color = '#dc2626';

        rollup.correction_checklist.forEach(item => {
          const div = document.createElement('div');
          div.className = 'checklist-item';
          div.innerHTML = `
            <div class="checklist-item-header">
              <div class="checklist-item-title">${item.sector_name}: ${item.field_name}</div>
              <span style="font-size:0.7rem; font-weight:bold; background:#fee2e2; color:#dc2626; padding:2px 6px; border-radius:4px;">${item.severity}</span>
            </div>
            <div class="checklist-item-details">
              <strong>Discrepancy:</strong> ${item.details}<br>
              <span style="color:#64748b;">Expected:</span> ${item.expected} | <span style="color:#dc2626;">Found:</span> ${item.actual}
            </div>
            <div class="checklist-fix-box">
              <strong>🔧 BarTender Action:</strong> ${item.bartender_fix}
            </div>
          `;
          checklistContainer.appendChild(div);
        });
      }
    }
  } catch (err) {
    console.error('Score Rollup Error:', err);
  }
}

// ============================================================================
// Defect Screenshot Attachments & PDF / Excel Downloads
// ============================================================================
async function uploadScreenshot(input) {
  if (!input.files || input.files.length === 0) return;

  const file = input.files[0];
  const formData = new FormData();
  formData.append('run_id', state.runId);
  formData.append('caption', `Defect Annotation: ${file.name}`);
  formData.append('screenshot', file);

  try {
    const resp = await fetch('/api/qc/screenshots/upload', { method: 'POST', body: formData });
    const json = await resp.json();

    if (json.status === 'success') {
      state.screenshots.push({
        file_path: json.file_path,
        caption: json.caption
      });

      // Display in gallery
      const gallery = document.getElementById('screenshot-gallery-container');
      const thumb = document.createElement('div');
      thumb.className = 'screenshot-thumb';
      
      const reader = new FileReader();
      reader.onload = e => {
        thumb.innerHTML = `
          <img src="${e.target.result}" alt="Defect Proof">
          <div class="screenshot-caption">${json.caption}</div>
        `;
        gallery.appendChild(thumb);
      };
      reader.readAsDataURL(file);
    }
  } catch (err) {
    console.error('Screenshot Upload Error:', err);
  }
}

async function downloadPDFReport() {
  const completedSectors = Object.values(state.sectors).filter(s => s !== null);
  const payload = {
    run_id: state.runId,
    designer_name: state.designer,
    rpo_number: state.rpo,
    item_code: state.itemCode,
    sectors: completedSectors,
    screenshots: state.screenshots
  };

  const resp = await fetch('/api/qc/report/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (resp.status === 403) {
    alert('⚠️ Report generation is locked: Overall QC Score is below 50%. Please resolve errors in BarTender and re-test.');
    return;
  }

  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `QC_Report_${state.rpo}_${state.runId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function downloadExcelReport() {
  const completedSectors = Object.values(state.sectors).filter(s => s !== null);
  const payload = {
    run_id: state.runId,
    designer_name: state.designer,
    rpo_number: state.rpo,
    item_code: state.itemCode,
    sectors: completedSectors
  };

  const resp = await fetch('/api/qc/report/excel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `QC_Audit_${state.rpo}_${state.runId}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function loadAuditHistory() {
  try {
    const resp = await fetch('/api/history');
    const json = await resp.json();
    if (json.status === 'success') {
      const tbody = document.querySelector('#history-table tbody');
      tbody.innerHTML = '';

      json.runs.forEach(r => {
        const tr = document.createElement('tr');
        const isPass = r.status.includes('PASS');
        tr.innerHTML = `
          <td><code>${r.id}</code></td>
          <td><strong>${r.designer_name}</strong></td>
          <td>${r.rpo_number}</td>
          <td>${r.item_code}</td>
          <td><strong>${r.overall_score}%</strong></td>
          <td><span class="badge-status ${isPass ? 'badge-pass' : 'badge-fail'}">${r.status}</span></td>
          <td style="font-size:0.75rem; color:#64748b;">${r.created_at}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error('History Load Error:', err);
  }
}

// ============================================================================
// Interactive Visual Diff Swipe Slider
// ============================================================================
function initSwipeSlider() {
  const container = document.getElementById('swipe-container');
  const handle = document.getElementById('swipe-bar');
  const overlay = document.getElementById('swipe-lay-img');

  if (!container || !handle || !overlay) return;

  let isDragging = false;

  const onMove = e => {
    if (!isDragging) return;
    const rect = container.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    let x = clientX - rect.left;
    x = Math.max(0, Math.min(x, rect.width));

    const pct = (x / rect.width) * 100;
    handle.style.left = `${pct}%`;
    overlay.style.clipPath = `polygon(0 0, ${pct}% 0, ${pct}% 100%, 0 100%)`;
  };

  const startDrag = () => { isDragging = true; };
  const stopDrag = () => { isDragging = false; };

  handle.addEventListener('mousedown', startDrag);
  window.addEventListener('mouseup', stopDrag);
  window.addEventListener('mousemove', onMove);

  handle.addEventListener('touchstart', startDrag);
  window.addEventListener('touchend', stopDrag);
  window.addEventListener('touchmove', onMove);
}
