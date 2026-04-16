#!/usr/bin/env python3
"""
Production readiness composite scorer.

Runs all audit scripts and computes a weighted 0-100 score.
This is the CLI equivalent of /production check.

Usage:
    python score_production_readiness.py [path]

Scoring weights:
    Security fundamentals:       25%
    Error handling & resilience: 20%
    Observability:               20%
    Deployment readiness:        15%
    Database patterns:           10%
    Container hygiene:           10%
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CategoryScore:
    name: str
    weight: float
    raw_score: int  # 0-100
    findings_summary: str

    @property
    def weighted(self) -> float:
        return self.raw_score * self.weight


def count_pattern(path: Path, pattern: str, file_types: list[str]) -> int:
    """Count occurrences of a regex pattern across files."""
    count = 0
    for ft in file_types:
        for filepath in path.rglob(f"*.{ft}"):
            if any(d in filepath.parts for d in [".git", "venv", ".venv", "node_modules", "__pycache__"]):
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                count += len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))
            except Exception:
                pass
    return count


def check_file_exists(path: Path, names: list[str]) -> bool:
    """Check if any of the named files exist in the project."""
    for name in names:
        if list(path.rglob(name)):
            return True
    return False


def score_security(path: Path) -> CategoryScore:
    """Score security fundamentals."""
    score = 100
    findings = []

    # Hardcoded secrets
    secrets = count_pattern(path, r'(password|secret|api_key|token)\s*=\s*"[^"]{8,}"', ["py", "js", "ts"])
    if secrets > 0:
        deduction = min(30, secrets * 15)
        score -= deduction
        findings.append(f"Hardcoded secrets: {secrets} instances (-{deduction})")

    # SQL injection
    sqli = count_pattern(path, r'f"(SELECT|INSERT|UPDATE|DELETE)', ["py"])
    if sqli > 0:
        deduction = min(30, sqli * 15)
        score -= deduction
        findings.append(f"SQL injection vectors: {sqli} (-{deduction})")

    # CORS wildcard
    cors = count_pattern(path, r'allow_origins.*\*', ["py"])
    if cors > 0:
        score -= 8
        findings.append("CORS wildcard origins (-8)")

    # Debug mode
    debug = count_pattern(path, r'DEBUG\s*=\s*True', ["py"])
    if debug > 0:
        score -= 4
        findings.append(f"Debug mode enabled: {debug} instances (-4)")

    # .env in .gitignore
    gitignore = path / ".gitignore"
    if gitignore.exists():
        gi_content = gitignore.read_text()
        if ".env" not in gi_content:
            score -= 4
            findings.append(".env not in .gitignore (-4)")

    return CategoryScore("Security Fundamentals", 0.25, max(0, score),
                         "; ".join(findings) if findings else "No issues found")


def score_error_handling(path: Path) -> CategoryScore:
    """Score error handling & resilience."""
    score = 100
    findings = []

    # Bare except: pass
    bare_except = count_pattern(path, r'except.*:.*pass\s*$', ["py"])
    if bare_except > 0:
        deduction = min(24, bare_except * 6)
        score -= deduction
        findings.append(f"Swallowed exceptions: {bare_except} (-{deduction})")

    # Missing timeouts (requests without timeout)
    no_timeout = count_pattern(path, r'requests\.(get|post|put|delete|patch)\([^)]*\)(?![^)]*timeout)', ["py"])
    if no_timeout > 0:
        deduction = min(12, no_timeout * 6)
        score -= deduction
        findings.append(f"HTTP calls without timeout: {no_timeout} (-{deduction})")

    return CategoryScore("Error Handling & Resilience", 0.20, max(0, score),
                         "; ".join(findings) if findings else "No issues found")


def score_observability(path: Path) -> CategoryScore:
    """Score observability."""
    score = 100
    findings = []

    # print() as logging
    prints = count_pattern(path, r'^\s*print\(', ["py"])
    if prints > 5:
        score -= 12
        findings.append(f"print() statements: {prints} — use structured logging (-12)")

    # Health endpoints
    has_health = count_pattern(path, r'/health|/healthz|/ready', ["py", "js", "ts"])
    if has_health == 0:
        score -= 8
        findings.append("No health check endpoints (-8)")

    # Structured logging library
    has_structlog = check_file_exists(path, ["structlog*"]) or count_pattern(path, r'import structlog', ["py"]) > 0
    has_loguru = count_pattern(path, r'import loguru|from loguru', ["py"]) > 0
    has_pino = count_pattern(path, r"require.*pino|import.*pino", ["js", "ts"]) > 0
    if not (has_structlog or has_loguru or has_pino):
        score -= 8
        findings.append("No structured logging library detected (-8)")

    # Correlation IDs
    has_correlation = count_pattern(path, r'request.id|request_id|correlation.id|trace.id|X-Request-ID', ["py", "js", "ts"])
    if has_correlation == 0:
        score -= 6
        findings.append("No request correlation IDs (-6)")

    return CategoryScore("Observability", 0.20, max(0, score),
                         "; ".join(findings) if findings else "No issues found")


def score_deployment(path: Path) -> CategoryScore:
    """Score deployment readiness."""
    score = 100
    findings = []

    # Hardcoded localhost
    localhost = count_pattern(path, r'localhost|127\.0\.0\.1', ["py", "js", "ts"])
    if localhost > 2:
        deduction = min(12, (localhost - 2) * 3)
        score -= deduction
        findings.append(f"Hardcoded localhost: {localhost} instances (-{deduction})")

    # SIGTERM handling
    has_sigterm = count_pattern(path, r'SIGTERM|signal\.signal|process\.on.*SIGTERM', ["py", "js", "ts"])
    if has_sigterm == 0:
        score -= 8
        findings.append("No graceful shutdown (SIGTERM) handling (-8)")

    # Config validation
    has_settings = count_pattern(path, r'BaseSettings|SettingsConfigDict|envalid', ["py", "js", "ts"])
    if has_settings == 0:
        score -= 4
        findings.append("No startup config validation (-4)")

    return CategoryScore("Deployment Readiness", 0.15, max(0, score),
                         "; ".join(findings) if findings else "No issues found")


def score_database(path: Path) -> CategoryScore:
    """Score database patterns."""
    score = 100
    findings = []

    # Connection pooling
    has_pool = count_pattern(path, r'pool_size|create_pool|Pool\(|pgbouncer', ["py", "js", "ts", "ini", "cfg"])
    if has_pool == 0 and count_pattern(path, r'postgres|psycopg|asyncpg|sqlalchemy', ["py"]) > 0:
        score -= 6
        findings.append("No connection pooling detected (-6)")

    # SELECT *
    select_star = count_pattern(path, r'SELECT\s+\*', ["py", "js", "ts"])
    if select_star > 0:
        deduction = min(6, select_star * 3)
        score -= deduction
        findings.append(f"SELECT * usage: {select_star} instances (-{deduction})")

    return CategoryScore("Database Patterns", 0.10, max(0, score),
                         "; ".join(findings) if findings else "No issues found")


def score_container(path: Path) -> CategoryScore:
    """Score container hygiene."""
    score = 100
    findings = []

    dockerfiles = list(path.rglob("Dockerfile")) + list(path.rglob("Dockerfile.*"))
    if not dockerfiles:
        return CategoryScore("Container Hygiene", 0.10, 100, "No Dockerfiles found (N/A)")

    for df in dockerfiles:
        content = df.read_text(encoding="utf-8")

        if "USER " not in content:
            score -= 6
            findings.append(f"{df.name}: running as root (-6)")

        if "HEALTHCHECK" not in content:
            score -= 3
            findings.append(f"{df.name}: missing HEALTHCHECK (-3)")

        if ":latest" in content:
            score -= 3
            findings.append(f"{df.name}: using :latest tag (-3)")

    # .dockerignore
    if not (path / ".dockerignore").exists() and dockerfiles:
        score -= 4
        findings.append("No .dockerignore (-4)")

    return CategoryScore("Container Hygiene", 0.10, max(0, score),
                         "; ".join(findings) if findings else "No issues found")


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print("Production Readiness Score")
    print(f"{'='*60}\n")

    categories = [
        score_security(target),
        score_error_handling(target),
        score_observability(target),
        score_deployment(target),
        score_database(target),
        score_container(target),
    ]

    total = sum(c.weighted for c in categories)

    # Display results
    print(f"{'Category':<32} {'Score':>7} {'Weight':>7} {'Weighted':>9}")
    print("-" * 60)
    for c in categories:
        print(f"{c.name:<32} {c.raw_score:>5}/100 {c.weight:>6.0%} {c.weighted:>8.1f}")
    print("-" * 60)
    print(f"{'TOTAL':<32} {'':>7} {'':>7} {total:>7.0f}/100")

    # Grade
    if total >= 90:
        grade = "A"
    elif total >= 80:
        grade = "B"
    elif total >= 70:
        grade = "C"
    elif total >= 50:
        grade = "D"
    else:
        grade = "F"

    print(f"\nGrade: {grade}")

    # Details
    print(f"\n{'='*60}")
    print("Details")
    print(f"{'='*60}\n")
    for c in categories:
        if c.findings_summary != "No issues found":
            print(f"  {c.name}:")
            for finding in c.findings_summary.split("; "):
                print(f"    - {finding}")
            print()

    # Grade interpretation
    interpretations = {
        "A": "Production-ready. Ship with confidence.",
        "B": "Solid foundation. Minor improvements won't block deployment.",
        "C": "Acceptable for staging. Address HIGH items before production.",
        "D": "Needs significant work. Multiple categories need attention.",
        "F": "Not production-ready. Critical issues must be resolved first.",
    }
    print(f"\n{interpretations[grade]}")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
