/* TaleVision — Dashboard JavaScript
 * Polling + mode switch + language + suspend schedule
 */

const POLL_INTERVAL_MS = 30000;  // 30 seconds
let pollTimer = null;
let currentMode = null;

// ── Topbar clock ──────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const el = document.getElementById('topbar-clock');
  if (el) el.textContent = `${hh}:${mm}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── Status polling ────────────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();
    applyStatus(data);
    refreshPreview();
  } catch (e) {
    console.warn('Status poll failed:', e);
  }
}

function applyStatus(data) {
  currentMode = data.mode || currentMode;

  // Topbar mode pill
  const pill = document.getElementById('topbar-mode');
  if (pill) {
    pill.textContent = currentMode || '—';
    pill.className = 'tv-mode-pill' + (currentMode === 'slowmovie' ? ' tv-mode-pill--slowmovie' : '');
  }

  // Mode cards active highlight
  document.querySelectorAll('.tv-mode-card').forEach(card => {
    card.classList.toggle('active', card.dataset.mode === currentMode);
  });

  // Status rows
  setText('status-suspended', data.is_suspended ? '⛔ Yes' : '✅ No');
  if (data.last_update) {
    const d = new Date(data.last_update * 1000);
    setText('status-last-update', d.toLocaleTimeString());
  }
  setText('status-next-wake', data.next_wake ? new Date(data.next_wake).toLocaleString() : '—');

  // Mode-specific state
  const state = data.state || {};
  const isLitclock = currentMode === 'litclock';
  const isSlowmovie = currentMode === 'slowmovie';

  const quoteRow = document.getElementById('status-quote-row');
  const videoRow = document.getElementById('status-video-row');
  if (quoteRow) quoteRow.style.display = isLitclock ? '' : 'none';
  if (videoRow) videoRow.style.display = isSlowmovie ? '' : 'none';

  if (isLitclock) {
    const q = state.quote || '—';
    setText('status-quote', q.length > 120 ? q.slice(0, 120) + '…' : q);
  }
  if (isSlowmovie) {
    const v = state.video || '—';
    const t = state.frame_time ? ` @ ${state.frame_time}` : '';
    setText('status-video', v + t);
  }

  // Language section visibility
  const langSection = document.getElementById('section-language');
  if (langSection) langSection.style.display = isLitclock ? '' : 'none';
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

// ── Frame preview ─────────────────────────────────────────────────────────────
function refreshPreview() {
  const img = document.getElementById('preview-img');
  const placeholder = document.getElementById('preview-placeholder');
  if (!img) return;
  const ts = Date.now();
  const newSrc = `/api/frame?t=${ts}`;
  const tmp = new Image();
  tmp.onload = () => {
    img.src = newSrc;
    img.style.display = 'block';
    if (placeholder) placeholder.style.display = 'none';
  };
  tmp.onerror = () => {
    img.style.display = 'none';
    if (placeholder) placeholder.style.display = '';
  };
  tmp.src = newSrc;
}

// ── Mode switch ───────────────────────────────────────────────────────────────
async function switchMode(mode) {
  try {
    const res = await fetch('/api/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    });
    if (res.ok) {
      currentMode = mode;
      applyStatus({ mode, is_suspended: false, state: {} });
    }
  } catch (e) {
    console.error('switchMode error:', e);
  }
}

// ── Force refresh ─────────────────────────────────────────────────────────────
async function forceRefresh() {
  const btn = document.getElementById('refresh-btn');
  if (btn) btn.classList.add('spinning');
  try {
    await fetch('/api/refresh', { method: 'POST' });
    // Poll status + preview after a short delay
    setTimeout(() => {
      pollStatus();
      if (btn) btn.classList.remove('spinning');
    }, 2000);
  } catch (e) {
    console.error('forceRefresh error:', e);
    if (btn) btn.classList.remove('spinning');
  }
}

// ── Language select ───────────────────────────────────────────────────────────
async function loadLanguages() {
  try {
    const res = await fetch('/api/languages');
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById('lang-select');
    if (!select) return;
    select.innerHTML = '';
    (data.languages || []).forEach(lang => {
      const opt = document.createElement('option');
      opt.value = lang;
      opt.textContent = lang.toUpperCase();
      select.appendChild(opt);
    });
  } catch (e) {
    console.warn('loadLanguages error:', e);
  }
}

async function setLanguage(lang) {
  if (!lang) return;
  try {
    await fetch('/api/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang }),
    });
  } catch (e) {
    console.error('setLanguage error:', e);
  }
}

// ── Suspend schedule ──────────────────────────────────────────────────────────
async function saveSuspend(event) {
  event.preventDefault();
  const enabled = document.getElementById('suspend-enabled').checked;
  const start = document.getElementById('suspend-start').value;
  const end = document.getElementById('suspend-end').value;
  const days = Array.from(document.querySelectorAll('input[name="suspend-day"]:checked'))
    .map(el => parseInt(el.value, 10));
  try {
    const res = await fetch('/api/suspend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, start, end, days }),
    });
    if (res.ok) {
      const msg = document.getElementById('suspend-saved');
      if (msg) {
        msg.style.display = 'inline';
        setTimeout(() => { msg.style.display = 'none'; }, 2500);
      }
    }
  } catch (e) {
    console.error('saveSuspend error:', e);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  pollStatus();
  loadLanguages();
  pollTimer = setInterval(pollStatus, POLL_INTERVAL_MS);
});
