#!/usr/bin/env bash
set -euo pipefail

# production-stack-skills uninstaller
# Removes from BOTH ~/.claude/ and ~/.agents/.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/vstorm-co/production-stack-skills/main/uninstall.sh | bash
#   OR: ./uninstall.sh

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

# ── Detect interactive mode ───────────────────────────────────────────
INTERACTIVE=true
if [ ! -t 0 ]; then
    INTERACTIVE=false
fi

# ── Header ────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}  Uninstall production-stack-skills${NC}"
echo ""

TARGET_BASES=("${HOME}/.claude" "${HOME}/.agents")

# ── Show what will be removed ─────────────────────────────────────────
info "The following will be removed:"
echo ""

FOUND=0
for BASE_DIR in "${TARGET_BASES[@]}"; do
    SKILLS_DIR="${BASE_DIR}/skills"
    AGENTS_DIR="${BASE_DIR}/agents"

    if [ -d "$SKILLS_DIR/production" ]; then
        echo -e "    ${DIM}Orchestrator:${NC}  $SKILLS_DIR/production/"
        ((FOUND++))
    fi

    for skill_dir in "$SKILLS_DIR"/production-*/; do
        [ -d "$skill_dir" ] || continue
        echo -e "    ${DIM}Skill:${NC}         $skill_dir"
        ((FOUND++))
    done

    for agent_file in "$AGENTS_DIR"/production-*.md; do
        [ -f "$agent_file" ] || continue
        echo -e "    ${DIM}Agent:${NC}         $agent_file"
        ((FOUND++))
    done
done

echo ""

if [ "$FOUND" -eq 0 ]; then
    info "Nothing to remove — production-stack-skills is not installed."
    echo ""
    exit 0
fi

# ── Confirmation ──────────────────────────────────────────────────────
if [ "$INTERACTIVE" = true ]; then
    echo -ne "  Remove ${FOUND} components? ${DIM}[y/N]${NC} "
    read -r REPLY
    if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
        info "Cancelled."
        echo ""
        exit 0
    fi
else
    info "Non-interactive mode — proceeding with removal."
fi

echo ""

# ── Remove components ─────────────────────────────────────────────────
REMOVED=0
for BASE_DIR in "${TARGET_BASES[@]}"; do
    SKILLS_DIR="${BASE_DIR}/skills"
    AGENTS_DIR="${BASE_DIR}/agents"

    if [ -d "$SKILLS_DIR/production" ]; then
        rm -rf "$SKILLS_DIR/production"
        ok "Removed $SKILLS_DIR/production"
        ((REMOVED++))
    fi

    for skill_dir in "$SKILLS_DIR"/production-*/; do
        [ -d "$skill_dir" ] || continue
        rm -rf "$skill_dir"
        ok "Removed $skill_dir"
        ((REMOVED++))
    done

    for agent_file in "$AGENTS_DIR"/production-*.md; do
        [ -f "$agent_file" ] || continue
        rm -f "$agent_file"
        ok "Removed $agent_file"
        ((REMOVED++))
    done
done

echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  ${GREEN}${BOLD}Uninstall complete.${NC} Removed ${REMOVED} components."
echo ""
echo -e "  ${DIM}To reinstall:${NC}"
echo -e "    curl -fsSL https://raw.githubusercontent.com/vstorm-co/production-stack-skills/main/install.sh | bash"
echo ""
