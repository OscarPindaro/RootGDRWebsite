(function () {
  if (window.__circeusTabs) return;
  window.__circeusTabs = true;

  // Panels are the caller's content, marked with data-tabs-panel="<value>".
  function sync(root) {
    var checked = root.querySelector('.tabs__input:checked');
    var value = checked ? checked.value : null;
    root.querySelectorAll('[data-tabs-panel]').forEach(function (panel) {
      panel.hidden = panel.dataset.tabsPanel !== value;
    });
  }

  document.addEventListener('change', function (event) {
    if (!event.target.matches('.tabs__input')) return;
    var root = event.target.closest('[data-tabs]');
    if (root) sync(root);
  });

  document.querySelectorAll('[data-tabs]').forEach(sync);
  document.body.addEventListener('htmx:afterSwap', function (event) {
    event.target.querySelectorAll('[data-tabs]').forEach(sync);
  });
})();
