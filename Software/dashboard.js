const statusEl = document.getElementById("dashboard-status");

function byId(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const element = byId(id);
  if (element) {
    element.textContent = value;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  const numeric = Number(value || 0);
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatDecimal(value, digits = 2) {
  const numeric = Number(value || 0);
  return numeric.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPercent(value) {
  return `${formatDecimal(value, 2)}%`;
}

function formatConfidence(value) {
  const numeric = Number(value || 0);
  const percent = numeric <= 1 ? numeric * 100 : numeric;
  return `${formatDecimal(percent, 1)}%`;
}

function formatLatency(ms) {
  const numeric = Number(ms || 0);
  if (numeric >= 1000) {
    return `${formatDecimal(numeric / 1000, 2)}s`;
  }
  return `${formatDecimal(numeric, 0)}ms`;
}

function formatDate(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function emptyMarkup(message) {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}

function barMarkup(value, maxValue = 100, kind = "") {
  const numeric = Math.max(0, Number(value || 0));
  const max = Math.max(1, Number(maxValue || 100));
  const width = Math.min(100, (numeric / max) * 100);
  const className = kind ? `bar-fill ${kind}` : "bar-fill";
  return `
    <div class="bar-track">
      <div class="${className}" style="width: ${width}%"></div>
    </div>
  `;
}

function renderOverview(overview) {
  setText("total-runs", formatNumber(overview.total_benchmark_runs));
  setText("total-workflows", formatNumber(overview.total_workflows));
  setText("success-rate", formatPercent(overview.success_rate));
  setText("failure-rate", formatPercent(overview.failure_rate));
  setText("reliability-score", formatDecimal(overview.reliability_score, 2));
  setText("last-updated", `Last updated: ${formatDate(overview.last_updated)}`);
}

function renderModelLeaderboard(models) {
  const table = byId("model-table");
  if (!models.length) {
    table.innerHTML = `<tr><td colspan="6">No model benchmark rows found.</td></tr>`;
    return;
  }

  table.innerHTML = models.map((model) => `
    <tr>
      <td>${formatNumber(model.rank)}</td>
      <td class="model-name">${escapeHtml(model.model)}</td>
      <td><span class="score-chip">${formatDecimal(model.reliability_score_v2, 2)}</span></td>
      <td>${formatPercent(model.success_rate)}</td>
      <td>${formatLatency(model.average_execution_time_ms)}</td>
      <td>${formatConfidence(model.average_confidence)}</td>
    </tr>
  `).join("");
}

function renderToolReliability(tools) {
  const grid = byId("tool-grid");
  if (!tools.length) {
    grid.innerHTML = emptyMarkup("No tool reliability rows found.");
    return;
  }

  grid.innerHTML = tools.map((tool) => `
    <article class="tool-card">
      <header>
        <span class="tool-name">${escapeHtml(tool.tool_name)}</span>
        <span class="score-chip">${formatDecimal(tool.reliability_score, 2)}</span>
      </header>
      <div class="mini-stats">
        <div><span>Success</span><strong>${formatPercent(tool.success_rate)}</strong></div>
        <div><span>Failure</span><strong>${formatPercent(tool.failure_rate)}</strong></div>
        <div><span>Latency</span><strong>${formatLatency(tool.average_latency_ms)}</strong></div>
        <div><span>Timeout</span><strong>${formatPercent(tool.timeout_rate)}</strong></div>
      </div>
    </article>
  `).join("");
}

function renderWorkflowAnalytics(workflow) {
  const stages = workflow.stage_summary || [];
  setText(
    "workflow-summary",
    `${formatNumber(workflow.successful_workflows)} of ${formatNumber(workflow.total_workflows)} workflows completed`
  );

  const failureList = byId("stage-failures");
  const latencyList = byId("stage-latency");
  if (!stages.length) {
    failureList.innerHTML = emptyMarkup("No stage failure metrics found.");
    latencyList.innerHTML = emptyMarkup("No stage latency metrics found.");
  } else {
    failureList.innerHTML = stages.map((stage) => `
      <div class="bar-row">
        <div class="bar-label">
          <strong>${escapeHtml(stage.stage)}</strong>
          <span>${formatPercent(stage.failure_rate)} failures</span>
        </div>
        ${barMarkup(stage.failure_rate, 100, stage.failure_rate > 0 ? "danger" : "")}
      </div>
    `).join("");

    const maxLatency = Math.max(...stages.map((stage) => Number(stage.average_latency_ms || 0)), 1);
    latencyList.innerHTML = stages.map((stage) => `
      <div class="bar-row">
        <div class="bar-label">
          <strong>${escapeHtml(stage.stage)}</strong>
          <span>${formatLatency(stage.average_latency_ms)}</span>
        </div>
        ${barMarkup(stage.average_latency_ms, maxLatency, "warning")}
      </div>
    `).join("");
  }

  const dropList = byId("confidence-drops");
  const drops = workflow.confidence_drops || [];
  if (!drops.length) {
    dropList.innerHTML = emptyMarkup("No confidence drops found.");
    return;
  }

  dropList.innerHTML = drops.map((drop) => {
    const value = Number(drop.drop || 0);
    const sign = value > 0 ? "-" : "+";
    const display = `${sign}${formatDecimal(Math.abs(value) * 100, 1)} pts`;
    return `
      <div class="drop-row">
        <span class="drop-route">${escapeHtml(drop.from_stage)} to ${escapeHtml(drop.to_stage)}</span>
        <span class="drop-value">${display}</span>
      </div>
    `;
  }).join("");
}

function renderPredictionAnalytics(prediction) {
  setText("prediction-accuracy", formatPercent(prediction.accuracy));
  setText("prediction-precision", formatPercent(prediction.precision));
  setText("prediction-recall", formatPercent(prediction.recall));
  setText("prediction-fp", formatNumber(prediction.false_positives));
  setText("prediction-fn", formatNumber(prediction.false_negatives));
}

function renderGuardrailAnalytics(guardrails) {
  setText("guardrail-interventions", formatNumber(guardrails.interventions));
  setText("guardrail-prevented", formatNumber(guardrails.prevented_failures));
  setText("guardrail-recovery", formatPercent(guardrails.recovery_success_rate));
  setText("guardrail-latency", formatLatency(guardrails.recovery_latency_ms));
}

function renderHistoricalTrends(trends) {
  const list = byId("trend-list");
  if (!trends.length) {
    list.innerHTML = emptyMarkup("No historical trend rows found.");
    return;
  }

  list.innerHTML = trends.map((trend) => `
    <div class="trend-row">
      <div class="trend-label">
        <strong>${escapeHtml(trend.label)}</strong>
        <span>${formatDate(trend.created_at)}</span>
      </div>
      <div class="bar-label">
        <span>Reliability ${formatDecimal(trend.reliability_score, 2)}</span>
        <span>Success ${formatPercent(trend.success_rate)} | Failure ${formatPercent(trend.failure_rate)}</span>
      </div>
      ${barMarkup(trend.reliability_score, 100)}
    </div>
  `).join("");
}

function renderSdkWorkflows(sdk) {
  setText("sdk-total", formatNumber(sdk.total_workflows));
  setText("sdk-success", formatPercent(sdk.success_rate));
  setText("sdk-latency", formatLatency(sdk.average_latency_ms));

  const table = byId("sdk-workflow-table");
  const workflows = sdk.recent_workflows || [];
  if (!workflows.length) {
    table.innerHTML = `<tr><td colspan="7">No SDK-submitted workflows yet.</td></tr>`;
    return;
  }

  table.innerHTML = workflows.map((workflow) => {
    const success = workflow.success === 1 ? "Yes" : workflow.success === 0 ? "No" : "--";
    const risk = workflow.predicted_failure_probability === null || workflow.predicted_failure_probability === undefined
      ? "--"
      : formatPercent(Number(workflow.predicted_failure_probability) * 100);
    return `
      <tr>
        <td class="model-name">${escapeHtml(workflow.project_name)}</td>
        <td>${escapeHtml(workflow.workflow_name)}</td>
        <td>${escapeHtml(workflow.status)}</td>
        <td>${success}</td>
        <td>${risk}</td>
        <td>${escapeHtml(workflow.guardrail_action || "--")}</td>
        <td>${formatLatency(workflow.total_latency_ms)}</td>
      </tr>
    `;
  }).join("");
}

async function loadDashboard() {
  try {
    const response = await fetch("/api/dashboard", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }
    const payload = await response.json();
    renderOverview(payload.overview || {});
    renderModelLeaderboard(payload.model_leaderboard || []);
    renderToolReliability(payload.tool_reliability || []);
    renderWorkflowAnalytics(payload.workflow_analytics || {});
    renderPredictionAnalytics(payload.prediction_analytics || {});
    renderGuardrailAnalytics(payload.guardrail_analytics || {});
    renderHistoricalTrends(payload.historical_trends || []);
    renderSdkWorkflows(payload.sdk_workflows || {});
    statusEl.textContent = "Reliability data loaded";
    statusEl.classList.remove("error");
  } catch (error) {
    statusEl.textContent = `Dashboard error: ${error.message}`;
    statusEl.classList.add("error");
  }
}

loadDashboard();
