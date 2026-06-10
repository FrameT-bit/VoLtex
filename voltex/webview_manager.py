from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from string import Template
from typing import Any

from .config import VoltexConfig
from .server import BridgeInfo


############################################################
# INJECTED JAVASCRIPT                                      #
############################################################

SCRIPT_TEMPLATE = Template(
    r"""
(() => {
  if (window.__voltexInstalled) {
    return;
  }
  window.__voltexInstalled = true;

  const bridgeUrl = $bridge_url;
  const secret = $secret;
  const rememberLogin = $remember_login;
  const seenCookies = new Set();
  const seenEvents = new Set();
  let armedUntil = 0;

  async function request(path, payload = null, method = 'POST') {
    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Voltex-Secret': secret
        },
        credentials: 'omit'
      };
      if (payload !== null) {
        options.body = JSON.stringify(payload);
      }
      const response = await fetch(`$${bridgeUrl}$${path}`, options);
      const data = await response.json().catch(() => ({}));
      return { ok: response.ok, status: response.status, ...data };
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  async function post(path, payload) {
    return request(path, payload, 'POST');
  }

  function debug(event, payload = {}) {
    post('/api/debug', { event, href: String(window.location.href), ...payload });
  }

  function arm(reason) {
    armedUntil = Date.now() + 12000;
    debug('client_armed', { reason });
  }

  function notify(message) {
    if (!message) {
      return;
    }
    let toast = document.getElementById('voltex-notice');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'voltex-notice';
      toast.style.cssText = [
        'position:fixed',
        'left:16px',
        'right:16px',
        'bottom:16px',
        'z-index:2147483647',
        'background:#202124',
        'color:#fff',
        'border:1px solid #5f6368',
        'border-radius:8px',
        'box-shadow:0 8px 24px rgba(0,0,0,.35)',
        'padding:14px 16px',
        'font:14px/1.4 system-ui,sans-serif',
        'white-space:pre-wrap'
      ].join(';');
      document.documentElement.appendChild(toast);
    }
    toast.textContent = message;
    window.clearTimeout(toast.__voltexTimer);
    toast.__voltexTimer = window.setTimeout(() => toast.remove(), 16000);
  }

  function handleLaunchResult(result) {
    if (result && result.ok === false) {
      notify(result.error || 'Vortex player could not start.');
    }
  }

  function launch(uri) {
    if (typeof uri !== 'string' || !uri.startsWith('vortex://')) {
      return false;
    }
    debug('client_launch_candidate', { uri });
    post('/api/launch', { uri }).then(handleLaunchResult);
    return true;
  }

  function launchFromText(text, reason) {
    if (typeof text !== 'string') {
      return false;
    }
    const match = text.match(/vortex:\/\/[^\s"'<>]+/);
    if (!match) {
      return false;
    }
    debug('client_uri_found', { reason, uri: match[0] });
    return launch(match[0]);
  }

  function sendCookie() {
    const cookie = document.cookie || '';
    if (!cookie || seenCookies.has(cookie)) {
      return;
    }
    seenCookies.add(cookie);
    post('/api/auth/token', { cookie, persist: rememberLogin });
  }

  function scanDocument(reason) {
    if (Date.now() > armedUntil) {
      return;
    }
    const html = document.documentElement ? document.documentElement.innerHTML : '';
    launchFromText(html, reason);
  }

  async function pollEvents() {
    const result = await request('/api/events', null, 'GET');
    if (!result || result.ok === false || !Array.isArray(result.events)) {
      return;
    }
    for (const event of result.events) {
      const key = `$${event.ts}:$${event.event}`;
      if (seenEvents.has(key)) {
        continue;
      }
      seenEvents.add(key);
      if (event.event === 'launch_error') {
        notify(event.detail || 'Vortex player could not start.');
      }
    }
  }

  document.addEventListener('click', event => {
    arm('click');
    const target = event.target;
    const link = target && target.closest ? target.closest('a[href]') : null;
    if (link && launch(link.href)) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  document.addEventListener('pointerdown', () => arm('pointerdown'), true);
  document.addEventListener('submit', event => {
    arm('submit');
    const form = event.target;
    if (form && form.action && launch(form.action)) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  const originalOpen = window.open;
  window.open = function(url, ...rest) {
    if (launch(url)) {
      return null;
    }
    return originalOpen.call(window, url, ...rest);
  };

  const originalFetch = window.fetch;
  if (typeof originalFetch === 'function') {
    window.fetch = async function(...args) {
      const response = await originalFetch.apply(this, args);
      if (Date.now() <= armedUntil) {
        try {
          const clone = response.clone();
          clone.text().then(text => launchFromText(text, 'fetch')).catch(() => {});
        } catch (_) {}
      }
      return response;
    };
  }

  const OriginalXHR = window.XMLHttpRequest;
  if (typeof OriginalXHR === 'function') {
    window.XMLHttpRequest = function() {
      const xhr = new OriginalXHR();
      xhr.addEventListener('load', () => {
        if (Date.now() <= armedUntil) {
          try {
            launchFromText(xhr.responseText, 'xhr');
          } catch (_) {}
        }
      });
      return xhr;
    };
  }

  try {
    const originalAssign = window.location.assign.bind(window.location);
    window.location.assign = function(url) {
      if (!launch(url)) {
        originalAssign(url);
      }
    };
  } catch (_) {}

  setInterval(() => scanDocument('interval'), 500);
  setInterval(pollEvents, 2000);
  setInterval(sendCookie, 1500);
  sendCookie();
  debug('client_injected');
})();
"""
)


