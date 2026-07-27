/* Hindsight evidence console
   ---------------------------------------------------------------------------
   Four behaviours, no framework:
     1. theme toggle that respects the OS until the visitor overrides it
     2. accessible info popovers so no term is left unexplained
     3. a backend activity log that can replay step by step
     4. the publish form's approval affordance

   Everything degrades: with JS disabled the page still renders the full audit
   and a static copy of the log inside <noscript>.
*/

(function () {
  "use strict";

  var root = document.documentElement;
  var THEME_KEY = "hindsight-theme";

  function readJSON(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent);
    } catch (err) {
      return fallback;
    }
  }

  /* -- 1. Theme ----------------------------------------------------------- */

  function currentTheme() {
    var explicit = root.getAttribute("data-theme");
    if (explicit) return explicit;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  function initTheme() {
    var toggle = document.getElementById("theme-toggle");
    if (!toggle) return;

    function sync() {
      var theme = currentTheme();
      toggle.setAttribute(
        "title",
        theme === "light" ? "Switch to dark theme" : "Switch to light theme"
      );
    }

    toggle.addEventListener("click", function () {
      var next = currentTheme() === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch (err) {
        /* private mode: the choice simply will not persist */
      }
      sync();
    });

    // Follow the OS only while the visitor has not chosen for themselves.
    var media = window.matchMedia("(prefers-color-scheme: light)");
    if (media.addEventListener) {
      media.addEventListener("change", function () {
        var stored = null;
        try {
          stored = localStorage.getItem(THEME_KEY);
        } catch (err) {
          /* ignore */
        }
        if (!stored) sync();
      });
    }

    sync();
  }

  /* -- 2. Info popovers --------------------------------------------------- */

  function initPopovers() {
    var glossary = readJSON("glossary-data", {});
    var open = null;

    var popover = document.createElement("div");
    popover.className = "popover";
    popover.setAttribute("role", "dialog");
    popover.hidden = true;
    popover.innerHTML = '<h4></h4><p class="short"></p><p class="body"></p>';
    document.body.appendChild(popover);

    var titleEl = popover.querySelector("h4");
    var shortEl = popover.querySelector(".short");
    var bodyEl = popover.querySelector(".body");

    function close() {
      if (!open) return;
      open.setAttribute("aria-expanded", "false");
      popover.hidden = true;
      open = null;
    }

    function place(trigger) {
      var rect = trigger.getBoundingClientRect();
      var width = popover.offsetWidth;
      var left = rect.left + window.scrollX + rect.width / 2 - width / 2;
      var margin = 12;
      left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

      var below = rect.bottom + window.scrollY + 10;
      var above = rect.top + window.scrollY - popover.offsetHeight - 10;
      var overflowsBottom = rect.bottom + popover.offsetHeight + 20 > window.innerHeight;

      popover.style.left = left + "px";
      popover.style.top = (overflowsBottom && above > window.scrollY ? above : below) + "px";
    }

    function openFor(trigger) {
      var entry = glossary[trigger.getAttribute("data-info")];
      if (!entry) return;
      titleEl.textContent = entry.term;
      shortEl.textContent = entry.short;
      bodyEl.textContent = entry.body;
      popover.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      open = trigger;
      place(trigger);
    }

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-info]");
      if (trigger) {
        event.preventDefault();
        var wasOpen = open === trigger;
        close();
        if (!wasOpen) openFor(trigger);
        return;
      }
      if (!event.target.closest(".popover")) close();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && open) {
        var trigger = open;
        close();
        trigger.focus();
      }
    });

    window.addEventListener("resize", close);
    window.addEventListener(
      "scroll",
      function () {
        if (open) place(open);
      },
      { passive: true }
    );
  }

  /* -- 3. Activity log ---------------------------------------------------- */

  function initActivityLog() {
    var container = document.getElementById("activity-log");
    if (!container) return;

    var activity = readJSON("activity-data", []);
    var status = document.getElementById("log-status");
    var replayBtn = document.getElementById("replay-log");
    var showAllBtn = document.getElementById("show-all-log");
    var timer = null;

    function lineFor(item) {
      var line = document.createElement("div");
      line.className = "log-line";
      line.setAttribute("data-ok", String(item.ok));

      var chan = document.createElement("span");
      chan.className = "chan";
      chan.setAttribute("data-channel", item.channel);
      chan.textContent = item.channel;

      var mark = document.createElement("span");
      mark.className = "mark";
      mark.textContent = item.ok === true ? "OK" : item.ok === false ? "!!" : "--";

      var body = document.createElement("span");
      body.className = "body";
      var msg = document.createElement("span");
      msg.className = "msg";
      msg.textContent = item.message;
      body.appendChild(msg);
      if (item.detail) {
        var detail = document.createElement("span");
        detail.className = "detail";
        detail.textContent = item.detail;
        body.appendChild(detail);
      }

      var src = document.createElement("span");
      src.className = "src";
      src.setAttribute("data-source", item.source);
      src.textContent = item.source;

      line.appendChild(chan);
      line.appendChild(mark);
      line.appendChild(body);
      line.appendChild(src);
      return line;
    }

    function stop() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (replayBtn) replayBtn.disabled = false;
    }

    function renderAll() {
      stop();
      container.innerHTML = "";
      activity.forEach(function (item) {
        container.appendChild(lineFor(item));
      });
      if (status) status.textContent = activity.length + " operations";
    }

    function replay() {
      stop();
      container.innerHTML = "";
      var index = 0;
      if (replayBtn) replayBtn.disabled = true;
      var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      var interval = reduced ? 60 : 420;

      timer = setInterval(function () {
        if (index >= activity.length) {
          stop();
          if (status) status.textContent = activity.length + " operations";
          return;
        }
        container.appendChild(lineFor(activity[index]));
        container.scrollTop = container.scrollHeight;
        index += 1;
        if (status) status.textContent = "step " + index + " of " + activity.length;
      }, interval);
    }

    if (replayBtn) replayBtn.addEventListener("click", replay);
    if (showAllBtn) showAllBtn.addEventListener("click", renderAll);

    renderAll();
  }

  /* -- 4. Publish form ---------------------------------------------------- */

  function initPublishForm() {
    var approval = document.getElementById("approve_writeback");
    var form = document.querySelector('form[action="/publish"]');
    if (!approval || !form) return;

    var button = form.querySelector('button[type="submit"]');
    if (!button) return;

    approval.addEventListener("change", function () {
      button.textContent = approval.checked
        ? "Publish approved evidence"
        : "Preview write-back";
    });

    form.addEventListener("submit", function () {
      button.disabled = true;
      button.textContent = approval.checked
        ? "Publishing and re-reading DataHub evidence..."
        : "Building a mutation-free preview...";
    });
  }

  function boot() {
    initTheme();
    initPopovers();
    initActivityLog();
    initPublishForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
