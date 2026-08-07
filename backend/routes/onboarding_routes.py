from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

try:
    import ai_observability_store
    import customer_dashboard_store
    import onboarding_store
    import posthog_client
except Exception:  # pragma: no cover - package import fallback
    from .. import ai_observability_store
    from .. import customer_dashboard_store
    from .. import onboarding_store
    from .. import posthog_client


router = APIRouter(tags=["onboarding"])


class OnboardingGenerateKeyRequest(BaseModel):
    framework: str = Field("JavaScript", max_length=80)
    name: str = Field("Onboarding key", max_length=80)
    onboarding_id: str = Field("", max_length=120)


class OnboardingTestEventRequest(BaseModel):
    framework: str = Field("JavaScript", max_length=80)
    api_key: str = Field(..., min_length=8, max_length=240)
    onboarding_id: str = Field("", max_length=120)
    project_id: str = Field("onboarding", max_length=120)


def public_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def onboarding_id_from_request(request: Request, supplied: str = "") -> str:
    return onboarding_store.clean_id(
        supplied
        or request.headers.get("x-onboarding-id", "")
        or request.headers.get("x-session-id", "")
        or "anonymous"
    )


def capture_onboarding_event(
    request: Request,
    event: str,
    *,
    onboarding_id: str = "",
    properties: dict[str, Any] | None = None,
) -> None:
    resolved_id = onboarding_id_from_request(request, onboarding_id)
    posthog_client.capture(
        distinct_id=resolved_id,
        event=event,
        properties={
            "onboarding_id": resolved_id,
            "path": request.url.path,
            **(properties or {}),
        },
    )


