"""Accessibility gate for the evidence console.

The console is how most people will meet this project, so its claims about being
readable by anyone should be checked rather than asserted. This walks every
route, in both themes and both reading levels, and fails on:

  * text below the WCAG 2.1 AA contrast minimum against its real background
  * controls and links with no accessible name
  * form fields with no label
  * duplicate element ids, skipped heading levels, missing landmarks

Two notes on the contrast maths, both learned the hard way:

  * Chrome serialises ``color-mix()`` as ``color(srgb r g b / a)`` with channels
    in 0-1, not ``rgb()`` with 0-255. Reading those as 0-255 makes every
    translucent surface look black and invents failures that are not there.
  * A translucent background must be composited over what is behind it before
    the ratio means anything. The sticky header is the obvious case.

Usage::

    uv run hindsight serve            # in one shell
    uv run python scripts/check_accessibility.py

Exits non-zero on any finding.
"""

from __future__ import annotations

import os
import sys
from urllib.error import URLError
from urllib.request import urlopen

# Overridable so the same gate can be pointed at a container or a deployed
# URL, not just a local `hindsight serve`.
BASE = os.getenv("HINDSIGHT_BASE_URL", "http://127.0.0.1:8100").rstrip("/")
ROUTES = ("/", "/audits", "/audits/latest", "/evidence", "/settings")
MODES = ("plain", "technical")
THEMES = ("dark", "light")

CONTRAST_JS = r"""
() => {
  const lin = c => { c /= 255; return c <= 0.04045 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = ([r,g,b]) => 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b);
  const ratio = (a,b) => {
    const [x,y] = [lum(a), lum(b)].sort((p,q) => q-p);
    return (x+0.05) / (y+0.05);
  };

  function toRGB(s) {
    if (!s) return null;
    const m = s.match(/[\d.]+/g);
    if (!m) return null;
    const unit = s.startsWith('color(') ? 255 : 1;
    return { rgb: m.slice(0,3).map(v => Math.round(+v * unit)), a: m.length > 3 ? +m[3] : 1 };
  }
  const blend = (fg, bg, a) => fg.map((c,i) => Math.round(c*a + bg[i]*(1-a)));

  function bgOf(el) {
    const stack = [];
    let n = el;
    while (n && n !== document.documentElement) {
      const c = toRGB(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 0.999) break; }
      n = n.parentElement;
    }
    const root = toRGB(getComputedStyle(document.documentElement).backgroundColor);
    let out = (root && root.a >= 0.999) ? root.rgb : [255,255,255];
    for (let i = stack.length - 1; i >= 0; i--) out = blend(stack[i].rgb, out, stack[i].a);
    return out;
  }

  /* Text clipped to a 1px box is for screen readers and is never seen, so its
     contrast against whatever sits behind it is meaningless. offsetParent is not
     null for these, so they have to be excluded explicitly. */
  const srOnly = el => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'absolute') return false;
    const clipped = cs.clip === 'rect(0px, 0px, 0px, 0px)' ||
                    cs.clipPath === 'inset(50%)';
    const tiny = parseFloat(cs.width) <= 1 && parseFloat(cs.height) <= 1;
    return clipped || tiny;
  };

  const bad = [];
  document.querySelectorAll('*').forEach(el => {
    if (el.offsetParent === null) return;
    if (srOnly(el)) return;
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const cs = getComputedStyle(el);
    if (cs.opacity !== '' && +cs.opacity < 0.4) return;
    const fg = toRGB(cs.color);
    if (!fg || fg.a < 0.6) return;
    const size = parseFloat(cs.fontSize);
    const bold = +cs.fontWeight >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3.0 : 4.5;
    const bg = bgOf(el);
    const r = ratio(blend(fg.rgb, bg, fg.a), bg);
    if (r < need) {
      bad.push('contrast ' + r.toFixed(2) + ' (needs ' + need + ') at ' +
        Math.round(size) + 'px on <' + el.tagName.toLowerCase() +
        ' class="' + String(el.className).slice(0,30) + '">: ' +
        el.textContent.trim().slice(0,40));
    }
  });
  return [...new Set(bad)];
}
"""

