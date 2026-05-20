# Deploy Nexora as a Public Website

Nexora is now configured as one public web app:

- `/` opens the Nexora website.
- `/chat`, `/upload`, `/image`, `/search`, and the other API routes run from the same domain.
- The frontend automatically uses the public domain when hosted, and still uses `http://127.0.0.1:8000` when opened as a local file.

## Fastest public deploy: Render

1. Push this project to a GitHub repository.
2. Open Render and choose **New +** -> **Blueprint**.
3. Connect the repository.
4. Render will read `render.yaml`.
5. Deploy.

After deployment, Render gives a public URL like:

```text
https://nexora-ai.onrender.com
```

That URL is the website everyone can open.

## Manual Render setup

If you do not use Blueprint:

```text
Build command:
pip install -r backend/requirements.txt

Start command:
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT

Health check:
/health
```

## Docker deploy

Any Docker host can run:

```powershell
docker build -t nexora-ai .
docker run -p 8000:8000 nexora-ai
```

Then open:

```text
http://localhost:8000
```

## Notes

- Pollinations and web search work without paid API keys.
- Ollama only works on the public server if that server also has Ollama installed and reachable.
- The current JSON memory storage is local to the running server. For a serious multi-user public app, connect persistent disk or a database later.
