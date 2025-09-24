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
