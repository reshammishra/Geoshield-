/**
 * GeoShield – Dashboard Controller
 * Orchestrates KPIs, What Changed In Last 24 Hours, Priority Queue, and Filters.
 */

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

async function initDashboard() {
  // 1. Initialise map
  if (typeof initGeoShieldMap === 'function') {
    initGeoShieldMap('map-viewport');
  }

  // 2. Load KPIs and What Changed
  await Promise.all([
    loadKPISummary(),
    loadWhatChanged(),
    loadPriorityQueue()
  ]);

  // 3. Bind filter events
  const filterForm = document.getElementById('dashboard-filter-form');
  if (filterForm) {
    filterForm.addEventListener('change', () => {
      applyDashboardFilters();
    });
  }
}

function getSelectedFilters() {
  const years = Array.from(document.querySelectorAll('input[name="year"]:checked')).map(el => el.value);
  const types = Array.from(document.querySelectorAll('input[name="event_type"]:checked')).map(el => el.value);
  const confMin = document.getElementById('conf-slider')?.value || 50;

  return {
    years: years,
    event_types: types,
    confidence_min: confMin
  };
}

async function loadKPISummary(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.years) filters.years.forEach(y => params.append('years', y));
    if (filters.event_types) filters.event_types.forEach(t => params.append('event_types', t));
    if (filters.confidence_min) params.append('confidence_min', filters.confidence_min);

    const res = await fetch(`/api/dashboard/summary?${params.toString()}`);
    const data = await res.json();

    document.getElementById('kpi-total-detections').innerText = window.GeoShield.formatNumber(data.total_detections);
    document.getElementById('kpi-fire-count').innerText = window.GeoShield.formatNumber(data.fire_count);
    document.getElementById('kpi-flood-count').innerText = window.GeoShield.formatNumber(data.flood_count);
    document.getElementById('kpi-high-severity').innerText = window.GeoShield.formatNumber(data.high_severity);
    document.getElementById('kpi-area-affected').innerText = `${window.GeoShield.formatNumber(data.total_area_km2)} km²`;
    
    // Header summary strip
    if (document.getElementById('strip-cities')) {
      document.getElementById('strip-cities').innerText = data.cities_covered;
      document.getElementById('strip-date-range').innerText = `${data.date_from} → ${data.date_to}`;
      document.getElementById('strip-max-frp').innerText = `${data.max_frp} MW`;
    }

  } catch (err) {
    console.error('KPI summary load error', err);
  }
}

async function loadWhatChanged() {
  const container = document.getElementById('what-changed-card');
  if (!container) return;

  try {
    const res = await fetch('/api/dashboard/what-changed');
    const data = await res.json();

    const formatDelta = (val) => {
      if (val === null || val === undefined) return '';
      const sign = val > 0 ? '+' : '';
      const color = val > 0 ? 'var(--color-fire)' : 'var(--color-normal)';
      return `<span style="color:${color}; font-weight:700; margin-left:4px;">${sign}${val}</span>`;
    };

    container.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:0.75rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-light); padding-bottom:0.5rem;">
          <span style="font-size:0.85rem; color:var(--text-secondary);">Total Active Detections</span>
          <div>
            <strong style="font-family:var(--font-mono);">${data.recent_total}</strong>
            ${formatDelta(data.delta_total)}
          </div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-light); padding-bottom:0.5rem;">
          <span style="font-size:0.85rem; color:var(--text-secondary);">🔥 Fire Activity</span>
          <div>
            <strong style="font-family:var(--font-mono);">${data.recent_fire}</strong>
            ${formatDelta(data.delta_fire)}
          </div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-light); padding-bottom:0.5rem;">
          <span style="font-size:0.85rem; color:var(--text-secondary);">🌊 Flood Indications</span>
          <div>
            <strong style="font-family:var(--font-mono);">${data.recent_flood}</strong>
            ${formatDelta(data.delta_flood)}
          </div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-light); padding-bottom:0.5rem;">
          <span style="font-size:0.85rem; color:var(--text-secondary);">🔴 High Severity Escalations</span>
          <div>
            <strong style="font-family:var(--font-mono);">${data.recent_high}</strong>
            ${formatDelta(data.delta_high)}
          </div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.85rem; color:var(--text-secondary);">⚡ Average FRP Change</span>
          <div>
            <strong style="font-family:var(--font-mono);">${data.recent_avg_frp} MW</strong>
            ${formatDelta(data.delta_avg_frp)}
          </div>
        </div>
      </div>
    `;

  } catch (err) {
    console.error('What changed error', err);
  }
}

async function loadPriorityQueue() {
  const tbody = document.getElementById('priority-queue-tbody');
  if (!tbody) return;

  try {
    const res = await fetch('/api/incidents/priority?n=8');
    const data = await res.json();

    if (!data.priority_queue || data.priority_queue.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No critical incidents queued.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.priority_queue.map(item => {
      let riskBadge = 'badge-low';
      if (item.risk_level === 'CRITICAL') riskBadge = 'badge-critical';
      else if (item.risk_level === 'HIGH') riskBadge = 'badge-high';
      else if (item.risk_level === 'MEDIUM') riskBadge = 'badge-medium';

      return `
        <tr onclick="window.GeoShield.openIncidentDrawer('${item.event_id}')">
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-highlight);">#${item.priority_rank}</td>
          <td>
            <strong>${item.city || 'Unknown Region'}</strong>
            <span style="display:block; font-size:0.7rem; color:var(--text-muted); font-family:var(--font-mono);">ID: #${item.event_id}</span>
          </td>
          <td><span class="badge ${item.event_type === 'Fire' ? 'badge-fire' : 'badge-flood'}">${item.event_type}</span></td>
          <td><span class="badge ${riskBadge}">${item.risk_score}/100</span></td>
          <td style="font-family:var(--font-mono); color:var(--color-warning); font-weight:600;">${item.max_frp} MW</td>
          <td style="font-size:0.75rem; color:var(--text-muted);">${item.latest_detection.slice(0, 10)}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Priority queue error', err);
  }
}

function applyDashboardFilters() {
  const filters = getSelectedFilters();
  loadKPISummary(filters);
  if (typeof loadMapIncidents === 'function') {
    loadMapIncidents(filters);
  }
}
