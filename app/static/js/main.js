/* static/js/main.js */

/* ============ THEME TOGGLE ============ */
(function () {
  const root = document.documentElement;
  const btn = document.getElementById("themeToggle");

  // initial theme: localStorage -> system -> 'light'
  const saved = localStorage.getItem("theme");
  const systemDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initial = saved ? saved : (systemDark ? "dark" : "light");

  root.setAttribute("data-theme", initial);
  if (btn) {
    btn.textContent = initial === "dark" ? "🌞" : "🌙";
    btn.setAttribute("aria-label", initial === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }

  // react to system changes if user hasn't chosen explicitly
  if (!saved && window.matchMedia) {
    try {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
        const theme = e.matches ? "dark" : "light";
        root.setAttribute("data-theme", theme);
        if (btn) {
          btn.textContent = theme === "dark" ? "🌞" : "🌙";
          btn.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
        }
      });
    } catch (_) {
      // older browsers: ignore
    }
  }

  if (btn) {
    btn.addEventListener("click", function () {
      const current = root.getAttribute("data-theme") || "light";
      const next = current === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      btn.textContent = next === "dark" ? "🌞" : "🌙";
      btn.setAttribute("aria-label", next === "dark" ? "Switch to light theme" : "Switch to dark theme");
    });
  }
})();

/* ============ MOBILE NAV (BURGER) ============ */
(function () {
  const toggle = document.getElementById("navToggle");
  const menu = document.getElementById("navMenu");
  if (!toggle || !menu) return;

  toggle.addEventListener("click", function () {
    menu.classList.toggle("open");
    toggle.setAttribute("aria-expanded", menu.classList.contains("open") ? "true" : "false");
  });

  // close on link click
  var links = menu.querySelectorAll(".nav-link");
  links.forEach(function (a) {
    a.addEventListener("click", function () {
      menu.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });
})();

/* ============ AUTO-HIDE ALERTS ============ */
(function () {
  var alerts = document.querySelectorAll(".alert");
  if (!alerts.length) return;

  alerts.forEach(function (el) {
    // keep if marked no-autohide
    if (el.dataset.autohide === "false") return;

    setTimeout(function () {
      el.style.transition = "opacity 0.5s ease";
      el.style.opacity = "0";
      setTimeout(function () {
        if (el && el.parentNode) el.parentNode.removeChild(el);
      }, 500);
    }, 4000);
  });
})();

/* ============ PAGE LOADER ON NAVIGATION ============ */
(function () {
  window.addEventListener("beforeunload", function () {
    document.body.classList.add("loading");
  });
})();

/* ============ CSRF HELPERS (Django) ============ */
(function () {
  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split("; ") : [];
    for (let i = 0; i < cookies.length; i++) {
      const parts = cookies[i].split("=");
      const key = decodeURIComponent(parts[0]);
      if (key === name) {
        return decodeURIComponent(parts.slice(1).join("="));
      }
    }
    return null;
  }

  // attach to window for easy reuse
  window.csrfToken = function () {
    return getCookie("csrftoken");
  };

  // tiny helper for POSTing JSON with CSRF
  window.postJSON = async function (url, data) {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      body: JSON.stringify(data || {}),
    });
    return resp;
  };
})();

