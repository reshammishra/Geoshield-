/**
 * GeoShield – Alert Center Controller
 * Manages active alerts, rules CRUD, and automated detector scans.
 */

document.addEventListener('DOMContentLoaded', () => {
  initAlertCenter();
});

function initAlertCenter() {
  loadAlertStats();
  loadAlerts();
  loadRules();

  const scanBtn = document.getElementById('btn-scan-alerts');
  if (scanBtn) {
    scanBtn.addEventListener('click', async () => {
      scanBtn.disabled = true;
      scanBtn.innerText = 'Scanning Satellite Feeds...';
      try {
        const res = await fetch('/api/alerts/scan', { method: 'POST' });
        const data = await res.json();
        window.GeoShield.toast(`Scan complete: ${data.triggered} new alerts triggered!`, 'success');
        loadAlertStats();
        loadAlerts();
      } catch (err) {
        window.GeoShield.toast('Scan failed: ' + err.message, 'error');
      } finally {
        scanBtn.disabled = false;
        scanBtn.innerText = '⚡ Scan Detections Now';
      }
    });
  }

  const ruleForm = document.getElementById('create-rule-form');
  if (ruleForm) {
    ruleForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('rule-name').value;
      const cond = document.getElementById('rule-cond').value;
      const thresh = document.getElementById('rule-thresh').value;
      const etype = document.getElementById('rule-type').value;

      try {
        const res = await fetch('/api/alert-rules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, condition: cond, threshold: thresh, event_type: etype })
        });
        if (res.ok) {
          window.GeoShield.toast('Rule created successfully', 'success');
          ruleForm.reset();
          loadRules();
        }
      } catch (err) {
        window.GeoShield.toast('Failed to create rule', 'error');
      }
    });
  }
}

async function loadAlertStats() {
  try {
    const res = await fetch('/api/alerts/stats');
    const data = await res.json();

    document.getElementById('stat-total-alerts')?.innerText = data.total;
    document.getElementById('stat-active-alerts')?.innerText = data.active;
    document.getElementById('stat-acked-alerts')?.innerText = data.acknowledged;
    document.getElementById('stat-resolved-alerts')?.innerText = data.resolved;
  } catch (err) {
    console.error('Alert stats error', err);
  }
}

async function loadAlerts(statusFilter = '') {
  const tbody = document.getElementById('alerts-tbody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-muted);">Loading active alerts...</td></tr>`;

  try {
    const url = statusFilter ? `/api/alerts?status=${statusFilter}` : '/api/alerts';
    const res = await fetch(url);
    const data = await res.json();

    if (!data.alerts || data.alerts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No alerts logged. Click 'Scan Detections Now' to evaluate against active rules.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.alerts.map(a => `
      <tr>
        <td style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">${a.timestamp.slice(0, 16).replace('T', ' ')}</td>
        <td><strong>${a.city || 'India Sector'}</strong></td>
        <td><span class="badge ${a.label === 'Fire' ? 'badge-fire' : 'badge-flood'}">${a.label}</span></td>
        <td><strong style="color:var(--color-warning);">${a.frp ? a.frp.toFixed(0) + ' MW' : '0 MW'}</strong></td>
        <td>
          <span class="badge ${a.status === 'ACTIVE' ? 'badge-critical' : a.status === 'ACKNOWLEDGED' ? 'badge-medium' : 'badge-low'}">
            ${a.status}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:6px;">
            ${a.status === 'ACTIVE' ? `
              <button class="btn btn-secondary" style="padding:2px 8px; font-size:0.75rem;" onclick="acknowledgeAlert(${a.id})">Acknowledge</button>
            ` : ''}
            ${a.status !== 'RESOLVED' ? `
              <button class="btn btn-secondary" style="padding:2px 8px; font-size:0.75rem;" onclick="resolveAlert(${a.id})">Resolve</button>
            ` : '<span style="color:var(--text-muted); font-size:0.75rem;">Resolved</span>'}
          </div>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Alerts load error', err);
  }
}

async function acknowledgeAlert(id) {
  try {
    const res = await fetch(`/api/alerts/${id}/acknowledge`, { method: 'POST' });
    if (res.ok) {
      window.GeoShield.toast(`Alert #${id} acknowledged`, 'info');
      loadAlertStats();
      loadAlerts();
    }
  } catch (err) {
    window.GeoShield.toast('Action failed', 'error');
  }
}

async function resolveAlert(id) {
  try {
    const res = await fetch(`/api/alerts/${id}/resolve`, { method: 'POST' });
    if (res.ok) {
      window.GeoShield.toast(`Alert #${id} resolved`, 'success');
      loadAlertStats();
      loadAlerts();
    }
  } catch (err) {
    window.GeoShield.toast('Action failed', 'error');
  }
}

async function loadRules() {
  const container = document.getElementById('rules-list');
  if (!container) return;

  try {
    const res = await fetch('/api/alert-rules');
    const data = await res.json();

    container.innerHTML = (data.rules || []).map(r => `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid var(--border-light);">
        <div>
          <strong style="font-size:0.85rem; color:var(--text-primary);">${r.name}</strong>
          <span style="display:block; font-size:0.75rem; color:var(--text-muted);">
            If <code>${r.condition}</code> ≥ ${r.threshold} (${r.event_type})
          </span>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <button class="btn ${r.enabled ? 'btn-primary' : 'btn-secondary'}" style="padding:3px 10px; font-size:0.72rem;" onclick="toggleRule(${r.id})">
            ${r.enabled ? 'Active' : 'Disabled'}
          </button>
          <button class="btn btn-danger" style="padding:3px 8px; font-size:0.72rem;" onclick="deleteRule(${r.id})">×</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Rules error', err);
  }
}

async function toggleRule(id) {
  await fetch(`/api/alert-rules/${id}/toggle`, { method: 'POST' });
  loadRules();
}

async function deleteRule(id) {
  if (confirm('Delete this rule?')) {
    await fetch(`/api/alert-rules/${id}`, { method: 'DELETE' });
    loadRules();
  }
}
