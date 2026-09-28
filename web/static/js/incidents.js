/**
 * GeoShield – Incidents Catalog Controller
 * Provides paginated access to fused disaster incidents, sorting, and filter controls.
 */

let currentPage = 1;

document.addEventListener('DOMContentLoaded', () => {
  initIncidentsPage();
});

function initIncidentsPage() {
  loadIncidents(1);

  const filterForm = document.getElementById('incidents-filter-form');
  if (filterForm) {
    filterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      loadIncidents(1);
    });
  }

  // Check URL params for focus query
  const urlParams = new URLSearchParams(window.location.search);
  const focusId = urlParams.get('focus');
  if (focusId) {
    setTimeout(() => window.GeoShield.openIncidentDrawer(focusId), 500);
  }
}

async function loadIncidents(page = 1) {
  currentPage = page;
  const tbody = document.getElementById('incidents-tbody');
  const paginationContainer = document.getElementById('pagination-controls');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:2rem; color:var(--text-muted);">Loading incidents from event fusion engine...</td></tr>`;

  try {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('per_page', 25);

    const yearVal = document.getElementById('filter-year')?.value;
    if (yearVal) params.append('years', yearVal);

    const typeVal = document.getElementById('filter-type')?.value;
    if (typeVal && typeVal !== 'all') params.append('event_types', typeVal);

    const sevVal = document.getElementById('filter-severity')?.value;
    if (sevVal && sevVal !== 'all') params.append('severity', sevVal);

    const confVal = document.getElementById('filter-confidence')?.value;
    if (confVal) params.append('confidence_min', confVal);

    const res = await fetch(`/api/incidents?${params.toString()}`);
    const data = await res.json();

    if (!data.incidents || data.incidents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:2rem; color:var(--text-muted);">No fused incidents match selected filters.</td></tr>`;
      if (paginationContainer) paginationContainer.innerHTML = '';
      return;
    }

    document.getElementById('total-incident-count')?.innerText = `${data.total.toLocaleString()} Incidents`;

    tbody.innerHTML = data.incidents.map(inc => {
      let riskBadge = 'badge-low';
      if (inc.risk_level === 'CRITICAL') riskBadge = 'badge-critical';
      else if (inc.risk_level === 'HIGH') riskBadge = 'badge-high';
      else if (inc.risk_level === 'MEDIUM') riskBadge = 'badge-medium';

      return `
        <tr onclick="window.GeoShield.openIncidentDrawer('${inc.event_id}')">
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-highlight);">#${inc.event_id}</td>
          <td>
            <strong>${inc.city || 'Unknown'}</strong>
            <span style="display:block; font-size:0.7rem; color:var(--text-muted);">Lat ${inc.latitude.toFixed(2)}, Lon ${inc.longitude.toFixed(2)}</span>
          </td>
          <td><span class="badge ${inc.event_type === 'Fire' ? 'badge-fire' : 'badge-flood'}">${inc.event_type}</span></td>
          <td><span class="badge ${riskBadge}">${inc.risk_score}/100</span></td>
          <td style="font-family:var(--font-mono);">${inc.detection_count}</td>
          <td style="font-family:var(--font-mono); color:var(--color-warning); font-weight:600;">${inc.max_frp} MW</td>
          <td>${inc.duration_days} d</td>
          <td style="font-size:0.75rem; color:var(--text-muted);">${inc.latest_detection.slice(0, 10)}</td>
        </tr>
      `;
    }).join('');

    // Render pagination
    if (paginationContainer) {
      paginationContainer.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
          <span style="font-size:0.8rem; color:var(--text-muted);">Page ${data.page} of ${data.pages}</span>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary" ${data.page <= 1 ? 'disabled' : ''} onclick="loadIncidents(${data.page - 1})">Previous</button>
            <button class="btn btn-secondary" ${data.page >= data.pages ? 'disabled' : ''} onclick="loadIncidents(${data.page + 1})">Next</button>
          </div>
        </div>
      `;
    }

  } catch (err) {
    console.error('Failed to load incidents', err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--color-fire);">Error loading incidents: ${err.message}</td></tr>`;
  }
}
