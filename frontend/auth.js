(function () {
  const TOKEN_KEY = "nexoraAuthToken";
  const USER_KEY = "nexoraAuthUser";
  const USER_ID_KEY = "nexoraUserId";

  let authConfig = null;
  let clerk = null;

  function $(id) {
    return document.getElementById(id);
  }

  function setStatus(message, kind) {
    const el = $("nxAuthStatus");
    if (!el) return;
    el.textContent = message || "";
    el.dataset.kind = kind || "info";
  }

  function currentUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch (_error) {
      return null;
    }
  }

  function authToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function publicUserFromClerk(user) {
    if (!user) return null;
    const email = user.primaryEmailAddress?.emailAddress || user.emailAddresses?.[0]?.emailAddress || "";
    return {
      id: user.id,
      email,
      name: user.fullName || user.username || email || "Nexora user",
      auth_provider: "clerk",
    };
  }

  async function refreshClerkSession() {
    if (!clerk || !clerk.session) return "";
    const token = await clerk.session.getToken();
    if (token) localStorage.setItem(TOKEN_KEY, token);
    const user = publicUserFromClerk(clerk.user);
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
      localStorage.setItem(USER_ID_KEY, user.id || "");
      localStorage.setItem("nexoraUser", user.name || user.email || "Nexora user");
      window.nexoraUserId = user.id || "";
    }
    refreshAuthUi();
    return token || "";
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(USER_ID_KEY);
    window.nexoraUserId = "";
    refreshAuthUi();
  }

  function installFetchAuth() {
    if (window.__nexoraAuthFetchInstalled) return;
    window.__nexoraAuthFetchInstalled = true;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
      let token = authToken();
      if (clerk && clerk.session) {
        token = await refreshClerkSession();
      }
      if (!token) return originalFetch(input, init);

      const url = typeof input === "string" ? input : input && input.url;
      const isRelative = typeof url === "string" && (url.startsWith("/") || !/^https?:\/\//i.test(url));
      const sameOrigin = typeof url === "string" && /^https?:\/\//i.test(url) && new URL(url, window.location.href).origin === window.location.origin;
      const configuredApi = window.API_BASE || window.API_BASE_SAFE || window.API_BASE_V2 || "";
      const configuredApiMatch = configuredApi && typeof url === "string" && url.startsWith(configuredApi);
      if (!isRelative && !sameOrigin && !configuredApiMatch) return originalFetch(input, init);

      const nextInit = Object.assign({}, init || {});
      const headers = new Headers(nextInit.headers || (input && input.headers) || {});
      if (!headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      nextInit.headers = headers;
      return originalFetch(input, nextInit);
    };
  }

  function loadClerkSdk() {
    return new Promise((resolve, reject) => {
      if (window.Clerk) {
        resolve();
        return;
      }
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js";
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Could not load Clerk authentication SDK."));
      document.head.appendChild(script);
    });
  }

  async function loadConfig() {
    const response = await fetch("/auth/config", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Auth configuration is unavailable.");
    authConfig = await response.json();
    if (!authConfig.configured || !authConfig.clerk_publishable_key) {
      throw new Error("Clerk is not configured on this deployment.");
    }
    return authConfig;
  }

  function buildAuthUi() {
    const root = $("login");
    if (!root) return;
    root.innerHTML = `
      <div class="login-box nx-auth-box">
        <div class="login-close" id="nxAuthClose">x</div>
        <div class="login-title">Nexora Account</div>
        <button class="login-btn" id="nxClerkSignIn" type="button">Sign in</button>
        <button class="login-btn nx-auth-secondary" id="nxClerkSignUp" type="button">Create account</button>
        <button class="login-btn nx-auth-secondary" id="nxClerkReset" type="button">Reset password</button>
        <button class="login-btn nx-auth-secondary" id="nxAuthLogout" type="button">Log out</button>
        <div class="nx-auth-status" id="nxAuthStatus"></div>
        <div class="nx-auth-note">Google, GitHub, email verification, and password reset are handled by Clerk. SDK install stays public; sign in only for protected cloud features and private workspace data.</div>
      </div>
    `;
    injectStyles();
    bindAuthUi();
  }

  function injectStyles() {
    if ($("nxAuthStyles")) return;
    const style = document.createElement("style");
    style.id = "nxAuthStyles";
    style.textContent = `
      .nx-auth-box{width:min(380px,calc(100vw - 36px));border-radius:8px!important}
      .nx-auth-secondary{margin-top:8px;background:#262a33!important}
      .nx-auth-status{min-height:20px;margin-top:10px;font-size:13px;color:#cbd5e1}
      .nx-auth-status[data-kind="error"]{color:#fca5a5}
      .nx-auth-status[data-kind="ok"]{color:#86efac}
      .nx-auth-note{margin-top:12px;color:#94a3b8;font-size:12px;line-height:1.45}
    `;
    document.head.appendChild(style);
  }

  function bindAuthUi() {
    $("nxClerkSignIn")?.addEventListener("click", () => {
      clerk?.openSignIn?.({ redirectUrl: window.location.href });
    });
    $("nxClerkSignUp")?.addEventListener("click", () => {
      clerk?.openSignUp?.({ redirectUrl: window.location.href });
    });
    $("nxClerkReset")?.addEventListener("click", () => {
      clerk?.openSignIn?.({ initialValues: {}, redirectUrl: window.location.href });
      setStatus("Choose forgot password in the Clerk sign-in flow.", "info");
    });
    $("nxAuthLogout")?.addEventListener("click", logout);
    $("nxAuthClose")?.addEventListener("click", () => {
      $("login").style.display = currentUser() ? "none" : "flex";
    });
  }

  async function syncBackendProfile() {
    try {
      const response = await fetch("/auth/me", { headers: { Accept: "application/json" } });
      if (response.ok) {
        const payload = await response.json();
        if (payload.user) {
          localStorage.setItem(USER_ID_KEY, payload.user.id || "");
        }
      }
    } catch (_error) {
      return;
    }
  }

  async function logout() {
    try {
      await clerk?.signOut?.();
      await fetch("/auth/logout", { method: "POST" });
    } catch (_error) {
      // Local cleanup still matters if the network is gone.
    }
    clearSession();
    setStatus("Logged out.", "ok");
    $("login").style.display = "flex";
  }

  function refreshAuthUi() {
    const user = currentUser();
    const logoutButton = $("nxAuthLogout");
    if (logoutButton) logoutButton.style.display = user ? "block" : "none";
  }

  async function boot() {
    buildAuthUi();
    installFetchAuth();
    window.nexoraGetAuthToken = authToken;
    window.getNexoraUserId = function () {
      return localStorage.getItem(USER_ID_KEY) || window.nexoraUserId || localStorage.getItem("nexoraUser") || "default";
    };
    try {
      await loadConfig();
      await loadClerkSdk();
      clerk = new window.Clerk(authConfig.clerk_publishable_key);
      await clerk.load();
      if (clerk.session) {
        await refreshClerkSession();
        await syncBackendProfile();
        $("login").style.display = "none";
      } else if (!localStorage.getItem("nexoraUser")) {
        $("login").style.display = "flex";
      }
      clerk.addListener?.(async ({ user, session }) => {
        if (session || user) {
          await refreshClerkSession();
          await syncBackendProfile();
          $("login").style.display = "none";
        } else {
          clearSession();
        }
      });
    } catch (error) {
      setStatus(error.message || "Clerk setup failed.", "error");
    }
    refreshAuthUi();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