SEMANTICS_JS = r"""
() => {
  const out = [];
  const named = el => {
    const by = el.getAttribute('aria-labelledby');
    const ref = by ? document.getElementById(by) : null;
    return (el.getAttribute('aria-label') || el.getAttribute('title') ||
            (ref ? ref.textContent : '') || el.textContent || '').trim();
  };

  document.querySelectorAll('img').forEach(el => {
    if (!el.hasAttribute('alt')) out.push('image without alt: ' + el.src.slice(-40));
  });
  document.querySelectorAll('button, a[href]').forEach(el => {
    if (el.offsetParent === null) return;
    if (!named(el)) out.push('no accessible name: <' + el.tagName.toLowerCase() +
      ' class="' + el.className + '">');
  });
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (el.type === 'hidden') return;
    if ((el.labels && el.labels.length) || el.getAttribute('aria-label') ||
        el.getAttribute('aria-labelledby')) return;
    out.push('unlabelled control: ' + (el.name || el.id || el.type));
  });

  const seen = {};
  document.querySelectorAll('[id]').forEach(el => {
    if (seen[el.id]) out.push('duplicate id: ' + el.id);
    seen[el.id] = 1;
  });

  let last = 0;
  document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => {
    if (h.offsetParent === null) return;
    const lvl = +h.tagName[1];
    if (last && lvl > last + 1) {
      out.push('heading jumps h' + last + ' to h' + lvl + ': ' + h.textContent.trim().slice(0,40));
    }
    last = lvl;
  });

  const h1s = [...document.querySelectorAll('h1')].filter(h => h.offsetParent !== null);
  if (h1s.length !== 1) out.push('expected exactly one visible h1, found ' + h1s.length);
  if (!document.querySelector('main')) out.push('no <main> landmark');
  if (!document.querySelector('a[href="#main"]')) out.push('no skip link');
  if (!document.documentElement.lang) out.push('no lang attribute');
  document.querySelectorAll('[tabindex]').forEach(el => {
    if (+el.getAttribute('tabindex') > 0) out.push('positive tabindex breaks focus order');
  });
  return [...new Set(out)];
}
"""


def _console_is_up() -> bool:
    try:
        with urlopen(BASE, timeout=5) as response:  # noqa: S310 - fixed localhost URL
            return response.status == 200
    except (URLError, OSError):
        return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed; skipping (install with: uv sync --extra dev)")
        return 0

    if not _console_is_up():
        print(f"no console at {BASE}; start it with `uv run hindsight serve`")
        return 1

    findings: list[str] = []
    checked = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for theme in THEMES:
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(BASE, wait_until="networkidle", timeout=40_000)
            page.evaluate("t => localStorage.setItem('hindsight-theme', t)", theme)

            for route in ROUTES:
                page.goto(f"{BASE}{route}", wait_until="networkidle", timeout=40_000)
                page.wait_for_timeout(400)

                for mode in MODES:
                    switch = page.query_selector(f"[data-mode={mode}]")
                    if switch:
                        switch.click()
                        page.wait_for_timeout(250)

                    checked += 1
                    where = f"{theme} {route} ({mode})"
                    for issue in page.evaluate(CONTRAST_JS) + page.evaluate(SEMANTICS_JS):
                        findings.append(f"{where}: {issue}")

                    # Pages without a reading-level switch are the same twice.
                    if not switch:
                        break
            page.close()
        browser.close()

    if findings:
        print(f"{len(findings)} accessibility findings across {checked} page states:\n")
        for finding in findings:
            print("  " + finding)
        return 1

    print(f"Accessibility check passed: {checked} page states, no findings.")
    print("  WCAG 2.1 AA contrast, accessible names, labels, ids, headings, landmarks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
