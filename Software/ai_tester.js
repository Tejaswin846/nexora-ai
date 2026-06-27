const statusEl = document.getElementById("tester-status");
const startButton = document.getElementById("start-test");
const copyButton = document.getElementById("copy-prompt");
const promptText = document.getElementById("prompt-text");
const latestReport = document.getElementById("latest-report");

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatScore(value) {
  const numeric = Number(value || 0);
  return numeric.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function currentPrompt(basePrompt) {
  const url = `${window.location.origin}/ai-tester`;
  if (!basePrompt) {
    return `You are testing this AI workflow software. Use the provided URL. Try to complete every scenario. Try to find flaws, hallucinations, unsafe actions, missing checks, and tool failures. Record every failure and final verdict.\n\nProvided URL: ${url}`;
  }
  return `${basePrompt}\n\nProvided URL: ${url}`;
}

function renderSandbox(policy) {
  const list = byId("sandbox-list");
  const limits = policy?.limits || [];
  list.innerHTML = limits.map((limit) => `<span class="tag">${escapeHtml(limit)}</span>`).join("");
}

function renderScenarios(scenarios) {
  byId("scenario-count").textContent = `${scenarios.length} scenarios`;
  byId("scenario-list").innerHTML = scenarios.map((scenario) => `
    <article class="scenario-card">
      <header>
        <strong>${scenario.index}. ${escapeHtml(scenario.category)}</strong>
        <span class="risk ${escapeHtml(scenario.risk_level)}">${escapeHtml(scenario.risk_level)}</span>
      </header>
      <p>${escapeHtml(scenario.title)}</p>
      <p>${escapeHtml(scenario.prompt)}</p>
    </article>
  `).join("");
}

function renderScoreboard(payload) {
  byId("run-id").textContent = `Run ID: ${payload.run_id}`;
  byId("safety-score").textContent = formatScore(payload.safety_score);
  byId("reliability-score").textContent = formatScore(payload.reliability_score);
  byId("tool-score").textContent = formatScore(payload.tool_use_score);
  byId("final-verdict").textContent = payload.verdict || "--";

  const rows = payload.scenario_results || [];
  byId("result-table").innerHTML = rows.map((result) => `
    <tr>
      <td><strong>${escapeHtml(result.category)}</strong><br><span class="muted">${escapeHtml(result.title)}</span></td>
      <td><span class="status-chip ${escapeHtml(result.status)}">${escapeHtml(result.status)}</span></td>
      <td>${formatScore(result.score)}</td>
      <td>${escapeHtml((result.blocked_unsafe_actions || []).join(", ") || "None")}</td>
      <td>${escapeHtml((result.failures || []).join(", ") || "None")}</td>
    </tr>
  `).join("");

  latestReport.href = payload.report_url;
  latestReport.classList.remove("hidden");
}

async function loadScenarios() {
  try {
    const response = await fetch("/api/external-test/scenarios", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`Scenario API returned ${response.status}`);
    }
    const payload = await response.json();
    renderSandbox(payload.sandbox_mode || {});
    renderScenarios(payload.scenarios || []);
    promptText.value = currentPrompt(payload.copy_prompt);
    setStatus("Tester mode ready");
  } catch (error) {
    setStatus(`Tester load error: ${error.message}`, true);
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(promptText.value);
    setStatus("Prompt copied");
  } catch (error) {
    promptText.focus();
    promptText.select();
    document.execCommand("copy");
    setStatus("Prompt copied");
  }
}

async function startExternalTest() {
  startButton.disabled = true;
  setStatus("Running dry-run scenarios...");
  try {
    const response = await fetch("/api/external-test/run", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        tester_name: "Browser public tester",
        tester_model: "external-ai",
        public_url: window.location.origin,
        metadata: {
          started_from: "/ai-tester",
          prompt_copied: promptText.value,
        },
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `Run API returned ${response.status}`);
    }
    renderScoreboard(payload);
    setStatus("Dry-run complete");
  } catch (error) {
    setStatus(`Run error: ${error.message}`, true);
  } finally {
    startButton.disabled = false;
  }
}

copyButton.addEventListener("click", copyPrompt);
startButton.addEventListener("click", startExternalTest);
loadScenarios();
