#!/usr/bin/env python3
"""
Dockerfile linting for production hardening.

Checks Dockerfiles for common production anti-patterns:
- Running as root (no USER directive)
- Using :latest tag
- Missing HEALTHCHECK
- Secrets in ARG/ENV
- Missing .dockerignore
- Single-stage builds for compiled languages
- Missing --no-cache-dir on pip install
- Not cleaning apt lists

Usage:
    python audit_dockerfile.py [path]
    python audit_dockerfile.py .
    python audit_dockerfile.py Dockerfile
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    message: str

    def __str__(self) -> str:
        return f"  [{self.severity}] {self.file}:{self.line} — {self.message}"


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    def add(self, file: str, line: int, severity: str, message: str) -> None:
        self.findings.append(Finding(file, line, severity, message))


SECRET_PATTERNS = re.compile(
    r'(password|secret|api_key|token|private_key|credentials|auth)',
    re.IGNORECASE,
)


def audit_dockerfile(filepath: Path, result: AuditResult) -> None:
    """Audit a single Dockerfile."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()
    filename = str(filepath)
    result.files_scanned += 1

    has_user = False
    has_healthcheck = False
    has_multi_stage = False
    from_count = 0
    has_pip_no_cache = True
    has_apt_cleanup = True

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        upper = stripped.upper()

        # FROM analysis
        if upper.startswith("FROM "):
            from_count += 1
            # Check for :latest
            if ":latest" in stripped.lower() or (
                " AS " not in stripped.upper()
                and ":" not in stripped.split()[1]
                and "@" not in stripped.split()[1]
            ):
                if ":latest" in stripped.lower():
                    result.add(filename, i, "MEDIUM",
                               "Using :latest tag — pin to a specific version for reproducible builds")
                elif ":" not in stripped.split()[1] and "@" not in stripped.split()[1]:
                    result.add(filename, i, "MEDIUM",
                               "No version tag on base image — pin to a specific version")

        # USER directive
        if upper.startswith("USER "):
            user_val = stripped.split(None, 1)[1] if len(stripped.split()) > 1 else ""
            if user_val.strip().lower() == "root":
                result.add(filename, i, "HIGH",
                           "USER root — container runs as root, use a non-root user")
            else:
                has_user = True

        # HEALTHCHECK
        if upper.startswith("HEALTHCHECK "):
            has_healthcheck = True

        # ARG/ENV with secrets
        if upper.startswith(("ARG ", "ENV ")):
            if SECRET_PATTERNS.search(stripped):
                result.add(filename, i, "CRITICAL",
                           f"Potential secret in {stripped.split()[0]} — "
                           "visible in docker history, use BuildKit --mount=type=secret")

        # COPY .env
        if upper.startswith("COPY "):
            parts = stripped.split()
            for part in parts[1:]:
                if ".env" in part.lower() and part != ".env.example":
                    result.add(filename, i, "CRITICAL",
                               f"COPY {part} — secrets baked into image layer permanently")

        # pip install without --no-cache-dir
        if "pip install" in stripped and "--no-cache-dir" not in stripped:
            has_pip_no_cache = False
            result.add(filename, i, "LOW",
                       "pip install without --no-cache-dir — caches wheels in image layer")

        # apt-get install without cleanup in same layer
        if "apt-get install" in stripped:
            # Check if rm -rf /var/lib/apt/lists is in the same RUN
            run_block = stripped
            if "rm -rf /var/lib/apt/lists" not in run_block:
                # Could be multi-line RUN, but flag anyway
                has_apt_cleanup = False

        # EXPOSE without preceding USER
        if upper.startswith("EXPOSE "):
            pass  # informational only

    # Multi-stage detection
    if from_count > 1:
        has_multi_stage = True

    # Post-scan checks
    if not has_user:
        result.add(filename, 0, "HIGH",
                   "No USER directive — container runs as root. "
                   "Add USER 65532 (distroless) or create a dedicated user")

    if not has_healthcheck:
        result.add(filename, 0, "MEDIUM",
                   "No HEALTHCHECK — orchestrator cannot detect hung processes. "
                   "Add HEALTHCHECK with appropriate interval and timeout")

    if not has_multi_stage and from_count == 1:
        result.add(filename, 0, "MEDIUM",
                   "Single-stage build — ships build tools and source code to production. "
                   "Use multi-stage: builder + slim runtime")

    if not has_apt_cleanup and "apt-get install" in content:
        result.add(filename, 0, "LOW",
                   "apt-get install without cleanup — add '&& rm -rf /var/lib/apt/lists/*' "
                   "in the same RUN layer")


def check_dockerignore(project_dir: Path, result: AuditResult) -> None:
    """Check if .dockerignore exists and has essential entries."""
    dockerignore = project_dir / ".dockerignore"

    if not dockerignore.exists():
        result.add(str(project_dir / ".dockerignore"), 0, "MEDIUM",
                   "No .dockerignore — COPY . sends .git, .env, node_modules to daemon")
        return

    content = dockerignore.read_text(encoding="utf-8").lower()
    essential = {
        ".git": "Version control history",
        ".env": "Environment secrets",
    }

    for pattern, description in essential.items():
        if pattern not in content:
            result.add(str(dockerignore), 0, "LOW",
                       f".dockerignore missing '{pattern}' — {description} sent to build context")


def audit_directory(path: Path) -> AuditResult:
    """Find and audit all Dockerfiles in a directory."""
    result = AuditResult()

    # Find Dockerfiles
    patterns = ["Dockerfile", "Dockerfile.*", "*.dockerfile"]
    dockerfiles = set()
    for pattern in patterns:
        dockerfiles.update(path.rglob(pattern))

    # Filter out non-files and hidden directories
    skip_dirs = {"node_modules", ".git", "venv", ".venv"}
    for df in sorted(dockerfiles):
        if any(part in skip_dirs for part in df.parts):
            continue
        if df.is_file():
            audit_dockerfile(df, result)

    # Check .dockerignore at project root
    check_dockerignore(path, result)

    return result


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    if target.is_file():
        result = AuditResult()
        audit_dockerfile(target, result)
    else:
        result = audit_directory(target)

    # Output
    print(f"\n{'='*60}")
    print(f"Dockerfile Audit — {result.files_scanned} files scanned")
    print(f"{'='*60}\n")

    if not result.findings:
        print("  No issues found. Containers look solid!\n")
        sys.exit(0)

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        findings = [f for f in result.findings if f.severity == severity]
        if findings:
            print(f"### {severity} ({len(findings)})\n")
            for f in findings:
                print(f)
            print()

    critical = sum(1 for f in result.findings if f.severity == "CRITICAL")
    high = sum(1 for f in result.findings if f.severity == "HIGH")
    medium = sum(1 for f in result.findings if f.severity == "MEDIUM")
    low = sum(1 for f in result.findings if f.severity == "LOW")

    print(f"{'='*60}")
    print(f"  Critical: {critical}  High: {high}  Medium: {medium}  Low: {low}")
    print(f"  Total: {len(result.findings)} findings")
    print(f"{'='*60}\n")

    if critical > 0 or high > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
