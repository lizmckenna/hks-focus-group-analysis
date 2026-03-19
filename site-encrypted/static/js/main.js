// Dark mode toggle
function initThemeToggle() {
  const toggle = document.querySelector('.theme-toggle');
  if (!toggle) return;

  const saved = localStorage.getItem('theme');
  if (saved === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    toggle.textContent = 'light';
  }

  toggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    if (current === 'dark') {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
      toggle.textContent = 'dark';
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
      toggle.textContent = 'light';
    }
  });
}

// Scroll fade-in
function initFadeIn() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll('.fade-in').forEach((el) => observer.observe(el));
}

// Active nav link
function initActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('nav .nav-links a').forEach((a) => {
    if (a.getAttribute('href') === path ||
        (path.includes(a.getAttribute('href')) && a.getAttribute('href') !== '/')) {
      a.classList.add('active');
    }
  });
}

// Quote toggle buttons
function initQuoteToggles() {
  document.querySelectorAll('.quote-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (target) {
        target.classList.toggle('open');
        btn.textContent = target.classList.contains('open')
          ? 'Hide additional quotes'
          : btn.dataset.label || 'Show more quotes';
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initFadeIn();
  initActiveNav();
  initQuoteToggles();
});
