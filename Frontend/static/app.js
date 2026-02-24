/* ═══════════════════════════════════════════════════════════════════════════
   NephroScan — app.js   (SPA Logic)
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const STATE = {
  user: null,
  currentPatient: null,   // { patient_id, first_name, last_name, age, gender, ... }
  medicalParams: null,    // raw form values
  lastPrediction: null,   // { result, patient_id }
  patientsCache: [],
  donutChart: null,
  shapExplanations: null, // cached from /api/explain
};

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  document.getElementById('login-form').addEventListener('submit', handleLogin);
  document.getElementById('patient-details-form').addEventListener('submit', handlePatientDetails);
  document.getElementById('medical-params-form').addEventListener('submit', handleMedicalParams);
  document.getElementById('sidebar-toggle').addEventListener('click', toggleSidebar);
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
  document.getElementById('mobile-menu-btn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('mobile-open');
  });
  checkSession();
});

// ── Particles ──────────────────────────────────────────────────────────────
function initParticles() {
  const container = document.getElementById('particles');
  if (!container) return;
  for (let i = 0; i < 18; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const size = 4 + Math.random() * 10;
    Object.assign(p.style, {
      width: size + 'px',
      height: size + 'px',
      left: Math.random() * 100 + '%',
      top: Math.random() * 100 + '%',
      animationDuration: (4 + Math.random() * 8) + 's',
      animationDelay: (Math.random() * 4) + 's',
    });
    container.appendChild(p);
  }
}

// ── Session Check ──────────────────────────────────────────────────────────
async function checkSession() {
  try {
    const res = await api('/api/auth/me');
    if (res.status === 'success') {
      setUser(res.user);
      showApp();
      navigate('view-dashboard');
    }
  } catch (_) { /* not logged in */ }
}

// ── Login ──────────────────────────────────────────────────────────────────
async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  setLoading(btn, true);

  try {
    const res = await api('/api/auth/login', {
      method: 'POST',
      body: {
        username: document.getElementById('login-username').value,
        password: document.getElementById('login-password').value,
      },
    });
    if (res.status === 'success') {
      setUser(res.user);
      showApp();
      navigate('view-dashboard');
    } else {
      errEl.classList.remove('hidden');
    }
  } catch (_) {
    errEl.classList.remove('hidden');
  } finally {
    setLoading(btn, false);
  }
}

async function logout() {
  await api('/api/auth/logout', { method: 'POST' }).catch(() => {});
  STATE.user = null;
  document.getElementById('app-shell').classList.add('hidden');
  document.getElementById('view-login').classList.add('active');
  document.getElementById('view-login').style.display = 'block';
  document.getElementById('login-username').value = '';
  document.getElementById('login-password').value = '';
}

function togglePwd() {
  const inp = document.getElementById('login-password');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// ── User & App Shell ───────────────────────────────────────────────────────
function setUser(user) {
  STATE.user = user;
  const initials = (user.full_name || user.username)[0].toUpperCase();
  document.getElementById('user-name-sidebar').textContent = user.full_name || user.username;
  document.getElementById('user-role-sidebar').textContent = user.role;
  document.getElementById('user-avatar').textContent = initials;
  // Topbar avatar
  const ta = document.getElementById('topbar-avatar-initials');
  if (ta) ta.textContent = initials;
  // Popover
  const pa = document.getElementById('profile-popover-avatar');
  const pn = document.getElementById('profile-popover-name');
  const pr = document.getElementById('profile-popover-role');
  if (pa) pa.textContent = initials;
  if (pn) pn.textContent = user.full_name || user.username;
  if (pr) pr.textContent = user.role;

  // Admin-only elements
  document.querySelectorAll('.admin-only').forEach(el => {
    if (user.role === 'admin') el.classList.remove('hidden');
    else el.classList.add('hidden');
  });
}

// ── Profile popover toggle ────────────────────────────────────────────
function toggleProfileMenu() {
  const pop   = document.getElementById('profile-popover');
  const caret = document.getElementById('profile-caret');
  const open  = !pop.classList.contains('hidden');
  if (open) { closeProfileMenu(); return; }
  pop.classList.remove('hidden');
  caret.classList.add('open');
}

function closeProfileMenu() {
  document.getElementById('profile-popover')?.classList.add('hidden');
  document.getElementById('profile-caret')?.classList.remove('open');
}

// Close popover when clicking anywhere outside
document.addEventListener('click', (e) => {
  const wrap = document.getElementById('profile-menu-wrap');
  if (wrap && !wrap.contains(e.target)) closeProfileMenu();
});

function showApp() {
  document.getElementById('view-login').style.display = 'none';
  document.getElementById('view-login').classList.remove('active');
  document.getElementById('app-shell').classList.remove('hidden');
}

// ── Navigation ─────────────────────────────────────────────────────────────
function navigate(viewId) {
  document.querySelectorAll('.inner-view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById(viewId);
  if (target) {
    target.classList.add('active');
  }

  // Update page title
  const titles = {
    'view-dashboard':      'Dashboard',
    'view-patient-details':'New Assessment — Patient Details',
    'view-medical-params': 'New Assessment — Medical Parameters',
    'view-results':        'Assessment Results',
    'view-patient-lookup': 'Patient Lookup',
    'view-patient-profile':'Patient Profile',
    'view-admin':          'Admin Panel',
  };
  document.getElementById('page-title').textContent = titles[viewId] || 'NephroScan';

  // Update sidebar active state
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === viewId ||
      (viewId === 'view-patient-details' && item.dataset.view === 'view-assessment'));
  });

  // Lazy load data
  if (viewId === 'view-dashboard') loadDashboard();
  if (viewId === 'view-patient-lookup') loadPatients();
  if (viewId === 'view-admin') { loadUsersTable(); loadPatientsAdmin(); }

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('mobile-open');
}

// ── Sidebar ────────────────────────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}

// ── Theme ──────────────────────────────────────────────────────────────────
function toggleTheme() {
  const html = document.documentElement;
  html.setAttribute('data-theme', html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
}

// ═══════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════
async function loadDashboard() {
  try {
    const [statsRes, patientsRes] = await Promise.all([
      api('/api/dashboard/stats'),
      api('/api/patients'),
    ]);

    if (statsRes.status === 'success') {
      const s = statsRes.stats;
      animateCount('stat-patients',    s.total_patients || 0);
      animateCount('stat-predictions', s.total_predictions || 0);
      animateCount('stat-ckd',         s.ckd_positive || 0);
      animateCount('stat-users',       s.total_users || 0);
      renderDonut(s.ckd_positive || 0, (s.total_predictions || 0) - (s.ckd_positive || 0));
    }

    if (patientsRes.status === 'success') {
      STATE.patientsCache = patientsRes.patients || [];
      renderRecentPatients(STATE.patientsCache.slice(-10).reverse());
    }
  } catch (err) {
    console.error('Dashboard load error:', err);
  }
}

function animateCount(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = 0;
  const duration = 900;
  const step = t => {
    el.textContent = Math.round(start + (target - start) * Math.min(t / duration, 1));
    if (t < duration) requestAnimationFrame(dt => step(t + dt));
  };
  requestAnimationFrame(dt => step(dt));
}

function renderDonut(ckdCount, noCkdCount) {
  const ctx = document.getElementById('chart-donut');
  if (!ctx) return;
  if (STATE.donutChart) STATE.donutChart.destroy();

  STATE.donutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['CKD Positive', 'CKD Negative'],
      datasets: [{
        data: [ckdCount || 0, noCkdCount || 0],
        backgroundColor: ['#e63946', '#2dc653'],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, font: { size: 12 } } },
      },
      cutout: '68%',
    },
  });
}

