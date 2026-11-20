// Compatibility cleanup only. Streamlit owns connection recovery; do not cover
// its page, force a reload, or ask the user to reopen a working chart.
(() => {
  function removeLegacyOverlay() {
    const panel = document.getElementById('soxl-preview-recovery');
    if (panel) panel.remove();
  }
  function start() {
    removeLegacyOverlay();
    // An older script in an already-open document may still create its card.
    new MutationObserver(removeLegacyOverlay).observe(document.documentElement, {
      childList: true, subtree: true
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }
})();
