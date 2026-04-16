#!/usr/bin/env bash
set -euo pipefail

# production-stack-skills installer
# Installs to BOTH ~/.claude/ and ~/.agents/ so the same skills work with
# Claude Code, Codex, and any AGENTS.md-compatible agent CLI.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/vstorm-co/production-stack-skills/main/install.sh | bash
#   OR: git clone + ./install.sh (uses local files)

REPO_URL="https://github.com/vstorm-co/production-stack-skills.git"
BRANCH="main"

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "  ${BLUE}INFO${NC}  $*"; }
ok()    { echo -e "  ${GREEN} OK ${NC}  $*"; }
warn()  { echo -e "  ${YELLOW}WARN${NC}  $*"; }
fail()  { echo -e "  ${RED}FAIL${NC}  $*"; }

# ── Detect interactive mode ───────────────────────────────────────────
INTERACTIVE=true
if [ ! -t 0 ]; then
    INTERACTIVE=false
fi

# ── Header ────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}  production-stack-skills${NC}"
echo -e "  ${DIM}Stop shipping demo-quality code.${NC}"
echo -e "  ${DIM}By Vstorm — vstorm.co${NC}"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Phase 1: Prerequisites ────────────────────────────────────────────
info "Checking prerequisites..."

# Git
if command -v git &>/dev/null; then
    ok "git $(git --version | awk '{print $3}')"
else
    fail "git not found — required for remote install"
    exit 1
fi

# Python
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VERSION=$("$cmd" --version 2>&1 | awk '{print $2}')
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 8 ]; then
            PYTHON_CMD="$cmd"
            ok "Python ${PY_VERSION}"
            break
        fi
    fi
done
if [ -z "$PYTHON_CMD" ]; then
    warn "Python 3.8+ not found — audit scripts won't work (skills still install)"
fi

# Agent CLI detection (informational)
DETECTED_CLIS=()
if command -v claude &>/dev/null; then
    DETECTED_CLIS+=("Claude Code")
fi
if command -v codex &>/dev/null; then
    DETECTED_CLIS+=("Codex")
fi
if [ "${#DETECTED_CLIS[@]}" -gt 0 ]; then
    ok "Detected agent CLI(s): ${DETECTED_CLIS[*]}"
else
    warn "No agent CLI detected — skills will install but won't activate until one is available"
    echo -e "       Install Claude Code: ${DIM}https://docs.anthropic.com/en/docs/claude-code${NC}"
fi

echo ""

# ── Phase 2: Source detection ─────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
TEMP_DIR=""
SOURCE_DIR=""

if [ -f "$SCRIPT_DIR/production/SKILL.md" ]; then
    SOURCE_DIR="$SCRIPT_DIR"
    info "Installing from local directory: ${SOURCE_DIR}"
else
    TEMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TEMP_DIR"' EXIT
    info "Cloning from GitHub..."
    if git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TEMP_DIR/repo" 2>/dev/null; then
        SOURCE_DIR="$TEMP_DIR/repo"
        ok "Repository cloned"
    else
        fail "Failed to clone repository from ${REPO_URL}"
        exit 1
    fi
fi

echo ""

# ── Phase 3: Install to each target (Claude Code + AGENTS.md spec) ────
# Mirror the same install into both ~/.claude/ and ~/.agents/ so skills
# work with any agent CLI that follows either convention.
TARGET_BASES=("${HOME}/.claude" "${HOME}/.agents")

INSTALLED_TOTAL=0
FAILED_TOTAL=0
AGENT_COUNT_TOTAL=0
SCRIPT_COUNT_TOTAL=0
CHECKLIST_COUNT_TOTAL=0

