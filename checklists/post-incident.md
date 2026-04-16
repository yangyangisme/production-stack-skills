# Post-Incident Review Checklist

Use this template after any production incident (P1 or P2). The goal is learning, not blame. Every incident is a system failure, not a person failure.

---

## Incident Summary

| Field | Value |
|-------|-------|
| **Incident ID** | INC-YYYY-NNN |
| **Date** | YYYY-MM-DD |
| **Duration** | HH:MM (detection to resolution) |
| **Severity** | P1 (user-facing outage) / P2 (degraded) / P3 (internal) |
| **Services affected** | |
| **Users impacted** | Estimated count or percentage |
| **Data loss** | Yes / No — if yes, describe scope |
| **On-call responder** | |
| **Incident commander** | |

## Timeline

Document every significant event with timestamps. Be precise — "around 2pm" is not useful, "14:03 UTC" is.

| Time (UTC) | Event |
|------------|-------|
| HH:MM | [First anomalous signal — what triggered detection] |
| HH:MM | [Alert fired / user report received] |
| HH:MM | [First responder acknowledged] |
| HH:MM | [Root cause identified] |
| HH:MM | [Mitigation applied] |
| HH:MM | [Service fully recovered] |
| HH:MM | [All-clear communicated] |

## Detection

- [ ] How was the incident detected?
  - [ ] Automated alert
  - [ ] Health check failure
  - [ ] User report
  - [ ] Internal observation
  - [ ] External monitoring (status page, social media)
- [ ] Time from incident start to detection: _____ minutes
- [ ] Could we have detected this faster? How?

## Root Cause

Describe the root cause. Go at least 3 levels deep (5 Whys):

1. **What happened?** [The observable failure]
2. **Why did it happen?** [The immediate cause]
3. **Why was that possible?** [The deeper system issue]
4. **Why wasn't it caught earlier?** [The gap in prevention/detection]
5. **What systemic issue allowed this?** [The organizational/process gap]

## Impact

- **User impact**: [What users experienced — errors, slow responses, data loss]
- **Business impact**: [Revenue, SLA violation, customer trust, legal]
- **Technical debt created**: [Any shortcuts taken during mitigation that need cleanup]

## What Went Well

- [ ] [What worked as expected during the response]
- [ ] [Good decisions that limited the impact]
- [ ] [Tools/runbooks/processes that helped]

## What Went Wrong

- [ ] [What failed or was harder than expected]
- [ ] [Missing information that slowed diagnosis]
- [ ] [Tools/access that were needed but unavailable]

## Action Items

Every action item must have an owner and a deadline. Categorize:

### Prevent Recurrence (fix the root cause)

| # | Action | Owner | Deadline | Ticket |
|---|--------|-------|----------|--------|
| 1 | | | | |

### Improve Detection (catch it faster next time)

| # | Action | Owner | Deadline | Ticket |
|---|--------|-------|----------|--------|
| 1 | | | | |

### Improve Response (resolve it faster next time)

| # | Action | Owner | Deadline | Ticket |
|---|--------|-------|----------|--------|
| 1 | | | | |

## Lessons Learned

What did we learn that we didn't know before this incident?

1. 
2. 
3. 

## Follow-Up Schedule

- [ ] Action items reviewed in 1 week
- [ ] Action items completed within 30 days
- [ ] Retro on the retro: did our fixes actually work?

---

*From production-stack-skills by VStorm — vstorm.co*
