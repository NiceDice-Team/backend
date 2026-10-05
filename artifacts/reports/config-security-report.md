# django-check security report

Status: **PASS WITH KNOWN FINDINGS**

| Critical | High | Medium | Low | Informational | Known | New |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 2 | 4 | 0 | 0 | 6 | 0 |

## Findings

- `SEC-CONFIG-001` [Medium] You don't appear to be using Django's built-in cross-site request forgery protection via the middleware ('django.middleware.csrf.CsrfViewMiddleware' is not in your MIDDLEWARE). Enabling the middleware is the safest approach to ensure you don't leave any holes. — `src.settings`
- `SEC-CONFIG-002` [Medium] You have not set a value for the SECURE_HSTS_SECONDS setting. If your entire site is served only over SSL, you may want to consider setting a value and enabling HTTP Strict Transport Security. Be sure to read the documentation first; enabling HSTS carelessly can cause serious, irreversible problems. — `src.settings`
- `SEC-CONFIG-003` [Medium] Your SECURE_SSL_REDIRECT setting is not set to True. Unless your site should be available over both SSL and non-SSL connections, you may want to either set this setting True or configure a load balancer or reverse-proxy server to redirect all connections to HTTPS. — `src.settings`
- `SEC-CONFIG-004` [High] Your SECRET_KEY has less than 50 characters, less than 5 unique characters, or it's prefixed with 'django-insecure-' indicating that it was generated automatically by Django. Please generate a long and random value, otherwise many of Django's security-critical features will be vulnerable to attack. — `src.settings`
- `SEC-CONFIG-005` [Medium] SESSION_COOKIE_SECURE is not set to True. Using a secure-only session cookie makes it more difficult for network traffic sniffers to hijack user sessions. — `src.settings`
- `SEC-CONFIG-006` [High] You should not have DEBUG set to True in deployment. — `src.settings`

Raw evidence is retained as an artifact; secret values and response bodies are omitted here.
