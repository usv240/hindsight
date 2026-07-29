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

  /* -- 5. Live DataHub status --------------------------------------------- */

  function initStatusPolling() {
    var pill = document.getElementById("datahub-status");
    if (!pill || !window.fetch) return;

    var label = pill.querySelector(".connection-label");

    function refresh() {
      fetch("/api/health/datahub", { headers: { Accept: "application/json" } })
        .then(function (response) {
          return response.ok ? response.json() : null;
        })
        .then(function (health) {
          if (!health) return;
          pill.setAttribute("data-state", health.state);
          pill.setAttribute("title", health.detail || "");
          if (label) label.textContent = health.label;
        })
        .catch(function () {
          // The console itself is unreachable; leave the last known state.
        });
    }

    // The server already rendered a probed state, so wait a full interval
    // before asking again rather than duplicating work on load.
    setInterval(refresh, 15000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) refresh();
    });
  }

  /* -- 6. Plain / technical reading level ---------------------------------
     Defaults to plain, because a first-time visitor has no reason to know what
     an AUC is. The choice persists so a returning reviewer is not sent back to
     the beginner view every time. */

  function initModeSwitch() {
    var MODE_KEY = "hindsight-mode";
    var stored = null;
    try {
      stored = localStorage.getItem(MODE_KEY);
    } catch (err) {
      /* private mode */
    }
    var mode = stored === "technical" ? "technical" : "plain";
    document.body.setAttribute("data-mode", mode);

    var buttons = document.querySelectorAll(".mode-switch [data-mode]");
    if (!buttons.length) return;

    function apply(next) {
      document.body.setAttribute("data-mode", next);
      Array.prototype.forEach.call(buttons, function (button) {
        button.setAttribute(
          "aria-pressed",
          button.getAttribute("data-mode") === next ? "true" : "false"
        );
      });
      try {
        localStorage.setItem(MODE_KEY, next);
      } catch (err) {
        /* private mode */
      }
      /* Whole sections appear and disappear here, so anything tracking them
         needs to recount rather than trust its last answer. */
      document.dispatchEvent(new CustomEvent("hindsight:modechange"));
    }

    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function () {
        apply(button.getAttribute("data-mode"));
      });
    });

    apply(mode);
  }

  /* -- 7. Action feedback --------------------------------------------------
     Running an audit posts and redirects. Without feedback the click appears to
     do nothing, then the page changes - which reads as a glitch. */

  function initActionFeedback() {
    var forms = document.querySelectorAll('form[action="/audits/run"]');
    Array.prototype.forEach.call(forms, function (form) {
      form.addEventListener("submit", function () {
        var control = form.querySelector("button");
        if (!control) return;
        control.setAttribute("aria-busy", "true");
        control.classList.add("is-running");
        if (!control.classList.contains("scenario-card")) {
          control.textContent = "Running audit...";
        }
        control.disabled = true;
        // Re-enable if the browser restores this page from cache.
        window.addEventListener("pageshow", function () {
          control.disabled = false;
          control.classList.remove("is-running");
          control.removeAttribute("aria-busy");
        });
      });
    });
  }

  /* -- 8. Section spy -----------------------------------------------------
     The audit page is long enough that the sticky jump nav stops being useful
     once you no longer know which pill you are standing in. This marks the
     section currently under the header.

     Heading elements are only a few pixels tall, so IntersectionObserver would
     flicker on and off; reading positions against the same offset the browser
     already uses for scroll-padding is steadier.
  --------------------------------------------------------------------------- */

  function initSectionSpy() {
    var nav = document.querySelector(".jumpnav");
    if (!nav) return;

    var links = [].slice.call(nav.querySelectorAll('a[href^="#"]'));
    if (links.length < 2) return;

    /* Sorted by where the target sits on the page, not by nav order. The two
       agree today, but a spy that silently depends on them agreeing goes wrong
       the first time someone reorders a pill. */
    var pairs = links
      .map(function (link) {
        return {
          link: link,
          target: document.getElementById(link.getAttribute("href").slice(1)),
        };
      })
      .filter(function (pair) {
        return pair.target !== null;
      })
      .sort(function (a, b) {
        var order = a.target.compareDocumentPosition(b.target);
        /* eslint-disable-next-line no-bitwise */
        return order & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      });

    var offset = 132;  /* topbar + jump nav + a little breathing room */
    var queued = false;

    function visible(el) {
      return !!(el && el.offsetParent !== null);
    }

    function update() {
      queued = false;
      var current = null;

      pairs.forEach(function (pair) {
        if (!visible(pair.link) || !visible(pair.target)) return;
        if (pair.target.getBoundingClientRect().top - offset <= 0) current = pair.link;
      });

      var shown = pairs.filter(function (pair) {
        return visible(pair.link) && visible(pair.target);
      });

      /* Before the first heading scrolls past, the first pill is the honest
         answer - not "nothing selected". */
      if (!current && shown.length) current = shown[0].link;

      /* The last section or two sit inside the final viewport, so their
         headings never cross the line and the spy would stall one pill short.
         At the bottom of the page, the last section is where you are. */
      var atBottom =
        window.innerHeight + window.scrollY >= document.body.scrollHeight - 2;
      if (atBottom && shown.length) current = shown[shown.length - 1].link;

      links.forEach(function (link) {
        var on = link === current;
        link.classList.toggle("is-current", on);
        if (on) {
          link.setAttribute("aria-current", "true");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    }

    function schedule() {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(update);
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    /* Switching reading level shows and hides whole sections. */
    document.addEventListener("hindsight:modechange", schedule);
    /* The activity log renders after boot, so the page gets taller without a
       scroll or resize event. Without this the spy answers about a page height
       that no longer exists. */
    if (window.ResizeObserver) {
      new ResizeObserver(schedule).observe(document.body);
    }
    update();
  }

  /* -- 9. Print ------------------------------------------------------------
     The print stylesheet does the work; this is only so the affordance exists
     for someone who would never think to press Ctrl+P on a web app.
  --------------------------------------------------------------------------- */

  function initPrint() {
    var button = document.querySelector("[data-print]");
    if (!button) return;
    button.addEventListener("click", function () {
      window.print();
    });
  }

  /* -- 10. Evidence record ------------------------------------------------
     Fetched on first open from the same endpoint the download button serves,
     so what you read and what you save cannot drift apart. Without JS the
     "Open raw" link still works, which is why the fetch is an enhancement
     rather than the only route to the data.
  --------------------------------------------------------------------------- */

  function initEvidenceRecord() {
    var toggle = document.querySelector("[data-evidence-toggle]");
    var panel = document.getElementById("evidence-record");
    if (!toggle || !panel) return;

    var body = panel.querySelector("[data-evidence-body]");
    var loaded = false;

    toggle.addEventListener("click", function () {
      var opening = panel.hidden;
      panel.hidden = !opening;
      toggle.setAttribute("aria-expanded", String(opening));
      toggle.textContent = opening ? "Hide evidence" : "View evidence";

      if (!opening || loaded || !body) return;
      loaded = true;

      fetch(body.getAttribute("data-src"))
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.text();
        })
        .then(function (text) {
          body.textContent = text;
        })
        .catch(function (error) {
          loaded = false;  /* let a retry happen on the next open */
          body.textContent =
            "Could not load the record (" + error.message + "). " +
            "Use Open raw or Download instead.";
        });

      if (panel.scrollIntoView) panel.scrollIntoView({ block: "nearest" });
    });
  }

  function boot() {
    initTheme();
    initPrint();
    initEvidenceRecord();
    initModeSwitch();
    initSectionSpy();
    initPopovers();
    initActivityLog();
    initPublishForm();
    initStatusPolling();
    initActionFeedback();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
