---
name: grok-studio-setup
description: One-time (and re-runnable) setup for grok-studio on Grok Bot - creates the Lead, Designer, Animator, Builder and Coding GrokBots with their instructions, installs headless Blender on the cloud computer, connects the user's Roblox Studio through the bridge, checks Figma, and smoke-tests that every bot can reach Studio. Use when the user says "set up grok studio", "install the team", "create the bots", right after installing the plugin, or when a bot finds the team or connectors missing.
user-invocable: true
argument-hint: "[--no-figma] [--no-blender] [--reconnect]"
---

# grok-studio setup

Goal: after installing the plugin, the user types `/grok-studio-setup` once and ends up with
a working team. Do the steps in order, tell the user in one short line what you're on,
and only stop for things that need them (approvals, sign-ins, opening Studio).

`<plugin>` below means `/workspace/grok-studio/plugin` on Grok Bot (Step 1 creates it),
or the plugin's root folder (two levels up from this SKILL.md) on a local agent.

## Step 0 - Where am I?

- **Grok Bot** (cloud Linux computer, `/workspace` exists, other Bots can be created):
  do every step below.
- **Local agent** (Claude Code, Cursor or Grok Build on the user's PC): there are no
  separate Bots. The team runs as subagents from `<plugin>/agents/` (`designer`,
  `animator`, `builder`, `coder`), and the main session acts as the Lead with the
  `grok-studio` skill. Studio connects through the plugin's own MCP config. Skip to Step 4
  (check Studio with `list_roblox_studios`) and Step 5, then finish.
- `--reconnect`: the team already exists and the bridge died (new day, PC restarted).
  Do Step 4 only, then Step 6.

## Step 1 - Workspace and plugin files

Every Bot needs the plugin's files (role instructions, the Blender installer, helper
scripts) at one fixed path, `/workspace/grok-studio/plugin`:

```bash
GS=/workspace/grok-studio
mkdir -p "$GS/games" "$GS/.tools"
if [ ! -f "$GS/plugin/skills/team-protocol/SKILL.md" ]; then
  # 1) the installed plugin, if this computer has its files
  SRC=$(find / -path '*/skills/grok-studio-setup/SKILL.md' -not -path "$GS/*" 2>/dev/null | head -n1)
  if [ -n "$SRC" ]; then
    ln -sfn "$(dirname "$(dirname "$(dirname "$SRC")")")" "$GS/plugin"
  else
    # 2) otherwise the same version from GitHub (version = the one in this plugin's manifest)
    VER=0.2.0
    rm -rf "$GS/plugin.tmp" && mkdir -p "$GS/plugin.tmp"
    { curl -fsSL "https://github.com/brain-xiang/grok-studio/archive/refs/tags/v$VER.tar.gz" ||
      curl -fsSL "https://github.com/brain-xiang/grok-studio/archive/refs/heads/main.tar.gz"; } |
      tar -xz -C "$GS/plugin.tmp" --strip-components=1
    rm -rf "$GS/plugin" && mv "$GS/plugin.tmp" "$GS/plugin"
  fi
fi
ls "$GS/plugin/agents" "$GS/plugin/scripts"
```

If neither works, stop and tell the user. Every later step needs these files. On
`--reconnect`, skip this when the folder already exists.

## Step 2 - Create the team

Create these Bots (skip any that already exist with the same name). For each one, set the
name, the title, the sidebar section **Grok Studio**, and the instructions: the text of the
listed file **without** its `---` frontmatter block. Copy the text exactly. Don't
summarize it, because the instructions are the Bot's standing orders.

| Name | Title | Instructions file |
|---|---|---|
| Lead GrokBot | Producer: plans the game, runs the team, playtests | `<plugin>/skills/grok-studio-setup/lead-bot.md` |
| Coding GrokBot | Programmer: all Luau scripts | `<plugin>/agents/coder.md` |
| Designer GrokBot | UI designer: HUD, menus, icon, thumbnails | `<plugin>/agents/designer.md` |
| Builder GrokBot | World builder + 3D modeler (Studio and Blender) | `<plugin>/agents/builder.md` |
| Animator GrokBot | Animator: rigs and animations | `<plugin>/agents/animator.md` |

Skills are shared by all of the user's Bots, so there is nothing to attach. Each Bot's
instructions name the skills it uses.

