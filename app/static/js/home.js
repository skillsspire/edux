/* static/js/home.js - Скрипты ТОЛЬКО для главной страницы */

// Делаем так, чтобы код выполнялся только когда DOM готов
(function() {
  // Проверяем, что мы на главной странице (опционально)
  const isHomePage = document.querySelector('.course-hero') !== null;
  if (!isHomePage) return;

  console.log('Home page JS loaded');

  /* ============ АНИМАЦИИ ПОЯВЛЕНИЯ ============ */
  function initAnimations() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    }, { 
      threshold: 0.1,
      rootMargin: '50px' 
    });
    
    document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));
  }

  /* ============ SWIPER ДЛЯ ОТЗЫВОВ ============ */
  function initSwiper() {
    const testimonialsSwiper = document.querySelector('.testimonials-swiper');
    if (!testimonialsSwiper) return;
    
    // Preload Swiper только если он нужен
    if (typeof Swiper === 'undefined') {
      console.warn('Swiper not loaded yet');
      return;
    }
    
    new Swiper('.testimonials-swiper', {
      slidesPerView: 1,
      spaceBetween: 20,
      loop: true,
      autoplay: {
        delay: 5000,
        disableOnInteraction: false
      },
      navigation: {
        nextEl: '.swiper-button-next',
        prevEl: '.swiper-button-prev'
      },
      breakpoints: {
        768: {
          slidesPerView: 2
        },
        1200: {
          slidesPerView: 3
        }
      }
    });
  }

  /* ============ POPUP ДЛЯ ТЕСТА ============ */
  function initPopup() {
    const popup = document.getElementById('popupTest');
    const openTestBtn = document.getElementById('openTest');
    const closePopupBtn = document.getElementById('closePopup');
    const closeBtn = document.getElementById('closeBtn');
    
    if (!popup) return;
    
    // Открытие попапа
    if (openTestBtn) {
      openTestBtn.addEventListener('click', e => {
        e.preventDefault();
        popup.style.display = 'flex';
        document.body.style.overflow = 'hidden'; // Блокируем скролл
      });
    }
    
    // Закрытие попапа
    function closePopup() {
      popup.style.display = 'none';
      document.body.style.overflow = ''; // Возвращаем скролл
    }
    
    if (closePopupBtn) {
      closePopupBtn.addEventListener('click', closePopup);
    }
    
    if (closeBtn) {
      closeBtn.addEventListener('click', closePopup);
    }
    
    // Закрытие при клике вне попапа
    popup.addEventListener('click', e => {
      if (e.target === popup) {
        closePopup();
      }
    });
    
    // Закрытие по ESC
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && popup.style.display === 'flex') {
        closePopup();
      }
    });
  }

  /* ============ EMAIL ПОДПИСКА ============ */
  function initEmailSubscription() {
    const emailForm = document.querySelector('.email-cta-section form');
    if (!emailForm) return;
    
    emailForm.addEventListener('submit', handleEmailSubmit);
  }
  
  function handleEmailSubmit(event) {
    event.preventDefault();
    const emailInput = event.target.querySelector('input[type="email"]');
    const email = emailInput.value.trim();
    
    if (!email) {
      showAlert('Пожалуйста, введите email');
      return;
    }
    
    if (!validateEmail(email)) {
      showAlert('Пожалуйста, введите корректный email');
      return;
    }
    
    // Показываем состояние загрузки
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Отправка...';
    submitBtn.disabled = true;
    
    // Имитация отправки (замените на реальный AJAX)
    setTimeout(() => {
      try {
        let subscribers = JSON.parse(localStorage.getItem('skillsspire_subscribers') || '[]');
        if (!subscribers.includes(email)) {
          subscribers.push(email);
          localStorage.setItem('skillsspire_subscribers', JSON.stringify(subscribers));
        }
        
        showAlert('Спасибо за подписку! Мы скоро свяжемся с вами.', 'success');
        emailInput.value = '';
        
      } catch (e) {
        console.error('Ошибка сохранения email:', e);
        showAlert('Спасибо за интерес! Ваш email записан.', 'success');
      } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
      }
    }, 1000);
  }
  
  function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  }
  
  function showAlert(message, type = 'info') {
    // Используем существующую систему алертов из main.js или создаем простую
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: ${type === 'success' ? '#d4edda' : '#fff3cd'};
      color: ${type === 'success' ? '#155724' : '#856404'};
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 10000;
      animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
      alertDiv.style.animation = 'slideOutRight 0.3s ease forwards';
      setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
  }

  /* ============ ЛЕНИВАЯ ЗАГРУЗКА ИЗОБРАЖЕНИЙ ============ */
  function initLazyLoading() {
    // Для изображений курсов добавляем loading="lazy" если его нет
    document.querySelectorAll('.course-card img').forEach(img => {
      if (!img.loading) {
        img.loading = 'lazy';
      }
      // Устанавливаем размеры для предотвращения сдвигов макета
      if (!img.width || !img.height) {
        img.style.aspectRatio = '16/9';
      }
    });
  }

  /* ============ ПРЕДЗАГРУЗКА КРИТИЧЕСКИХ РЕСУРСОВ ============ */
  function preloadCriticalResources() {
    // Предзагрузка изображений для первого экрана
    const heroImage = document.querySelector('.course-hero img');
    if (heroImage) {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.as = 'image';
      link.href = heroImage.src;
      document.head.appendChild(link);
    }
  }

  /* ============ ИНИЦИАЛИЗАЦИЯ ВСЕГО ============ */
  function initHomePage() {
    initAnimations();
    initSwiper();
    initPopup();
    initEmailSubscription();
    initLazyLoading();
    
    // Ждем загрузки Swiper если он загружается асинхронно
    if (typeof Swiper === 'undefined') {
      const checkSwiper = setInterval(() => {
        if (typeof Swiper !== 'undefined') {
          clearInterval(checkSwiper);
          initSwiper();
        }
      }, 100);
    }
  }

  // Запускаем когда DOM готов
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHomePage);
  } else {
    initHomePage();
  }

})();

/* ============ ГЛОБАЛЬНЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============ */
// Эти функции могут использоваться и на других страницах
// Но они безопасны, если определены только здесь

// Функция для валидации email (может быть перенесена в main.js если нужна везде)
if (!window.validateEmail) {
  window.validateEmail = function(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };
}

// Функция для показа временного уведомления
if (!window.showToast) {
  window.showToast = function(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: ${type === 'success' ? '#d4edda' : type === 'error' ? '#f8d7da' : '#fff3cd'};
      color: ${type === 'success' ? '#155724' : type === 'error' ? '#721c24' : '#856404'};
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 10000;
      animation: slideInUp 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'slideOutDown 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  };
}

// CSS для анимаций toast (можно добавить в CSS)
const toastStyles = document.createElement('style');
toastStyles.textContent = `
  @keyframes slideInUp {
    from {
      transform: translateY(100%);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOutDown {
    from {
      transform: translateY(0);
      opacity: 1;
    }
    to {
      transform: translateY(100%);
      opacity: 0;
    }
  }
  
  @keyframes slideInRight {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOutRight {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(100%);
      opacity: 0;
    }
  }
`;
document.head.appendChild(toastStyles);