# Software Reliability Engine

Project name: Software

Mission: solve the reliability problem of AI agents.

Core problem: AI agents perform well in simulations but often fail in real-world execution because of tool failures, timeouts, planning errors, context loss, and execution breakdowns.

Objective: build a system that measures, predicts, and improves AI-agent reliability.

## Phase 1 Scope

Phase 1 is the Reliability Engine. It does not add AI assistant features. It only measures and scores AI-agent workflow reliability.

The engine receives benchmark runs, workflow events, agent events, tool calls, recovery attempts, and real-world execution results. It converts them into a single Reliability Score from 0 to 100 and stores history for trend analysis.

## Architecture

```text
AI Agents / Simulations / Real Workflows
        |
        v
Telemetry Collector API
        |
        v
Event Normalizer
        |
        v
Benchmark Run Store
        |
        +-------------------+
        |                   |
        v                   v
Reliability Scoring   Failure Classifier
        |                   |
        +---------+---------+
                  |
                  v
Reliability Snapshot Store
                  |
                  v
Dashboard API
                  |
                  v
Reliability Dashboard
```

## Core Modules

### 1. Telemetry Collector

Accepts raw events from simulations, real-agent experiments, workflow runners, agent wrappers, and tool providers.

Input examples:

- workflow started
- agent completed
- tool call succeeded
- tool call failed
- retry started
- rollback started
- escalation created
- workflow completed

### 2. Event Normalizer

Converts raw events into a consistent internal format.

Normalized fields:

- run_id
- workflow_id
- agent_id
- model_id
- provider
- provider_url
- environment: simulation or real_world
- event_type
- status
- confidence
- execution_time_ms
- failure_category
- recovery_action
- created_at

### 3. Failure Classifier

Classifies failure events into stable categories.

Failure categories:

- tool_failure
- provider_timeout
- model_load_timeout
- planning_error
- context_loss
- workflow_logic_failure
- parsing_failure
- memory_failure
- policy_violation
- unknown

### 4. Reliability Scoring Engine

Computes the 10 reliability metrics and final score.

Metrics:

1. Success Rate
2. Failure Rate
3. Recovery Rate
4. Retry Success Rate
5. Tool Reliability
6. Timeout Rate
7. Confidence Accuracy
8. Average Execution Time
9. Escalation Rate
10. Workflow Completion Rate

### 5. Benchmark History Store

Stores every benchmark run, every workflow result, every agent result, and every computed score.

Supports:

- compare models
- compare agents
- compare simulation vs real-world performance
- track performance over time
- detect reliability regressions

### 6. Dashboard API

Provides scorecards, trend lines, comparison tables, and failure breakdowns.

Dashboard fields:

- Reliability Score
- Success Rate
- Failure Rate
- Timeout Rate
- Tool Reliability
- Average Execution Time
- Simulation Gap
- Historical Trends

## Reliability Score Bands

| Score | Band | Meaning |
|---:|---|---|
| 90-100 | Production Ready | Safe for high-volume production use with monitoring |
| 80-89 | Stable | Reliable enough for controlled production or pilot customers |
| 60-79 | Experimental | Useful for testing, not yet trusted for critical workflows |
| 0-59 | Unreliable | Needs reliability work before real deployment |

## External AI Tester Mode

Public tester mode is available at:

```text
/ai-tester
```

It lets external AI systems such as ChatGPT, Claude, Gemini, Perplexity, and
Antigravity run a sandboxed reliability suite against Software without live side
effects. The mode includes 12 scenario categories, dry-run Gmail/Calendar/GitHub
tool checks, database/delete blocks, prompt-injection and hallucination traps,
copyable external-AI prompts, scoreboards, and public reports.

Runner endpoints:

```http
GET /api/external-test/scenarios
POST /api/external-test/run
GET /api/external-test/results/{run_id}
GET /external-test/report/{run_id}
```

See [EXTERNAL_AI_TESTER.md](EXTERNAL_AI_TESTER.md) for sandbox limits, adapter
behavior, payload examples, and report contents.

## Public SDK Access

The SDK page is public:

```text
/sdk
```

Install commands, docs, examples, and downloads are not behind login:

```bash
pip install software-sdk
npm install software-sdk
```

Local mode needs no account and supports local validation, local plans, dry-run
examples, and sandbox workflow tests. Authenticated cloud mode starts only when
using protected cloud workflow execution, saved projects, user memory, audit
logs, integrations, or team/workspace features.

Optional cloud auth:

```bash
software login
# or
SOFTWARE_API_KEY=...
```

## Authentication Provider

Software uses Clerk for dashboard and cloud-workspace authentication. Clerk
handles signup, login, logout, password reset, email verification, Google OAuth,
GitHub OAuth, and JWT/session validation. Supabase remains a database/storage
layer for mirrored user profiles and per-user records; stored records use the
Clerk `user_id`.

## Scoring Formula

All component metrics are normalized to 0-100.

