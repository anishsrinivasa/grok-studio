---
name: setup-bridge
description: >-
  The one command that sets up grok-studio on Grok Bot. Connects the user's Roblox Studio
  through the bridge, creates the Lead, Coding, Designer, Builder and Animator GrokBots,
  installs headless Blender on the cloud computer, checks Figma and an optional Open
  Cloud key, smoke-tests that every Bot reaches Studio, then hands the user's game idea
  to Lead GrokBot. Safe to re-run: it only reconnects or repairs what's missing. Use for
  "setup bridge", "set up grok studio", "connect Studio", right after installing the
  plugin, or when any Bot finds the team or Studio missing.
user-invocable: true
argument-hint: "[--no-figma] [--no-blender]"
---

# /setup-bridge: set up everything

After installing the plugin, the user runs `/setup-bridge` once and the team is ready to
build. Run the steps in order. Before each step, tell the user in one short line what
you're on. Only stop for what needs them: approving PC commands, opening Studio, signing
in. Re-running is safe: every step checks what already exists and skips or repairs it.

`<plugin>` = `/workspace/grok-studio/plugin` (Step 1 creates it).

## Step 1 - Plugin files and workspace (cloud computer)

The Bots need the plugin's files (Bot instructions, the Blender installer, helper scripts)
at one fixed path. Take them from wherever this skill was loaded. If that isn't known,
search for them, and as a last resort download the same version from GitHub:

```bash
GS=/workspace/grok-studio
mkdir -p "$GS/games" "$GS/.tools"
if [ ! -f "$GS/plugin/skills/setup-bridge/lead-bot.md" ]; then
  # a) the folder this SKILL.md was loaded from, two levels up (fill in if you know it)
  SRC_ROOT=""
  # b) otherwise search for it
  [ -z "$SRC_ROOT" ] && SRC_ROOT=$(timeout 60 find / -xdev -path '*/skills/setup-bridge/lead-bot.md' \
      -not -path "$GS/*" 2>/dev/null | head -n1 | sed 's#/skills/setup-bridge/lead-bot.md##')
  if [ -n "$SRC_ROOT" ]; then
    ln -sfn "$SRC_ROOT" "$GS/plugin"
  else
    # c) download: release tag, then the dev branch, then main
    VER=0.2.0
    for REF in tags/v$VER heads/multi-bot-team heads/main; do
      rm -rf "$GS/plugin.tmp" && mkdir -p "$GS/plugin.tmp"
      curl -fsSL "https://github.com/brain-xiang/grok-studio/archive/refs/$REF.tar.gz" |
        tar -xz -C "$GS/plugin.tmp" --strip-components=1 2>/dev/null &&
        [ -f "$GS/plugin.tmp/skills/setup-bridge/lead-bot.md" ] && break
    done
    rm -rf "$GS/plugin" && mv "$GS/plugin.tmp" "$GS/plugin"
  fi
fi
ls "$GS/plugin/agents" "$GS/plugin/scripts"
```

If this fails, stop and tell the user. Every later step needs these files.

Then start the Blender install **in the background** (skip with `--no-blender`, or if
`cloud_blender.sh version` already works). It downloads a few hundred MB, so let it run
while you do Step 2:

```bash
B="$GS/plugin/skills/blender-assets/reference/cloud_blender.sh"
bash "$B" version >/dev/null 2>&1 || nohup bash "$B" install > "$GS/.tools/blender-install.log" 2>&1 &
```

## Step 2 - Connect Roblox Studio (the user's PC)

Studio only runs on Windows or macOS, so it stays on the user's PC, and the bridge exposes
it to the cloud. Run the **`connect-studio`** skill now, here in this chat: the user
approves its PC commands here. It:
- checks Studio is open with **Enable Studio as MCP server** on, and that Node.js is
  installed (it offers to install it)
- starts the bridge and tunnel on the PC
- writes `/workspace/grok-studio/.bridge.json`
- registers or updates the one shared `roblox-studio` connector
- verifies with `list_roblox_studios`

If Studio already answers `list_roblox_studios` and `.bridge.json` exists, skip this
step. If more than one Studio window is open, ask the user which place to build in, and
remember its name for Step 7.

## Step 3 - Create the team

Create these Bots, skipping any that already exist with the same name. For each one, set
the name, the title, the sidebar section **Grok Studio**, and the instructions: the text of
the listed file **without** its `---` frontmatter block. Copy it exactly, without
summarizing.

