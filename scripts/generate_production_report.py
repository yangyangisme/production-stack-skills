#!/usr/bin/env python3
"""
Generate a Markdown production readiness report.

Imports scoring functions from score_production_readiness.py and writes a
formatted report including score breakdown, findings, quick wins, and
recommendations.

Usage:
    python scripts/generate_production_report.py [path]

Output:
    production-readiness-report.md in the scanned project directory.
"""

import sys
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

# ---------------------------------------------------------------------------
# Import scoring functions from the sibling module.
# We add this script's directory to sys.path so the import works regardless
# of where the user invokes the script from.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from score_production_readiness import (  # noqa: E402
    CategoryScore,
    score_security,
    score_error_handling,
    score_observability,
    score_deployment,
    score_database,
    score_container,
)


# ---------------------------------------------------------------------------
# Grade helpers (mirrored from score_production_readiness.py)
# ---------------------------------------------------------------------------

_GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (50, "D"),
    (0, "F"),
]

_GRADE_INTERPRETATIONS: dict[str, str] = {
    "A": "Production-ready. Ship with confidence.",
    "B": "Solid foundation. Minor improvements won't block deployment.",
    "C": "Acceptable for staging. Address HIGH items before production.",
    "D": "Needs significant work. Multiple categories need attention.",
    "F": "Not production-ready. Critical issues must be resolved first.",
}


def _compute_grade(total: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if total >= threshold:
            return grade
    return "F"


# ---------------------------------------------------------------------------
# Severity classification for individual findings
# ---------------------------------------------------------------------------

def _classify_severity(finding: str) -> str:
    """Heuristic severity based on the deduction magnitude."""
    # Extract the deduction value from strings like "(-15)" or "(-6)"
    import re
    match = re.search(r"\(-(\d+)\)", finding)
    if not match:
        return "INFO"
    deduction = int(match.group(1))
    if deduction >= 15:
        return "CRITICAL"
    if deduction >= 8:
        return "HIGH"
    if deduction >= 4:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Quick wins: findings with the highest bang-for-buck
# ---------------------------------------------------------------------------

@dataclass
class _QuickWin:
    category: str
    finding: str
    potential_points: float  # weighted improvement

    @property
    def label(self) -> str:
        return f"{self.finding} ({self.category})"


def _extract_quick_wins(categories: list[CategoryScore], top_n: int = 5) -> list[_QuickWin]:
    """Return the top-N findings ordered by weighted score improvement."""
    import re
    wins: list[_QuickWin] = []
    for cat in categories:
        if cat.findings_summary == "No issues found":
            continue
        for finding in cat.findings_summary.split("; "):
            match = re.search(r"\(-(\d+)\)", finding)
            if not match:
                continue
            raw_points = int(match.group(1))
            weighted_points = raw_points * cat.weight
            wins.append(_QuickWin(category=cat.name, finding=finding, potential_points=weighted_points))
    wins.sort(key=lambda w: w.potential_points, reverse=True)
    return wins[:top_n]


# ---------------------------------------------------------------------------
# Recommendations per grade
# ---------------------------------------------------------------------------

def _recommendations_for_grade(grade: str, categories: list[CategoryScore]) -> list[str]:
    """Return actionable recommendations based on grade and weak categories."""
    recs: list[str] = []

    # Find weakest categories
    weak = sorted(categories, key=lambda c: c.raw_score)

    if grade in ("D", "F"):
        recs.append("Focus on CRITICAL and HIGH findings before anything else.")
        recs.append("Run the scorer after each fix to track progress.")
    if grade in ("C", "D", "F"):
        for cat in weak[:2]:
            if cat.raw_score < 80:
                recs.append(f"Prioritize **{cat.name}** (score {cat.raw_score}/100).")
    if grade in ("A", "B"):
        recs.append("Address remaining MEDIUM/LOW findings to harden the deployment.")
    if any(c.name == "Security Fundamentals" and c.raw_score < 80 for c in categories):
        recs.append("Security score is below 80 -- resolve before any production deployment.")
    if any(c.name == "Error Handling & Resilience" and c.raw_score < 70 for c in categories):
        recs.append("Add retry, timeout, and circuit-breaker patterns to external calls.")
    if any(c.name == "Observability" and c.raw_score < 70 for c in categories):
        recs.append("Replace print() with structured logging and add health-check endpoints.")
    if any(c.name == "Deployment Readiness" and c.raw_score < 70 for c in categories):
        recs.append("Externalize configuration and add graceful shutdown handling.")

    if not recs:
        recs.append("No major recommendations. Keep up the good work.")

    return recs


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(target: Path) -> str:
    """Run all scorers and return the full Markdown report as a string."""
    project_name = target.resolve().name
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    categories: list[CategoryScore] = [
        score_security(target),
        score_error_handling(target),
        score_observability(target),
        score_deployment(target),
        score_database(target),
        score_container(target),
    ]

    total = sum(c.weighted for c in categories)
    grade = _compute_grade(total)
    interpretation = _GRADE_INTERPRETATIONS[grade]

    lines: list[str] = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    lines.append(f"# Production Readiness Report")
    lines.append("")
    lines.append(f"| Field   | Value |")
    lines.append(f"|---------|-------|")
    lines.append(f"| Project | **{project_name}** |")
    lines.append(f"| Date    | {now} |")
    lines.append(f"| Score   | **{total:.0f}/100** |")
    lines.append(f"| Grade   | **{grade}** -- {interpretation} |")
    lines.append("")

    # ------------------------------------------------------------------
    # Score Breakdown
    # ------------------------------------------------------------------
    lines.append("## Score Breakdown")
    lines.append("")
    lines.append("| Category | Raw Score | Weight | Weighted |")
    lines.append("|----------|-----------|--------|----------|")
    for c in categories:
        lines.append(f"| {c.name} | {c.raw_score}/100 | {c.weight:.0%} | {c.weighted:.1f} |")
    lines.append(f"| **TOTAL** | | | **{total:.0f}/100** |")
    lines.append("")

    # ------------------------------------------------------------------
    # Findings Per Category
    # ------------------------------------------------------------------
    lines.append("## Findings")
    lines.append("")
    for c in categories:
        lines.append(f"### {c.name}")
        lines.append("")
        if c.findings_summary == "No issues found":
            lines.append("No issues found.")
        else:
            for finding in c.findings_summary.split("; "):
                severity = _classify_severity(finding)
                lines.append(f"- **[{severity}]** {finding}")
        lines.append("")

    # ------------------------------------------------------------------
    # Quick Wins
    # ------------------------------------------------------------------
    quick_wins = _extract_quick_wins(categories)
    if quick_wins:
        lines.append("## Quick Wins")
        lines.append("")
        lines.append("Items that would improve the score the most, ordered by weighted impact:")
        lines.append("")
        for i, qw in enumerate(quick_wins, 1):
            lines.append(f"{i}. **+{qw.potential_points:.1f} pts** -- {qw.label}")
        lines.append("")

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    recs = _recommendations_for_grade(grade, categories)
    lines.append("## Recommendations")
    lines.append("")
    for rec in recs:
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    report = generate_report(target)

    output_path = target.resolve() / "production-readiness-report.md"
    output_path.write_text(report, encoding="utf-8")

    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
