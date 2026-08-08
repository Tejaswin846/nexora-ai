(function () {
  "use strict";

  var config = window.NEXORA_POSTHOG_CONFIG || {};
  if (!config.enabled || !config.publicKey || window.posthog) return;

  var host = config.host || "https://us.i.posthog.com";
  var assetHost = host.replace(".i.posthog.com", "-assets.i.posthog.com");

  function safeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, 80);
  }

  function featureNameFor(target) {
    var el = target && target.closest && target.closest("[data-posthog-feature],button,a,[role='button']");
    if (!el) return "";
    return (
      el.getAttribute("data-posthog-feature") ||
      el.getAttribute("aria-label") ||
      el.getAttribute("title") ||
      safeText(el.textContent) ||
      el.id ||
      el.className ||
      el.tagName ||
      ""
    ).toString().slice(0, 120);
  }

  function capture(event, properties) {
    try {
      if (window.posthog && typeof window.posthog.capture === "function") {
        window.posthog.capture(event, properties || {});
      }
    } catch (error) {
      // Analytics must never break the app.
    }
  }

  function identifyFromStorage() {
    try {
      var raw = localStorage.getItem("nexoraUser");
      if (!raw) return;
      var user = JSON.parse(raw);
      if (user && user.id && window.posthog && typeof window.posthog.identify === "function") {
        window.posthog.identify(String(user.id), {
          app: config.app || "Nexora",
          environment: config.environment || "development"
        });
      }
    } catch (error) {
      return;
    }
  }

  function initPostHog() {
    try {
      window.posthog.init(config.publicKey, {
        api_host: host,
        defaults: "2026-05-30",
        capture_pageview: true,
        autocapture: false,
        disable_session_recording: !config.sessionRecordingEnabled,
        mask_all_text: !!config.privacyMode,
        mask_all_element_attributes: !!config.privacyMode,
        session_recording: {
          maskAllInputs: true,
          maskTextSelector: config.privacyMode ? "body" : "",
          maskInputOptions: {
            password: true,
            email: true
          }
        },
        loaded: function () {
          identifyFromStorage();
          capture("app opened", {
            app: config.app || "Nexora",
            version: config.version || "",
            environment: config.environment || "",
            session_recording_enabled: !!config.sessionRecordingEnabled
          });
        }
      });
    } catch (error) {
      return;
    }
  }

  var script = document.createElement("script");
  script.async = true;
  script.crossOrigin = "anonymous";
  script.src = assetHost + "/static/array.js";
  script.onload = initPostHog;
  script.onerror = function () {
    window.NexoraPostHogLoadFailed = true;
  };
  (document.head || document.documentElement).appendChild(script);

  window.addEventListener("appinstalled", function () {
    capture("software installed", {
      source: "pwa",
      app: config.app || "Nexora"
    });
  });

  document.addEventListener("click", function (event) {
    var feature = featureNameFor(event.target);
    if (!feature) return;
    capture("feature used", {
      feature: feature,
      path: location.pathname,
      app: config.app || "Nexora"
    });
  }, true);

  window.nexoraTrackFeature = function (feature, properties) {
    capture("feature used", Object.assign({
      feature: safeText(feature),
      path: location.pathname,
      app: config.app || "Nexora"
    }, properties || {}));
  };

  window.nexoraTrackEvent = function (event, properties) {
    capture(safeText(event), Object.assign({
      path: location.pathname,
      app: config.app || "Nexora"
    }, properties || {}));
  };
})();
