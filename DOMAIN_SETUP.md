# Connect Nexora to a .com Domain

Nexora is already structured as one independent public web app:

- `/` serves the Nexora chat website.
- `/code` serves the Nexora Code page.
- `/chat`, `/upload`, `/image`, `/search`, and the other API routes run on the same domain.

The project can be deployed first to Render, then connected to a domain such as `yourdomain.com` or `www.yourdomain.com`. After deployment, users open the hosted URL. They do not use `localhost`.

## 1. Deploy the app

1. Push this repository to GitHub.
2. In Render, choose **New +** -> **Blueprint**.
3. Connect the repository.
4. Render reads `render.yaml` and deploys the web service.
5. Confirm the Render URL works, for example:

```text
https://nexora-ai.onrender.com
```

This URL is already independent from your computer. Your `.com` points to this hosted service.

## 2. Add the .com in Render

In the Render service:

1. Open **Settings**.
2. Find **Custom Domains**.
3. Add either:

```text
www.yourdomain.com
```

or:

```text
yourdomain.com
```

Render automatically adds the matching root or `www` version and redirects one to the other.

## 3. Point DNS to Render

At your domain registrar or DNS provider, add records based on your provider:

For `www.yourdomain.com`:

```text
Type:  CNAME
Name:  www
Value: nexora-ai.onrender.com
```

For `yourdomain.com`:

```text
Type:  ALIAS or ANAME
Name:  @
Value: nexora-ai.onrender.com
```

If your DNS provider does not support `ALIAS`, `ANAME`, or CNAME flattening for the root domain, Render also supports this fallback:

```text
Type:  A
Name:  @
Value: 216.24.57.1
```

Remove `AAAA` records while configuring the Render domain.

## 4. Verify and open

1. Go back to Render.
2. Click **Verify** beside the custom domain.
3. Wait for DNS and TLS to finish.
4. Open:

```text
https://www.yourdomain.com
```

or:

```text
https://yourdomain.com
```

## Official References

- Render custom domains: https://render.com/docs/custom-domains
- Render DNS provider setup: https://render.com/docs/configure-other-dns