| Name | Title | Instructions file |
|---|---|---|
| Lead GrokBot | Producer: plans the game, runs the team, playtests | `<plugin>/skills/setup-bridge/lead-bot.md` |
| Coding GrokBot | Programmer: all Luau scripts | `<plugin>/agents/coder.md` |
| Designer GrokBot | UI designer: HUD, menus, icon, thumbnails | `<plugin>/agents/designer.md` |
| Builder GrokBot | World builder + 3D modeler (Studio and Blender) | `<plugin>/agents/builder.md` |
| Animator GrokBot | Animator: rigs and animations | `<plugin>/agents/animator.md` |

Skills are shared by all of the user's Bots, so there is nothing to attach. If a Bot with
that name exists but has different instructions (an older plugin version), ask the user
once whether to update them all. Never delete a Bot.

Message each Bot:

```
[GS] HELLO from setup. Load the team-protocol skill and your role skills, then reply
"READY <role>" in one line.
```

Don't wait here. Collect the replies during Steps 4-6.

## Step 4 - Blender (cloud computer)

Wait for the background install from Step 1 (`tail "$GS/.tools/blender-install.log"`),
then check it:

```bash
bash "$GS/plugin/skills/blender-assets/reference/cloud_blender.sh" probe
```

`probe` renders a tiny test scene headless and picks the render engine (Workbench, or
Cycles on the CPU as a fallback).

If it failed (no space, unsupported CPU), say so in the Step 6 table. Builder and Animator
then work in Studio only.

## Step 5 - Optional connectors

- **Penpot** (optional, ask once): Penpot is a free, open-source design tool with MCP
  integration (https://penpot.app). If the user wants to design UI visually instead of
  building directly in Studio, check if Penpot MCP is available. Penpot can run:
  - Hosted at design.penpot.app (they open a file there and connect the MCP plugin)
  - Self-hosted via `npx @penpot/mcp` (local or remote server)
  Ask the user once if they want to connect Penpot. If yes, they need:
  1. A Penpot account (free at design.penpot.app or self-hosted)
  2. The MCP plugin loaded in their browser (development URL: http://localhost:4400/manifest.json
     when running locally; or the hosted MCP endpoint)
  3. An access token (stored as a secret: `PENPOT_ACCESS_TOKEN`)
  Test with a read-only MCP call (e.g., list files or current file). If it works, Penpot is
  available; if not or skipped, Designer uses Studio-direct by default. Never block on Penpot.
- **Figma** (skip with `--no-figma`): call the Figma connector's `whoami`. If it asks to
  sign in, the user clicks **Authorize** once. Free Figma plans can only read, about 20
  calls a month, so Designer builds UI directly in Studio either way. Never block on
  Figma.
- **Roblox Open Cloud key** (ask once, optional): with it, Builder's Blender models upload
  and insert into Studio automatically. Without it, each batch needs one **File > Import
  3D** click from the user, with the file already on their PC. If they want it:
  1. They create a key at https://create.roblox.com/dashboard/credentials with the
     **Assets API** (read + write) for their account (IP list open, or the cloud
     computer's IP).
  2. They save it through Grok Bot's secret prompt as `ROBLOX_OPEN_CLOUD_API_KEY`, plus
     their numeric user id as `ROBLOX_CREATOR_USER_ID` (or `ROBLOX_CREATOR_GROUP_ID`).
     Secrets are available to the shell as environment variables. Never take a key in
     plain chat, and never write it to `/workspace`.
  3. Check: `test -n "$ROBLOX_OPEN_CLOUD_API_KEY" && echo set`.

## Step 6 - Smoke test

Send each specialist:

```
[GS] TASK ping: call list_roblox_studios and get_studio_state (read-only) and reply
"DONE ping <studio name> <state>".
```

All four answering with the same Studio proves the shared connector works for Bots
running in parallel. Then show the user:

| Part | Status |
|---|---|
| Roblox Studio | connected to "<place name>" / not connected: <why> |
| Bots | 5/5 ready, or which are missing |
| Blender (cloud) | Blender <version> / not installed: <why> |
| Penpot | connected / skipped |
| Figma | signed in / read-only / skipped |
| Model uploads | automatic (Open Cloud key) / one Import 3D click per batch |

## Step 7 - Ready to build

Tell the user:
- **Build:** describe the game right here, or in Lead GrokBot. If they describe it here,
  send it to Lead GrokBot as `[GS] NEW GAME from the user: <their words, verbatim>` plus
  the Studio place name from Step 2, then say "Lead GrokBot is on it. Follow along there."
- **Stop:** tell any grok-studio Bot "disconnect Studio" (`connect-studio` disconnect
  section), or press Ctrl+C in the bridge window. The bridge key dies with it.
- **Next time:** run `/setup-bridge` again. It only reconnects Studio, because everything
  else is already there.
