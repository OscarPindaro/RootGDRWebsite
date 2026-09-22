/* Behaviour for common.Dialog and the components built on it.
 *
 * A native <dialog> shown with showModal() already traps focus and closes on
 * Escape, so this script only adds what the element does not do itself:
 * remembering the control that opened the dialog and returning focus to it,
 * wiring the close controls, and exposing pending/error state for requests.
 */
(function () {
  if (window.rootGdrDialog) return;

  var openerByDialog = new WeakMap();
  var lastTrigger = null;

  var FOCUSABLE = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(',');

  function focusables(dialog) {
    return Array.prototype.filter.call(
      dialog.querySelectorAll(FOCUSABLE),
      function (element) { return element.offsetParent !== null; }
    );
  }

  function clearError(dialog) {
    var output = dialog.querySelector('[data-dialog-error]');
    if (!output) return;
    output.textContent = '';
    output.hidden = true;
  }

  function showError(dialog, message) {
    var output = dialog.querySelector('[data-dialog-error]');
    if (!output) return;
    output.textContent = message;
    output.hidden = false;
  }

  function setPending(dialog, pending) {
    dialog.dataset.pending = pending ? 'true' : 'false';
    dialog.setAttribute('aria-busy', pending ? 'true' : 'false');
    dialog.querySelectorAll('[data-dialog-confirm], [data-dialog-close]').forEach(
      function (element) { element.disabled = pending; }
    );
  }

  function open(dialog, opener) {
    if (!dialog) return;
    if (opener) openerByDialog.set(dialog, opener);
    if (!dialog.dataset.dialogBound) {
      dialog.dataset.dialogBound = 'true';
      dialog.addEventListener('close', function () { restoreFocus(dialog); });
    }
    clearError(dialog);
    setPending(dialog, false);
    if (!dialog.open) dialog.showModal();
    var target = dialog.querySelector('[data-dialog-autofocus]') || focusables(dialog)[0];
    if (target) target.focus();
  }

  function restoreFocus(dialog) {
    var opener = openerByDialog.get(dialog);
    openerByDialog.delete(dialog);
    if (opener && document.contains(opener)) opener.focus();
  }

  function close(dialog) {
    if (dialog && dialog.open) dialog.close();
  }

  window.rootGdrDialog = {open: open, close: close, setPending: setPending, showError: showError};

  document.addEventListener('click', function (event) {
    if (!(event.target instanceof Element)) return;

    var trigger = event.target.closest('[data-dialog-open]');
    if (trigger) {
      var dialog = document.getElementById(trigger.getAttribute('data-dialog-open'));
      if (dialog) {
        event.preventDefault();
        open(dialog, trigger);
        return;
      }
    }

    var closer = event.target.closest('[data-dialog-close]');
    if (closer) {
      event.preventDefault();
      close(closer.closest('dialog[data-dialog]'));
    }
  });

  // htmx-loaded dialogs (invite, confirm) open once they land in the page.
  document.addEventListener('htmx:beforeRequest', function (event) {
    lastTrigger = event.detail && event.detail.elt;
    var dialog = lastTrigger && lastTrigger.closest('dialog[data-dialog]');
    if (dialog) setPending(dialog, true);
  });

  document.addEventListener('htmx:afterSwap', function (event) {
    var scope = event.target;
    if (!scope || !scope.querySelectorAll) return;
    scope.querySelectorAll('dialog[data-dialog]').forEach(function (dialog) {
      open(dialog, lastTrigger);
    });
    lastTrigger = null;
  });

  document.addEventListener('htmx:afterRequest', function (event) {
    var elt = event.detail && event.detail.elt;
    var dialog = elt && elt.closest('dialog[data-dialog]');
    if (!dialog) return;
    setPending(dialog, false);
    if (event.detail.successful) close(dialog);
  });

  ['htmx:responseError', 'htmx:sendError', 'htmx:timeout'].forEach(function (name) {
    document.addEventListener(name, function (event) {
      var elt = event.detail && event.detail.elt;
      var dialog = elt && elt.closest('dialog[data-dialog]');
      if (dialog) {
        setPending(dialog, false);
        showError(dialog, 'Non è stato possibile completare l’operazione. Riprova.');
      }
    });
  });
})();