############################################################
# WEBVIEW LIFECYCLE                                        #
############################################################

class WebviewManager:
    def __init__(self, config: VoltexConfig, bridge: BridgeInfo) -> None:
        self._config = config
        self._bridge = bridge
        self._reported_injection_errors: set[str] = set()

    def build_script(self) -> str:
        return SCRIPT_TEMPLATE.substitute(
            bridge_url=json.dumps(self._bridge.base_url),
            secret=json.dumps(self._bridge.secret),
            remember_login=json.dumps(self._config.remember_login),
        )

    def start(self) -> None:
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not installed. Install requirements.txt first.") from exc

        window = webview.create_window("VoLtex", self._config.site_url, width=1280, height=800)
        window.events.loaded += self._inject
        webview.start(
            self._on_start,
            window,
            gui="gtk",
            private_mode=not self._config.persistent_session,
            storage_path=str(self._config.webview_storage_path),
        )

    def _on_start(self, window: object) -> None:
        self._install_native_interceptor(window)

    def _inject(self, window: object) -> None:
        script = self.build_script()
        evaluator = getattr(window, "evaluate_js", None) or getattr(window, "execute_js", None)
        if evaluator is None:
            raise RuntimeError("pywebview window does not expose a JavaScript evaluator")
        try:
            evaluator(script)
        except Exception as exc:
            detail = str(exc)
            key = detail[:300]
            if key not in self._reported_injection_errors:
                self._reported_injection_errors.add(key)
                self._post_bridge_async(
                    "/api/debug",
                    {
                        "event": "client_injection_blocked",
                        "detail": detail[:800],
                    },
                )

    ############################################################
    # NATIVE GTK INTERCEPTOR                                   #
    ############################################################

    def _install_native_interceptor(self, window: object) -> None:
        try:
            import webview.platforms.gtk as gtk_platform
        except Exception as exc:
            self._post_bridge_async("/api/debug", {"event": "native_interceptor_unavailable", "detail": str(exc)})
            return

        uid = getattr(window, "uid", "")
        webkit = getattr(gtk_platform, "webkit", None)
        browser_view = self._wait_for_browser_view(gtk_platform, uid)
        if browser_view is None or webkit is None:
            self._post_bridge_async(
                "/api/debug",
                {
                    "event": "native_interceptor_unavailable",
                    "uid": uid,
                    "known_uids": list(getattr(gtk_platform.BrowserView, "instances", {}).keys()),
                    "has_webkit": webkit is not None,
                },
            )
            return

        def install() -> bool:
            browser_view.webview.connect("decide-policy", intercept_navigation)
            self._post_bridge_async("/api/debug", {"event": "native_interceptor_installed", "uid": uid})
            return False

        def intercept_navigation(_webview: object, decision: object, _decision_type: object) -> bool:
            try:
                if type(decision) is not webkit.NavigationPolicyDecision:
                    return False
                uri = decision.get_navigation_action().get_request().get_uri()
                if not isinstance(uri, str) or not uri.startswith("vortex://"):
                    return False
                decision.ignore()
                self._post_bridge_async("/api/debug", {"event": "native_launch_candidate", "uri": uri})
                self._post_bridge_async("/api/launch", {"uri": uri})
                return True
            except Exception as exc:
                self._post_bridge_async("/api/debug", {"event": "native_interceptor_error", "detail": str(exc)})
                return False

        glib = getattr(gtk_platform, "glib", None)
        if glib is None:
            install()
            return
        glib.idle_add(install)

    def _wait_for_browser_view(self, gtk_platform: object, uid: str) -> object | None:
        instances = getattr(gtk_platform.BrowserView, "instances", {})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            browser_view = instances.get(uid)
            if browser_view is not None:
                return browser_view
            time.sleep(0.05)
        return None

    ############################################################
    # BRIDGE HELPERS                                           #
    ############################################################

    def _post_bridge_async(self, path: str, payload: dict[str, Any]) -> None:
        thread = threading.Thread(target=self._post_bridge, args=(path, payload), daemon=True)
        thread.start()

    def _post_bridge(self, path: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self._bridge.base_url}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Voltex-Secret": self._bridge.secret,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2):
                pass
        except (OSError, urllib.error.URLError):
            pass