If a Bot with that name exists but its instructions differ from the file (an older plugin
version), show the user the Bot names and ask once whether to update them all. Never
delete a Bot.

After creating them, message each new Bot:

```
[GS] HELLO from setup. Load the team-protocol skill and your role skills, then reply
"READY <role>" in one line.
```

Wait for all five `READY` replies. A Bot that doesn't answer within a few minutes is
reported in Step 6 instead of blocking setup.

If you are not Lead GrokBot yourself, from now on you only relay: the Lead owns the user's
PC and the builds.

## Step 3 - Blender on the cloud computer (skip with `--no-blender`)

Builder and Animator run Blender headless on the shared cloud computer, so the user needs
nothing installed for it.

```bash
bash <plugin>/skills/blender-assets/reference/cloud_blender.sh install
bash <plugin>/skills/blender-assets/reference/cloud_blender.sh version
```

The first install downloads Blender (a few hundred MB) into `/workspace/grok-studio/.tools`.
It only needs to happen once per account. If it fails (no space, unsupported CPU), report
it in Step 6: the team then builds models in Studio only (`roblox-building`).

## Step 4 - Connect the user's Roblox Studio

Studio only runs on Windows or macOS, so it stays on the user's PC and is reached through
the bridge. Only **Lead GrokBot** touches the user's PC.

- If you are the Lead: run the `setup-bridge` skill now.
- Otherwise send the Lead:
  ```
  [GS] TASK setup-bridge: connect the user's Roblox Studio (setup-bridge skill), write
  /workspace/grok-studio/.bridge.json, reply DONE with the Studio window name.
  ```
  Then tell the user: "Lead GrokBot is connecting your Studio. Approve its PC commands in
  its chat, and keep Roblox Studio open with your place."

Before the bridge, the user must have Roblox Studio open with a place and **Assistant >
... > Manage MCP Servers > Enable Studio as MCP server** turned on. `setup-bridge` checks
this and explains it if it's missing.

## Step 5 - Optional connectors

- **Figma** (skip with `--no-figma`): call the Figma connector's `whoami`. If it asks for
  sign-in, the user clicks **Authorize** once. Free Figma plans can only read, and only
  about 20 calls a month, so Designer builds UI directly in Studio either way. Never block
  on Figma.
- **Roblox Open Cloud key** (optional, ask once): with a key, Builder's Blender models
  upload and insert into Studio automatically. Without one, each batch of models needs one
  **File > Import 3D** click from the user. If they want it:
  1. They create a key at https://create.roblox.com/dashboard/credentials with the **Assets
     API** (read + write) for their account. Leave the IP list open, or add the cloud
     computer's IP if they know it.
  2. They give it to you as a Grok Bot **secret** named `ROBLOX_OPEN_CLOUD_API_KEY`, plus
     their numeric user id as `ROBLOX_CREATOR_USER_ID` (or `ROBLOX_CREATOR_GROUP_ID` for a
     group game). Never ask for it in plain chat, and never write it to `/workspace`.
  3. Check that the shell sees it: `test -n "$ROBLOX_OPEN_CLOUD_API_KEY" && echo set`. If
     secrets are not exposed to the shell on this account, say so and fall back to the
     Import 3D route.

## Step 6 - Smoke test and report

The Lead sends every specialist:

```
[GS] TASK ping: call list_roblox_studios and get_studio_state (read-only) and reply
"DONE ping <studio name> <state>".
```

All four answering with the same Studio proves the shared connector works for parallel
Bots. Then give the user one short table:

| Part | Status |
|---|---|
| Bots | 5/5 ready (or which are missing) |
| Roblox Studio | connected to "<place name>" / not connected: <why> |
| Blender (cloud) | Blender <version> / not installed: <why> |
| Figma | signed in / read-only / skipped |
| Model uploads | automatic (Open Cloud key) / one Import 3D click per batch |

End with how to use it:
- **Build:** open Lead GrokBot and describe the game ("make a co-op tycoon where...").
- **Stop:** tell Lead GrokBot "disconnect Studio", or press Ctrl+C in the bridge window.
  The bridge key dies with it.
- **Next time:** `/grok-studio-setup --reconnect` (or just ask the Lead to build: it
  reconnects by itself).
