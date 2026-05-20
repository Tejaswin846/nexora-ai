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

## Public Website

This project is ready for public hosting on Render, Railway, Fly.io, or any Docker host.

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

After deployment, the host gives a public URL like:

```text
https://nexora-ai.onrender.com
```

That URL is the website everyone can access.
