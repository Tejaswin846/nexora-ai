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

Nexora uses Supabase Auth for signup, login, logout, email verification, and password recovery. Configure the backend with the base Supabase project URL only:

```text
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-public-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-backend-service-role-key
NEXORA_PUBLIC_APP_URL=https://your-public-app-url
```

Do not include `/rest/v1/` in `SUPABASE_URL`. The anon key is safe for browser auth flows; the service role key is backend-only and must never be exposed to frontend code.

Password reset uses Supabase recovery email delivery. `/auth/forgot-password` sends the recovery email, the recovery link opens `/reset-password`, and the browser calls Supabase `updateUser` with the recovery session to set the new password. If Supabase or SMTP rejects the email request, the API returns an honest error instead of showing fake success.

User data is resolved from the bearer token when a user is signed in. Projects, workflows, memory, sessions, settings, and stored provider API keys are scoped to that authenticated user; caller-supplied `user_id` values cannot override the token identity. If app data is moved into Supabase tables, apply the example policies in `backend/supabase_rls.sql`.

## SDK Access

Installing the SDK is public and does not require signing in:

```powershell
pip install -e .
```

SDK package installation and documentation are public. Protected cloud API calls still require an API key or an authenticated session when the endpoint is not public.
