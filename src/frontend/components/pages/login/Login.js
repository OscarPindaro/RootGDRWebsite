/* Place focus where the reader is already looking after the page is replaced.
 *
 * The auth forms post with `hx-target="body" hx-swap="outerHTML"`, so a refused
 * submission swaps the whole document and the browser drops focus to <body>.
 * The server redirects back to /login with an `error` summary in the form, so
 * after every swap we move focus to the summary (or to the first field the
 * server marked invalid), letting a screen reader announce the failure. The
 * summary is a tabindex="-1" wrapper, so it is focusable without joining the
 * tab order. `common.Dialog.js` owns its own afterSwap hook for dialogs; this
 * one is scoped to the auth page.
 */
(function () {
  function focusError() {
    var target =
      document.querySelector('.login-form [aria-invalid="true"]') ||
      document.querySelector('[data-login-error]');
    if (target) target.focus();
  }

  document.addEventListener('htmx:afterSwap', focusError);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', focusError);
  } else {
    focusError();
  }
})();
