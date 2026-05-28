# Deploy Nexora on Hugging Face Spaces

Hugging Face Spaces can host Nexora as a free Docker Space on CPU Basic hardware. Do not upgrade the Space hardware if you want zero payment.

This gives you a public HTTPS URL like:

```text
https://huggingface.co/spaces/YOUR_USERNAME/nexora-ai
```

The direct app URL usually becomes:

```text
https://YOUR_USERNAME-nexora-ai.hf.space
```

## What is already configured

- `Dockerfile` runs the FastAPI app on port `7860`.
- `README.md` includes Hugging Face Space metadata:

```yaml
sdk: docker
app_port: 7860
```

## Deploy from this computer

1. Log in to Hugging Face.
2. Create a token with write access.
3. Save the token to:

```text
C:\Users\user\Desktop\hf_token.txt
```

4. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_huggingface.ps1
```

The script creates or updates the public Space and uploads this project directly.

## Notes

- Keep hardware on **CPU Basic**. GPU and CPU Upgrade hardware are paid.
- Free CPU Spaces may sleep when unused and wake up on the next visit.
- Pollinations and web search work without paid API keys.
- Local JSON memory is stored inside the running Space. For permanent multi-user storage, connect external storage later.