function renderRecentPatients(patients) {
  const el = document.getElementById('recent-patients-table');
  if (!el) return;
  if (!patients.length) { el.innerHTML = '<p class="muted-text">No patients yet.</p>'; return; }

  el.innerHTML = `<table>
    <thead><tr>
      <th>Patient</th><th>Age</th><th>Gender</th><th>Physician</th><th></th>
    </tr></thead>
    <tbody>${patients.map(p => `
      <tr>
        <td><strong>${p.first_name} ${p.last_name}</strong><br><small class="muted-text">${p.patient_id}</small></td>
        <td>${p.age || '—'}</td>
        <td>${p.gender || '—'}</td>
        <td>${p.physician || '—'}</td>
        <td><button class="btn btn-ghost btn-sm" onclick="viewPatient('${p.patient_id}')">View</button></td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

// ═══════════════════════════════════════════════════════════════════════════
//  ASSESSMENT — Step 1: Patient Details
// ═══════════════════════════════════════════════════════════════════════════
async function handlePatientDetails(e) {
  e.preventDefault();
  const form = e.target;
  const data = formToObj(form);
  data.registered_by = STATE.user?.username || '';

  try {
    const res = await api('/api/patients', { method: 'POST', body: data });
    if (res.status === 'success') {
      // Fetch the saved patient record
      const allRes = await api('/api/patients');
      const patients = allRes.patients || [];
      // Find the most recently registered patient by this user
      const saved = patients.find(p => p.first_name === data.first_name && p.last_name === data.last_name);
      STATE.currentPatient = saved || { ...data, patient_id: 'TEMP' };
    } else {
      STATE.currentPatient = { ...data, patient_id: 'TEMP' };
    }
  } catch (_) {
    STATE.currentPatient = { ...data, patient_id: 'TEMP' };
  }

  // Pre-fill age in step 2
  const ageInput = document.getElementById('param-age');
  if (ageInput && data.age) ageInput.value = data.age;

  const banner = document.getElementById('params-patient-banner');
  const fn = STATE.currentPatient?.first_name || data.first_name;
  const ln = STATE.currentPatient?.last_name || data.last_name;
  if (banner) banner.textContent = `Patient: ${fn} ${ln}`;

  navigate('view-medical-params');
  showToast('Patient details saved.', 'success');
}

// ═══════════════════════════════════════════════════════════════════════════
//  ASSESSMENT — Step 2: Medical Params → API
// ═══════════════════════════════════════════════════════════════════════════
async function handleMedicalParams(e) {
  e.preventDefault();
  const btn = document.getElementById('run-analysis-btn');
  setLoading(btn, true);

  const form = e.target;
  const raw = formToObj(form);
  STATE.medicalParams = raw;

  // Build payload for /api/predict
  const payload = { ...raw };
  // patient_id for saving prediction
  if (STATE.currentPatient?.patient_id) {
    payload.patient_id = STATE.currentPatient.patient_id;
  }
  payload.performed_by = STATE.user?.username || '';

  try {
    const res = await api('/api/predict', { method: 'POST', body: payload });
    if (res.status === 'success' || res.ensemble_result !== undefined) {
      STATE.lastPrediction = res;
      renderResults(res, raw);
      navigate('view-results');
    } else {
      showToast('Prediction failed: ' + (res.message || 'Unknown error'), 'error');
    }
  } catch (err) {
    showToast('Error contacting server: ' + err.message, 'error');
  } finally {
    setLoading(btn, false);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
//  RESULTS RENDERER
// ═══════════════════════════════════════════════════════════════════════════
function renderResults(res, params) {
  const container = document.getElementById('results-content');
  const isCKD = res.ensemble_result === 'ckd';
  const conf = Math.round((res.ensemble_confidence || 0) * 100);
  const role = STATE.user?.role || '';
  const isSpecialist = role === 'admin' || (role === 'doctor' && (STATE.user?.full_name || '').startsWith('Dr.'));
  const isNurse = role === 'nurse';
  const isDoctorNoTitle = role === 'doctor' && !(STATE.user?.full_name || '').startsWith('Dr.');
  const canSeeFullAnalysis = !isNurse && !isDoctorNoTitle;

  // Reset SHAP section & control button visibility before any early return
  document.getElementById('shap-section')?.classList.add('hidden');
  const shapBtn = document.getElementById('generate-shap-btn');
  if (shapBtn) {
    shapBtn.classList.toggle('hidden', !canSeeFullAnalysis);
    // Reset spinner state from previous run
    const t = shapBtn.querySelector('.btn-text');
    const s = shapBtn.querySelector('.btn-spinner');
    if (t) t.classList.remove('hidden');
    if (s) s.classList.add('hidden');
    shapBtn.disabled = false;
    shapBtn.classList.remove('hidden');   // will be hidden below if not specialist
    if (!canSeeFullAnalysis) shapBtn.classList.add('hidden');
  }

  let html = '';

  // ── Verdict banner (all roles) ──────────────────────────────────────────
  html += `
  <div class="verdict-banner ${isCKD ? 'ckd' : 'no-ckd'}">
    <div class="verdict-icon">${isCKD ? '⚠️' : '✅'}</div>
    <div>
      <div class="verdict-title" style="color:${isCKD ? 'var(--c-red)' : 'var(--c-green)'}">
        ${isCKD ? 'Chronic Kidney Disease Detected' : 'No CKD Detected'}
      </div>
      <div class="verdict-sub">Ensemble model consensus — ${res.models_agree || 0}/9 models in agreement</div>
    </div>
    <div class="verdict-conf">
      <div class="verdict-conf-value" style="color:${isCKD ? 'var(--c-red)' : 'var(--c-green)'}">${conf}%</div>
      <div class="verdict-conf-label">Confidence</div>
    </div>
  </div>`;

  // ── KDIGO Stage (all roles) ─────────────────────────────────────────────
  const sc = parseFloat(params.sc) || null;
  const age = parseFloat(params.age) || null;
  const genderStr = (STATE.currentPatient?.gender || params.gender || 'Male');
  if (sc !== null && age !== null) {
    const kdigo = computeKDIGO(sc, age, genderStr);
    html += renderKDIGOCard(kdigo);
  }

  // ── Nurse checklist (nurse only) ────────────────────────────────────────
  if (isNurse) {
    html += renderNurseChecklist(isCKD);
    container.innerHTML = html;
    return;
  }

  // ── Doctor (no Dr. title) — verdict only ────────────────────────────────
  if (isDoctorNoTitle) {
    html += `<div class="restricted-banner">🔒 Detailed model breakdown is visible to specialist physicians (Dr.) and administrators only.</div>`;
    container.innerHTML = html;
    return;
  }

  // ── Full analysis (Dr. / admin) ─────────────────────────────────────────
  html += `<h3 class="models-title">Individual Model Results</h3>
  <div class="models-grid">`;

  const allModelResults = res.model_results || {};
  for (const [modelName, mres] of Object.entries(allModelResults)) {
    const mCkd = mres.prediction === 'ckd';
    const mConf = Math.round((mres.confidence || 0) * 100);
    html += `
    <div class="model-card ${mCkd ? 'ckd' : 'no-ckd'}">
      <div class="model-name">${formatModelName(modelName)}</div>
      <div class="model-verdict" style="color:${mCkd ? 'var(--c-red)' : 'var(--c-green)'}">
        ${mCkd ? 'CKD' : 'No CKD'}
      </div>
      <div class="conf-bar-wrap">
        <div class="conf-bar ${mCkd ? 'ckd' : 'no-ckd'}" style="width:${mConf}%"></div>
      </div>
      <div class="conf-value">${mConf}% confidence</div>
    </div>`;
  }

  html += `</div>`;

  // ── Submitted parameters summary ────────────────────────────────────────
  html += `<h3 class="section-title" style="margin-top:1.5rem">Submitted Parameters</h3>
  <div class="params-summary-grid">`;

  const paramLabels = {
    age:'Age', bp:'Blood Pressure', sg:'Specific Gravity', al:'Albumin', su:'Sugar',
    rbc:'Red Blood Cells', pc:'Pus Cells', pcc:'Pus Cell Clumps', ba:'Bacteria',
    bgr:'Blood Glucose', bu:'Blood Urea', sc:'Serum Creatinine', sod:'Sodium',
    pot:'Potassium', hemo:'Haemoglobin', pcv:'PCV', wc:'WBC Count', rc:'RBC Count',
    htn:'Hypertension', dm:'Diabetes', cad:'CAD', appet:'Appetite', pe:'Pedal Edema', ane:'Anaemia',
  };

  for (const [k, label] of Object.entries(paramLabels)) {
    const val = params[k];
    if (val !== undefined && val !== '') {
      html += `<div class="param-summary-item">
        <span class="param-summary-key">${label}</span>
        <span class="param-summary-val">${val}</span>
      </div>`;
    }
  }

  html += `</div>`;

  container.innerHTML = html;

  // Animate confidence bars
  setTimeout(() => {
    container.querySelectorAll('.conf-bar').forEach(bar => {
      const w = bar.style.width;
      bar.style.width = '0';
      setTimeout(() => { bar.style.width = w; }, 50);
    });
  }, 50);
}

function renderKDIGOCard(kdigo) {
  const { egfr, stage, label, color, recommendation } = kdigo;
  return `
  <div class="kdigo-card" style="background:${color}18; border-color:${color}">
    <div class="kdigo-stage-badge" style="background:${color}">Stage ${stage}</div>
    <div>
      <div class="kdigo-egfr">${egfr !== null ? egfr.toFixed(1) : '—'} <small style="font-size:.7em;font-weight:400">mL/min/1.73m²</small></div>
      <div class="kdigo-label">eGFR (CKD-EPI 2021) — <strong>${label}</strong></div>
      <div class="kdigo-rec">${recommendation}</div>
    </div>
  </div>`;
}

function renderNurseChecklist(isCKD) {
  const items = isCKD
    ? ['Monitor blood pressure every 4–6 hours','Record fluid intake and output accurately','Administer prescribed medications on schedule','Provide a low-potassium, low-phosphorus diet','Restrict dietary protein as directed','Educate patient about CKD management and lifestyle','Ensure follow-up nephrology appointment is scheduled','Monitor for signs of fluid overload (oedema, SOB)']
    : ['Continue routine vital sign monitoring','Maintain adequate hydration','Encourage healthy lifestyle habits — diet, exercise','Schedule routine follow-up as per protocol'];
  return `
  <div class="card" style="padding:1.5rem; margin-top:1rem">
    <h3 class="card-header-title">Nursing Care Checklist</h3>
    <ul style="list-style:none;display:flex;flex-direction:column;gap:.6rem">
      ${items.map(i => `<li style="display:flex;gap:.6rem;align-items:flex-start">
        <input type="checkbox" style="margin-top:.15em;flex-shrink:0" />
        <span style="font-size:.875rem">${i}</span>
      </li>`).join('')}
    </ul>
  </div>`;
}

function formatModelName(key) {
  const names = {
    'logistic_regression':'Logistic Regression',
    'svm':'SVM',
    'decision_tree':'Decision Tree',
    'random_forest':'Random Forest',
    'gradient_boosting':'Gradient Boosting',
    'xgboost':'XGBoost',
    'catboost':'CatBoost',
    'knn':'KNN',
    'naive_bayes':'Naive Bayes',
  };
  return names[key] || key;
}

// ═══════════════════════════════════════════════════════════════════════════
//  KDIGO / CKD-EPI 2021
// ═══════════════════════════════════════════════════════════════════════════
function computeKDIGO(sc, age, gender) {
  // CKD-EPI 2021 (race-free)
  let egfr = null;
  const isFemale = gender && gender.toLowerCase().startsWith('f');
  const kappa = isFemale ? 0.7 : 0.9;
  const alpha = isFemale ? -0.241 : -0.302;
  const sexCoeff = isFemale ? 1.012 : 1.0;
  const ratio = sc / kappa;

  if (sc > 0 && age > 0) {
    const term1 = Math.min(ratio, 1) ** alpha;
    const term2 = Math.max(ratio, 1) ** (-1.200);
    egfr = 142 * term1 * term2 * (0.9938 ** age) * sexCoeff;
    egfr = Math.round(egfr * 10) / 10;
  }

  let stage, label, color, recommendation;
  if (egfr === null) {
    stage = '?'; label = 'Unknown'; color = '#6b7a8d';
    recommendation = 'Serum creatinine or age required for eGFR calculation.';
  } else if (egfr >= 90) {
    stage = 'G1'; label = 'Normal or High'; color = '#2dc653';
    recommendation = 'Kidney function is normal. Routine annual check-up recommended.';
  } else if (egfr >= 60) {
    stage = 'G2'; label = 'Mildly Decreased'; color = '#90c55a';
    recommendation = 'Annual monitoring. Control BP & glucose.';
  } else if (egfr >= 45) {
    stage = 'G3a'; label = 'Mildly–Moderately Decreased'; color = '#ffc300';
    recommendation = 'Refer to nephrologist. 6-monthly monitoring. Dietary restrictions.';
  } else if (egfr >= 30) {
    stage = 'G3b'; label = 'Moderately–Severely Decreased'; color = '#f4a261';
    recommendation = 'Nephrology follow-up every 3 months. Prepare for RRT discussion.';
  } else if (egfr >= 15) {
    stage = 'G4'; label = 'Severely Decreased'; color = '#e06030';
    recommendation = '⚠ Urgent nephrology. Plan renal replacement therapy (dialysis/transplant).';
  } else {
    stage = 'G5'; label = 'Kidney Failure'; color = '#e63946';
    recommendation = '🚨 Kidney failure. Immediate nephrology intervention. Initiate RRT if not already.';
  }

  return { egfr, stage, label, color, recommendation };
}

// ═══════════════════════════════════════════════════════════════════════════
// ── Feature label & clinical range maps ──────────────────────────────────
// Maps raw feature code → human-readable label
const FEAT_LABEL = {
  age:'Age', bp:'Blood Pressure', sg:'Specific Gravity', al:'Albumin', su:'Sugar',
  rbc:'Red Blood Cells', pc:'Pus Cells', pcc:'Pus Cell Clumps', ba:'Bacteria',
  bgr:'Blood Glucose', bu:'Blood Urea', sc:'Serum Creatinine',
  sod:'Sodium', pot:'Potassium', hemo:'Haemoglobin', pcv:'Packed Cell Volume',
  wc:'White Cell Count', rc:'Red Cell Count', htn:'Hypertension', dm:'Diabetes',
  cad:'Coronary Artery Disease', appet:'Appetite', pe:'Pedal Oedema', ane:'Anaemia'
};
// Clinical normal ranges for numeric parameters (for Plot 5)
const CLINICAL_RANGES = {
  hemo: { label:'Haemoglobin',        unit:'g/dl',    min:13,    max:17    },
  sc:   { label:'Serum Creatinine',   unit:'mg/dl',   min:0.5,   max:1.2   },
  bu:   { label:'Blood Urea',         unit:'mg/dl',   min:7,     max:25    },
  bgr:  { label:'Blood Glucose',      unit:'mg/dl',   min:70,    max:125   },
  sod:  { label:'Sodium',             unit:'mEq/L',   min:135,   max:145   },
  pot:  { label:'Potassium',          unit:'mEq/L',   min:3.5,   max:5.0   },
  sg:   { label:'Specific Gravity',   unit:'',        min:1.010, max:1.025 },
  bp:   { label:'Blood Pressure',     unit:'mm Hg',   min:60,    max:90    },
  pcv:  { label:'Packed Cell Volume', unit:'%',       min:36,    max:52    },
};

// ──────────────────────────────────────────────────────────────────────────
//  SHAP
async function generateShap() {
  if (!STATE.medicalParams) { showToast('No prediction data available.', 'error'); return; }

  const btn = document.getElementById('generate-shap-btn');
  setLoading(btn, true);

  try {
    const payload = { ...STATE.medicalParams };
    if (STATE.currentPatient?.patient_id) payload.patient_id = STATE.currentPatient.patient_id;

    const res = await api('/api/explain', { method: 'POST', body: payload });
    if (res.status === 'success' && res.explanations) {
      STATE.shapExplanations = res.explanations;
      renderShap(res.explanations);
      document.getElementById('shap-section').classList.remove('hidden');
      document.getElementById('generate-shap-btn').classList.add('hidden');
    } else {
      showToast('SHAP explanation failed: ' + (res.message || 'Unknown'), 'error');
    }
  } catch (err) {
    showToast('SHAP error: ' + err.message, 'error');
  } finally {
    setLoading(btn, false);
  }
}

function renderShap(explanations) {
  // Populate model selector, default to Random Forest
  const sel = document.getElementById('shap-model-select');
  if (sel) {
    const models = Object.keys(explanations).filter(m => explanations[m] && !explanations[m].error);
    sel.innerHTML = models
      .map(m => `<option value="${m}" ${m === 'Random Forest' ? 'selected' : ''}>${m}</option>`)
      .join('');
    // If Random Forest not available, fall back to first
    if (!models.includes('Random Forest') && models.length) sel.value = models[0];
  }
  reRenderShap();
}

function reRenderShap() {
  const sel = document.getElementById('shap-model-select');
  const modelName = sel ? sel.value : 'Random Forest';
  const shapData  = (STATE.shapExplanations || {})[modelName];
  if (!shapData || shapData.error) {
    showToast(`SHAP data not available for ${modelName}`, 'error');
    return;
  }
  renderShapPlots(modelName, shapData, STATE.medicalParams || {});
}

function renderShapPlots(modelName, shapData, params) {
  /* shapData = { featureCode: shapValue, ... } sorted by |val| desc */

  // ── Read live CSS custom-property values for full dark-mode compatibility ──
  const cs       = getComputedStyle(document.documentElement);
  const cRed     = cs.getPropertyValue('--c-red').trim()       || '#e63946';
  const cPrimary = cs.getPropertyValue('--c-primary').trim()   || '#1B6CA8';
  const cAccent  = cs.getPropertyValue('--c-accent').trim()    || '#00C9B8';
  const cSurface = cs.getPropertyValue('--surface').trim()     || '#ffffff';
  const cSurf2   = cs.getPropertyValue('--surface-2').trim()   || '#f7f9fb';
  const cBg      = cs.getPropertyValue('--bg').trim()          || '#f0f4f8';
  const cBorder  = cs.getPropertyValue('--border').trim()      || '#dce3ea';
  const cText    = cs.getPropertyValue('--text').trim()        || '#1a2332';
  const cMuted   = cs.getPropertyValue('--text-muted').trim()  || '#6b7a8d';
  const cPriDark = cs.getPropertyValue('--c-primary-dark').trim() || '#124e7c';
  // Semantic colours
  const colRisk  = cRed;       // feature increases CKD risk
  const colProt  = cPrimary;   // feature decreases CKD risk (protective)
  const colTotal = cAccent;    // waterfall total bar

  // ── Build sorted entries (top 15 by magnitude) ─────────────────────────
  const allEntries = Object.entries(shapData).filter(([k]) => k !== 'error');
  const sorted = [...allEntries].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const top = sorted.slice(0, 15);
  const topLabels  = top.map(([k]) => FEAT_LABEL[k] || k);
  const topValues  = top.map(([, v]) => v);
  const topColors  = topValues.map(v => v >= 0 ? colRisk : colProt);

  // Alphabetical entries for waterfall
  const alpha = [...allEntries].sort((a, b) =>
    (FEAT_LABEL[a[0]] || a[0]).localeCompare(FEAT_LABEL[b[0]] || b[0])).slice(0, 15);
  const alphaLabels = alpha.map(([k]) => FEAT_LABEL[k] || k);
  const alphaValues = alpha.map(([, v]) => v);
  const netShap = allEntries.reduce((s, [, v]) => s + v, 0);

  // Risk vs protective sums
  const riskSum = allEntries.filter(([, v]) => v > 0).reduce((s, [, v]) => s + v, 0);
  const protSum = allEntries.filter(([, v]) => v < 0).reduce((s, [, v]) => s + Math.abs(v), 0);

  // Shared Plotly layout base using live CSS vars
  const layoutBase = {
    paper_bgcolor: 'rgba(0,0,0,0)', // fully transparent — card provides background
    plot_bgcolor:  cSurf2,
    font: { family: 'Inter, system-ui, sans-serif', size: 12, color: cText },
    margin: { t: 30, r: 80, b: 60, l: 170 },
  };
  const axisBase = {
    color: cMuted,
    gridcolor: cBorder,
    linecolor: cBorder,
    zerolinecolor: cMuted,
  };
  const cfg = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d','select2d'],
    toImageButtonOptions: { format: 'png', scale: 2 },
  };
  const plotTransition = { duration: 500, easing: 'cubic-in-out' };

  // ── PLOT 1 — Feature Impact bar chart ────────────────────────────
  Plotly.newPlot('shap-plot1', [{
    type: 'bar', orientation: 'h',
    y: topLabels, x: topValues,
    marker: { color: topColors },
    text: topValues.map(v => (v >= 0 ? '+' : '') + v.toFixed(4)),
    textposition: 'outside',
    textfont: { color: topColors, size: 11 },
    hovertemplate: '<b>%{y}</b><br>SHAP: %{x:.5f}<extra></extra>',
  }], {
    ...layoutBase,
    height: 420,
    xaxis: { ...axisBase, title: { text: 'SHAP Value  (+ increases CKD risk,  − decreases CKD risk)', font: { color: cMuted } }, zeroline: true, zerolinewidth: 1.5 },
    yaxis: { ...axisBase, automargin: true },
    shapes: [{ type:'line', x0:0, x1:0, y0:-0.5, y1:top.length-0.5, line:{ color:cMuted, width:1.5, dash:'dot' } }],
  }, cfg);

  // ── PLOT 2 — Waterfall chart ───────────────────────────────────
  Plotly.newPlot('shap-plot2', [{
    type: 'waterfall', orientation: 'v',
    x: [...alphaLabels, 'Net SHAP Score'],
    y: [...alphaValues, netShap],
    measure: [...alphaValues.map(() => 'relative'), 'total'],
    text: [...alphaValues, netShap].map(v => (v >= 0 ? '+' : '') + v.toFixed(4)),
    textposition: 'outside',
    textfont: { size: 10, color: cText },
    increasing: { marker: { color: colRisk } },
    decreasing: { marker: { color: colProt } },
    totals:     { marker: { color: colTotal } },
    connector:  { line: { color: cBorder, width: 1 } },
    hovertemplate: '<b>%{x}</b><br>Contribution: %{y:.5f}<extra></extra>',
  }], {
    ...layoutBase,
    height: 380,
    margin: { ...layoutBase.margin, l: 60, b: 120 },
    xaxis: { ...axisBase, tickangle: -40, automargin: true },
    yaxis: { ...axisBase, title: { text: 'Cumulative SHAP contribution', font: { color: cMuted } }, zeroline: true },
  }, cfg);

  // ── PLOT 3 — Donut: Risk vs Protective ─────────────────────────
  const donutLabel = netShap >= 0 ? '❌ At Risk' : '✅ Protected';
  const donutColor = netShap >= 0 ? colRisk : colProt;
  Plotly.newPlot('shap-plot3', [{
    type: 'pie', hole: 0.55,
    labels: ['Protective Features', 'Risk Features'],
    values: [protSum, riskSum],
    marker: { colors: [colProt, colRisk] },
    textinfo: 'percent',
    textposition: 'inside',
    insidetextfont: { color: '#fff', size: 12 },
    hovertemplate: '<b>%{label}</b><br>Weight: %{value:.4f}<br>%{percent}<extra></extra>',
  }], {
    ...layoutBase,
    height: 300,
    margin: { t: 20, r: 20, b: 60, l: 20 },
    legend: { orientation: 'h', y: -0.20, font: { color: cText, size: 11 }, xanchor: 'center', x: 0.5 },
    annotations: [{ text: `<b>${donutLabel}</b>`, showarrow: false, font: { size: 13, color: donutColor }, x: 0.5, y: 0.5, xref: 'paper', yref: 'paper', xanchor: 'center', yanchor: 'middle' }],
  }, cfg);

  // ── PLOT 4 — Risk-o-Meter gauge ──────────────────────────────
  const ensConf    = STATE.lastPrediction?.ensemble_confidence || 0;
  const ensResult  = STATE.lastPrediction?.ensemble_result || 'no_ckd';
  const gaugeValue = Math.round(ensConf * 100);
  const gaugeColor = ensResult === 'ckd' ? colRisk : colProt;
  Plotly.newPlot('shap-plot4', [{
    type: 'indicator',
    domain: { x: [0.05, 0.95], y: [0.05, 0.9] },
    mode: 'gauge+number+delta',
    value: gaugeValue,
    delta: { reference: 50, decreasing: { color: colProt }, increasing: { color: colRisk } },
    number: { suffix: '%', font: { size: 28, color: cText } },
    gauge: {
      axis: { range: [0, 100], tickwidth: 1, tickcolor: cMuted, tickfont: { color: cMuted }, nticks: 6 },
      bar: { color: gaugeColor, thickness: 0.3 },
      bgcolor: 'rgba(0,0,0,0)',
      borderwidth: 1.5,
      bordercolor: cBorder,
      steps: [
        { range: [0,  20], color: 'rgba(27,108,168,0.12)'  },
        { range: [20, 40], color: 'rgba(27,108,168,0.06)'  },
        { range: [40, 60], color: 'rgba(255,195,0, 0.12)'  },
        { range: [60, 80], color: 'rgba(230,57,70, 0.08)'  },
        { range: [80,100], color: 'rgba(230,57,70, 0.18)'  },
      ],
      threshold: { line: { color: cPriDark, width: 3 }, thickness: 0.75, value: gaugeValue },
    },
  }], {
    ...layoutBase,
    height: 300,
    margin: { t: 40, r: 60, b: 20, l: 60 },
    annotations: [
      { text:'Safe',     x:0.06, y:0.10, xref:'paper', yref:'paper', showarrow:false, font:{size:9,color:cMuted} },
      { text:'Low',      x:0.23, y:0.27, xref:'paper', yref:'paper', showarrow:false, font:{size:9,color:cMuted} },
      { text:'Mid',      x:0.50, y:0.88, xref:'paper', yref:'paper', showarrow:false, font:{size:9,color:cMuted} },
      { text:'High',     x:0.77, y:0.27, xref:'paper', yref:'paper', showarrow:false, font:{size:9,color:cMuted} },
      { text:'Critical', x:0.94, y:0.10, xref:'paper', yref:'paper', showarrow:false, font:{size:9,color:cMuted} },
    ],
  }, cfg);

  // Force responsive resize so both plots snap to container width
  setTimeout(() => { Plotly.Plots.resize('shap-plot3'); Plotly.Plots.resize('shap-plot4'); }, 50);
  // ── PLOT 5 — Patient values vs normal ranges ──────────────────────
  const p5Features = Object.keys(CLINICAL_RANGES).filter(k => params[k] !== undefined && params[k] !== '');
  const p5Labels   = p5Features.map(k => CLINICAL_RANGES[k].label);
  const p5Devs     = p5Features.map(k => {
    const r   = CLINICAL_RANGES[k];
    const val = parseFloat(params[k]);
    const mid = (r.min + r.max) / 2;
    const half = (r.max - r.min) / 2;
    return half > 0 ? Math.round(((val - mid) / half) * 1000) / 10 : 0;
  });
  const p5Colors = p5Devs.map(d => Math.abs(d) > 100 ? colRisk : colProt);

  Plotly.newPlot('shap-plot5', [
    { type:'scatter', mode:'lines', name:'', showlegend:false, hoverinfo:'skip',
      x:[-0.5, p5Labels.length-0.5], y:[100,100],
      line:{ color:colRisk, dash:'dot', width:1.5 } },
    { type:'scatter', mode:'lines', name:'Normal Range', showlegend:false, hoverinfo:'skip',
      x:[-0.5, p5Labels.length-0.5], y:[-100,-100],
      line:{ color:colRisk, dash:'dot', width:1.5 },
      fill:'tonexty', fillcolor:`${colProt}1a` },
    { type:'bar', name:'Patient Value',
      x:p5Labels, y:p5Devs,
      marker:{ color:p5Colors },
      text:p5Devs.map(d => (d>=0?'+':'') + d + '%'),
      textposition:'outside',
      textfont:{ size:11, color:p5Colors },
      hovertemplate:'<b>%{x}</b><br>Deviation: %{y:.1f}% from midpoint<extra></extra>' },
  ], {
    ...layoutBase,
    height: 360,
    margin: { t:30, r:40, b:90, l:60 },
    xaxis: { ...axisBase, tickangle:-30, automargin:true },
    yaxis: { ...axisBase, title:{ text:'Deviation from Normal Range Mid-point (%)', font:{color:cMuted} }, zeroline:true },
    legend: { orientation:'h', y:-0.25, font:{ color:cText } },
    annotations: [{ text:'Normal Range', x:0.01, y:0.56, xref:'paper', yref:'paper', showarrow:false, font:{ size:10, color:colProt } }],
  }, cfg);

  // ── Clinical Interpretation (theme-class HTML) ──────────────────────
  const riskDrivers = sorted.filter(([, v]) => v > 0).slice(0, 4);
  const protFactors = sorted.filter(([, v]) => v < 0).slice(0, 3);
  const nrText = (code) => { const r = CLINICAL_RANGES[code]; return r ? `Normal: ${r.min}–${r.max} ${r.unit}` : null; };
  const direction = (v) => v >= 0
    ? 'pushing the model <em>toward CKD</em>. The higher this value, the greater the kidney stress signal.'
    : '<em>reducing</em> CKD likelihood in this prediction.';

  let html = `<h4 class="section-title">📄 Clinical Interpretation</h4>`;

  if (riskDrivers.length) {
    html += `<p class="params-section-title" style="margin-top:.75rem">🔴 Top Risk Drivers</p>`;
    for (const [code, val] of riskDrivers) {
      const lbl = FEAT_LABEL[code] || code;
      const nrt = nrText(code);
      html += `<div class="shap-interp-row risk">
        <span class="shap-interp-val risk">${val >= 0 ? '+' : ''}${val.toFixed(4)}</span>
        <span><b>${lbl}</b>${nrt ? ` <span class="muted-text">(${nrt})</span>` : ''} — This feature is ${direction(val)}</span>
      </div>`;
    }
  }

  if (protFactors.length) {
    html += `<p class="params-section-title" style="margin-top:.75rem">🟢 Top Protective Factors</p>`;
    for (const [code, val] of protFactors) {
      const lbl = FEAT_LABEL[code] || code;
      html += `<div class="shap-interp-row protective">
        <span class="shap-interp-val protective">${val.toFixed(4)}</span>
        <span><b>${lbl}</b> — This feature is ${direction(val)}</span>
      </div>`;
    }
  }

  const netEffect = netShap >= 0 ? 'a <b>net risk effect</b>' : 'a <b>net protective effect</b>';
  const netIcon   = netShap >= 0 ? '🚨' : '✅';
  html += `<div class="shap-net-banner">
    ${netIcon}
    <div><b>Net SHAP Score:
      <span class="shap-interp-val ${netShap >= 0 ? 'risk' : 'protective'}">${netShap >= 0 ? '+' : ''}${netShap.toFixed(4)}</span></b>
      — The combined SHAP signal shows ${netEffect} for this patient according to the <em>${modelName}</em> model.
    </div>
  </div>`;

  html += `<div class="shap-legend">
    <span><span class="shap-legend-dot" style="background:${colRisk}"></span> Risk feature (increases CKD probability)</span>
    <span><span class="shap-legend-dot" style="background:${colProt}"></span> Protective feature (decreases CKD probability)</span>
    <span class="muted-text">Bar length = strength of influence &nbsp;·&nbsp; Model: ${modelName}</span>
  </div>`;

  document.getElementById('shap-clinical-card').innerHTML = html;

  // ── Submitted Parameters (theme-class HTML) ──────────────────────
  const fmt = (v) => {
    if (v === null || v === undefined || v === '') return '—';
    const map = { normal:'Normal', abnormal:'Abnormal', present:'Present', notpresent:'Not Present', yes:'Yes', no:'No', good:'Good', poor:'Poor' };
    return map[String(v).toLowerCase()] ?? v;
  };
  const pRow = (label, val) => `<p class="shap-params-item">${label}: <span>${fmt(val)}</span></p>`;

  document.getElementById('shap-submitted-params').innerHTML = `
    <h4 class="section-title" style="cursor:pointer" onclick="this.nextElementSibling.classList.toggle('hidden')">
      🗒 Submitted Parameters <span class="muted-text" style="font-weight:400;font-size:.8rem">(click to collapse)</span>
    </h4>
    <div class="shap-params-grid">
      <div>
        <div class="shap-params-col-title">Urine Analysis</div>
        ${pRow('Spec. Gravity', params.sg)}
        ${pRow('Albumin',       params.al)}
        ${pRow('Sugar',         params.su)}
        ${pRow('RBC',           params.rbc)}
        ${pRow('Pus Cells',     params.pc)}
      </div>
      <div>
        <div class="shap-params-col-title">Biochemistry</div>
        ${pRow('Blood Pressure',  params.bp + (params.bp ? ' mm Hg' : ''))}
        ${pRow('Blood Glucose',   params.bgr + (params.bgr ? ' mg/dl' : ''))}
        ${pRow('Blood Urea',      params.bu  + (params.bu  ? ' mg/dl' : ''))}
        ${pRow('Serum Creatinine',params.sc  + (params.sc  ? ' mg/dl' : ''))}
      </div>
      <div>
        <div class="shap-params-col-title">Electrolytes / Hb</div>
        ${pRow('Sodium',     params.sod  + (params.sod  ? ' mEq/L' : ''))}
        ${pRow('Potassium',  params.pot  + (params.pot  ? ' mEq/L' : ''))}
        ${pRow('Haemoglobin',params.hemo + (params.hemo ? ' g/dl'  : ''))}
        ${pRow('PCV',        params.pcv  + (params.pcv  ? '%'      : ''))}
      </div>
      <div>
        <div class="shap-params-col-title">Medical History</div>
        ${pRow('Hypertension', params.htn)}
        ${pRow('Diabetes',     params.dm)}
        ${pRow('CAD',          params.cad)}
        ${pRow('Anaemia',      params.ane)}
        ${pRow('Appetite',     params.appet)}
      </div>
    </div>`;

  // ── Staggered entrance animation for all plot cards ─────────────────
  _animateShapCards();

  document.getElementById('shap-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* Stagger-animates every .shap-plot-card inside #shap-section into view */
function _animateShapCards() {
  const cards = Array.from(document.querySelectorAll('#shap-section .shap-plot-card'));
  // Reset so re-renders also replay the animation
  cards.forEach(c => c.classList.remove('anim-in'));
  // Double rAF: wait for browser to apply the opacity:0 reset before re-adding
  requestAnimationFrame(() => requestAnimationFrame(() => {
    cards.forEach((card, i) => setTimeout(() => card.classList.add('anim-in'), i * 95));
  }));
}

// ──────────────────────────────────────────────────────────────────────────
//  PATIENT LOOKUP
// ═══════════════════════════════════════════════════════════════════════════
async function loadPatients() {
  const wrap = document.getElementById('patients-table-wrap');
  if (wrap) wrap.innerHTML = '<p class="muted-text">Loading…</p>';
  try {
    const res = await api('/api/patients');
    if (res.status === 'success') {
      STATE.patientsCache = res.patients || [];
      renderPatientsTable(STATE.patientsCache, wrap);
    }
  } catch (err) {
    if (wrap) wrap.innerHTML = '<p class="muted-text">Failed to load patients.</p>';
  }
}

function filterPatients() {
  const q = document.getElementById('patient-search').value.toLowerCase();
  const filtered = STATE.patientsCache.filter(p =>
    (p.first_name + ' ' + p.last_name).toLowerCase().includes(q) ||
    (p.patient_id || '').toLowerCase().includes(q) ||
    (p.physician || '').toLowerCase().includes(q)
  );
  renderPatientsTable(filtered, document.getElementById('patients-table-wrap'));
}

function renderPatientsTable(patients, wrap) {
  if (!wrap) return;
  if (!patients.length) { wrap.innerHTML = '<p class="muted-text">No patients found.</p>'; return; }

  wrap.innerHTML = `<table>
    <thead><tr>
      <th>Patient ID</th><th>Name</th><th>Age</th><th>Gender</th><th>Physician</th><th>Registered</th><th>Actions</th>
    </tr></thead>
    <tbody>${patients.map(p => `
      <tr>
        <td class="mono" style="font-size:.78rem">${p.patient_id}</td>
        <td><strong>${p.first_name} ${p.last_name}</strong></td>
        <td>${p.age || '—'}</td>
        <td>${p.gender || '—'}</td>
        <td>${p.physician || '—'}</td>
        <td>${p.registration_date ? new Date(p.registration_date).toLocaleDateString() : '—'}</td>
        <td style="display:flex;gap:.4rem;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" onclick="viewPatient('${p.patient_id}')">View</button>
          <button class="btn btn-secondary btn-sm" onclick="startReanalysis('${p.patient_id}')">Re-run Analysis</button>
          ${STATE.user?.role === 'admin' ? `<button class="btn btn-danger btn-sm" onclick="deletePatient('${p.patient_id}')">Delete</button>` : ''}
        </td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

async function viewPatient(patientId) {
  navigate('view-patient-profile');
  const el = document.getElementById('patient-profile-content');
  el.innerHTML = 'Loading…';
  try {
    const [pRes, hRes] = await Promise.all([
      api(`/api/patients/${patientId}`),
      api(`/api/patients/${patientId}/history`),
    ]);
    if (pRes.status === 'success') {
      renderPatientProfile(pRes.patient, hRes.history || []);
    } else {
      el.innerHTML = '<p>Patient not found.</p>';
    }
  } catch (err) {
    el.innerHTML = '<p>Error loading patient.</p>';
  }
}

function renderPatientProfile(p, history) {
  const el = document.getElementById('patient-profile-content');
  const initials = ((p.first_name || '?')[0] + (p.last_name || '?')[0]).toUpperCase();
  const canEdit = STATE.user?.role === 'admin' || STATE.user?.role === 'doctor';
  const role = STATE.user?.role || '';
  const isSpecialist = role === 'admin' || (role === 'doctor' && (STATE.user?.full_name || '').startsWith('Dr.'));

  let html = `
  <div class="profile-header">
    <div class="profile-avatar">${initials}</div>
    <div>
      <div class="profile-name">${p.first_name} ${p.last_name}</div>
      <div class="profile-meta">${p.patient_id} · Age ${p.age || '—'} · ${p.gender || '—'} · Physician: ${p.physician || '—'}</div>
    </div>
    <div style="margin-left:auto;display:flex;gap:.5rem;flex-wrap:wrap">
      <button class="btn btn-primary btn-sm" onclick="startReanalysis('${p.patient_id}')">+ Re-run Analysis</button>
      ${canEdit ? `<button class="btn btn-ghost btn-sm" onclick="editPatient('${p.patient_id}')">Edit</button>` : ''}
      ${role === 'admin' ? `<button class="btn btn-danger btn-sm" onclick="deletePatient('${p.patient_id}')">Delete</button>` : ''}
    </div>
  </div>

  <h3 class="section-title">Assessment History</h3>`;

  if (!history.length) {
    html += '<p class="muted-text">No assessments recorded yet.</p>';
  } else {
    html += `<table>
      <thead><tr>
        <th>Date</th><th>Ensemble</th><th>Confidence</th><th>Performed By</th>
        ${isSpecialist ? '<th>Details</th>' : ''}
      </tr></thead>
      <tbody>`;
    for (const h of history) {
      const isCkd = h.ckd_detected === 1 || h.ckd_detected === true || h.ensemble_result === 'ckd';
      html += `<tr>
        <td>${h.prediction_date ? new Date(h.prediction_date).toLocaleString() : '—'}</td>
        <td><span class="badge ${isCkd ? 'badge-red' : 'badge-green'}">${isCkd ? 'CKD' : 'No CKD'}</span></td>
        <td>${h.ensemble_confidence != null ? Math.round(h.ensemble_confidence * 100) + '%' : '—'}</td>
        <td>${h.performed_by || '—'}</td>
        ${isSpecialist ? `<td><button class="btn btn-ghost btn-sm" onclick="showHistoryDetail(${JSON.stringify(h).replace(/"/g,'&quot;')})">Details</button></td>` : ''}
      </tr>`;
    }
    html += '</tbody></table>';
  }

  el.innerHTML = html;
}

function showHistoryDetail(h) {
  const models = h.model_results || {};
  let rows = '';
  for (const [name, mres] of Object.entries(models)) {
    const mCkd = mres.prediction === 'ckd';
    rows += `<tr>
      <td>${formatModelName(name)}</td>
      <td><span class="badge ${mCkd ? 'badge-red' : 'badge-green'}">${mCkd ? 'CKD' : 'No CKD'}</span></td>
      <td>${mres.confidence != null ? Math.round(mres.confidence * 100) + '%' : '—'}</td>
    </tr>`;
  }

  const body = document.getElementById('patient-edit-body');
  const modal = document.getElementById('modal-patient-edit');
  document.querySelector('#modal-patient-edit .modal-header h3').textContent = 'Assessment Detail';
  document.querySelector('#modal-patient-edit .modal-footer').innerHTML =
    '<button class="btn btn-ghost" onclick="closeModal(\'modal-patient-edit\')">Close</button>';

  body.innerHTML = `
    <p><strong>Date:</strong> ${new Date(h.prediction_date).toLocaleString()}</p>
    <p style="margin-bottom:.75rem"><strong>Performed by:</strong> ${h.performed_by || '—'}</p>
    <table><thead><tr><th>Model</th><th>Prediction</th><th>Confidence</th></tr></thead>
    <tbody>${rows}</tbody></table>`;

  modal.classList.remove('hidden');
}

// ── Re-run Analysis for an existing patient ─────────────────────────────────
async function startReanalysis(patientId) {
  showToast('Loading patient…');
  try {
    const [pRes, hRes] = await Promise.all([
      api(`/api/patients/${patientId}`),
      api(`/api/patients/${patientId}/history`),
    ]);
    if (pRes.status !== 'success') { showToast('Patient not found.', 'error'); return; }

    const p = pRes.patient;
    STATE.currentPatient = p;

    // Update Step-2 patient banner
    const banner = document.getElementById('params-patient-banner');
    if (banner) banner.textContent = `Patient: ${p.first_name} ${p.last_name} · ${p.patient_id}`;

    // Pre-fill age from patient record
    const ageInput = document.getElementById('param-age');
    if (ageInput && p.age) ageInput.value = p.age;

    // Pre-fill all medical params from the most recent assessment (if any)
    const history = hRes.history || [];
    if (history.length) {
      const last = history[history.length - 1];
      const lastParams = last.medical_params || {};
      const form = document.getElementById('medical-params-form');
      if (form && Object.keys(lastParams).length) {
        for (const [key, val] of Object.entries(lastParams)) {
          const el = form.elements[key];
          if (el && val !== null && val !== undefined) {
            el.value = val;
          }
        }
        showToast(`Pre-filled with last assessment (${new Date(last.prediction_date).toLocaleDateString()}). Update as needed.`);
      } else {
        showToast('Patient loaded. Enter new health parameters.');
      }
    } else {
      showToast('Patient loaded. Enter health parameters.');
    }

    navigate('view-medical-params');
  } catch (err) {
    showToast('Error loading patient: ' + err.message, 'error');
  }
}

async function deletePatient(patientId) {
  if (!confirm(`Delete patient ${patientId}? This cannot be undone.`)) return;
  try {
    const res = await api(`/api/patients/${patientId}`, { method: 'DELETE' });
    showToast(res.message || 'Patient deleted.', res.status === 'success' ? 'success' : 'error');
    if (res.status === 'success') {
      loadPatients();
      if (document.getElementById('view-patient-profile').classList.contains('active')) {
        navigate('view-patient-lookup');
      }
    }
  } catch (err) { showToast('Error deleting patient.', 'error'); }
}

async function editPatient(patientId) {
  const modal = document.getElementById('modal-patient-edit');
  const body  = document.getElementById('patient-edit-body');
  document.querySelector('#modal-patient-edit .modal-header h3').textContent = 'Edit Patient';
  document.querySelector('#modal-patient-edit .modal-footer').innerHTML = `
    <button class="btn btn-ghost" onclick="closeModal('modal-patient-edit')">Cancel</button>
    <button class="btn btn-primary" onclick="savePatientEdit('${patientId}')">Save Changes</button>`;

  body.innerHTML = 'Loading…';
  modal.classList.remove('hidden');
  modal._editId = patientId;

  const res = await api(`/api/patients/${patientId}`);
  if (res.status === 'success') {
    const p = res.patient;
    body.innerHTML = `
      <div class="form-row">
        <div class="form-group"><label class="form-label">First Name</label><input type="text" id="ep-first" class="form-control" value="${p.first_name || ''}"/></div>
        <div class="form-group"><label class="form-label">Last Name</label><input type="text" id="ep-last" class="form-control" value="${p.last_name || ''}"/></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Age</label><input type="number" id="ep-age" class="form-control" value="${p.age || ''}"/></div>
        <div class="form-group"><label class="form-label">Gender</label>
          <select id="ep-gender" class="form-control">
            <option value="Male" ${p.gender==='Male'?'selected':''}>Male</option>
            <option value="Female" ${p.gender==='Female'?'selected':''}>Female</option>
          </select>
        </div>
      </div>
      <div class="form-group"><label class="form-label">Physician</label><input type="text" id="ep-physician" class="form-control" value="${p.physician || ''}"/></div>
      <div class="form-group"><label class="form-label">Notes</label><textarea id="ep-notes" class="form-control" rows="2">${p.notes || ''}</textarea></div>`;
  }
}

async function savePatientEdit(patientId) {
  const pid = patientId || document.getElementById('modal-patient-edit')._editId;
  const data = {
    first_name: document.getElementById('ep-first')?.value,
    last_name: document.getElementById('ep-last')?.value,
    age: document.getElementById('ep-age')?.value,
    gender: document.getElementById('ep-gender')?.value,
    physician: document.getElementById('ep-physician')?.value,
    notes: document.getElementById('ep-notes')?.value,
  };
  try {
    const res = await api(`/api/patients/${pid}`, { method: 'PUT', body: data });
    showToast(res.message || 'Patient updated.', res.status === 'success' ? 'success' : 'error');
    if (res.status === 'success') {
      closeModal('modal-patient-edit');
      if (document.getElementById('view-patient-profile').classList.contains('active')) {
        viewPatient(pid);
      }
    }
  } catch (err) { showToast('Error updating patient.', 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════════
//  ADMIN — USERS
// ═══════════════════════════════════════════════════════════════════════════
async function loadUsersTable() {
  const wrap = document.getElementById('users-table-wrap');
  if (!wrap) return;
  wrap.innerHTML = 'Loading…';
  try {
    const res = await api('/api/users');
    if (res.status === 'success') renderUsersTable(res.users || []);
  } catch (_) { wrap.innerHTML = '<p>Error loading users.</p>'; }
}

function renderUsersTable(users) {
  const wrap = document.getElementById('users-table-wrap');
  if (!wrap) return;
  wrap.innerHTML = `<table>
    <thead><tr><th>Username</th><th>Full Name</th><th>Role</th><th>Email</th><th>Actions</th></tr></thead>
    <tbody>${users.map(u => `
      <tr>
        <td class="mono">${u.username}</td>
        <td>${u.full_name || '—'}</td>
        <td><span class="badge badge-${roleColor(u.role)}">${u.role}</span></td>
        <td>${u.email || '—'}</td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="editUser('${u.username}', '${u.full_name}', '${u.role}', '${u.email}')">Edit</button>
          ${u.username !== STATE.user?.username ? `<button class="btn btn-danger btn-sm" onclick="deleteUser('${u.username}')">Delete</button>` : ''}
        </td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

function roleColor(r) {
  return r === 'admin' ? 'red' : r === 'doctor' ? 'blue' : 'purple';
}

function showAddUserModal() {
  document.getElementById('modal-user-title').textContent = 'Add User';
  document.getElementById('nu-username').value = '';
  document.getElementById('nu-username').disabled = false;
  document.getElementById('nu-fullname').value = '';
  document.getElementById('nu-email').value = '';
  document.getElementById('nu-role').value = 'doctor';
  document.getElementById('nu-pwd-wrap').style.display = 'block';
  document.getElementById('nu-password').value = '';
  document.getElementById('user-msg').classList.add('hidden');
  document.getElementById('modal-add-user').dataset.mode = 'add';
  document.getElementById('modal-add-user').classList.remove('hidden');
}

function editUser(username, fullName, role, email) {
  document.getElementById('modal-user-title').textContent = 'Edit User';
  document.getElementById('nu-username').value = username;
  document.getElementById('nu-username').disabled = true;
  document.getElementById('nu-fullname').value = fullName;
  document.getElementById('nu-email').value = email || '';
  document.getElementById('nu-role').value = role;
  document.getElementById('nu-pwd-wrap').style.display = 'none';
  document.getElementById('user-msg').classList.add('hidden');
  document.getElementById('modal-add-user').dataset.mode = 'edit';
  document.getElementById('modal-add-user').dataset.editUser = username;
  document.getElementById('modal-add-user').classList.remove('hidden');
}

async function saveUser() {
  const modal = document.getElementById('modal-add-user');
  const msgEl = document.getElementById('user-msg');
  const mode = modal.dataset.mode;
  const username = document.getElementById('nu-username').value;
  const fullName = document.getElementById('nu-fullname').value;
  const email    = document.getElementById('nu-email').value;
  const role     = document.getElementById('nu-role').value;

  try {
    let res;
    if (mode === 'add') {
      const password = document.getElementById('nu-password').value;
      res = await api('/api/users', { method: 'POST', body: { username, password, full_name: fullName, role, email } });
    } else {
      const editUser_ = modal.dataset.editUser;
      res = await api(`/api/users/${editUser_}`, { method: 'PUT', body: { full_name: fullName, role, email } });
    }

    if (res.status === 'success') {
      closeModal('modal-add-user');
      showToast(mode === 'add' ? 'User created.' : 'User updated.', 'success');
      loadUsersTable();
    } else {
      msgEl.textContent = res.message || 'Error occurred.';
      msgEl.className = 'alert alert-danger';
      msgEl.classList.remove('hidden');
    }
  } catch (err) {
    msgEl.textContent = 'Request failed.';
    msgEl.className = 'alert alert-danger';
    msgEl.classList.remove('hidden');
  }
}

async function deleteUser(username) {
  if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return;
  try {
    const res = await api(`/api/users/${username}`, { method: 'DELETE' });
    showToast(res.message || 'User deleted.', res.status === 'success' ? 'success' : 'error');
    if (res.status === 'success') loadUsersTable();
  } catch (_) { showToast('Error deleting user.', 'error'); }
}

async function loadPatientsAdmin() {
  const wrap = document.getElementById('patients-admin-table-wrap');
  if (!wrap) return;
  wrap.innerHTML = 'Loading…';
  try {
    const res = await api('/api/patients');
    if (res.status === 'success') {
      STATE.patientsCache = res.patients || [];
      renderPatientsTable(STATE.patientsCache, wrap);
    }
  } catch (_) { wrap.innerHTML = '<p>Error loading patients.</p>'; }
}

function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => { p.classList.remove('active'); p.classList.add('hidden'); });
  btn.classList.add('active');
  const panel = document.getElementById(tabId);
  if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
}

// ═══════════════════════════════════════════════════════════════════════════
//  ACCOUNT / CHANGE PASSWORD
// ═══════════════════════════════════════════════════════════════════════════
function showAccountModal() {
  const u = STATE.user;
  if (!u) return;
  const initials = (u.full_name || u.username)[0].toUpperCase();
  // Modal header avatar
  const av = document.getElementById('acc-modal-avatar');
  if (av) av.textContent = initials;
  const un = document.getElementById('acc-modal-username');
  if (un) un.textContent = '@' + u.username;
  // Editable fields
  const fnInput = document.getElementById('acc-fullname-input');
  const emInput = document.getElementById('acc-email-input');
  const rlInput = document.getElementById('acc-role-display');
  if (fnInput) fnInput.value = u.full_name || '';
  if (emInput) emInput.value = u.email || '';
  if (rlInput) rlInput.value = u.role;
  // Password fields
  document.getElementById('old-pwd').value = '';
  document.getElementById('new-pwd').value = '';
  document.getElementById('confirm-pwd').value = '';
  document.getElementById('pwd-message').classList.add('hidden');
  document.getElementById('profile-save-message')?.classList.add('hidden');
  // Reset to first tab
  switchAccTab('tab-details', document.querySelector('.tabs .tab-btn'));
  document.getElementById('modal-account').classList.remove('hidden');
}

function switchAccTab(tabId, btn) {
  document.querySelectorAll('#modal-account .tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('#modal-account .tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(tabId)?.classList.add('active');
  if (btn) btn.classList.add('active');
  // Wire save button
  const saveBtn = document.getElementById('acc-save-btn');
  if (saveBtn) saveBtn.onclick = tabId === 'tab-details' ? saveProfile : changePassword;
}

async function saveProfile() {
  const msgEl = document.getElementById('profile-save-message');
  const fullName = document.getElementById('acc-fullname-input').value.trim();
  const email    = document.getElementById('acc-email-input').value.trim();
  const u = STATE.user;
  if (!u) return;

  try {
    const res = await api(`/api/users/${u.username}`, {
      method: 'PUT',
      body: { full_name: fullName, email, role: u.role },
    });
    if (res.status === 'success') {
      // Update local state & all UI display points
      u.full_name = fullName;
      u.email     = email;
      setUser(u);
      msgEl.textContent = 'Profile updated successfully.';
      msgEl.className = 'alert alert-success';
    } else {
      msgEl.textContent = res.message || 'Update failed.';
      msgEl.className = 'alert alert-danger';
    }
  } catch (err) {
    msgEl.textContent = 'Request failed: ' + err.message;
    msgEl.className = 'alert alert-danger';
  }
  msgEl.classList.remove('hidden');
}

async function changePassword() {
  const msgEl = document.getElementById('pwd-message');
  const oldPwd = document.getElementById('old-pwd').value;
  const newPwd = document.getElementById('new-pwd').value;
  const confirmPwd = document.getElementById('confirm-pwd').value;

  if (newPwd !== confirmPwd) {
    msgEl.textContent = 'New passwords do not match.';
    msgEl.className = 'alert alert-danger';
    msgEl.classList.remove('hidden');
    return;
  }
  if (newPwd.length < 6) {
    msgEl.textContent = 'Password must be at least 6 characters.';
    msgEl.className = 'alert alert-danger';
    msgEl.classList.remove('hidden');
    return;
  }

  try {
    const res = await api('/api/account/change-password', {
      method: 'POST',
      body: { old_password: oldPwd, new_password: newPwd },
    });
    msgEl.textContent = res.message || (res.status === 'success' ? 'Password changed.' : 'Error.');
    msgEl.className = 'alert ' + (res.status === 'success' ? 'alert-success' : 'alert-danger');
    msgEl.classList.remove('hidden');
  } catch (err) {
    msgEl.textContent = 'Request failed.';
    msgEl.className = 'alert alert-danger';
    msgEl.classList.remove('hidden');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════════════════
async function api(path, { method = 'GET', body } = {}) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw Object.assign(new Error(err.message || 'Request failed'), { status: res.status });
  }
  return res.json();
}

function formToObj(form) {
  const obj = {};
  new FormData(form).forEach((v, k) => { if (v !== '') obj[k] = v; });
  return obj;
}

function setLoading(btn, loading) {
  if (!btn) return;
  const textEl = btn.querySelector('.btn-text');
  const spinEl = btn.querySelector('.btn-spinner');
  btn.disabled = loading;
  if (textEl) textEl.classList.toggle('hidden', loading);
  if (spinEl) spinEl.classList.toggle('hidden', !loading);
}

let _toastTimer;
function showToast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast' + (type ? ' ' + type : '');
  el.classList.remove('hidden');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}

function closeModal(id) {
  document.getElementById(id)?.classList.add('hidden');
}
