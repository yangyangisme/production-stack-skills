#!/usr/bin/env python3
"""
Migration safety checker.

Scans SQL and Python migration files for dangerous patterns:
- Missing lock_timeout
- CREATE INDEX without CONCURRENTLY
- NOT NULL column additions without safe pattern
- Column renames and drops
- Column type changes
- Missing NOT VALID on constraint additions

Usage:
    python audit_migrations.py [path]
    python audit_migrations.py alembic/versions/
    python audit_migrations.py migrations/
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
    category: str
    message: str

    def __str__(self) -> str:
        return f"  [{self.severity}] {self.file}:{self.line} — {self.category}: {self.message}"


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    def add(self, file: str, line: int, severity: str, category: str, message: str) -> None:
        self.findings.append(Finding(file, line, severity, category, message))


# Patterns to detect in SQL content
PATTERNS = [
    # CREATE INDEX without CONCURRENTLY
    {
        "pattern": re.compile(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?!CONCURRENTLY)', re.IGNORECASE),
        "severity": "HIGH",
        "category": "Index",
        "message": "CREATE INDEX without CONCURRENTLY — locks table for writes during index build. "
                   "Use CREATE INDEX CONCURRENTLY",
    },
    # ALTER TABLE ... RENAME COLUMN
    {
        "pattern": re.compile(r'ALTER\s+TABLE\s+\w+\s+RENAME\s+COLUMN', re.IGNORECASE),
        "severity": "HIGH",
        "category": "Schema",
        "message": "Column rename — breaks old code during rolling deploy. "
                   "Use expand-contract: add new column, backfill, deploy, drop old",
    },
    # ALTER TABLE ... DROP COLUMN
    {
        "pattern": re.compile(r'ALTER\s+TABLE\s+\w+\s+DROP\s+COLUMN', re.IGNORECASE),
        "severity": "HIGH",
        "category": "Schema",
        "message": "DROP COLUMN — ensure all code references removed in previous deploy. "
                   "Verify no SELECT * usage",
    },
    # DROP TABLE
    {
        "pattern": re.compile(r'DROP\s+TABLE', re.IGNORECASE),
        "severity": "CRITICAL",
        "category": "Destructive",
        "message": "DROP TABLE — irreversible data loss. Ensure all references removed and backup exists",
    },
    # ALTER TABLE ... ALTER COLUMN ... TYPE (type change)
    {
        "pattern": re.compile(r'ALTER\s+TABLE\s+\w+\s+ALTER\s+COLUMN\s+\w+\s+(?:SET\s+DATA\s+)?TYPE', re.IGNORECASE),
        "severity": "HIGH",
        "category": "Schema",
        "message": "Column type change — may rewrite entire table with ACCESS EXCLUSIVE lock. "
                   "Use expand-contract unless widening varchar/numeric",
    },
    # ADD CONSTRAINT without NOT VALID
    {
        "pattern": re.compile(
            r'ADD\s+CONSTRAINT\s+\w+\s+(?:CHECK|FOREIGN\s+KEY)(?:(?!NOT\s+VALID).)*$',
            re.IGNORECASE | re.MULTILINE,
        ),
        "severity": "MEDIUM",
        "category": "Constraint",
        "message": "Adding constraint without NOT VALID — scans entire table under strong lock. "
                   "Use NOT VALID then VALIDATE in separate transaction",
    },
    # TRUNCATE
    {
        "pattern": re.compile(r'TRUNCATE\s+', re.IGNORECASE),
        "severity": "CRITICAL",
        "category": "Destructive",
        "message": "TRUNCATE — irreversible data deletion",
    },
    # DELETE without WHERE
    {
        "pattern": re.compile(r'DELETE\s+FROM\s+\w+\s*;', re.IGNORECASE),
        "severity": "CRITICAL",
        "category": "Destructive",
        "message": "DELETE without WHERE clause — deletes all rows in table",
    },
]

# Python/Alembic patterns
PYTHON_PATTERNS = [
    # op.drop_column
    {
        "pattern": re.compile(r'op\.drop_column\('),
        "severity": "HIGH",
        "category": "Schema",
        "message": "drop_column — ensure all code references removed in previous deploy",
    },
    # op.drop_table
    {
        "pattern": re.compile(r'op\.drop_table\('),
        "severity": "CRITICAL",
        "category": "Destructive",
        "message": "drop_table — irreversible data loss. Ensure backup exists",
    },
    # nullable=False without server_default on add_column
    {
        "pattern": re.compile(r'op\.add_column\([^)]*nullable\s*=\s*False(?![^)]*server_default)'),
        "severity": "HIGH",
        "category": "Schema",
        "message": "Adding NOT NULL column without server_default — "
                   "use 3-step pattern: nullable → backfill → constraint",
    },
    # RenameField (Django)
    {
        "pattern": re.compile(r'RenameField\('),
        "severity": "HIGH",
        "category": "Schema",
        "message": "RenameField — breaks old code during rolling deploy. Use expand-contract",
    },
]


def audit_sql_file(filepath: Path, result: AuditResult) -> None:
    """Audit a SQL migration file."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()
    filename = str(filepath)
    result.files_scanned += 1

    # Check for lock_timeout
    if "lock_timeout" not in content.lower():
        result.add(filename, 1, "MEDIUM", "Safety",
                   "Missing SET lock_timeout — migration may queue behind long queries and block all traffic")

    # Run pattern checks
    for check in PATTERNS:
        for i, line in enumerate(lines, 1):
            if check["pattern"].search(line):
                result.add(filename, i, check["severity"], check["category"], check["message"])


