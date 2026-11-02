/* CardioPath AI · progressive UI helpers · vanilla JS, no external dependencies.
   Clinical risk is rendered by the backend immediately; this file never scores risk. */
(() => {
  'use strict';
  const root = document.documentElement;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  // Same key the existing pages use, so one choice applies everywhere (CardioPath adaptation).
  const THEME_KEY = 'theme';

  // Theme is a nonclinical preference. Local storage is optional, not required.
  let savedTheme = null;
  try { savedTheme = localStorage.getItem(THEME_KEY); } catch (_) { /* file:// / privacy */ }

  function currentTheme() {
    if (root.dataset.theme === 'light' || root.dataset.theme === 'dark') return root.dataset.theme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function syncToggles() {
    const dark = currentTheme() === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-pressed', String(dark));
      button.setAttribute('aria-label', dark
        ? (button.dataset.labelDark || 'Switch to light theme')
        : (button.dataset.labelLight || 'Switch to dark theme'));
    });
  }

  function setTheme(theme) {
    root.dataset.theme = theme === 'dark' ? 'dark' : 'light';
    syncToggles();
    try { localStorage.setItem(THEME_KEY, root.dataset.theme); } catch (_) { /* no-op */ }
  }
  // Without a saved choice the page follows the system theme (CSS handles it); nothing is written.
  if (savedTheme === 'light' || savedTheme === 'dark') root.dataset.theme = savedTheme;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', syncToggles);
  else syncToggles();
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-theme-toggle]');
    if (button) setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  });

  // Cosmetic reveal is opt-in, never hides content before JS executes.
  // Do not opt clinical results, severity cards, alerts or hand-off blockers in.
  function observeReveal() {
    const revealItems = [...document.querySelectorAll('[data-reveal]')].filter(el =>
      !el.matches('[data-clinical-urgent]') &&
      !el.closest('.cp-result--high, .cp-result--very-high, .cp-alert--urgent, [data-clinical-urgent]'));
    if (reduceMotion.matches || !('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver(entries => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting && !reduceMotion.matches) target.classList.add('is-visible');
        if (isIntersecting) observer.unobserve(target);
      });
    }, { threshold: 0.06, rootMargin: '0px 0px -16px 0px' });
    revealItems.forEach(el => observer.observe(el));
    reduceMotion.addEventListener?.('change', event => {
      if (event.matches) observer.disconnect();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', observeReveal);
  else observeReveal();

  // Accessible, nonclinical notifications. Never use a toast for an urgent finding.
  function toast(message, options = {}) {
    const region = document.getElementById('cp-toast-region');
    if (!region || typeof message !== 'string' || !message.trim()) return;
    const kind = options.kind === 'error' ? 'error' : 'success';
    const item = document.createElement('div');
    item.className = `cp-toast cp-toast--${kind}`;
    item.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    const body = document.createElement('span');
    body.className = 'cp-toast__body';
    body.textContent = message;
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'cp-toast__close';
    close.textContent = '×';
    close.setAttribute('aria-label', options.dismissLabel || 'Dismiss notification');
    close.addEventListener('click', () => item.remove());
    item.append(body, close);
    region.append(item);
    // Errors persist until manually dismissed; success notices pause on interaction.
    if (kind === 'success') {
      let timeoutId;
      const stop = () => clearTimeout(timeoutId);
      const start = () => {
        stop();
        timeoutId = setTimeout(() => {
          if (!item.contains(document.activeElement) && !item.matches(':hover')) item.remove();
        }, 7000);
      };
      item.addEventListener('pointerenter', stop);
      item.addEventListener('pointerleave', start);
      item.addEventListener('focusin', stop);
      item.addEventListener('focusout', start);
      start();
    }
    return item;
  }
  
  // PWA Service Worker ro'yxatdan o'tkazish (Offline Resiliency)
  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/sw.js').catch(err => {
        console.debug('Service Worker register skipped/failed:', err);
      });
    });
  }

  // Oflayn holat monitoringi va xabarnomasi
  function updateNetworkStatus() {
    let bar = document.getElementById('cp-offline-banner');
    if (!navigator.onLine) {
      if (!bar) {
        bar = document.createElement('div');
        bar.id = 'cp-offline-banner';
        bar.style.cssText = 'background:#ea580c; color:#fff; text-align:center; padding:8px 16px; font-weight:600; font-size:13px; position:sticky; top:0; z-index:99999; box-shadow:0 2px 4px rgba(0,0,0,0.2);';
        bar.innerHTML = '⚠️ <strong>Oflayn rejim:</strong> Internet tarmog\'i uzildi. Platforma mahalliy kesh asosida ishlamoqda.';
        document.body.prepend(bar);
      }
    } else if (bar) {
      bar.remove();
      toast('Internet aloqasi tiklandi.', { kind: 'success' });
    }
  }
  window.addEventListener('online', updateNetworkStatus);
  window.addEventListener('offline', updateNetworkStatus);
  if (!navigator.onLine) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', updateNetworkStatus);
    else updateNetworkStatus();
  }

  
  // Ordinatoriya xavfsizlik qulfi (15 daqiqa harakatsizlik)
  const IDLE_TIMEOUT_MS = 15 * 60 * 1000;
  let idleTimer = null;

  function showIdleLock() {
    let overlay = document.getElementById('cp-idle-lock');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'cp-idle-lock';
      overlay.style.cssText = 'position:fixed; inset:0; z-index:999999; background:rgba(15,23,42,0.85); backdrop-filter:blur(8px); display:flex; align-items:center; justify-content:center; color:#fff; font-family:sans-serif; text-align:center; padding:20px;';
      overlay.innerHTML = `
        <div style="background:#1e293b; border:1px solid #334155; border-radius:12px; padding:28px 36px; max-width:440px; box-shadow:0 20px 25px -5px rgba(0,0,0,0.5);">
          <div style="font-size:40px; margin-bottom:12px;">🔒</div>
          <h3 style="margin:0 0 8px; font-size:18px; font-weight:700;">Ordinatoriya Xavfsizlik Qulfi</h3>
          <p style="margin:0 0 20px; font-size:13px; color:#94a3b8; line-height:1.5;">Bemor ma\'lumotlari xavfsizligi uchun tizim 15 daqiqa harakatsizlikdan so\'ng vaqtincha qulflandi.</p>
          <button id="cp-unlock-btn" style="background:#2563eb; color:#fff; border:none; padding:10px 20px; border-radius:6px; font-weight:600; cursor:pointer; font-size:14px; width:100%;">Seansni davom ettirish</button>
        </div>
      `;
      document.body.appendChild(overlay);
      const btn = document.getElementById('cp-unlock-btn');
      if (btn) btn.addEventListener('click', () => {
        overlay.remove();
        resetIdleTimer();
      });
    }
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(showIdleLock, IDLE_TIMEOUT_MS);
  }

  ['mousemove', 'keydown', 'pointerdown', 'touchstart', 'scroll'].forEach(evt => {
    window.addEventListener(evt, resetIdleTimer, { passive: true });
  });
  resetIdleTimer();

  window.CardioPathUI = Object.freeze({ setTheme, toast });
})();
