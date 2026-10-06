// Format all <time> elements to local timezone.
// Called on page load and after htmx swaps.
function formatTimes(root = document) {
  root.querySelectorAll("time[datetime]").forEach((el) => {
    const dt = new Date(el.getAttribute("datetime"));
    if (isNaN(dt)) return;
    el.textContent = dt.toLocaleString(undefined, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  });
}

// The browser's own calendar date as an ISO date string, from the local
// components and never a UTC conversion: a session created late at night keeps
// today's date here. Used by the new-session trigger's htmx values.
function localIsoDate(now = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

document.addEventListener("DOMContentLoaded", () => formatTimes());
document.body.addEventListener("htmx:afterSwap", (e) => formatTimes(e.target));
