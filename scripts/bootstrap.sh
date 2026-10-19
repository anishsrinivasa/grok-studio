#!/usr/bin/env bash
# bootstrap.sh - install grok-studio on a Grok Bot cloud computer without the plugin
# marketplace. Grok Bot has no "install from GitHub" path yet, so this downloads the
# plugin into /workspace/grok-studio/plugin, links its skills into the folders agent
# runtimes scan, and prints what to import if the skills still don't show up.
#
#   curl -fsSL https://raw.githubusercontent.com/anishsrinivasa/grok-studio/multi-bot-team/scripts/bootstrap.sh | bash
#
# Options (environment): GROK_STUDIO_REF=<branch or tag> (default multi-bot-team)
set -euo pipefail

REF="${GROK_STUDIO_REF:-multi-bot-team}"
GS=/workspace/grok-studio
[ -d /workspace ] || GS="$HOME/grok-studio"   # not on Grok Bot: install under $HOME
REPO=https://github.com/anishsrinivasa/grok-studio

mkdir -p "$GS/games" "$GS/.tools"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "[grok-studio] downloading $REPO ($REF) ..."
if command -v git >/dev/null 2>&1; then
  git clone -q --depth 1 --branch "$REF" "$REPO.git" "$tmp/src"
else
  case "$REF" in v[0-9]*) kind=tags ;; *) kind=heads ;; esac
  mkdir -p "$tmp/src"
  curl -fsSL "$REPO/archive/refs/$kind/$REF.tar.gz" | tar -xz -C "$tmp/src" --strip-components=1
fi
[ -f "$tmp/src/skills/setup-bridge/SKILL.md" ] || { echo "[grok-studio] ERROR: download incomplete" >&2; exit 1; }
# Record the commit for /setup-bridge's refresh check (tarball installs have no .git).
if [ ! -d "$tmp/src/.git" ]; then
  git ls-remote "$REPO.git" "refs/heads/$REF" 2>/dev/null | cut -f1 > "$tmp/src/.gs-commit" || true
fi

# Replace the plugin copy (never a symlink target the user owns).
[ -L "$GS/plugin" ] && rm -f "$GS/plugin"
rm -rf "$GS/plugin" && mv "$tmp/src" "$GS/plugin"
echo "[grok-studio] plugin files: $GS/plugin"

# Link each skill into the user-level skill folders agent runtimes read
# (~/.grok/skills for Grok, ~/.agents/skills for the AGENTS.md family).
for dir in "$HOME/.grok/skills" "$HOME/.agents/skills"; do
  mkdir -p "$dir"
  for s in "$GS/plugin/skills"/*/; do
    name="$(basename "$s")"
    ln -sfn "$GS/plugin/skills/$name" "$dir/$name"
  done
done

echo
echo "[grok-studio] skills:"
for s in "$GS/plugin/skills"/*/SKILL.md; do echo "  $(basename "$(dirname "$s")")  $s"; done
cat <<EOF

[grok-studio] Next:
  1. If /setup-bridge is not in your skills list yet, import each SKILL.md above as a
     skill with the same name (skills are shared by all your Bots, so once is enough).
  2. Run /setup-bridge.
EOF
