// stealth_main.js
// Injected via Page.addScriptToEvaluateOnNewDocument — runs BEFORE any page JS.
// Removes all known automation/CDP fingerprints used by Cloudflare, DataDome,
// Akamai BMP, Imperva, Kasada, hCaptcha, GoCaptcha, and Friendly Captcha.
//
// Modules: navigator.webdriver, plugins, languages, window.chrome, permissions,
// WebGL vendor/renderer, Canvas fingerprint, AudioContext jitter, Battery API,
// iframe.contentWindow recursion, cdc_* probe scrub.
//
// Idempotent and crash-safe (every module is wrapped in try/catch).
(() => {
  'use strict';
  if (window.__stealth_main_applied__) return;
  Object.defineProperty(window, '__stealth_main_applied__', { value: true, configurable: false });

  const cfg = window.__STEALTH_CFG__ || {};
  const safe = (fn) => { try { fn(); } catch (_) {} };

  // ── 1. navigator.webdriver ──────────────────────────────────────────────
  if (cfg.navigator !== false) {
    safe(() => {
      const proto = Navigator.prototype;
      delete proto.webdriver;
      Object.defineProperty(proto, 'webdriver', { get: () => false, configurable: true });
    });
  }

  // ── 2. navigator.plugins — non-empty PluginArray ─────────────────────────
  if (cfg.plugins !== false) {
    safe(() => {
      const pdf = Object.freeze({
        name: 'PDF Viewer', filename: 'internal-pdf-viewer',
        description: 'Portable Document Format', length: 1,
        0: Object.freeze({ type: 'application/pdf', suffixes: 'pdf',
          description: 'Portable Document Format', enabledPlugin: null }),
      });
      const chromePdf = Object.freeze({
        name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer',
        description: '', length: 1,
        0: Object.freeze({ type: 'application/pdf', suffixes: 'pdf',
          description: '', enabledPlugin: null }),
      });
      const arr = Object.create(PluginArray.prototype);
      Object.defineProperties(arr, {
        length: { value: 2, writable: false },
        0: { value: pdf, writable: false },
        1: { value: chromePdf, writable: false },
        item: { value: function(i) { return this[i] || null; }, writable: false },
        namedItem: { value: function(n) { return this[0].name === n ? this[0] : this[1].name === n ? this[1] : null; }, writable: false },
        refresh: { value: function() {}, writable: false },
      });
      Object.defineProperty(Navigator.prototype, 'plugins', { get: () => arr, configurable: true });
    });
  }

  // ── 3. navigator.languages ──────────────────────────────────────────────
  if (cfg.languages !== false) {
    safe(() => {
      Object.defineProperty(Navigator.prototype, 'languages', {
        get: () => cfg.languagesValue || ['en-US', 'en', 'de'],
        configurable: true,
      });
    });
  }

  // ── 4. window.chrome (must exist, realistic shape) ───────────────────────
  if (cfg.chromeRuntime !== false) {
    safe(() => {
      const chrome = window.chrome || {};
      chrome.runtime = chrome.runtime || {
        PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        PlatformArch: { ARM: 'arm', ARM64: 'arm64', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
        RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
        OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
      };
      chrome.app = chrome.app || {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
      };
      chrome.csi = chrome.csi || function() { return { startE: Date.now(), onloadT: Date.now(), pageT: 1, tran: 15 }; };
      chrome.loadTimes = chrome.loadTimes || function() {
        return {
          requestTime: Date.now() / 1000 - 0.5,
          startLoadTime: Date.now() / 1000 - 0.4,
          commitLoadTime: Date.now() / 1000 - 0.3,
          finishDocumentLoadTime: Date.now() / 1000 - 0.2,
          finishLoadTime: Date.now() / 1000 - 0.1,
          firstPaintTime: Date.now() / 1000 - 0.05,
          firstPaintAfterLoadTime: 0,
          navigationType: 'Other',
          wasFetchedViaSpdy: true,
          wasNpnNegotiated: true,
          npnNegotiatedProtocol: 'h2',
          wasAlternateProtocolAvailable: false,
          connectionInfo: 'h2',
        };
      };
      Object.defineProperty(window, 'chrome', { value: chrome, configurable: true, writable: true });
    });
  }

  // ── 5. permissions.query (notifications quirk) ──────────────────────────
  if (cfg.permissions !== false && navigator.permissions) {
    safe(() => {
      const orig = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = (params) => {
        if (params && params.name === 'notifications') {
          return Promise.resolve({
            state: Notification.permission,
            onchange: null,
            addEventListener: function() {},
            removeEventListener: function() {},
            dispatchEvent: function() { return true; },
          });
        }
        return orig(params);
      };
    });
  }

  // ── 6. WebGL — UNMASKED_VENDOR / UNMASKED_RENDERER ──────────────────────
  if (cfg.webgl !== false) {
    safe(() => {
      const vendor = cfg.webglVendor || 'Intel Inc.';
      const renderer = cfg.webglRenderer || 'Intel Iris OpenGL Engine';
      const patch = (proto) => {
        const orig = proto.getParameter;
        proto.getParameter = function(param) {
          if (param === 37445) return vendor;
          if (param === 37446) return renderer;
          return orig.call(this, param);
        };
      };
      if (window.WebGLRenderingContext) patch(WebGLRenderingContext.prototype);
      if (window.WebGL2RenderingContext) patch(WebGL2RenderingContext.prototype);
    });
  }

  // ── 7. Canvas — per-pixel jitter on toDataURL/getImageData ──────────────
  if (cfg.canvas !== false) {
    safe(() => {
      const seed = (cfg.canvasSeed || 0xC0FFEE) >>> 0;
      let s = seed;
      const rng = () => { s = (s * 1664525 + 1013904223) >>> 0; return (s & 0xff) / 255; };
      const jitter = (img) => {
        const data = img.data;
        for (let i = 0; i < data.length; i += 4) {
          if (rng() < 0.0025) data[i] ^= 1;
        }
        return img;
      };
      const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
      HTMLCanvasElement.prototype.toDataURL = function(...args) {
        try {
          const ctx = this.getContext('2d');
          if (ctx) {
            const img = ctx.getImageData(0, 0, this.width, this.height);
            jitter(img);
            ctx.putImageData(img, 0, 0);
          }
        } catch (_) {}
        return origToDataURL.apply(this, args);
      };
      const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
      CanvasRenderingContext2D.prototype.getImageData = function(...args) {
        const img = origGetImageData.apply(this, args);
        return jitter(img);
      };
    });
  }

  // ── 8. AudioContext — fingerprint jitter ────────────────────────────────
  if (cfg.audio !== false && window.AudioBuffer) {
    safe(() => {
      const orig = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = function(...args) {
        const data = orig.apply(this, args);
        if (!this.__stealth_jittered__) {
          for (let i = 0; i < data.length; i += 100) {
            data[i] += (Math.random() - 0.5) * 1e-7;
          }
          Object.defineProperty(this, '__stealth_jittered__', { value: true });
        }
        return data;
      };
    });
  }

  // ── 9. Battery API — realistic non-suspicious values ────────────────────
  if (cfg.battery !== false && navigator.getBattery) {
    safe(() => {
      navigator.getBattery = () => Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 0.87,
        addEventListener: function() {}, removeEventListener: function() {},
        dispatchEvent: function() { return true; },
      });
    });
  }

  // ── 10. iframe.contentWindow — propagate stealth to same-origin iframes ──
  if (cfg.iframe !== false) {
    safe(() => {
      const orig = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
      Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get() {
          const win = orig.get.call(this);
          if (win && !win.__stealth_main_applied__) {
            try {
              win.eval('(' + arguments.callee.caller.toString() + ')()');
            } catch (_) {}
          }
          return win;
        },
        configurable: true,
      });
    });
  }

  // ── 11. Function.prototype.toString — hide our patches as native ────────
  safe(() => {
    const origToString = Function.prototype.toString;
    const cache = new WeakMap();
    Function.prototype.toString = function() {
      if (cache.has(this)) return cache.get(this);
      return origToString.call(this);
    };
    window.__stealth_seal__ = (fn, src) => cache.set(fn, src);
  });

  // ── 12. Remove cdc_* and __webdriver_* probes ──────────────────────────
  safe(() => {
    const probes = [
      'cdc_adoQpoasnfa76pfcZLmcfl_Array',
      'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
      'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
      '$cdc_asdjflasutopfhvcZLmcfl_',
      '__webdriver_evaluate', '__selenium_evaluate',
      '__webdriver_script_function', '__webdriver_script_func',
      '__webdriver_script_fn', '__fxdriver_evaluate',
      '__driver_unwrapped', '__webdriver_unwrapped',
      '__driver_evaluate', '__selenium_unwrapped',
      '__fxdriver_unwrapped',
    ];
    for (const k of probes) {
      try { delete window[k]; } catch (_) {}
      try { delete document[k]; } catch (_) {}
    }
  });
})();
