---
name: penpot-ui
description: Design Roblox UI in Penpot (free, open-source design tool) and convert to native ScreenGuis. Alternative to Figma and the Studio-direct path. Handles the design -> extract -> convert -> build -> verify loop, with automatic fallback to building directly in Studio when Penpot isn't connected. Use for any Roblox UI design task when Penpot is available.
---

# Penpot UI Design for Roblox

Design Roblox UI in **Penpot** (free, open-source, https://penpot.app) and convert it to native
ScreenGuis. Penpot runs in the browser with an MCP plugin that exposes the Penpot Plugin API.

## When to use Penpot vs Studio-direct

- **Penpot path**: When the Penpot MCP is connected and the user wants a visual design tool, or
  when iterating on complex layouts (grids, flex, nested frames). Penpot excels at responsive
  layouts, shared components, and design tokens.
- **Studio-direct path** (from `roblox-ui` skill): When Penpot isn't connected, for simple HUDs
  (coin counters, health bars), or when speed matters more than visual polish. Always keep this
  as the fallback.

If Penpot is available, **prefer it for new screens**. If not, fall back to Studio-direct
immediately without blocking.

## Setup (one-time, optional)

The user connects Penpot through the setup-bridge skill. If they didn't, you can try once:

1. Check if the Penpot MCP is available (MCP server list or try a read-only call).
2. If yes, ask them (once) to open a Penpot file in their browser and connect the MCP plugin to
   the local MCP server (see Penpot MCP docs: https://help.penpot.app/mcp/ and
   https://github.com/penpot/penpot/blob/main/mcp/README.md). The access token goes through the
   **secret prompt**, never plain chat.
3. If they skip it or it fails, use Studio-direct for the rest of the session.

**DO NOT block on Penpot setup.** If it's not ready in one attempt, fall back.

## The Penpot -> Roblox Loop

### 1. Design in Penpot

Use the Penpot MCP's code execution tools to create design elements. Design one **board per screen**
at **1920x1080** (desktop reference). Use:

- **Frames/Rects** for containers, buttons, panels. Name them like Roblox instances
  (`HUD/CoinCounter/Amount`) - those names become the Studio hierarchy.
- **Text** for labels and button text. Set font, size, weight, alignment, color (from fills).
- **Images** for icons and sprites (you'll upload them to Roblox later via Open Cloud).
- **Flex layout** (row/column) for dynamic lists, menus. Set alignment, gap, padding.
- **Grid layout** for shops, inventories. Set columns, rows, gap.
- **Components** for reusable elements (buttons, cards). Name components ending in "Button" to
  auto-convert to TextButton/ImageButton.
- **Fills**: solid colors, gradients (linear -> UIGradient; radial approximated), images.
- **Strokes**: map to UIStroke (first stroke only, border mode).
- **Corner radius**: UICorner (uniform radius; if per-corner, takes max).
- **Constraints/proportion lock**: scale-based UDim2 + UIAspectRatioConstraint.

**Mobile-first**: design for scale, not pixels. Roblox needs it to work on phone/tablet/desktop.

### 2. Extract board data

Run the extraction snippet from `converters/penpot-to-roblox/extract_board.py` in the Penpot MCP's
code execution tool. Example (adapt to actual Penpot API, see README.md in the repo for the
real snippet):

```javascript
const board = penpot.currentBoard;
if (!board) return { error: "No board selected" };

function extractShape(shape) {
  // ... see extract_board.py for full snippet
  return { id, name, type, x, y, width, height, fills, strokes, children, ... };
}

const data = { id: board.id, name: board.name, width: board.width, height: board.height,
               children: board.children.map(extractShape) };
return data;
```

Save the JSON result as `games/<slug>/penpot/<board-name>.json`.

### 3. Convert to Roblox spec

Run the TypeScript converter (Node.js, installed in the environment):

```bash
cd /workspace/converters/penpot-to-roblox
[ ! -d node_modules ] && npm install
npm run build
node dist/cli.js "../../games/<slug>/penpot/<board-name>.json" "../../games/<slug>/penpot/<board-name>.spec.json"
```

The converter produces a Roblox UI spec JSON (`RobloxUISpec` type) plus warnings for unsupported
features. Review the warnings; if critical (e.g., radial gradient on a key element), note it in
your `DONE` message or fix it in Penpot.

### 4. Upload images (if any)

If the board has image fills, upload them to Roblox Open Cloud before building:

```bash
# For each image (extract from Penpot image data URIs or external URLs first):
python3 /workspace/scripts/opencloud_upload.py <image.png> --name "Icon Name" --type Image
# Returns: {"assetId": "123456789", "assetType": "Image", ...}
```

Build an image cache JSON mapping content hashes (from the spec's `image.contentHash`) to
`rbxassetid://<id>`:

```json
{
  "abc123hash": "rbxassetid://123456789",
  "def456hash": "rbxassetid://987654321"
}
```

Save it as `games/<slug>/penpot/<board-name>.images.json`.

### 5. Build in Studio

Load the Luau builder (`converters/penpot-to-roblox/PenpotUIBuilder.luau`) in Studio via
`execute_luau` (datamodel_type "Edit"):

```lua
-- Read the PenpotUIBuilder module (paste its content or load from file)
local PenpotUIBuilder = (function()
  -- ... paste PenpotUIBuilder.luau here, or loadstring from file
end)()

-- Read spec JSON
local HttpService = game:GetService("HttpService")
local specJson = [[paste spec JSON here, or read from file]]

-- Read image cache (optional, empty if no images)
local imageCacheJson = [[{"hash": "rbxassetid://id", ...}]] -- or '{}'
local imageCache = HttpService:JSONDecode(imageCacheJson)

-- Build the ScreenGui
local screen = PenpotUIBuilder.buildFromSpec(specJson, imageCache)
-- Returns the ScreenGui, now in StarterGui
```

If images aren't uploaded yet, the builder will warn about missing asset IDs. That's fine for
the first pass; upload images, update the cache, and rebuild.

### 6. Verify in Studio

1. **Visual check**: `screen_capture` the screen in Edit mode (StarterGui renders there). For
   phone and tablet sizes, use the Studio MCP's device simulator skill (if available).
2. **Export Penpot PNG**: In Penpot, export the board as PNG (via MCP or manual export). Compare
   side-by-side with the Studio capture. Colors, positions, sizes, text should match within
   tolerance.
3. **Luau verification** (optional, for CI or critical screens): Load
   `converters/penpot-to-roblox/PenpotUIVerifier.luau` and run:

   ```lua
   local PenpotUIVerifier = (function() -- paste PenpotUIVerifier.luau end)()
   local passed = PenpotUIVerifier.runVerification("<ScreenName>", specJson)
   -- Prints PASS/FAIL and lists failures
   ```

   This checks: every element present, sizes/positions within 1%, colors match, no off-screen
   elements. If it fails, fix the design or the converter.

4. Set `ui.screens[].status` -> `built` after the build, `verified` after the Lead's playtest.

## Rules & Best Practices

- **Naming is the contract**: Element names in Penpot become instance names in Roblox. Keep them
  stable. Coding GrokBot finds UI elements by name (`player.PlayerGui:WaitForChild("Hud")`).
- **Scale-based layout**: The converter uses `UDim2.fromScale()` for everything except hairlines.
  Design with relative sizes and positions (flex/grid help with this).
- **Mobile-first**: Test on phone size (390x844 or similar). Use UIAspectRatioConstraint,
  UISizeConstraint, and readable text sizes.
- **Button detection**: Frames/components with "button" or "btn" in the name (case-insensitive)
  have their child text converted to TextButton (if the child is text) or ImageButton (if image).
- **Image uploads**: Always upload images via Open Cloud. Never use external URLs directly in
  Roblox (they don't work at runtime). Cache asset IDs by content hash so nothing uploads twice.
- **Fallback to Studio-direct**: If Penpot fails (not connected, extraction error, converter bug),
  immediately switch to the Studio-direct path from `roblox-ui` skill. Don't waste time debugging
  Penpot unless the user explicitly wants it.

## Supported Features

- ✓ Frames, rects, text, images
- ✓ Flex layout (row/column) -> UIListLayout
- ✓ Grid layout -> UIGridLayout
- ✓ Fills: solid, linear gradient
- ✓ Strokes (first only)
- ✓ Corner radius (uniform)
- ✓ Opacity -> Transparency
- ✓ Font mapping (Inter -> BuilderSans, Roboto Mono -> RobotoMono, etc., see converter)
- ✓ Text alignment, wrapping
- ✓ Constraints -> scale-based UDim2 + aspect ratio
- ✓ Components (button detection)

## Unsupported Features (Warnings)

- ✗ Multiple strokes (uses first only)
- ✗ Radial gradients (approximated as linear)
- ✗ Per-corner radii (uses max)
- ✗ Shadows (not in Roblox)
- ✗ Blend modes, masks
- ✗ Rich text, text paths, variable fonts
- ✗ Vector graphics (rasterize to images first)

All unsupported features produce warnings in the converter output. Review them and decide if
they're critical.

## Files & Locations

- **Penpot exports**: `games/<slug>/penpot/<screen>.json`
- **Roblox specs**: `games/<slug>/penpot/<screen>.spec.json`
- **Image cache**: `games/<slug>/penpot/<screen>.images.json`
- **Converter**: `/workspace/converters/penpot-to-roblox/`
- **Extraction snippets**: `/workspace/converters/penpot-to-roblox/extract_board.py`

## Troubleshooting

- **Penpot MCP not connected**: Fall back to Studio-direct immediately. Don't retry unless the
  user explicitly asks to fix Penpot.
- **Extraction fails**: Check that a board is selected in Penpot. Try the list-boards snippet to
  see available boards.
- **Converter fails**: Check the board JSON structure. If Penpot changed their API, you may need
  to adapt the extraction snippet or converter (file an issue).
- **Images missing**: Upload them via `opencloud_upload.py` and update the image cache JSON.
- **Verification fails**: Compare the Penpot PNG export with the Studio capture. If they differ,
  fix the design or report a converter bug.

## Integration with setup-bridge

In `setup-bridge`, Penpot is an **optional** setup step (like Figma). The skill asks for the
Penpot access token (secret prompt), checks the connection, and records success/failure. If
skipped or failed, the Designer bot uses Studio-direct by default.

## Reporting to Lead

In team mode, report in your `DONE` message:
- Which screens were designed in Penpot (list board names)
- Element names Coding needs (e.g., `Hud/CoinCounter/Amount`)
- Any unsupported features that affected the design (e.g., "radial gradient on shop background
  approximated as linear")
- Whether images are uploaded (if not, list the manual upload steps for the user)

## Example Workflow

```bash
# 1. Extract from Penpot (via MCP code execution, save result)
echo '<extracted JSON>' > games/my-game/penpot/Hud.json

# 2. Convert
cd converters/penpot-to-roblox
npm run build
node dist/cli.js ../../games/my-game/penpot/Hud.json ../../games/my-game/penpot/Hud.spec.json
# Review warnings

# 3. Upload images (if any)
python3 ../../scripts/opencloud_upload.py coin.png --name "Coin Icon" --type Image
# -> {"assetId": "123"}
echo '{"abc123": "rbxassetid://123"}' > ../../games/my-game/penpot/Hud.images.json

# 4. Build in Studio (execute_luau)
# Load PenpotUIBuilder.luau, call buildFromSpec(specJson, imageCache)

# 5. Verify
# screen_capture, compare to Penpot PNG export, run PenpotUIVerifier if needed
```

Done when the ScreenGui is in StarterGui, matches the design, and `ui.screens[].status` is `built`.
