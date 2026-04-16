# Pre-Deployment Checklist

Copy this checklist into your PR or deployment ticket. Walk through every item before deploying to production.

---

## Data Layer

- [ ] Database migrations reviewed and classified:
  - Additive (safe): new tables, new nullable columns, new indexes
  - Transformative (risky): column type changes, data backfills, constraint additions
  - Destructive (dangerous): column drops, table drops, data deletion
- [ ] All `CREATE INDEX` statements use `CONCURRENTLY`
- [ ] All migrations include `SET lock_timeout = '2s'`
- [ ] Rollback script exists for every migration and has been tested
- [ ] Backup taken (or continuous backup verified)
- [ ] Migrations tested against production-scale data volume (not just dev DB)
- [ ] No `NOT NULL` additions without the 3-step pattern (nullable → backfill → constraint)

## Application Layer

- [ ] All new environment variables documented
- [ ] All required environment variables set in production
- [ ] Secrets rotated if compromised or on schedule
- [ ] Feature flags configured for gradual rollout (if applicable)
- [ ] API changes are backward-compatible (additive only)
- [ ] If breaking changes: API versioned and old version still works
- [ ] Request/response validation in place for new endpoints
- [ ] Error handling covers new failure modes

## Infrastructure

- [ ] Health check endpoints respond correctly (`/health/live`, `/health/ready`)
- [ ] Graceful shutdown tested (SIGTERM handling)
- [ ] Resource limits set (CPU, memory) in container/orchestrator config
- [ ] Autoscaling configured if traffic is variable
- [ ] DNS/routing changes verified (if applicable)
- [ ] SSL/TLS certificates valid and not expiring soon

## Observability

- [ ] Logs reaching aggregator (check after staging deploy)
- [ ] Key metrics have alerts (error rate, latency, availability)
- [ ] Traces enabled and visible in tracing backend
- [ ] Error budgets defined (SLO/SLI)
- [ ] New endpoints/features have corresponding metrics
- [ ] No sensitive data in log output

## Security

- [ ] No hardcoded secrets in code or config files
- [ ] Dependencies scanned for vulnerabilities (pip-audit, npm audit, Trivy)
- [ ] New endpoints have proper authentication and authorization
- [ ] Rate limiting applied to new public/auth endpoints
- [ ] CORS configuration reviewed for new origins
- [ ] Input validation on all new user-facing inputs

## Rollback Plan

- [ ] Rollback plan documented (not just "redeploy previous version"):
  - Schema rollback procedure
  - Data rollback procedure (if applicable)
  - Traffic routing rollback
- [ ] Team knows who has deploy access
- [ ] Incident communication channel identified
- [ ] On-call engineer aware of the deployment
- [ ] Rollback tested on staging

## Final Verification

- [ ] Staging deployment successful
- [ ] Smoke tests passed on staging
- [ ] Performance acceptable (no latency regression)
- [ ] No unexpected errors in staging logs
- [ ] Deploy window chosen (avoid Fridays, holidays, peak hours)

---

*From production-stack-skills by VStorm — vstorm.co*
