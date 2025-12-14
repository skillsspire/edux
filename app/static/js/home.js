// home.js - ДОЛЖЕН СОДЕРЖАТЬ ВСЕ ЭТИ СКРИПТЫ

// 1. Fade-up анимации
(function () {
  if (!('IntersectionObserver' in window)) return;

  const elements = document.querySelectorAll('.fade-up');
  if (!elements.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  elements.forEach((el, i) => {
    if (i < 20) observer.observe(el);
  });
})();

// 2. Swiper
(function () {
  const el = document.querySelector('.testimonials-swiper');
  if (!el || typeof Swiper === 'undefined') return;

  new Swiper(el, {
    slidesPerView: 1,
    spaceBetween: 20,
    loop: true,
    autoplay: { delay: 5000 },
    navigation: {
      nextEl: '.swiper-button-next',
      prevEl: '.swiper-button-prev'
    },
    breakpoints: {
      768: { slidesPerView: 2 },
      1200: { slidesPerView: 3 }
    }
  });
})();

// 3. Popup и формы
document.addEventListener('DOMContentLoaded', function() {
  // Popup для теста
  const openTestBtn = document.getElementById('openTest');
  const popupTest = document.getElementById('popupTest');
  const closePopupBtn = document.getElementById('closePopup');
  const closeBtn = document.getElementById('closeBtn');
  
  if (openTestBtn && popupTest) {
    openTestBtn.addEventListener('click', function(e) {
      e.preventDefault();
      popupTest.style.display = 'flex';
    });
    
    function closePopup() {
      popupTest.style.display = 'none';
    }
    
    if (closePopupBtn) closePopupBtn.addEventListener('click', closePopup);
    if (closeBtn) closeBtn.addEventListener('click', closePopup);
    
    popupTest.addEventListener('click', function(e) {
      if (e.target === popupTest) {
        closePopup();
      }
    });
  }
  
  // Форма подписки
  const emailForm = document.getElementById('email-subscribe-form');
  if (emailForm) {
    emailForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const emailInput = this.querySelector('input[type="email"]');
      if (emailInput && emailInput.value) {
        alert('Спасибо за подписку! На ' + emailInput.value + ' скоро придут полезные материалы.');
        emailInput.value = '';
      }
    });
  }
});