def framework_specs(base_url: str) -> list[dict[str, str]]:
    env = f"SOFTWARE_ENDPOINT={base_url}\nSOFTWARE_API_KEY=your_api_key_here"
    return [
        {
            "id": "javascript",
            "name": "JavaScript",
            "install_command": "# Node 18+ includes fetch; no package install required",
            "env": env,
            "sample_code": f"""const endpoint = process.env.SOFTWARE_ENDPOINT || "{base_url}";
const apiKey = process.env.SOFTWARE_API_KEY;

await fetch(`${{endpoint}}/api/events/ingest`, {{
  method: "POST",
  headers: {{
    "Content-Type": "application/json",
    "Authorization": `Bearer ${{apiKey}}`
  }},
  body: JSON.stringify({{
    project_id: "onboarding",
    event_type: "agent_run",
    message: "JavaScript agent replied",
    provider: "openai",
    model: "gpt-4.1",
    latency_ms: 920,
    prompt_tokens: 120,
    completion_tokens: 220,
    success: true
  }})
}});""",
        },
        {
            "id": "python",
            "name": "Python",
            "install_command": "pip install requests",
            "env": env,
            "sample_code": f"""import os
import requests

endpoint = os.getenv("SOFTWARE_ENDPOINT", "{base_url}")
api_key = os.environ["SOFTWARE_API_KEY"]

response = requests.post(
    f"{{endpoint}}/api/events/ingest",
    headers={{"Authorization": f"Bearer {{api_key}}"}},
    json={{
        "project_id": "onboarding",
        "event_type": "agent_run",
        "message": "Python agent replied",
        "provider": "openai",
        "model": "gpt-4.1",
        "latency_ms": 980,
        "prompt_tokens": 140,
        "completion_tokens": 260,
        "success": True,
    }},
    timeout=10,
)
response.raise_for_status()""",
        },
        {
            "id": "fastapi",
            "name": "FastAPI",
            "install_command": "pip install fastapi uvicorn requests",
            "env": env,
            "sample_code": f"""import os
import requests
from fastapi import FastAPI

app = FastAPI()
endpoint = os.getenv("SOFTWARE_ENDPOINT", "{base_url}")
api_key = os.environ["SOFTWARE_API_KEY"]

@app.post("/run-agent")
def run_agent():
    result = {{"answer": "FastAPI agent replied"}}
    requests.post(
        f"{{endpoint}}/api/events/ingest",
        headers={{"Authorization": f"Bearer {{api_key}}"}},
        json={{
            "project_id": "onboarding",
            "event_type": "agent_run",
            "message": result["answer"],
            "provider": "openai",
            "model": "gpt-4.1",
            "latency_ms": 1040,
            "prompt_tokens": 160,
            "completion_tokens": 300,
            "success": True,
        }},
        timeout=10,
    )
    return result""",
        },
        {
            "id": "express",
            "name": "Express",
            "install_command": "npm install express",
            "env": env,
            "sample_code": f"""import express from "express";

const app = express();
app.use(express.json());

const endpoint = process.env.SOFTWARE_ENDPOINT || "{base_url}";
const apiKey = process.env.SOFTWARE_API_KEY;

app.post("/run-agent", async (_req, res) => {{
  const result = {{ answer: "Express agent replied" }};
  await fetch(`${{endpoint}}/api/events/ingest`, {{
    method: "POST",
    headers: {{
      "Content-Type": "application/json",
      "Authorization": `Bearer ${{apiKey}}`
    }},
    body: JSON.stringify({{
      project_id: "onboarding",
      event_type: "agent_run",
      message: result.answer,
      provider: "openai",
      model: "gpt-4.1",
      latency_ms: 890,
      prompt_tokens: 110,
      completion_tokens: 210,
      success: true
    }})
  }});
  res.json(result);
}});

app.listen(3000);""",
        },
        {
            "id": "nextjs",
            "name": "Next.js",
            "install_command": "npx create-next-app@latest my-agent-app",
            "env": env,
            "sample_code": f"""export async function POST() {{
  const endpoint = process.env.SOFTWARE_ENDPOINT || "{base_url}";
  const apiKey = process.env.SOFTWARE_API_KEY;
  const result = {{ answer: "Next.js agent replied" }};

  await fetch(`${{endpoint}}/api/events/ingest`, {{
    method: "POST",
    headers: {{
      "Content-Type": "application/json",
      "Authorization": `Bearer ${{apiKey}}`
    }},
    body: JSON.stringify({{
      project_id: "onboarding",
      event_type: "agent_run",
      message: result.answer,
      provider: "openai",
      model: "gpt-4.1",
      latency_ms: 940,
      prompt_tokens: 130,
      completion_tokens: 240,
      success: true
    }})
  }});

  return Response.json(result);
}}""",
        },
    ]


def framework_by_name(name: str, base_url: str) -> dict[str, str]:
    normalized = str(name or "").strip().lower().replace(".", "").replace(" ", "")
    for item in framework_specs(base_url):
        if normalized in {item["id"], item["name"].lower().replace(".", "").replace(" ", "")}:
            return item
    raise HTTPException(status_code=400, detail="Choose JavaScript, Python, FastAPI, Express, or Next.js.")


def authenticate_any_onboarding_key(api_key: str) -> dict[str, Any] | None:
    record = onboarding_store.authenticate_api_key(api_key)
    if record:
        record["source"] = "onboarding"
        return record
    try:
        customer_record = customer_dashboard_store.authenticate_api_key(api_key)
    except Exception:
        customer_record = None
    if customer_record:
        return {
            "id": customer_record.get("id", ""),
            "user_id": customer_record.get("user_id", ""),
            "onboarding_id": "",
            "framework": "",
            "key_prefix": customer_record.get("key_prefix", ""),
            "source": "dashboard",
        }
    return None


@router.get("/api/onboarding/frameworks")
def get_onboarding_frameworks(request: Request) -> dict[str, Any]:
    frameworks = framework_specs(public_base_url(request))
    capture_onboarding_event(
        request,
        "onboarding_started",
        properties={"framework_count": len(frameworks)},
    )
    return {"ok": True, "frameworks": frameworks}


