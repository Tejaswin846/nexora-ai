# Software Reliability Engine API Routes

Base path:

```text
/v1/reliability
```

## External AI Tester Mode

Public tester page:

```http
GET /ai-tester
```

Scenario catalog:

```http
GET /api/external-test/scenarios
```

Run sandbox suite:

```http
POST /api/external-test/run
```

Request:

```json
{
  "tester_name": "ChatGPT",
  "tester_model": "external-ai",
  "public_url": "https://example.com",
  "scenario_ids": ["memory", "gmail_dry_run"],
  "observations": []
}
```

Results and public report:

```http
GET /api/external-test/results/{run_id}
GET /external-test/report/{run_id}
```

Tester mode is always sandboxed: no real emails, no real calendar events, no
database deletion, no paid API actions, dry-run for risky actions, and
confirmation cards for high-risk actions.

## Health

```http
GET /v1/reliability/health
```

Response:

```json
{
  "ok": true,
  "service": "software-reliability-engine",
  "version": "0.1.0"
}
```

## Register Model

```http
POST /v1/reliability/models
```

Request:

```json
{
  "id": "model_gemma3_12b",
  "provider": "ollama",
  "provider_url": "http://127.0.0.1:11434",
  "model_name": "gemma3:12b",
  "model_version": "local"
}
```

## Register Agent

```http
POST /v1/reliability/agents
```

Request:

```json
{
  "id": "agent_research",
  "agent_name": "ResearchAgent",
  "agent_role": "research",
  "owner_team": "AI Reliability"
}
```

## Register Workflow

```http
POST /v1/reliability/workflows
```

Request:

```json
{
  "id": "workflow_research_code_test",
  "workflow_name": "Research -> Code -> Test",
  "workflow_version": "v1",
  "description": "Three-agent reliability benchmark workflow"
}
```

## Create Benchmark Run

```http
POST /v1/reliability/benchmark-runs
```

Request:

```json
{
  "id": "bench_2026_06_19_real_gemma3",
  "benchmark_name": "Real Agent Experiment V1",
  "environment": "real_world",
  "model_id": "model_gemma3_12b",
  "workflow_id": "workflow_research_code_test",
  "started_at": "2026-06-19T17:00:00+05:30",
  "metadata": {
    "random_seed": 20260617,
    "total_requested_workflows": 100
  }
}
```

## Log Workflow Run

```http
POST /v1/reliability/workflow-runs
```

Request:

```json
{
  "id": "workflow_run_0001",
  "benchmark_run_id": "bench_2026_06_19_real_gemma3",
  "workflow_id": "workflow_research_code_test",
  "environment": "real_world",
  "status": "completed",
  "successful": true,
  "execution_time_ms": 9999,
  "confidence": 0.93,
  "failure_category": null,
  "failure_reason": null
}
```

## Log Agent Run

```http
POST /v1/reliability/agent-runs
```

Request:

```json
{
  "id": "agent_run_0001_research",
  "workflow_run_id": "workflow_run_0001",
  "benchmark_run_id": "bench_2026_06_19_real_gemma3",
  "agent_id": "agent_research",
  "model_id": "model_gemma3_12b",
  "agent_name": "ResearchAgent",
  "step_index": 1,
  "status": "completed",
  "successful": true,
  "confidence": 0.94,
  "execution_time_ms": 8500,
  "retry_count": 0,
  "timeout_detected": false,
  "tool_failure_detected": false
}
```

## Log Tool Call

```http
POST /v1/reliability/tool-calls
```

Request:

```json
{
  "id": "tool_call_0001",
  "agent_run_id": "agent_run_0001_research",
  "workflow_run_id": "workflow_run_0001",
  "benchmark_run_id": "bench_2026_06_19_real_gemma3",
  "tool_name": "ollama.generate",
  "provider": "ollama",
  "endpoint_url": "http://127.0.0.1:11434/api/generate",
  "status": "success",
  "successful": true,
  "execution_time_ms": 8500,
  "error_message": null
}
```

## Log Recovery Attempt

```http
POST /v1/reliability/recovery-attempts
```

Request:

```json
{
  "id": "recovery_0001",
  "workflow_run_id": "workflow_run_0004",
  "benchmark_run_id": "bench_2026_06_19_real_gemma3",
  "agent_run_id": "agent_run_0004_test",
  "recovery_type": "retry",
  "successful": true,
  "execution_time_ms": 1200,
  "reason": "low_confidence_with_retry_budget"
}
```

## Finalize Benchmark Run

```http
POST /v1/reliability/benchmark-runs/{benchmark_run_id}/finalize
```

Response:

```json
{
  "benchmark_run_id": "bench_2026_06_19_real_gemma3",
  "total_workflows": 100,
  "successful_workflows": 86,
  "failed_workflows": 14,
  "reliability_score": 84.7,
  "reliability_band": "Stable"
}
```

## Get Reliability Scorecard

```http
GET /v1/reliability/scorecard?environment=real_world&model_id=model_gemma3_12b
```

Response:

```json
{
  "reliability_score": 84.7,
  "reliability_band": "Stable",
  "success_rate": 86.0,
  "failure_rate": 14.0,
  "recovery_rate": 71.0,
  "retry_success_rate": 82.0,
  "tool_reliability": 96.0,
  "timeout_rate": 8.0,
  "confidence_accuracy": 91.0,
  "average_execution_time_ms": 9999,
  "escalation_rate": 6.0,
  "workflow_completion_rate": 86.0,
  "simulation_gap": 2.0
}
```

## Compare Models

```http
GET /v1/reliability/compare/models?model_ids=model_gemma3_12b,model_llama3_8b
```

Returns one scorecard per model.

## Compare Agents

```http
GET /v1/reliability/compare/agents?benchmark_run_id=bench_2026_06_19_real_gemma3
```

Returns one scorecard per agent.

## Compare Simulation And Real World

```http
GET /v1/reliability/compare/simulation-gap?workflow_id=workflow_research_code_test&model_id=model_gemma3_12b
```

Response:

```json
{
  "workflow_id": "workflow_research_code_test",
  "model_id": "model_gemma3_12b",
  "simulation_success_rate": 88.0,
  "real_world_success_rate": 86.0,
  "simulation_gap": 2.0,
  "status": "strong_real_world_transfer"
}
```

## Historical Trends

```http
GET /v1/reliability/trends?model_id=model_gemma3_12b&days=30
```

Returns daily or per-run data for:

- reliability_score
- success_rate
- failure_rate
- timeout_rate
- tool_reliability
- average_execution_time_ms
- simulation_gap

## Failure Breakdown

```http
GET /v1/reliability/failures?benchmark_run_id=bench_2026_06_19_real_gemma3
```

Response:

```json
{
  "top_failure_categories": [
    {
      "failure_category": "provider_timeout",
      "count": 8,
      "percentage": 57.14
    },
    {
      "failure_category": "planning_error",
      "count": 4,
      "percentage": 28.57
    }
  ],
  "top_failing_agents": [],
  "top_failing_tools": []
}
```
