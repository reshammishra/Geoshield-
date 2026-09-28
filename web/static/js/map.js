/**
 * GeoShield – Geospatial Command Map
 * Implements Leaflet.js with Event Clusters, Risk Score visual encoding,
 * Satellite Basemaps, and deep Incident Detail Drawer with Evidence traceability.
 */

window.GeoShieldMap = null;
let currentLayerGroup = null;
let heatmapLayer = null;

function initGeoShieldMap(elementId = 'map-viewport') {
  const container = document.getElementById(elementId);
  if (!container) return;

  // 1. Initialise map centered on India
  const map = L.map(elementId, {
    center: [22.5, 80.0],
    zoom: 5,
    minZoom: 4,
    maxZoom: 16,
    zoomControl: false
  });

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  // 2. Basemap layers
  const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CartoDB &copy; OpenStreetMap',
    maxZoom: 19
  });

  const satTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: '&copy; Esri World Imagery',
    maxZoom: 18
  });

  darkTiles.addTo(map);

  // Layer control dict
  const baseMaps = {
    "Command Dark": darkTiles,
    "Satellite Imagery": satTiles
  };

  currentLayerGroup = L.layerGroup().addTo(map);
  window.GeoShieldMap = map;

  // Load Map Incidents
  loadMapIncidents();

  // Bind layer switcher buttons if present
  const btnClusters = document.getElementById('layer-clusters');
  const btnHeatmap = document.getElementById('layer-heatmap');
  const btnSat = document.getElementById('layer-sat');

  if (btnClusters) {
    btnClusters.addEventListener('click', () => {
      if (satTiles) map.removeLayer(satTiles);
      if (heatmapLayer) map.removeLayer(heatmapLayer);
      darkTiles.addTo(map);
      currentLayerGroup.addTo(map);
      updateActiveLayerBtn(btnClusters);
    });
  }

  if (btnHeatmap) {
    btnHeatmap.addEventListener('click', async () => {
      if (currentLayerGroup) map.removeLayer(currentLayerGroup);
      await loadHeatmapLayer();
      updateActiveLayerBtn(btnHeatmap);
    });
  }

  if (btnSat) {
    btnSat.addEventListener('click', () => {
      if (darkTiles) map.removeLayer(darkTiles);
      satTiles.addTo(map);
      currentLayerGroup.addTo(map);
      updateActiveLayerBtn(btnSat);
    });
  }
}

function updateActiveLayerBtn(activeBtn) {
  document.querySelectorAll('.map-layer-btn').forEach(b => b.classList.remove('active'));
  if (activeBtn) activeBtn.classList.add('active');
}

async function loadMapIncidents(filters = {}) {
  if (!window.GeoShieldMap || !currentLayerGroup) return;
  currentLayerGroup.clearLayers();

  try {
    const params = new URLSearchParams(filters);
    const res = await fetch(`/api/incidents/map?${params.toString()}`);
    const data = await res.json();

    if (!data.features || data.features.length === 0) {
      return;
    }

    data.features.forEach(feat => {
      const [lon, lat] = feat.geometry.coordinates;
      const p = feat.properties;

      // Color encoding based on risk score and event type
      let markerColor = '#10B981'; // Green
      if (p.risk_score >= 75) markerColor = '#EF4444'; // Red
      else if (p.risk_score >= 50) markerColor = '#F59E0B'; // Amber
      else if (p.risk_score >= 25) markerColor = '#38BDF8'; // Blue

      const circle = L.circleMarker([lat, lon], {
        radius: Math.min(20, Math.max(6, Math.sqrt(p.detection_count) * 3)),
        fillColor: markerColor,
        color: '#FFFFFF',
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.75
      });

      // Quick hover tooltip
      circle.bindTooltip(`
        <div style="font-family:var(--font-main); font-size:0.8rem;">
          <strong style="color:${markerColor}">${p.event_type} (${p.city || 'Unknown'})</strong><br/>
          Risk Score: <strong>${p.risk_score}/100</strong> (${p.risk_level})<br/>
          Detections: ${p.detection_count} | Max FRP: ${p.max_frp} MW
        </div>
      `, { direction: 'top', offset: [0, -8] });

      // Click event opens the deep incident detail drawer
      circle.on('click', () => {
        window.GeoShield.openIncidentDrawer(p.event_id);
      });

      currentLayerGroup.addLayer(circle);
    });

  } catch (err) {
    console.error('Failed to load map incidents', err);
  }
}

async function loadHeatmapLayer() {
  if (!window.GeoShieldMap) return;
  try {
    const res = await fetch('/api/analytics/heatmap-data?max=3000');
    const data = await res.json();
    if (!data.points || data.points.length === 0) return;

    if (heatmapLayer) {
      window.GeoShieldMap.removeLayer(heatmapLayer);
    }

    if (L.heatLayer) {
      heatmapLayer = L.heatLayer(data.points, {
        radius: 20,
        blur: 15,
        maxZoom: 10,
        gradient: { 0.2: '#38BDF8', 0.5: '#F59E0B', 0.8: '#EF4444' }
      }).addTo(window.GeoShieldMap);
    } else {
      // Fallback simple circle cluster if heatLayer library not loaded
      heatmapLayer = L.layerGroup();
      data.points.forEach(pt => {
        L.circleMarker([pt[0], pt[1]], {
          radius: 4,
          fillColor: '#EF4444',
          color: 'transparent',
          fillOpacity: pt[2]
        }).addTo(heatmapLayer);
      });
      heatmapLayer.addTo(window.GeoShieldMap);
    }
  } catch (err) {
    console.error('Heatmap load error', err);
  }
}

