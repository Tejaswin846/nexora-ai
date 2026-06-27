"use strict";

const AUTH_REQUIRED_MESSAGE =
  "Authentication required for this cloud feature. You can still install and use the SDK locally without signing in.";

class SoftwareSDK {
  constructor(options = {}) {
    this.projectName = options.projectName || options.project_name || "local-project";
    this.apiUrl = options.apiUrl || options.api_url || "";
    this.apiKey = options.apiKey || options.api_key || process.env.SOFTWARE_API_KEY || "";
    this.mode = options.mode || (this.apiUrl ? "cloud" : "local");
    this.localWorkflows = new Map();
    this.localEvents = [];
  }

  createLocalPlan(goal, steps = [], metadata = {}) {
    const cleanSteps = steps.filter(Boolean).map((step) => String(step).trim()).filter(Boolean);
    const planSteps = cleanSteps.length
      ? cleanSteps
      : [
          "Clarify the workflow goal.",
          "List required inputs and constraints.",
          "Run the workflow in dry-run mode.",
          "Validate expected outputs and failure handling.",
          "Record the local verdict."
        ];
    return {
      ok: true,
      mode: "local",
      requiresAuth: false,
      projectName: this.projectName,
      goal: String(goal || "").trim(),
      steps: planSteps,
      metadata
    };
  }

  validateLocalWorkflow(plan) {
    const steps = Array.isArray(plan && plan.steps) ? plan.steps : [];
    const failures = [];
    if (!steps.length) failures.push("Plan must include at least one step.");
    if (!String((plan && plan.goal) || "").trim()) failures.push("Plan should include a goal.");
    return {
      ok: failures.length === 0,
      mode: "local",
      requiresAuth: false,
      failures,
      stepCount: steps.length
    };
  }

  dryRunWorkflow(workflowName, steps = [], metadata = {}) {
    const workflowId = `local_${Math.random().toString(16).slice(2)}${Date.now().toString(16)}`;
    const plan = this.createLocalPlan(workflowName, steps, metadata);
    const validation = this.validateLocalWorkflow(plan);
    const record = {
      workflowId,
      workflowName,
      status: validation.ok ? "dry_run_completed" : "dry_run_failed",
      plan,
      validation,
      createdAt: new Date().toISOString()
    };
    this.localWorkflows.set(workflowId, record);
    this.localEvents.push({ workflowId, eventType: "dry_run", createdAt: record.createdAt, metadata });
    return {
      ok: validation.ok,
      mode: "local",
      requiresAuth: false,
      workflowId,
      plan,
      validation,
      sideEffects: "none"
    };
  }

  testSandboxWorkflow(workflowName = "sandbox workflow", steps = []) {
    return this.dryRunWorkflow(
      workflowName,
      steps.length ? steps : ["Prepare dry-run inputs.", "Execute simulated tool calls.", "Verify no external side effects."],
      { sandbox: true }
    );
  }

  async startCloudWorkflow(payload) {
    if (!this.apiUrl || !this.apiKey) {
      throw new Error(AUTH_REQUIRED_MESSAGE);
    }
    const response = await fetch(`${this.apiUrl.replace(/\/$/, "")}/api/sdk/workflows/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Software-API-Key": this.apiKey
      },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.message || `Software API returned ${response.status}`);
    }
    return data;
  }
}

module.exports = {
  SoftwareSDK,
  AUTH_REQUIRED_MESSAGE
};