@router.post("/api/onboarding/generate-key")
def generate_onboarding_key(req: OnboardingGenerateKeyRequest, request: Request) -> dict[str, Any]:
    framework = framework_by_name(req.framework, public_base_url(request))
    onboarding_id = onboarding_id_from_request(request, req.onboarding_id)
    capture_onboarding_event(
        request,
        "framework_selected",
        onboarding_id=onboarding_id,
        properties={"framework": framework["name"]},
    )
    created = onboarding_store.create_api_key(onboarding_id, framework["name"], req.name)
    capture_onboarding_event(
        request,
        "api_key_generated",
        onboarding_id=onboarding_id,
        properties={
            "framework": framework["name"],
            "key_id": created["record"].get("id", ""),
            "key_prefix": created["record"].get("key_prefix", ""),
        },
    )
    return {
        "ok": True,
        "api_key": created["api_key"],
        "record": created["record"],
        "onboarding_id": created["onboarding_id"],
        "message": "API key generated. The full key is shown once.",
    }


@router.post("/api/onboarding/test-event")
def send_onboarding_test_event(req: OnboardingTestEventRequest, request: Request) -> dict[str, Any]:
    framework = framework_by_name(req.framework, public_base_url(request))
    onboarding_id = onboarding_id_from_request(request, req.onboarding_id)
    key_record = authenticate_any_onboarding_key(req.api_key)
    if not key_record:
        onboarding_store.mark_test_result(
            onboarding_id,
            framework=framework["name"],
            key_id="",
            verified=False,
            error="Invalid API key.",
        )
        capture_onboarding_event(
            request,
            "onboarding_failed",
            onboarding_id=onboarding_id,
            properties={"framework": framework["name"], "reason": "invalid_api_key"},
        )
        raise HTTPException(status_code=401, detail="Invalid API key. Generate a key or paste an active dashboard key.")

    trace_id = f"trace_onboarding_{uuid.uuid4().hex[:12]}"
    session_id = f"session_onboarding_{uuid.uuid4().hex[:10]}"
    event = ai_observability_store.record_ai_request(
        distinct_id=str(key_record.get("user_id") or f"onboarding:{onboarding_id}"),
        trace_id=trace_id,
        model=f"{framework['name']} sample",
        provider="onboarding",
        input_tokens=64,
        output_tokens=128,
        latency_ms=420,
        error=None,
        session_id=session_id,
        metadata={
            "user_id": str(key_record.get("user_id") or f"onboarding:{onboarding_id}"),
            "onboarding_id": onboarding_id,
            "project_id": req.project_id or "onboarding",
            "event_type": "onboarding_test",
            "framework": framework["name"],
            "api_key_id": key_record.get("id", ""),
            "api_key_source": key_record.get("source", "onboarding"),
        },
    )
    status = onboarding_store.mark_test_result(
        onboarding_id,
        framework=framework["name"],
        key_id=str(key_record.get("id", "")),
        event_id=str(event.get("id", "")),
        verified=True,
    )
    capture_onboarding_event(
        request,
        "test_event_sent",
        onboarding_id=onboarding_id,
        properties={"framework": framework["name"], "event_id": event.get("id", "")},
    )
    capture_onboarding_event(
        request,
        "onboarding_completed",
        onboarding_id=onboarding_id,
        properties={"framework": framework["name"], "event_id": event.get("id", "")},
    )
    return {
        "ok": True,
        "verified": True,
        "event": {
            "id": event.get("id", ""),
            "trace_id": event.get("trace_id", ""),
            "session_id": event.get("session_id", ""),
            "created_at": event.get("created_at", ""),
        },
        "status": status,
    }


@router.get("/api/onboarding/status")
def onboarding_status(request: Request, onboarding_id: str = "") -> dict[str, Any]:
    resolved_id = onboarding_id_from_request(request, onboarding_id)
    return {"ok": True, "status": onboarding_store.status_for(resolved_id)}