/* =========================================================
   MASCOT CONTROLLER (Snow Leopard helper)
   - eye tracking (cursor-look)
   - peek from edges occasionally
   - low-frequency patrol walk
   - wave on click, hint/celebrate events
   Requires SVG structure from mascot_snowleopard.html (ids/classes used below)
========================================================= */
(function () {
  const root = document.getElementById('mskt');
  if (!root) return;

  // Respect reduced motion
  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Elements inside SVG
  const irises  = root.querySelectorAll('.eye-i');    // pupils
  const eyelids = root.querySelectorAll('.eyelid');   // blink rects

  // State / timers
  let peekTimer = null;
  let patrolTimer = null;
  let visibleForPeek = true;

  // Config (tune if нужно)
  const CFG = {
    peekMin: 6000,          // 6s
    peekMax: 15000,         // 15s
    patrolMin: 20000,       // 20s
    patrolMax: 40000,       // 40s
    waveDuration: 800
  };

  /* ---------- Eye tracking (cursor-look) ---------- */
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  let lastTilt = 0;

  function onPointerMove(e) {
    const rect = root.getBoundingClientRect();
    const headX = rect.left + rect.width / 2;
    const headY = rect.top + rect.height / 2;
    const dx = clamp((e.clientX - headX) / 28, -3, 3);
    const dy = clamp((e.clientY - headY) / 28, -3, 3);
    irises.forEach(el => el.setAttribute('transform', `translate(${dx} ${dy})`));

    lastTilt = clamp((e.clientX - headX) / 120, -6, 6);
    root.style.setProperty('--mskt-tilt', lastTilt.toFixed(2) + 'deg');
    root.classList.add('look');
  }
  window.addEventListener('pointermove', onPointerMove, { passive: true });

  /* ---------- Peek behavior (from screen edges) ---------- */
  const edges = ['peek-left', 'peek-right', 'peek-top', 'peek-bottom'];

  function schedulePeek() {
    if (reduceMotion) return;
    const delay = CFG.peekMin + Math.random() * (CFG.peekMax - CFG.peekMin);
    clearTimeout(peekTimer);
    peekTimer = setTimeout(doPeek, delay);
  }
  function doPeek() {
    if (document.hidden || !visibleForPeek) { schedulePeek(); return; }
    const edgeClass = edges[Math.floor(Math.random() * edges.length)];
    root.classList.add(edgeClass, 'peek-enter');
    setTimeout(() => root.classList.remove('peek-enter'), 500);

    // look roughly to center
    irises.forEach(el => el.setAttribute('transform', 'translate(1 0)'));

    // hide back
    setTimeout(() => {
      root.classList.add('peek-exit');
      setTimeout(() => {
        root.classList.remove('peek-exit', edgeClass);
        schedulePeek();
      }, 380);
    }, 2500);
  }
  schedulePeek();

  /* ---------- Patrol walk (across bottom) ---------- */
  function schedulePatrol() {
    if (reduceMotion) return;
    const delay = CFG.patrolMin + Math.random() * (CFG.patrolMax - CFG.patrolMin);
    clearTimeout(patrolTimer);
    patrolTimer = setTimeout(patrol, delay);
  }
  function patrol() {
    if (document.hidden) { schedulePatrol(); return; }
    // don't patrol while peeking
    if (edges.some(c => root.classList.contains(c))) { schedulePatrol(); return; }

    root.classList.add('patrol');
    visibleForPeek = false;

    // after animation ends (~14.5s in CSS), reset back to corner
    setTimeout(() => {
      root.classList.remove('patrol');
      root.style.left = '';
      root.style.top = '';
      root.style.right = '18px';
      root.style.bottom = '18px';
      visibleForPeek = true;
      schedulePatrol();
    }, 14500);
  }
  schedulePatrol();

  /* ---------- Interactions ---------- */
  root.addEventListener('click', () => {
    root.classList.add('wave');
    setTimeout(() => root.classList.remove('wave'), CFG.waveDuration);
  });

  document.addEventListener('mascot:celebrate', () => {
    root.classList.add('wave');
    setTimeout(() => root.classList.remove('wave'), CFG.waveDuration);
  });

  document.addEventListener('mascot:hint', (e) => {
    const msg = e.detail?.text || 'подсказка';
    const bubble = root.querySelector('.mskt-bubble');
    const text = root.querySelector('.mskt-text');
    if (!bubble || !text) return;
    text.textContent = msg;
    bubble.style.opacity = '1';
    setTimeout(() => bubble.style.opacity = '', 2600);
  });

  // pause/resume when tab visibility changes
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearTimeout(peekTimer);
      clearTimeout(patrolTimer);
    } else {
      schedulePeek();
      schedulePatrol();
    }
  });

  // Optional: greeting on hero
  if (document.querySelector('.course-hero')) {
    setTimeout(() => {
      const evt = new CustomEvent('mascot:hint', { detail: { text: 'начни с поиска курса 👇' } });
      document.dispatchEvent(evt);
    }, 1200);
  }
})();
