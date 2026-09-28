/**
 * GeoShield – Intelligence Assistant Client Controller
 * Sends queries to the backend dataset analyst and renders grounded data responses.
 */

document.addEventListener('DOMContentLoaded', () => {
  initAssistant();
});

function initAssistant() {
  const form = document.getElementById('assistant-form');
  const input = document.getElementById('assistant-input');
  const chips = document.querySelectorAll('.suggestion-chip');

  if (form && input) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      sendMessage(q);
      input.value = '';
    });
  }

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-query') || chip.innerText.replace(/[""]/g, '').trim();
      sendMessage(q);
    });
  });
}

async function sendMessage(query) {
  const container = document.getElementById('chat-history');
  if (!container) return;

  // Append user bubble
  appendBubble('user', query);

  // Append thinking indicator
  const loadingId = 'loading-' + Date.now();
  const loadingDiv = document.createElement('div');
  loadingDiv.id = loadingId;
  loadingDiv.className = 'chat-bubble bubble-assistant loading';
  loadingDiv.innerHTML = `<span class="pulse-dot" style="display:inline-block; margin-right:6px;"></span> Querying real NASA VIIRS satellite datasets...`;
  container.appendChild(loadingDiv);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await fetch('/api/assistant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    const data = await res.json();
    loadingDiv.remove();

    if (data.error) {
      appendBubble('assistant', `<span style="color:var(--color-fire);">Query Error: ${data.error}</span>`);
      return;
    }

    // Build rich response card
    let metricsHtml = '';
    if (data.metrics && Object.keys(data.metrics).length > 0) {
      metricsHtml = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin:10px 0;">
          ${Object.entries(data.metrics).map(([k, v]) => `
            <div style="background:var(--bg-card); padding:8px 10px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase; display:block;">${k}</span>
              <strong style="font-size:0.95rem; font-family:var(--font-mono); color:var(--text-highlight);">${v}</strong>
            </div>
          `).join('')}
        </div>
      `;
    }

    // Records table if available
    let tableHtml = '';
    if (data.records && data.records.length > 0) {
      const headers = Object.keys(data.records[0]);
      tableHtml = `
        <div class="table-responsive" style="margin-top:10px; border:1px solid var(--border-subtle); border-radius:var(--radius-sm);">
          <table class="custom-table" style="font-size:0.75rem;">
            <thead>
              <tr>${headers.map(h => `<th>${h.replace('_', ' ').toUpperCase()}</th>`).join('')}</tr>
            </thead>
            <tbody>
              ${data.records.map(r => `
                <tr>${headers.map(h => `<td>${r[h]}</td>`).join('')}</tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    const contentHtml = `
      <div>
        <p style="margin-bottom:6px; line-height:1.5;">${formatMarkdown(data.answer)}</p>
        ${metricsHtml}
        ${tableHtml}
        <div style="font-size:0.68rem; color:var(--text-muted); margin-top:8px; display:flex; align-items:center; gap:6px;">
          <span>🛰️ Verified Source: ${data.source}</span>
        </div>
      </div>
    `;

    appendBubble('assistant', contentHtml);

  } catch (err) {
    loadingDiv.remove();
    appendBubble('assistant', `<span style="color:var(--color-fire);">Network error querying assistant: ${err.message}</span>`);
  }
}

function appendBubble(sender, htmlContent) {
  const container = document.getElementById('chat-history');
  if (!container) return;

  const b = document.createElement('div');
  b.className = `chat-bubble bubble-${sender}`;
  b.innerHTML = htmlContent;
  container.appendChild(b);
  container.scrollTop = container.scrollHeight;
}

function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>');
}
