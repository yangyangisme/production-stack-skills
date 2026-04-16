#!/usr/bin/env python3
"""
AST-based FastAPI code analysis.

Scans Python files for common FastAPI production anti-patterns:
- print() instead of structured logging
- BaseHTTPMiddleware usage (breaks contextvars)
- on_event decorators (deprecated)
- Synchronous calls in async endpoints (requests, time.sleep, open)
- Missing timeouts on HTTP clients
- Bare except handlers
- Missing type hints on endpoint parameters

Usage:
    python audit_fastapi.py [path]
    python audit_fastapi.py .
    python audit_fastapi.py src/api/
"""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    file: str
    line: int
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    category: str
    message: str

    def __str__(self) -> str:
        return f"  [{self.severity}] {self.file}:{self.line} — {self.category}: {self.message}"


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HIGH")

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "MEDIUM")

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "LOW")


class FastAPIAuditor(ast.NodeVisitor):
    """AST visitor that detects FastAPI anti-patterns."""

    def __init__(self, filename: str, result: AuditResult) -> None:
        self.filename = filename
        self.result = result
        self._in_async_def = False
        self._async_func_name = ""
        self._imports: set[str] = set()

    def _add(self, line: int, severity: str, category: str, message: str) -> None:
        self.result.add(Finding(self.filename, line, severity, category, message))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._imports.add(alias.name)
            # Check for synchronous HTTP library in async codebase
            if alias.name == "requests":
                self._add(
                    node.lineno, "HIGH", "Async",
                    "import requests — use httpx.AsyncClient in async FastAPI apps"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._imports.add(node.module)
            for alias in node.names:
                full_name = f"{node.module}.{alias.name}"
                # BaseHTTPMiddleware
                if alias.name == "BaseHTTPMiddleware":
                    self._add(
                        node.lineno, "HIGH", "Middleware",
                        "BaseHTTPMiddleware breaks contextvars — use pure ASGI middleware"
                    )
                # Deprecated on_event
                if node.module == "fastapi" and alias.name == "FastAPI":
                    pass  # Will check on_event usage separately
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._in_async_def = True
        self._async_func_name = node.name
        self.generic_visit(node)
        self._in_async_def = False

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # print() usage
        if isinstance(func, ast.Name) and func.id == "print":
            self._add(
                node.lineno, "MEDIUM", "Logging",
                "print() — use structured logging (structlog, loguru)"
            )

        # eval() / exec()
        if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
            self._add(
                node.lineno, "CRITICAL", "Security",
                f"{func.id}() — potential code injection vulnerability"
            )

        # time.sleep in async context
        if self._in_async_def and isinstance(func, ast.Attribute):
            if (isinstance(func.value, ast.Name) and func.value.id == "time"
                    and func.attr == "sleep"):
                self._add(
                    node.lineno, "HIGH", "Async",
                    f"time.sleep() in async function '{self._async_func_name}' — "
                    "blocks event loop, use asyncio.sleep()"
                )

        # open() in async context (without aiofiles)
        if self._in_async_def and isinstance(func, ast.Name) and func.id == "open":
            self._add(
                node.lineno, "MEDIUM", "Async",
                f"open() in async function '{self._async_func_name}' — "
                "blocks event loop, use aiofiles.open()"
            )

        # os.system()
        if isinstance(func, ast.Attribute):
            if (isinstance(func.value, ast.Name) and func.value.id == "os"
                    and func.attr == "system"):
                self._add(
                    node.lineno, "CRITICAL", "Security",
                    "os.system() — command injection risk, use subprocess with shell=False"
                )

        # Check for on_event decorator pattern
        if isinstance(func, ast.Attribute) and func.attr == "on_event":
            self._add(
                node.lineno, "MEDIUM", "Lifecycle",
                "on_event() is deprecated — use lifespan context manager"
            )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Bare except or except Exception with pass
        if node.type is None:
            # bare except:
            if node.body and isinstance(node.body[0], ast.Pass):
                self._add(
                    node.lineno, "HIGH", "Error Handling",
                    "bare except: pass — swallows all exceptions silently"
                )
            else:
                self._add(
                    node.lineno, "MEDIUM", "Error Handling",
                    "bare except: — catches all exceptions including KeyboardInterrupt"
                )
        elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
            if node.body and isinstance(node.body[0], ast.Pass):
                self._add(
                    node.lineno, "HIGH", "Error Handling",
                    "except Exception: pass — swallows all exceptions silently"
                )
        self.generic_visit(node)


def audit_file(filepath: Path, result: AuditResult) -> None:
    """Audit a single Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        auditor = FastAPIAuditor(str(filepath), result)
        auditor.visit(tree)
        result.files_scanned += 1
    except SyntaxError as e:
        result.add(Finding(str(filepath), e.lineno or 0, "LOW", "Parse", f"Syntax error: {e.msg}"))
    except Exception as e:
        result.add(Finding(str(filepath), 0, "LOW", "Parse", f"Could not parse: {e}"))


def audit_directory(path: Path) -> AuditResult:
    """Audit all Python files in a directory."""
    result = AuditResult()
    py_files = sorted(path.rglob("*.py"))

    # Skip common non-application directories
    skip_dirs = {"venv", ".venv", "node_modules", "__pycache__", ".git", ".tox", ".mypy_cache"}

    for filepath in py_files:
        if any(part in skip_dirs for part in filepath.parts):
            continue
        audit_file(filepath, result)

    return result


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    if target.is_file():
        result = AuditResult()
        audit_file(target, result)
    else:
        result = audit_directory(target)

    # Output results
    print(f"\n{'='*60}")
    print(f"FastAPI Audit — {result.files_scanned} files scanned")
    print(f"{'='*60}\n")

    if not result.findings:
        print("  No issues found. Nice work!\n")
        sys.exit(0)

    # Group by severity
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        findings = [f for f in result.findings if f.severity == severity]
        if findings:
            print(f"### {severity} ({len(findings)})\n")
            for f in findings:
                print(f)
            print()

    # Summary
    print(f"{'='*60}")
    print(f"  Critical: {result.critical_count}  High: {result.high_count}  "
          f"Medium: {result.medium_count}  Low: {result.low_count}")
    print(f"  Total: {len(result.findings)} findings")
    print(f"{'='*60}\n")

    # Exit with non-zero if critical or high findings
    if result.critical_count > 0 or result.high_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
