---
name: penpot-ui
description: Optional Penpot design path for Roblox UI. Design a screen as a Penpot board, extract it over the Penpot MCP, convert it to a scale-based ScreenGui spec, build it in Studio and verify it. Use only when the user wants to design in Penpot and the Penpot MCP is connected; otherwise use the Studio-direct path in roblox-ui.
---

# Penpot UI (optional)

Penpot (https://penpot.app) is an open-source design tool. Its free plan and self-hosting
cost nothing. This path is **strictly optional**: it is just another way to produce the
same ScreenGuis the Studio-direct path in `roblox-ui` builds.

**Never block on Penpot.** If the Penpot MCP is not connected, a call fails, or the user
didn't ask for Penpot, use Studio-direct (`roblox-ui`) and carry on. One retry at most.

`<plugin>` = `/workspace/grok-studio/plugin`. `CONV` = `<plugin>/converters/penpot-to-roblox`.
The converter needs only Node 18+ (`dist/` is committed, so no `npm install` or build step).

## Connecting (once, only if the user wants Penpot)

The Penpot MCP has two parts: an MCP server the agent talks to, and the MCP plugin inside
the user's open Penpot tab. MCP always acts on the page in focus in that tab.

- **Remote MCP** (recommended, nothing to install): the user goes to Your account →
  Integrations → MCP Server in Penpot, enables it, creates the MCP key, and copies the
  server URL (`https://<penpot host>/mcp/stream?userToken=<MCP key>`).
  **The URL contains the key.** Collect it only through Grok Bot's secret prompt, never in
  chat, files or logs, and register it as an HTTP MCP server named `penpot`. Then the user
  opens the design file and clicks File → MCP Server → Connect.
- **Local MCP** (only when the agent and the browser run on the same machine):
  `npx -y @penpot/mcp@stable`, load `http://localhost:4400/manifest.json` as a plugin in
  Penpot, click Connect, MCP endpoint `http://localhost:4401/mcp`. No key needed.

Check with a read-only call (`high_level_overview`). If it fails, say so once and fall back.
Help: https://help.penpot.app/mcp/

## Design rules (when you draw the board yourself via `execute_code`)

- One **board per screen**, 1920x1080, top level on the page. Board name = ScreenGui name
  (`Hud`, `Shop`). Layer names = instance names, the contract with Coding
  (`Hud/CoinCounter/Amount`): keep them stable and unique among siblings.
- The board's own fill is only a backdrop and is not built. Add a full-size rectangle named
  `Background` if the screen needs one.
- Set **constraints** on top-level elements (right/bottom/center) so they hug the right edge
  or corner on phones. Without them, the converter infers anchors from placement.
- Flex (row/column) → UIListLayout, uniform grids → UIGridLayout. Absolutely positioned
  children turn the layout off (fixed positions are kept).
- Containers whose name contains `Button`/`Btn` become TextButton (or ImageButton for images
  and vectors); their text child stays a TextLabel.
- Fonts: Roblox has its own catalogue. Mapped: Source Sans Pro (Penpot's default), Fredoka,
  Luckiest Guy, Gotham, Montserrat, Roboto, Roboto Mono, Arial, Bangers, Oswald, Nunito and
  more (`FONT_FAMILIES` in `src/converter.ts`). Anything else becomes Builder Sans, warned.
- Not supported (warned): shadows, blur, blend modes, letter spacing, justified text, mixed
  text styles inside one text, radial gradients (drawn linear).

## The loop

1. **Extract.** Read `CONV/penpot/extract_board.js`, set `BOARD` to the board name (or leave
   it empty to use the board around the selection), and pass the whole file as the `code` of
   the Penpot MCP `execute_code` tool. Save the returned JSON as
   `games/<slug>/penpot/<Board>.json`. Read-only.
2. **Convert.**
   ```bash
   node CONV/dist/cli.js games/<slug>/penpot/<Board>.json games/<slug>/penpot/<Board>.spec.json
   ```
   Warnings go to stderr. Read them: fix the design or note them in your DONE message.
3. **Images** (skip if the spec's `images` is empty). Put the spec's `images` array into
   `IMAGES` in `CONV/penpot/export_images.js`, run it with `execute_code` (in batches if the
   result is large), save the result, then:
   ```bash
   python3 CONV/penpot/save_images.py <result.json> games/<slug>/penpot/<Board>-images --upload
   ```
   This uploads through `<plugin>/scripts/opencloud_upload.py` (Open Cloud secrets from
   setup), caches by content hash, and writes `images.json` (`{key: "rbxassetid://..."}`).
   Without the Open Cloud key, drop `--upload` and tell the user which files to import.
4. **Build** with `execute_luau` (datamodel_type `Edit`):
   ```lua
   local Builder = (function()
   <contents of CONV/PenpotUIBuilder.luau>
   end)()
   local spec = [==[<contents of <Board>.spec.json>]==]
   local images = game:GetService("HttpService"):JSONDecode([==[<images.json or {}>]==])
   local screen, report = Builder.build(spec, { parent = game:GetService("StarterGui"), images = images })
   print(Builder.report(report))
   ```
   Rebuilding replaces the ScreenGui it built before. It refuses to replace a same-named
   ScreenGui it did not build, so hand-made UI is never destroyed.
5. **Verify** in the same or a new `execute_luau` call:
   ```lua
   local Verifier = (function()
   <contents of CONV/PenpotUIVerifier.luau>
   end)()
   local r = Verifier.verify(game:GetService("StarterGui")[<ScreenGui name>], spec)
   print(Verifier.report(r)) -- PASS/FAIL with every mismatch
   ```
   It checks every element (class, position, size, anchor, colours, text, font, corner,
   stroke, gradient, layout, padding) and that each visible element is on screen. Then
   `screen_capture` in Edit mode and compare with `export_shape` of the board in Penpot.
   Check phone and tablet sizes as `roblox-ui` describes.
6. Set `ui.designSource` to `penpot` and `ui.screens[].status` to `built`.

Edits after the build: change the design in Penpot and run the loop again. Behaviour (button
clicks, values) belongs to Coding's scripts, which find elements by name.
