(function () {
  const TOKEN_KEY = "nexoraAuthToken";
  const REFRESH_KEY = "nexoraRefreshToken";
  const USER_KEY = "nexoraAuthUser";
  const USER_ID_KEY = "nexoraUserId";

  let supabaseClient = null;
  let authConfig = null;

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
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

  function setSession(session, user) {
    const activeUser = user || (session && session.user) || null;
    if (session && session.access_token) {
      localStorage.setItem(TOKEN_KEY, session.access_token);
    }
    if (session && session.refresh_token) {
      localStorage.setItem(REFRESH_KEY, session.refresh_token);
    }
    if (activeUser) {
      const name = activeUser.user_metadata?.name || activeUser.user_metadata?.full_name || activeUser.email || "Nexora user";
      localStorage.setItem(USER_KEY, JSON.stringify(activeUser));
      localStorage.setItem(USER_ID_KEY, activeUser.id || "");
      localStorage.setItem("nexoraUser", name);
      window.nexoraUserId = activeUser.id || "";
    }
    refreshAuthUi();
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(USER_ID_KEY);
    window.nexoraUserId = "";
    refreshAuthUi();
  }

  function installFetchAuth() {
    if (window.__nexoraAuthFetchInstalled) return;
    window.__nexoraAuthFetchInstalled = true;
    const originalFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
      const token = authToken();
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

  function loadSupabaseSdk() {
    return new Promise((resolve, reject) => {
      if (window.supabase && window.supabase.createClient) {
        resolve();
        return;
      }
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Could not load Supabase authentication SDK."));
      document.head.appendChild(script);
    });
  }

  async function loadConfig() {
    const response = await fetch("/auth/config", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Auth configuration is unavailable.");
    authConfig = await response.json();
    if (!authConfig.configured) {
      throw new Error("Supabase Auth is not configured on this deployment.");
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
        <div class="nx-auth-tabs">
          <button type="button" data-auth-tab="signin" class="active">Sign in</button>
          <button type="button" data-auth-tab="signup">Sign up</button>
          <button type="button" data-auth-tab="forgot">Reset</button>
        </div>
        <input class="login-input" id="nxAuthName" placeholder="Name" autocomplete="name" />
        <input class="login-input" id="nxAuthEmail" placeholder="Email" autocomplete="email" />
        <input class="login-input" id="nxAuthPassword" type="password" placeholder="Password" autocomplete="current-password" />
        <button class="login-btn" id="nxAuthSubmit" type="button">Sign in</button>
        <button class="login-btn nx-auth-secondary" id="nxAuthLogout" type="button">Log out</button>
        <div class="nx-auth-status" id="nxAuthStatus"></div>
        <div class="nx-auth-note">SDK install is public. Sign in is needed only for protected cloud API calls and private workspace data.</div>
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
      .nx-auth-tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:12px}
      .nx-auth-tabs button{border:1px solid rgba(255,255,255,.12);background:#171a21;color:#d7ddea;border-radius:8px;padding:9px 8px;cursor:pointer}
      .nx-auth-tabs button.active{background:#2563eb;color:#fff}
      .nx-auth-secondary{margin-top:8px;background:#262a33!important}
      .nx-auth-status{min-height:20px;margin-top:10px;font-size:13px;color:#cbd5e1}
      .nx-auth-status[data-kind="error"]{color:#fca5a5}
      .nx-auth-status[data-kind="ok"]{color:#86efac}
      .nx-auth-note{margin-top:12px;color:#94a3b8;font-size:12px;line-height:1.45}
      #nxAuthName[data-hidden="true"],#nxAuthPassword[data-hidden="true"]{display:none}
    `;
    document.head.appendChild(style);
  }

  function activeTab() {
    const active = document.querySelector("[data-auth-tab].active");
    return active ? active.getAttribute("data-auth-tab") : "signin";
  }

  function setTab(tab) {
    document.querySelectorAll("[data-auth-tab]").forEach((button) => {
      button.classList.toggle("active", button.getAttribute("data-auth-tab") === tab);
    });
    const name = $("nxAuthName");
    const password = $("nxAuthPassword");
    const submit = $("nxAuthSubmit");
    if (name) name.dataset.hidden = tab === "signup" ? "false" : "true";
    if (password) password.dataset.hidden = tab === "forgot" ? "true" : "false";
    if (submit) submit.textContent = tab === "signup" ? "Create account" : tab === "forgot" ? "Send reset email" : "Sign in";
    setStatus("", "info");
  }

  function bindAuthUi() {
    document.querySelectorAll("[data-auth-tab]").forEach((button) => {
      button.addEventListener("click", () => setTab(button.getAttribute("data-auth-tab")));
    });
    $("nxAuthSubmit")?.addEventListener("click", submitAuth);
    $("nxAuthLogout")?.addEventListener("click", logout);
    $("nxAuthClose")?.addEventListener("click", () => {
      $("login").style.display = currentUser() ? "none" : "flex";
    });
    setTab("signin");
  }

  async function submitAuth() {
    const tab = activeTab();
    const email = ($("nxAuthEmail")?.value || "").trim();
    const password = $("nxAuthPassword")?.value || "";
    const name = ($("nxAuthName")?.value || "").trim();
    try {
      setStatus("Working...", "info");
      if (!email) throw new Error("Enter your email address.");
      if (tab === "forgot") {
        const { error } = await supabaseClient.auth.resetPasswordForEmail(email, {
          redirectTo: authConfig.reset_redirect_url,
        });
        if (error) throw error;
        setStatus("Password reset email sent by Supabase. Check your inbox and spam folder.", "ok");
        return;
      }
      if (password.length < 6) throw new Error("Password must be at least 6 characters.");
      if (tab === "signup") {
        const { data, error } = await supabaseClient.auth.signUp({
          email,
          password,
          options: {
            data: { name },
            emailRedirectTo: authConfig.email_redirect_url,
          },
        });
        if (error) throw error;
        setSession(data.session, data.user);
        setStatus(data.session ? "Account created and signed in." : "Account created. Check your email to verify before signing in.", "ok");
        return;
      }
      const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
      if (error) throw error;
      setSession(data.session, data.user);
      await syncBackendProfile();
      setStatus("Signed in.", "ok");
      $("login").style.display = "none";
    } catch (error) {
      setStatus(error.message || "Authentication failed.", "error");
    }
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
      await supabaseClient?.auth?.signOut();
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
      await loadSupabaseSdk();
      supabaseClient = window.supabase.createClient(authConfig.supabase_url, authConfig.supabase_anon_key, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      });
      const { data } = await supabaseClient.auth.getSession();
      if (data && data.session) {
        setSession(data.session, data.session.user);
        await syncBackendProfile();
        $("login").style.display = "none";
      } else if (!localStorage.getItem("nexoraUser")) {
        $("login").style.display = "flex";
      }
      supabaseClient.auth.onAuthStateChange((_event, session) => {
        if (session) setSession(session, session.user);
      });
    } catch (error) {
      setStatus(error.message || "Auth setup failed.", "error");
    }
    refreshAuthUi();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
