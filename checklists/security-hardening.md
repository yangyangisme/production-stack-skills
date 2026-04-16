# Security Hardening Checklist

Systematic security review for production deployments. Work through each section. Mark items as done, N/A (with reason), or TODO (with ticket link).

---

## Authentication

- [ ] Passwords hashed with bcrypt (cost ≥ 12) or argon2id
- [ ] No MD5, SHA1, or SHA256 for password storage
- [ ] JWT access tokens expire in ≤ 15 minutes
- [ ] JWT refresh tokens expire in ≤ 7 days
- [ ] JWT secret key is ≥ 256 bits, loaded from secret manager
- [ ] JWT tokens stored in HttpOnly cookies (not localStorage)
- [ ] JWT `alg: none` is rejected
- [ ] Failed login attempts are rate-limited (5-10 per 15 minutes)
- [ ] Account lockout after N failed attempts (with email notification)
- [ ] Password reset tokens are single-use and expire in ≤ 1 hour
- [ ] Session invalidated on logout (server-side, not just client cookie deletion)
- [ ] Re-authentication required for sensitive actions (password change, email change, delete account)

## Authorization

- [ ] Every endpoint has explicit authorization (not just authentication)
- [ ] Object-level access control: user A cannot access user B's resources by changing IDs
- [ ] Admin endpoints require admin role verification (not just "hidden" URLs)
- [ ] Role checks happen server-side only (never trust client claims)
- [ ] Principle of least privilege: default deny, explicitly grant
- [ ] API keys scoped to minimum necessary permissions

## Input Validation

- [ ] All user input validated at the API boundary
- [ ] Input validation uses allowlists, not denylists
- [ ] String inputs have maximum length limits
- [ ] Numeric inputs have range constraints
- [ ] File uploads validated: type (MIME + magic bytes), size, filename sanitized
- [ ] Path parameters sanitized (no directory traversal: `../`)
- [ ] Request body size limited (express.json limit, nginx client_max_body_size)

## Injection Prevention

- [ ] All SQL queries use parameterized statements
- [ ] No f-string/template literal SQL construction
- [ ] No `eval()`, `exec()` with user-supplied data
- [ ] No `os.system()`, `subprocess(shell=True)` with user input
- [ ] No `pickle.loads()` on untrusted data
- [ ] No `yaml.load()` — use `yaml.safe_load()`
- [ ] Template engines use auto-escaping (Jinja2, Handlebars)
- [ ] GraphQL queries have depth and complexity limits

## Secrets Management

- [ ] No hardcoded secrets in source code
- [ ] No secrets in environment variable declarations in code
- [ ] `.env` files in `.gitignore`
- [ ] Production secrets in a secret manager (Vault, AWS SM, GCP SM, Doppler)
- [ ] No secrets in Docker ARG or ENV instructions
- [ ] No secrets in docker-compose.yml (use env_file or Docker secrets)
- [ ] No secrets in CI/CD logs (masked variables)
- [ ] Secret rotation procedure documented
- [ ] Pre-commit hook for secret detection (detect-secrets, gitleaks, trufflehog)

## Transport Security

- [ ] HTTPS enforced in production (HTTP → HTTPS redirect)
- [ ] TLS 1.2+ only (TLS 1.0/1.1 disabled)
- [ ] HSTS header present: `Strict-Transport-Security: max-age=63072000; includeSubDomains`
- [ ] SSL certificates auto-renewed (Let's Encrypt, AWS ACM, etc.)
- [ ] Internal service-to-service communication uses TLS or private network

## Security Headers

- [ ] `Strict-Transport-Security` (HSTS)
- [ ] `Content-Security-Policy` (CSP)
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: DENY`
- [ ] `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- [ ] `X-XSS-Protection: 0` (modern browsers, CSP supersedes this)
- [ ] No `X-Powered-By` header (reveals technology stack)

## CORS

- [ ] Not `allow_origins=["*"]` with `allow_credentials=True`
- [ ] Specific origin whitelist (not wildcard)
- [ ] `allow_methods` restricted to what's needed
- [ ] `allow_headers` restricted to what's needed
- [ ] Preflight caching configured (`max_age`)

## Rate Limiting

- [ ] Auth endpoints: ≤ 10 requests per 15 minutes per IP
- [ ] Public API endpoints: reasonable limit per user/IP
- [ ] Returns 429 with `Retry-After` header
- [ ] Rate limit state stored in Redis/centralized store (not in-memory per instance)

## Dependency Security

- [ ] Dependencies scanned for known CVEs:
  - Python: `pip-audit`
  - Node.js: `npm audit`
  - Go: `govulncheck`
  - Docker: `trivy image`
- [ ] No deprecated packages with known security issues
- [ ] Dependabot or Renovate configured for automatic updates
- [ ] CI/CD fails build on HIGH/CRITICAL vulnerabilities

## Data Protection

- [ ] PII identified and documented (names, emails, addresses, phone numbers)
- [ ] Sensitive data encrypted at rest (database, backups)
- [ ] Sensitive data encrypted in transit (TLS)
- [ ] Column-level encryption for highly sensitive fields (SSN, payment cards)
- [ ] Data retention policy defined and enforced
- [ ] GDPR right-to-deletion implemented (if applicable)
- [ ] Audit log for data access (who accessed what, when)
- [ ] No sensitive data in logs (passwords, tokens, credit cards, PII)

## Container Security

- [ ] Running as non-root user
- [ ] Read-only filesystem with explicit tmpfs for writable paths
- [ ] Capabilities dropped (`cap_drop: ALL`, add back only what's needed)
- [ ] `no-new-privileges` security option set
- [ ] Base image pinned by digest (not `latest`)
- [ ] Image scanned with Trivy (no HIGH/CRITICAL CVEs)
- [ ] No secrets in image layers (`docker history --no-trunc` is clean)

## Network Security

- [ ] Database not accessible from public internet
- [ ] Services communicate over private network
- [ ] Firewall/security groups restrict ingress to necessary ports only
- [ ] WAF in front of public-facing endpoints (if applicable)
- [ ] DDoS protection configured (Cloudflare, AWS Shield, etc.)

## Monitoring & Incident Response

- [ ] Authentication failures logged with IP, timestamp, user-agent
- [ ] Authorization failures logged
- [ ] Alert on spike in 401/403 responses
- [ ] Alert on spike in 500 errors
- [ ] Incident response plan documented
- [ ] Security contact email published (security.txt)

---

*From production-stack-skills by VStorm — vstorm.co*
