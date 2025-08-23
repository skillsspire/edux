// ===== THEME TOGGLE =====
const themeToggle = document.getElementById("themeToggle");
const rootHtml = document.documentElement;

if (localStorage.getItem("theme")) {
    rootHtml.setAttribute("data-theme", localStorage.getItem("theme"));
    if (themeToggle) {
        themeToggle.textContent =
            localStorage.getItem("theme") === "dark" ? "🌞" : "🌙";
    }
}

themeToggle?.addEventListener("click", () => {
    let currentTheme = rootHtml.getAttribute("data-theme");
    let newTheme = currentTheme === "light" ? "dark" : "light";
    rootHtml.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
    themeToggle.textContent = newTheme === "dark" ? "🌞" : "🌙";
});

// ===== MOBILE MENU (BURGER) =====
const navToggle = document.getElementById("navToggle");
const navMenu = document.getElementById("navMenu");

navToggle?.addEventListener("click", () => {
    navMenu.classList.toggle("open");
});

// Закрывать меню при клике на ссылку
document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        navMenu.classList.remove("open");
    });
});

// ===== AUTO-HIDE ALERTS =====
document.querySelectorAll(".alert").forEach((alert) => {
    setTimeout(() => {
        alert.style.opacity = "0";
        alert.style.transition = "opacity 0.5s ease";
        setTimeout(() => alert.remove(), 500);
    }, 4000);
});

// ===== PAGE LOADER =====
window.addEventListener("beforeunload", () => {
    document.body.classList.add("loading");
});