def audit_python_migration(filepath: Path, result: AuditResult) -> None:
    """Audit a Python migration file (Alembic or Django)."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()
    filename = str(filepath)
    result.files_scanned += 1

    # Check for lock_timeout in Alembic migrations
    if "op." in content and "lock_timeout" not in content:
        result.add(filename, 1, "MEDIUM", "Safety",
                   "Missing lock_timeout — add op.execute(\"SET lock_timeout = '2s'\") as first statement")

    # Check for SQL patterns embedded in Python
    for check in PATTERNS:
        for i, line in enumerate(lines, 1):
            if check["pattern"].search(line):
                result.add(filename, i, check["severity"], check["category"], check["message"])

    # Check Python-specific patterns
    for check in PYTHON_PATTERNS:
        for i, line in enumerate(lines, 1):
            if check["pattern"].search(line):
                result.add(filename, i, check["severity"], check["category"], check["message"])

    # Check for missing downgrade
    if "def upgrade" in content and "def downgrade" not in content:
        result.add(filename, 1, "MEDIUM", "Rollback",
                   "Missing downgrade() function — migration cannot be rolled back")
    elif "def downgrade" in content:
        # Check if downgrade is just pass
        downgrade_match = re.search(r'def downgrade\(\):\s*\n\s*pass', content)
        if downgrade_match:
            result.add(filename, 1, "LOW", "Rollback",
                       "downgrade() is just pass — consider implementing a real rollback")


def audit_directory(path: Path) -> AuditResult:
    """Find and audit migration files."""
    result = AuditResult()
    skip_dirs = {"node_modules", ".git", "venv", ".venv", "__pycache__"}

    # SQL files
    for filepath in sorted(path.rglob("*.sql")):
        if any(part in skip_dirs for part in filepath.parts):
            continue
        if filepath.is_file():
            audit_sql_file(filepath, result)

    # Python migration files (Alembic versions or Django migrations)
    migration_dirs = ["versions", "migrations"]
    for filepath in sorted(path.rglob("*.py")):
        if any(part in skip_dirs for part in filepath.parts):
            continue
        # Only audit files that look like migrations
        if any(d in filepath.parts for d in migration_dirs) or "migration" in filepath.name.lower():
            if filepath.is_file() and filepath.name != "__init__.py":
                audit_python_migration(filepath, result)

    return result


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    if target.is_file():
        result = AuditResult()
        if target.suffix == ".sql":
            audit_sql_file(target, result)
        elif target.suffix == ".py":
            audit_python_migration(target, result)
        else:
            print(f"Unsupported file type: {target.suffix}", file=sys.stderr)
            sys.exit(1)
    else:
        result = audit_directory(target)

    print(f"\n{'='*60}")
    print(f"Migration Safety Audit — {result.files_scanned} files scanned")
    print(f"{'='*60}\n")

    if not result.findings:
        print("  No issues found. Migrations look safe!\n")
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