/**
 * Slide-in Incident Detail Drawer with Traceable Evidence Records
 */
window.GeoShield.openIncidentDrawer = async function(eventId) {
  const drawer = document.getElementById('incident-drawer');
  if (!drawer) return;

  drawer.classList.add('open');
  const body = document.getElementById('drawer-content');
  if (!body) return;

  body.innerHTML = `
    <div style="text-align:center; padding:3rem; color:var(--text-muted);">
      <div class="pulse-dot" style="margin:0 auto 1rem; width:12px; height:12px;"></div>
      Loading Incident #${eventId} Intelligence...
    </div>
  `;

  try {
    const res = await fetch(`/api/incidents/${eventId}`);
    if (!res.ok) throw new Error('Incident not found');
    const inc = await res.json();

    let riskBadgeClass = 'badge-low';
    if (inc.risk_level === 'CRITICAL') riskBadgeClass = 'badge-critical';
    else if (inc.risk_level === 'HIGH') riskBadgeClass = 'badge-high';
    else if (inc.risk_level === 'MEDIUM') riskBadgeClass = 'badge-medium';

    // Build factor explanations
    const factorsHtml = (inc.risk_factors || []).map(f => `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border-light); font-size:0.8rem;">
        <div>
          <strong style="color:var(--text-primary);">${f.factor}</strong>
          <span style="font-size:0.7rem; color:var(--text-muted); display:block;">${f.detail}</span>
        </div>
        <span style="font-family:var(--font-mono); font-weight:700; color:var(--color-flood);">+${f.points} pts</span>
      </div>
    `).join('');

    // Evidence table rows
    const evidenceHtml = (inc.evidence || []).map(e => `
      <tr>
        <td style="font-family:var(--font-mono);">${e.acq_date || 'N/A'}</td>
        <td>${e.latitude?.toFixed(3)}, ${e.longitude?.toFixed(3)}</td>
        <td style="color:var(--color-warning); font-weight:700;">${e.frp ? e.frp.toFixed(1) + ' MW' : '0 MW'}</td>
        <td>${e.confidence || 75}%</td>
      </tr>
    `).join('');

    body.innerHTML = `
      <div style="margin-bottom:1.25rem;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <span class="badge ${inc.event_type === 'Fire' ? 'badge-fire' : 'badge-flood'}">${inc.event_type}</span>
            <span class="badge ${riskBadgeClass}" style="margin-left:4px;">${inc.risk_level}</span>
            <h2 style="font-size:1.25rem; font-weight:800; margin-top:0.4rem; color:var(--text-primary);">
              ${inc.city || 'Unknown Region'} Cluster
            </h2>
            <span style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">
              EVENT_ID: #${inc.event_id}
            </span>
          </div>
          <div style="text-align:right;">
            <div style="font-size:1.6rem; font-weight:800; font-family:var(--font-mono); color:var(--text-highlight);">
              ${inc.risk_score}<span style="font-size:0.85rem; color:var(--text-muted);">/100</span>
            </div>
            <span style="font-size:0.68rem; text-transform:uppercase; color:var(--text-muted); font-weight:700;">Dynamic Risk Score</span>
          </div>
        </div>
      </div>

      <!-- Quick Metrics Strip -->
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:1.25rem;">
        <div style="background:var(--bg-card); padding:8px 10px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
          <span style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase; display:block;">Detections</span>
          <strong style="font-size:0.95rem; font-family:var(--font-mono);">${inc.detection_count}</strong>
        </div>
        <div style="background:var(--bg-card); padding:8px 10px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
          <span style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase; display:block;">Max FRP</span>
          <strong style="font-size:0.95rem; font-family:var(--font-mono); color:var(--color-warning);">${inc.max_frp} MW</strong>
        </div>
        <div style="background:var(--bg-card); padding:8px 10px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
          <span style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase; display:block;">Duration</span>
          <strong style="font-size:0.95rem; font-family:var(--font-mono);">${inc.duration_days} Days</strong>
        </div>
      </div>

      <!-- Explainable Risk Engine Breakdown -->
      <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:12px; margin-bottom:1.25rem;">
        <h4 style="font-size:0.8rem; font-weight:700; color:var(--text-secondary); text-transform:uppercase; margin-bottom:8px;">
          ⚖️ Explainable Risk Calculation Factors
        </h4>
        ${factorsHtml}
      </div>

      <!-- Raw Observation Evidence Traceability -->
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h4 style="font-size:0.8rem; font-weight:700; color:var(--text-secondary); text-transform:uppercase;">
            🛰️ Underlying Satellite Evidence (${inc.evidence_count} Points)
          </h4>
        </div>
        <div class="table-responsive" style="max-height:220px; overflow-y:auto; border:1px solid var(--border-subtle); border-radius:var(--radius-sm);">
          <table class="custom-table" style="font-size:0.75rem;">
            <thead>
              <tr>
                <th>Date</th>
                <th>Coords</th>
                <th>FRP</th>
                <th>Conf</th>
              </tr>
            </thead>
            <tbody>
              ${evidenceHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;

  } catch (err) {
    body.innerHTML = `
      <div style="padding:2rem; color:var(--color-fire); text-align:center;">
        Failed to load incident detail: ${err.message}
      </div>
    `;
  }
};

window.GeoShield.closeIncidentDrawer = function() {
  const drawer = document.getElementById('incident-drawer');
  if (drawer) drawer.classList.remove('open');
};