for BASE_DIR in "${TARGET_BASES[@]}"; do
    SKILLS_DIR="${BASE_DIR}/skills"
    AGENTS_DIR="${BASE_DIR}/agents"
    INSTALL_DIR="${SKILLS_DIR}/production"

    info "Installing to ${BOLD}${BASE_DIR}${NC}..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/scripts"
    mkdir -p "$INSTALL_DIR/checklists"
    mkdir -p "$AGENTS_DIR"

    INSTALLED=0
    FAILED=0

    # Main orchestrator
    if cp "$SOURCE_DIR/production/SKILL.md" "$INSTALL_DIR/SKILL.md" 2>/dev/null; then
        ok "production (orchestrator)"
        ((INSTALLED++))
    else
        fail "production (orchestrator)"
        ((FAILED++))
    fi

    # Sub-skills
    for skill_dir in "$SOURCE_DIR"/skills/*/; do
        [ -d "$skill_dir" ] || continue
        skill_name=$(basename "$skill_dir")
        target_dir="${SKILLS_DIR}/${skill_name}"
        mkdir -p "$target_dir"

        if cp -r "$skill_dir"* "$target_dir/" 2>/dev/null; then
            ok "$skill_name"
            ((INSTALLED++))
        else
            fail "$skill_name"
            ((FAILED++))
        fi
    done

    # Subagent files
    AGENT_COUNT=0
    for agent_file in "$SOURCE_DIR"/agents/*.md; do
        [ -f "$agent_file" ] || continue
        agent_name=$(basename "$agent_file")
        if cp "$agent_file" "$AGENTS_DIR/$agent_name" 2>/dev/null; then
            ((AGENT_COUNT++))
        fi
    done
    if [ "$AGENT_COUNT" -gt 0 ]; then
        ok "${AGENT_COUNT} audit agents"
    fi

    # Python scripts
    SCRIPT_COUNT=0
    if [ -d "$SOURCE_DIR/scripts" ]; then
        for script_file in "$SOURCE_DIR"/scripts/*.py; do
            [ -f "$script_file" ] || continue
            cp "$script_file" "$INSTALL_DIR/scripts/"
            chmod +x "$INSTALL_DIR/scripts/$(basename "$script_file")"
            ((SCRIPT_COUNT++))
        done
    fi
    if [ "$SCRIPT_COUNT" -gt 0 ]; then
        ok "${SCRIPT_COUNT} audit scripts"
    fi

    # Checklists
    CHECKLIST_COUNT=0
    if [ -d "$SOURCE_DIR/checklists" ]; then
        for checklist_file in "$SOURCE_DIR"/checklists/*.md; do
            [ -f "$checklist_file" ] || continue
            cp "$checklist_file" "$INSTALL_DIR/checklists/"
            ((CHECKLIST_COUNT++))
        done
    fi
    if [ "$CHECKLIST_COUNT" -gt 0 ]; then
        ok "${CHECKLIST_COUNT} reference checklists"
    fi

    INSTALLED_TOTAL=$((INSTALLED_TOTAL + INSTALLED))
    FAILED_TOTAL=$((FAILED_TOTAL + FAILED))
    AGENT_COUNT_TOTAL=$((AGENT_COUNT_TOTAL + AGENT_COUNT))
    SCRIPT_COUNT_TOTAL=$((SCRIPT_COUNT_TOTAL + SCRIPT_COUNT))
    CHECKLIST_COUNT_TOTAL=$((CHECKLIST_COUNT_TOTAL + CHECKLIST_COUNT))

    echo ""
done

# ── Phase 4: Summary ─────────────────────────────────────────────────
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$FAILED_TOTAL" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}Installation complete!${NC}"
else
    echo -e "  ${YELLOW}${BOLD}Installation completed with ${FAILED_TOTAL} warning(s).${NC}"
fi

echo ""
echo -e "  ${DIM}Installed to:${NC}  ~/.claude/skills/production* + ~/.agents/skills/production*"
echo -e "  ${DIM}Works with:${NC}    Claude Code, Codex, and any AGENTS.md-compatible agent CLI"
echo -e "  ${DIM}Skills:${NC}        ${INSTALLED_TOTAL} components (across both targets)"
echo -e "  ${DIM}Agents:${NC}        ${AGENT_COUNT_TOTAL} audit agents"
echo -e "  ${DIM}Scripts:${NC}       ${SCRIPT_COUNT_TOTAL} Python scripts"
echo -e "  ${DIM}Checklists:${NC}    ${CHECKLIST_COUNT_TOTAL} reference docs"

echo ""
echo -e "  ${BOLD}Commands:${NC}"
echo -e "    ${CYAN}/production check${NC}      Full audit with 0-100 score"
echo -e "    ${CYAN}/production fastapi${NC}    FastAPI production patterns"
echo -e "    ${CYAN}/production postgres${NC}   PostgreSQL safety"
echo -e "    ${CYAN}/production docker${NC}     Container hardening"
echo -e "    ${CYAN}/production deploy${NC}     Pre-deployment checklist"
echo -e "    ${CYAN}/production monitoring${NC} Observability setup"
echo -e "    ${CYAN}/production security${NC}   Security hardening"
echo -e "    ${CYAN}/production errors${NC}     Error handling patterns"
echo -e "    ${CYAN}/production review${NC}     Code review"
echo -e "    ${CYAN}/production plan${NC}       Architecture planning"

echo ""
echo -e "  ${DIM}Documentation:${NC} https://github.com/vstorm-co/production-stack-skills"
echo -e "  ${DIM}Uninstall:${NC}     curl -fsSL https://raw.githubusercontent.com/vstorm-co/production-stack-skills/main/uninstall.sh | bash"
echo ""
echo -e "  Built by ${BOLD}Vstorm${NC} — vstorm.co"
echo ""
