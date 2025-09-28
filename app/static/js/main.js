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
   MASCOT CONTROLLER (PNG version)
   - tilt-to-cursor (лёгкий наклон головы)
   - peek из краёв, patrol по низу
   - клики, подсказки
   - публичное API: mascot.hop/nod/shake/wink/say
========================================================= */
(function(){
  const root = document.getElementById('mskt');
  if(!root) return;

  const wrap   = root.querySelector('.mskt-imgwrap');
  const winkImg= root.querySelector('.mskt-wink-img'); // может отсутствовать
  const bubble = root.querySelector('.mskt-bubble');
  const textEl = root.querySelector('.mskt-text');

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- Helpers
  const clamp = (v,min,max)=>Math.max(min, Math.min(max,v));
  function pulse(cls, ms=500){ root.classList.add(cls); setTimeout(()=>root.classList.remove(cls), ms); }

  // ---- Public API
  window.mascot = {
    hop(){ pulse('hop', 520); },
    shake(){ pulse('shake', 420); },
    nod(){ pulse('nod', 460); },
    wink(){
      if(!winkImg){ pulse('nod', 320); return; } // fallback без слоя-века
      root.classList.add('wink');
      setTimeout(()=> root.classList.add('wink-off'), 280);
      setTimeout(()=> { root.classList.remove('wink','wink-off'); }, 360);
    },
    say(msg='подсказка', ms=2400){
      if(!bubble || !textEl) return;
      textEl.textContent = msg;
      bubble.style.opacity = '1';
      setTimeout(()=> bubble.style.opacity = '', ms);
    }
  };

  // ---- Tilt to cursor
  function onPointerMove(e){
    const r = wrap.getBoundingClientRect();
    const cx = r.left + r.width/2;
    const dx = clamp((e.clientX - cx)/120, -6, 6);
    root.style.setProperty('--mskt-tilt', dx.toFixed(2) + 'deg');
    root.classList.add('look');
  }
  window.addEventListener('pointermove', onPointerMove, { passive:true });

  // ---- Peek & Patrol
  const edges = ['peek-left','peek-right','peek-top','peek-bottom'];
  const CFG = { peekMin:6000, peekMax:15000, patrolMin:20000, patrolMax:40000 };
  let peekTimer=null, patrolTimer=null, allowPeek=true;

  function schedulePeek(){
    if(reduceMotion) return;
    clearTimeout(peekTimer);
    peekTimer = setTimeout(doPeek, CFG.peekMin + Math.random()*(CFG.peekMax-CFG.peekMin));
  }
  function doPeek(){
    if(document.hidden || !allowPeek){ schedulePeek(); return; }
    const edge = edges[(Math.random()*edges.length)|0];
    root.classList.add(edge,'peek-enter');
    setTimeout(()=> root.classList.remove('peek-enter'), 500);
    setTimeout(()=>{
      root.classList.add('peek-exit');
      setTimeout(()=>{ root.classList.remove('peek-exit', edge); schedulePeek(); }, 380);
    }, 2500);
  }
  schedulePeek();

  function schedulePatrol(){
    if(reduceMotion) return;
    clearTimeout(patrolTimer);
    patrolTimer = setTimeout(patrol, CFG.patrolMin + Math.random()*(CFG.patrolMax-CFG.patrolMin));
  }
  function patrol(){
    if(document.hidden) { schedulePatrol(); return; }
    if(edges.some(c=>root.classList.contains(c))) { schedulePatrol(); return; }
    root.classList.add('patrol'); allowPeek=false;
    setTimeout(()=>{
      root.classList.remove('patrol');
      root.style.left=''; root.style.top=''; root.style.right='18px'; root.style.bottom='88px';
      allowPeek=true; schedulePatrol();
    }, 14500);
  }
  schedulePatrol();

  // ---- Interactions & events
  root.addEventListener('click', ()=> window.mascot.hop());
  document.addEventListener('mascot:celebrate', ()=> window.mascot.hop());
  document.addEventListener('mascot:hint', (e)=> window.mascot.say(e.detail?.text || 'подсказка'));

  // ---- Visibility
  document.addEventListener('visibilitychange', ()=>{
    if(document.hidden){ clearTimeout(peekTimer); clearTimeout(patrolTimer); }
    else { schedulePeek(); schedulePatrol(); }
  });

  // Greeting on hero
  if(document.querySelector('.course-hero')){
    setTimeout(()=> window.mascot.say('начни с поиска курса 👇'), 1200);
  }
})();

(function(){
  const root = document.getElementById('assist-root');
  if(!root) return;

  const fab = root.querySelector('[data-fab]');
  const panel = document.getElementById('assist-panel');
  const btnClose = root.querySelector('[data-panel-close]');
  const teaser = root.querySelector('[data-teaser]');
  const teaserClose = root.querySelector('[data-teaser-close]');
  const nowEl = root.querySelector('[data-now]');
  const autoshow = parseInt(root.dataset.teaserAutoshowMs || "0", 10);
  const aiEnabled = (root.dataset.aiEnabled === "true");
  const askForm = root.querySelector('[data-ask-form]');
  const chatBox = root.querySelector('[data-chat]');

  // time label
  try {
    const t = new Date();
    nowEl && (nowEl.textContent = t.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}));
  } catch(e){}

  // teaser autoshow once
  if (teaser && !localStorage.getItem('assistTeaserSeen')) {
    if (autoshow > 0) setTimeout(()=> teaser.hidden = false, autoshow);
  }

  teaserClose && teaserClose.addEventListener('click', () => {
    teaser.hidden = true;
    localStorage.setItem('assistTeaserSeen','1');
  });

  function openPanel(){
    panel.setAttribute('aria-hidden','false');
    fab.setAttribute('aria-expanded','true');
    teaser && (teaser.hidden = true);
  }
  function closePanel(){
    panel.setAttribute('aria-hidden','true');
    fab.setAttribute('aria-expanded','false');
  }

  fab && fab.addEventListener('click', () => {
    const isOpen = panel.getAttribute('aria-hidden') === 'false';
    isOpen ? closePanel() : openPanel();
  });
  btnClose && btnClose.addEventListener('click', closePanel);
  document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') closePanel(); });

  // AI form (disabled by default)
  if (!aiEnabled && askForm) {
    askForm.hidden = true;
  } else if (askForm) {
    askForm.hidden = false;
    if (chatBox) chatBox.hidden = false;

    askForm.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const input = askForm.querySelector('input[name="q"]');
      const text = (input.value || '').trim();
      if (!text) return;

      appendMsg(text, 'user');
      input.value = '';
      appendMsg('Печатаю…', 'bot', true);

      try{
        const res = await fetch('/api/assistant/ask/', {
          method:'POST',
          headers:{
            'Content-Type':'application/json',
            'X-CSRFToken': getCSRF()
          },
          body: JSON.stringify({ question: text, page: location.pathname })
        });
        const data = await res.json();
        replaceLastTyping(data.answer || 'Готово.');
      }catch(err){
        replaceLastTyping('Скоро подключим ИИ. Пока напишите нам в мессенджер 👇');
      }
    });
  }

  function appendMsg(text, who='bot', typing=false){
    chatBox.hidden = false;
    const div = document.createElement('div');
    div.className = 'assist-msg ' + (who === 'user' ? 'assist-msg--user' : 'assist-msg--bot');
    div.textContent = text;
    if(typing) div.dataset.typing = "1";
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }
  function replaceLastTyping(text){
    const last = chatBox.querySelector('[data-typing="1"]');
    if (last){ last.remove(); }
    appendMsg(text, 'bot', false);
  }
  function getCSRF(){
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
})();
