// Tiny helpers. No framework, nothing to build.
document.addEventListener('DOMContentLoaded', () => {
  // Highlight nav link for the current page
  const path = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('nav a[data-page]').forEach(a => {
    if (a.getAttribute('data-page') === path) a.classList.add('active');
  });

  // Copy buttons
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const target = document.querySelector(btn.getAttribute('data-copy'));
      if (!target) return;
      try {
        await navigator.clipboard.writeText(target.innerText);
        const orig = btn.innerText;
        btn.innerText = 'Copied';
        setTimeout(() => (btn.innerText = orig), 1200);
      } catch (e) {
        console.warn(e);
      }
    });
  });
});
