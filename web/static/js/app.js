/**
 * GeoShield – Global App Utilities
 * Handles sidebar toggling, search dropdown, and toast notifications.
 */

window.GeoShield = {
  toast(message, type = 'info') {
    const container = document.getElementById('toast-container') || (() => {
      const c = document.createElement('div');
      c.id = 'toast-container';
      document.body.appendChild(c);
      return c;
    })();

    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span>${message}</span>`;
    container.appendChild(t);

    setTimeout(() => {
      t.style.opacity = '0';
      setTimeout(() => t.remove(), 300);
    }, 4000);
  },

  formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return Number(num).toLocaleString();
  }
};

document.addEventListener('DOMContentLoaded', () => {
  // Mobile sidebar toggle
  const mobileToggle = document.getElementById('btn-mobile-sidebar');
  const sidebar = document.querySelector('.sidebar');
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }

  // Global search input
  const searchInput = document.getElementById('global-search');
  const searchDropdown = document.getElementById('search-dropdown');

  if (searchInput && searchDropdown) {
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      const query = e.target.value.trim();
      if (query.length < 2) {
        searchDropdown.style.display = 'none';
        return;
      }

      debounceTimer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
          const data = await res.json();
          if (data.results && data.results.length > 0) {
            searchDropdown.innerHTML = data.results.map(r => `
              <div class="search-result-item" onclick="window.GeoShield.handleSearchResult(${r.lat}, ${r.lon}, '${r.event_id}')">
                <strong style="color:var(--text-highlight); font-size:0.85rem;">${r.title}</strong>
                <span style="font-size:0.75rem; color:var(--text-muted);">${r.subtitle}</span>
              </div>
            `).join('');
            searchDropdown.style.display = 'block';
          } else {
            searchDropdown.innerHTML = `<div style="padding:0.75rem; font-size:0.8rem; color:var(--text-muted); text-align:center;">No matching locations or incidents.</div>`;
            searchDropdown.style.display = 'block';
          }
        } catch (err) {
          console.error('Search error', err);
        }
      }, 300);
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
        searchDropdown.style.display = 'none';
      }
    });
  }

  window.GeoShield.handleSearchResult = (lat, lon, eventId) => {
    searchDropdown.style.display = 'none';
    if (window.GeoShieldMap && window.GeoShieldMap.flyTo) {
      window.GeoShieldMap.flyTo([lat, lon], 10);
      if (eventId) {
        window.GeoShield.openIncidentDrawer(eventId);
      }
    } else {
      window.location.href = `/incidents?focus=${eventId}`;
    }
  };
});