```text
Reliability Score =
  Success Rate Score        * 0.20
+ Failure Rate Score        * 0.10
+ Recovery Rate Score       * 0.12
+ Retry Success Score       * 0.08
+ Tool Reliability Score    * 0.12
+ Timeout Score             * 0.10
+ Confidence Accuracy Score * 0.08
+ Execution Time Score      * 0.08
+ Escalation Score          * 0.05
+ Completion Rate Score     * 0.07
```

Weights total 1.00.

## Metric Definitions

### Success Rate

```text
successful_workflows / total_workflows * 100
```

### Failure Rate Score

Failure rate is inverted because lower is better.

```text
100 - (failed_workflows / total_workflows * 100)
```

### Recovery Rate

```text
successfully_recovered_workflows / workflows_with_failures * 100
```

If no failures occurred, recovery rate is 100.

### Retry Success Rate

```text
successful_retries / total_retries * 100
```

If no retries occurred, retry success is 100 only if the overall run succeeded. Otherwise it is 0.

### Tool Reliability

```text
successful_tool_calls / total_tool_calls * 100
```

If no tool calls occurred, this metric is excluded from model comparison and set to 100 for non-tool workflows.

### Timeout Score

Timeout rate is inverted.

```text
100 - (timeout_events / total_events * 100)
```

### Confidence Accuracy

Measures whether confidence scores predict real outcomes.

```text
1 - average(abs(confidence - actual_success))
```

Where:

- confidence is 0.0 to 1.0
- actual_success is 1.0 for success, 0.0 for failure

Normalized:

```text
(1 - average_error) * 100
```

### Execution Time Score

Compares average execution time to the target service level objective.

```text
score = max(0, 100 - ((avg_execution_time_ms - target_ms) / target_ms * 100))
```

If average execution time is below target, score is 100.

Default target:

```text
target_ms = 10000
```

### Escalation Score

Escalation rate is inverted.

```text
100 - (escalations / total_workflows * 100)
```

Escalations are not always bad, but high escalation rates show low autonomy.

### Workflow Completion Rate

```text
completed_workflows / started_workflows * 100
```

## Simulation Gap

Simulation Gap measures the difference between simulation success and real-world success.

```text
simulation_gap = simulation_success_rate - real_world_success_rate
```

Interpretation:

- 0-5 percentage points: strong real-world transfer
- 5-15 percentage points: acceptable but needs investigation
- 15+ percentage points: simulation is not predictive enough

## Database Schema

See [schema.sql](schema.sql).

## API Routes

See [api_routes.md](api_routes.md).

## Dashboard Requirements

### Main Scorecard

Shows:

- Reliability Score
- Reliability Band
- Success Rate
- Failure Rate
- Recovery Rate
- Timeout Rate
- Tool Reliability
- Simulation Gap

### Benchmark History

Shows:

- score over time
- success rate over time
- timeout rate over time
- average execution time over time
- model comparison
- agent comparison

### Failure Breakdown

Shows:

- top failure categories
- top failing tools
- timeout-heavy models
- workflow stages with highest failure rate
- escalation-heavy workflows

### Model Comparison

Compares:

- model name
- provider
- reliability score
- success rate
- timeout rate
- execution time
- confidence accuracy
- cost per successful workflow, when cost is available

### Agent Comparison

Compares:

- agent name
- role
- reliability score
- failure rate
- retry success rate
- average confidence
- average execution time

## Implementation Plan

### Step 1: Data Contracts

Define stable event schemas:

- BenchmarkRun
- WorkflowRun
- AgentRun
- ToolCall
- RecoveryAttempt
- ReliabilitySnapshot

### Step 2: Storage

Implement database tables from [schema.sql](schema.sql).

Recommended first database:

```text
SQLite for local benchmark development.
PostgreSQL for production.
```

### Step 3: Event Ingestion API

Create API routes for:

- create benchmark run
- log workflow result
- log agent event
- log tool call
- log recovery attempt
- finalize benchmark run

### Step 4: Scoring Engine

Implement deterministic scoring first.

Inputs:

- benchmark_run_id
- environment
- model_id
- agent_id
- time window

Output:

- 10 normalized metrics
- final Reliability Score
- reliability band
- simulation gap

### Step 5: Historical Comparison

Support comparisons:

- model vs model
- agent vs agent
- simulation vs real-world
- current run vs previous run
- 7-day and 30-day trends

### Step 6: Dashboard API

Expose:

- current scorecard
- trend data
- comparison tables
- failure breakdowns

### Step 7: Regression Alerts

Add alert rules:

- reliability score drops by more than 5 points
- timeout rate doubles
- tool reliability drops below 95%
- simulation gap exceeds 15 percentage points
- escalation rate exceeds configured threshold

## Phase 1 Deliverables

- Reliability scoring framework
- Benchmark history storage
- Model comparison
- Agent comparison
- Simulation vs real-world comparison
- Historical trends
- Dashboard API contract
- Deterministic score formula

## What Phase 1 Does Not Build

- New AI assistant features
- New agent behaviors
- Automatic prompt improvement
- Autonomous workflow optimization
- Human approval workflows

Phase 1 is only about measuring and proving reliability.
