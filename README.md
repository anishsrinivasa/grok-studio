# grok-studio

**An agentic Roblox studio inside Grok Bot.** Install the plugin, run one setup command,
and you get a team of five Grok Bots that build a complete Roblox game in *your* Roblox
Studio from one prompt:

| Bot | Does |
|---|---|
| **Lead GrokBot** | talks to you, writes the game spec, plans and hands out tasks, runs playtests, final gate |
| **Coding GrokBot** | all Luau: server services, remotes with validation, DataStores, client controllers |
| **Designer GrokBot** | UI (HUD, menus, shops) in Studio, optional Figma, icon and thumbnails |
| **Builder GrokBot** | the world and every 3D model, in Studio (parts, procedural and generated models) and in Blender |
| **Animator GrokBot** | rigs and animations (Luau keyframes in Studio, or Blender) |

The Bots message each other directly, work in parallel, and share one cloud computer and
one `game-spec.json`. They follow a team protocol, so five agents in one Studio don't
break each other's work.

Also works in **Claude Code / Grok Build / Cursor**: the same roles ship as subagents in
`agents/` (redirect files; canonical source is `roles/`), and the main session plays the Lead.

> Status: **v0.2.0, early.** The bridge was run end to end against a live Studio on
> Windows. The multi-bot flow has not yet done a full build. See [Limitations](#limitations).

---

## Run it on Grok Bot

**You do only this:**
1. **Install the plugin.** Until it's listed on the marketplace, paste this to any Grok Bot:
   > Run `curl -fsSL https://raw.githubusercontent.com/anishsrinivasa/grok-studio/multi-bot-team/scripts/bootstrap.sh | bash`
   > and do what it prints.

   It downloads the plugin into `/workspace/grok-studio/plugin` and links the skills. If
   they don't show up as skills, the Bot imports each one.
2. **Roblox Studio:** install it, sign in, open or create a place, turn on **Team Create**,
   and enable **Assistant > ... > Manage MCP Servers > Enable Studio as MCP server**. In
   Grok Bot, set **Settings > General > Bot > Execution on Local Computer** to *Ask every
   time*.
3. **Type `/setup-bridge`.** Paste keys only when it opens the secret prompt:
   - the Roblox Open Cloud key: it shows the link and the scopes
   - an ngrok authtoken and static domain, if ngrok isn't set up yet
4. **Approve** the first-time PC and firewall prompts, and create a **Grok Studio** sidebar
   section if it asks (Bots can't).

**`/setup-bridge` does the rest:**
- checks the Open Cloud key's scopes and owner without printing it
- installs Node and the bridge on your PC as a background service. The service survives
  restarts, uses one stable key and a static URL, and the Studio connector is registered
  once.
- installs headless Blender on the Bots' cloud computer
- creates the team Bots
- runs a readiness gate:
  - the team reaches the same Studio place and Blender
  - a Blender-to-Studio model round trip (upload, insert, import checks, then the test
    model is deleted)
  - a 5-second Luau play test
  - a screen capture

It says **ready** only when the gate passes. Then describe the game right there (it goes
to **Lead GrokBot**), or in Lead GrokBot:

> Make a co-op tycoon where players run a volcano-powered hot sauce factory. Conveyor
> droppers make sauce bottles, players collect cash, buy upgrades and unlock a second
> floor. Low-poly cartoon style, mobile-friendly UI, no monetization. Save progress.
> Make a thumbnail and icon.

**Afterwards:** every task starts with a health check that reconnects on its own. If
anything is off, run `/setup-bridge` again: it only repairs what's broken. **Stop:** tell
a grok-studio Bot "disconnect Studio".

## How it works

```mermaid
flowchart LR
   U([You]) <--> L[Lead GrokBot]
    L -- TASK / FIX --> C[Coding] & D[Designer] & B[Builder] & A[Animator] & V[VFX] & S[SFX] & M[Marketing]
    C & D & B & A & V & S & M -- DONE / BLOCKED / ASK --> L
    subgraph Cloud computer shared by all Bots
      SPEC[(/workspace/grok-studio/games/slug/<br/>game-spec.json, locks, .blend files, exports)]
      BL[headless Blender]
    end
    C & D & B & A & V & S & M & L --- SPEC
    B & A --- BL
    subgraph Your PC
      BR[bridge: supergateway + tunnel] --> ST[Roblox Studio MCP] --> RS[Roblox Studio]
      BR --> FD[file drop<br/>~/grok-studio/drop]
    end
    C & D & B & A & V & S & M & L -- one shared roblox-studio connector --> BR
```

- **Studio** stays on your PC (it only runs on Windows/macOS). The bridge exposes it to
  the cloud Bots behind one authenticated, static URL (a background service with a stable key). See
  [`bridge/README.md`](bridge/README.md).
- **Blender** runs headless on the cloud computer. Models reach Studio through an Open Cloud
  upload (automatic, if you add a key) or one **Import 3D** click per batch, with the file
  already dropped on your PC.
- **Team protocol** ([`skills/team-protocol`](skills/team-protocol/SKILL.md)):
  - every Bot writes only its own part of the place and of the spec
  - only the Lead plays the game (a `studio-play` lock, so nobody edits while play mode
    is on)
  - specialists never message the user; only the Lead talks to the user
  - the Lead collects gated approvals (uploads, publishes) from the user at preflight and
    executes the gated actions when specialists report exports are ready
  - spec writes take a lock
  - one `.blend` file per asset
  - fixed `TASK` / `DONE` / `BLOCKED` / `ASK` / `READY-UPLOAD` / `UPLOADED` / `FIX` message formats

## What's inside

```
.cursor-plugin/plugin.json   Cursor / Grok Bot plugin manifest
.claude-plugin/plugin.json   Claude Code plugin manifest
mcp.json, .mcp.json          MCP servers (local agents; Grok Bot uses the bridge)
roles/                       Role manifests and agent instructions (8 roles: lead, coder, designer, builder, animator, vfx, sfx, marketing)
  <role-id>/
    manifest.json            Machine-readable role definition
    agent.md                 Agent instructions
    example-*.md             Example task or artifact
agents/                      Legacy agent files (kept for compatibility; roles/ is canonical)
skills/
  setup-bridge/              /setup-bridge: the one setup command - Studio, the Bots, Blender, smoke test
  team-protocol/             workspace layout, ownership, locks, message formats
  grok-studio/               Lead playbook: preflight, spec, plan, dispatch, playtests, gate, handoff
  connect-studio/            persistent bridge on the user's PC (local execution): install, status, restart, connector
  game-spec/                 prompt -> game-spec.json (+ schema.json, example)
  roblox-code/               Luau architecture, remotes, DataStores, anti-exploit (+ reference/*.luau)
  roblox-ui/                 Studio-direct ScreenGui builder, Figma path (+ reference/UiKit.luau)
  roblox-building/           maps, terrain, lighting, tagged parts, Studio generation tools
  roblox-vfx/                particle effects, beams, trails, explosions, screen effects
  roblox-audio/              sound sourcing from Creator Store, SoundGroups, mixing, 3D spatial audio
  blender-assets/            headless cloud Blender, checkpoints, review renders, FBX export, upload
  roblox-animations/         R15 keyframes in Luau or Blender, ids, publishing
  playtest-loop/             play, simulate input, read logs, route fixes, report
  thumbnail-and-icon/        512x512 icon, 1920x1080 thumbnails
  marketing-social/          X (Twitter) marketing drafts and posting (post-ship)
bridge/                      start-bridge.ps1 / .sh, files-server.mjs (file drop)
scripts/                     bootstrap.sh, roles.py (role discovery/validation), opencloud_upload.py, validate.py
setup/                       Declarative setup flow definitions, welcome template
rules/roblox-luau.mdc        Luau conventions (Cursor rule)
CONTRIBUTING.md              Add your own GrokBot role
```

## Local agents (Claude Code, Cursor, Grok Build)

Studio on the same machine, no bridge needed.
- **Claude Code:** `claude --plugin-dir /path/to/grok-studio` (or a marketplace you
  control). It reads `.claude-plugin/plugin.json`, `skills/`, `agents/` and `.mcp.json`.
  Then: *"Use the grok-studio skill to build ..."*. The main session is the Lead, and
  `coder`/`designer`/`builder`/`animator` run as subagents.
- **Cursor:** copy the folder (not a symlink) into `~/.cursor/plugins/local/grok-studio`,
  then **Developer: Reload Window**.
- **Requirements:** Node.js LTS (`npx`), uv (`uvx`) for the local Blender MCP (optional),
  Blender with the MCP for Blender add-on (`uvx mcp-for-blender setup`, optional).
- **Avoid duplicate tools:** if Studio's *Quick connect* or `mcp-for-blender setup` already
  added `Roblox_Studio`/`blender` to your client, remove those entries or disable this
  plugin's copies.

## Connector setup reference

### 1. Roblox Studio MCP (required)
- Built into Studio; local **stdio** process. Official configs
  ([docs](https://create.roblox.com/docs/studio/mcp)):
  - Windows: `cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat`
  - macOS: `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP`
- Tools used: `list_roblox_studios`, `script_read`, `multi_edit`, `script_search`,
  `script_grep`, `execute_luau`, `search_game_tree`, `inspect_instance`, `search_asset`,
  `insert_asset`, `generate_mesh`, `generate_material`, `generate_procedural_model`,
  `get_studio_state`, `start_stop_play`, `get_console_output`, `screen_capture`,
  `character_navigation`, `user_keyboard_input`, `user_mouse_input`, `subagent`, `skill`.
  Every call takes a `studio_id`.

**How this plugin handles the OS difference.** A plugin `mcp.json` can't be OS-conditional,
so instead of asking every user to configure a path, the `roblox-studio` entry runs
`node ${CURSOR_PLUGIN_ROOT}/scripts/studio-mcp.mjs` (Claude Code: `${CLAUDE_PLUGIN_ROOT}`).
The launcher picks the right binary per OS, passes stdio straight through, and writes
diagnostics to stderr only. Override with the environment variable
`ROBLOX_STUDIO_MCP_PATH` for non-standard installs. We deliberately did **not** use a
Cursor plugin variable (`${ROBLOX_STUDIO_MCP_COMMAND}`): variables are set by admins in the
dashboard (Plugins > Configure), would force every user to configure something, and the
docs don't promise substitution inside `command`. Zero-config wins.

### 2. Blender MCP (optional, recommended)
- `uvx mcp-for-blender` (PyPI package formerly `blender-mcp`; `uvx blender-mcp` still
  works) - [github.com/ahujasid/mcp-for-blender](https://github.com/ahujasid/mcp-for-blender).
- Add-on: `uvx mcp-for-blender setup` or `uvx mcp-for-blender install-addon`, then enable
  **Interface: MCP for Blender** in Preferences > Add-ons.
- This plugin sets `BLENDER_MCP_SAFE_MODE=1`: scripts that touch arbitrary files, the
  network, or spawn processes are blocked; modeling, materials, rendering, saving, and
  import/export still work.
- **Alternative:** Blender's official [Blender Lab MCP server](https://www.blender.org/lab/mcp-server/)
  (Blender 5.1+, add-on from the Blender Lab repository). Its tool set differs; the
  `blender-assets` skill is written against mcp-for-blender but the bpy code it sends is
  portable. Blender Lab warns that it runs LLM-generated code without guards.

### 3. Figma MCP (optional)
- Remote server `https://mcp.figma.com/mcp`, OAuth on first use
  ([docs](https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/)).
- Canvas writes (`use_figma`) are documented for Professional, Education, Organization and
  Enterprise plans (beta, free during beta). Read tools are rate-limited: View/Collab seats
  up to 20 calls/month; Full/Dev seats on Professional up to 200/day
  ([rate limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/)).
  On a Starter plan, expect to use the Studio-direct UI path.
- Figma also ships its own Cursor/Claude plugin with Figma skills; you can use that instead
  of this entry.

## Security

- **MCP servers here execute code.** Studio MCP runs Luau in your open places; Blender MCP
  runs Python in Blender. Only connect agents you trust, and work in a scratch place or
  keep a `.rbxl` backup.
- **Bridge:** it runs as a background service with a static URL and one stable key. While
  your PC is on, anyone holding the URL + key can run Luau in your open Studio places and
  write files into `~/grok-studio/drop`. Mitigations:
  - a 256-bit key readable only by your user account
  - the gateway listens only on this PC (loopback) behind the tunnel
  - requests without the key get HTTP 401
  - Blender on the PC is off by default (opt-in, safe mode)
  - `restart -RotateKey` replaces the key: do it if it ever leaks
  - `stop` or `uninstall-service` turns the bridge off
  Work in a scratch place, or rely on Team Create's version history.
- **Free models:** the skills inspect inserted Creator Store assets for suspicious scripts
  (`require(` by ID, `loadstring`, `getfenv`) - still review them.
- **API keys:** Open Cloud keys are only used from outside Ro