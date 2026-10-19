# grok-studio

**An agentic Roblox studio inside Grok Bot.** Install the plugin, call the Lead, and setup starts automatically. You get a team of eight Grok Bots that build a complete Roblox game in *your* Roblox Studio from one prompt:

| Bot | Does |
|---|---|
| **Lead GrokBot** | talks to you, writes the game spec, plans and hands out tasks, runs playtests, final gate |
| **Coding GrokBot** | all Luau: server services, remotes with validation, DataStores, client controllers |
| **Designer GrokBot** | UI (HUD, menus, shops) in Studio, optional Figma |
| **Builder GrokBot** | the world and every 3D model, in Studio (parts, procedural and generated models) and in Blender |
| **Animator GrokBot** | rigs and animations (Luau keyframes in Studio, or Blender) |
| **VFX GrokBot** | particle effects, beams, trails, explosions, screen post-effects |
| **SFX GrokBot** | sound design via Creator Store, SoundGroups, mixing, spatial audio |
| **Marketing GrokBot** | icons, thumbnails, and post-ship X (Twitter) marketing drafts |

The Bots message each other directly, work in parallel, and share one cloud computer and
one `game-spec.json`. They follow a team protocol, so eight agents in one Studio don't
break each other's work.

---

## Install and Run

**Quick start (3 steps):**

1. **Install the plugin** - Paste this to any Grok Bot:
   ```
   Run curl -fsSL https://raw.githubusercontent.com/anishsrinivasa/grok-studio/main/scripts/bootstrap.sh | bash and do what it prints.
   ```
   Downloads the plugin into `/workspace/grok-studio/plugin` and links the skills.

2. **Install Roblox Studio** - Sign in, open or create a place, turn on **Team Create**, and enable **Assistant > ... > Manage MCP Servers > Enable Studio as MCP server**.

3. **Call the Lead** - Message **Lead GrokBot** (it's created automatically):
   ```
   Hi! Let's set up grok-studio.
   ```
   
   **Setup starts automatically.** It will:
   - Auto-detect Studio, bridge, Blender, API keys
   - Show you templated step cards for any missing requirements
   - Ask capability questions (Figma seat type, X posting route, animation planning)
   - Collect upfront approvals (upload models, publish animations)
   - Generate a dynamic welcome message listing every active bot (with full vs fallback capabilities) and any disabled bots with requirements

**Then describe your game:**
> Make a co-op tycoon where players run a volcano-powered hot sauce factory. Conveyor
> droppers make sauce bottles, players collect cash, buy upgrades and unlock a second
> floor. Low-poly cartoon style, mobile-friendly UI, no monetization. Save progress.
> Make a thumbnail and icon.

**Afterwards:** every task starts with a health check. If anything breaks, message Lead GrokBot "reconnect Studio" or "run setup again".

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
