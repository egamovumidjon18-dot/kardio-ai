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
  window.CardioPathUI = Object.freeze({ setTheme, toast });
})();
