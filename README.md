---
title: Nexora AI
sdk: docker
app_port: 7860
pinned: false
---

# Nexora AI

Nexora is a full-stack AI assistant website with chat, memory, realtime search, image generation, file/image upload, and a polished web UI.

## Local Website

Run the backend from `backend/`:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

The backend now serves the frontend directly, so you do not need to open `frontend/index.html` manually.

## Independent Public Website

This project is ready for public hosting on Hugging Face Spaces, Railway, Fly.io, Render, or any Docker host.

When deployed, Nexora runs from the host's public URL instead of `localhost`. Your computer does not need to stay on.

For a zero-payment deployment, use Hugging Face Spaces on CPU Basic hardware and do not upgrade the Space hardware.

Recommended Render setup:

```text
Build command:
pip install -r backend/requirements.txt

Start command:
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT

Health check:
/health
```

Or use the included:

- `render.yaml`
- `Procfile`
- `Dockerfile`
- `DEPLOYMENT.md`
- `HUGGINGFACE_DEPLOY.md`

After deployment, the host gives a public URL like:

```text
https://nexora-ai.onrender.com
```

That URL is the website everyone can access.

## .com Domain

After the app is deployed, connect a real `.com` domain from your registrar or DNS provider. The exact records depend on the provider, but the project is ready for a custom domain on the same full-stack service.

See [`DOMAIN_SETUP.md`](DOMAIN_SETUP.md) for the `.com` checklist.

## Authentication

Nexora uses Clerk for signup, login, logout, email verification, Google OAuth, GitHub OAuth, password reset, and JWT/session validation. Supabase is kept as the database/storage layer for profiles and user-owned records.

```text
CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
CLERK_JWT_ISSUER=https://your-clerk-issuer
CLERK_WEBHOOK_SECRET=whsec_...
NEXORA_PUBLIC_APP_URL=https://your-public-app-url
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-backend-service-role-key
```

Never expose `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET`, or `SUPABASE_SERVICE_ROLE_KEY` to frontend code. `CLERK_PUBLISHABLE_KEY` is the only Clerk key sent to the browser.

Do not include `/rest/v1/` in `SUPABASE_URL`. Supabase Auth is not used; Clerk owns password reset, email verification, OAuth, and sessions.

User data is resolved from the Clerk bearer token when a user is signed in. Projects, workflows, memory, sessions, settings, and stored provider API keys are scoped to the Clerk `user_id`; caller-supplied `user_id` values cannot override the token identity. Clerk profiles are mirrored to Supabase storage when configured. If app data is moved into Supabase tables, apply the example policies in `backend/supabase_rls.sql`.

## SDK Access

Installing the SDK is public and does not require signing in:

```powershell
pip install software-sdk
npm install software-sdk
```

SDK package installation, docs, examples, downloads, and install commands are public. Local mode can run validation, create plans, run dry-run examples, and test sandbox workflows without login.

Cloud mode is optional and starts only when protected features are used:

```powershell
software login
# or
$env:SOFTWARE_API_KEY="..."
```

Protected cloud API calls still require an API key or authenticated session for workflow execution, saved projects, user memory, audit logs, external app integrations, and team/workspace features.
