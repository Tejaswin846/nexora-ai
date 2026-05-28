# Deploy Nexora as an Independent Public Website

Nexora is now configured as one public web app:

- `/` opens the Nexora website.
- `/chat`, `/upload`, `/image`, `/search`, and the other API routes run from the same domain.
- The frontend automatically uses the public domain when hosted.
- `localhost` is only for development. The live site runs from the hosting provider and works even when your computer is off.

## Free public deploy: Hugging Face Spaces

This project can run as a free Docker Space on Hugging Face **CPU Basic** hardware. Keep the Space on CPU Basic for zero payment.

1. Log in to Hugging Face.
2. Create a write token.
3. Save it to `C:\Users\user\Desktop\hf_token.txt`.
4. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_huggingface.ps1
```

The script prints the public Space URL and direct app URL.

## Alternative deploy: Render

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

## Connect a .com domain

After Render deploys the app, add your `.com` in the service's **Settings** -> **Custom Domains** area. Then add the DNS records at your domain registrar.

Typical DNS:

```text
www  CNAME  nexora-ai.onrender.com
@    ALIAS  nexora-ai.onrender.com
```

If your provider does not support `ALIAS`, `ANAME`, or CNAME flattening for the root domain, Render supports an `A` record to `216.24.57.1`.

See `DOMAIN_SETUP.md` for the full custom-domain checklist.

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
- JSON memory storage lives in `backend/nexora_data` by default. On a hosted server, set `NEXORA_DATA_DIR` to a mounted disk path or connect a database for persistent multi-user storage.
