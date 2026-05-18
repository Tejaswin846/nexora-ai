# Nexora AI

Nexora is a personal AI assistant with an adaptive persona, memory-backed style control, and a lightweight performance profile tuned for this laptop.

## Website

The GitHub Pages website is served from:

```text
docs/index.html
```

After publishing to GitHub Pages, the public URL will look like:

```text
https://YOUR_GITHUB_USERNAME.github.io/nexora-ai/
```

## Local Backend

Run the backend from `backend/`:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Then open the website. The frontend talks to:

```text
http://127.0.0.1:8000
```

