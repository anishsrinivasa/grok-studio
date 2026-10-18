---
name: roblox-ui
description: Designs and builds Roblox game UI (HUD, menus, shops, prompts) that works on phone, tablet and desktop. Optional Figma path (design frames with the Figma MCP, read design context, rebuild in Studio) and an always-available Studio-direct path that builds ScreenGuis with scale-based layout via Luau executed through the Studio MCP. Use for any Roblox UI/GUI work or Stage 3 of a one-shot build.
---

# Roblox UI

Build every `game-spec.json` -> `ui.screens[]` entry as a `ScreenGui` in `StarterGui`, styled
from `ui.styleGuide`, and wire it to client controllers. `reference/UiKit.luau` is a
ready-to-paste builder (make/corner/stroke/padding/screen helpers + an example HUD).

## Choose a path

1. **Figma path** - only if preflight found the Figma MCP authenticated (`whoami` works)
   **and** the user's seat can write to the canvas. As of Oct 2026 Figma documents canvas
   writes (`use_figma`) for Professional, Education, Organization and Enterprise plans; it
   is in beta, and read tools are rate-limited by seat (View/Collab seats: ~20 calls/month;
   Full/Dev seats on Professional: ~200/day). Source:
   https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/ and
   https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/ . Budget your calls:
   design all screens in as few `use_figma` calls as possible, then read each frame once.
2. **Studio-direct path** (default, always works) - build directly with Luau. Use this when
   Figma is missing, rate-limited, or the user didn't ask for Figma.

Set `ui.designSource` accordingly.

### Figma path

1. `create_new_file` (or use `ui.figmaFileUrl` if the user gave one). Store the URL in the
   spec.
2. With `use_figma`, create one frame per screen at **1920x1080** (desktop) and a
   **390x844**-ish phone variant for complex screens. Use auto layout, the spec palette as
   local variables/styles, and name layers exactly like the Roblox instances you will
   create (`Hud/CoinCounter/Amount`).
3. Read back: `get_metadata` for structure, `get_design_context` for sizes/colors/text,
   `get_screenshot` for a visual reference. Don't re-read frames you didn't change.
4. Translate to Roblox (below): pixel positions -> **scale** (`x / frameWidth`,
   `y / frameHeight`), auto layout -> `UIListLayout`/`UIGridLayout` + `UIPadding`, corner
   radius -> `UICorner`, strokes -> `UIStroke`, drop shadows -> skip or a soft 9-slice
   `ImageLabel`. Images must be uploaded to Roblox before they can be used (see
   `thumbnail-and-icon` for upload options) - until then leave `Image = ""`.
5. Continue with the Studio-direct build steps using those numbers.

### Studio-direct path

Build with `execute_luau` (`datamodel_type: "Edit"`) - one screen per call - using the
`reference/UiKit.luau` helpers. Each builder must be **idempotent**: destroy-and-recreate the
`ScreenGui` by name.

## Layout rules (mobile-first)

- **Scale, not offset:** `Size`/`Position` use `UDim2.fromScale(...)`. Offsets only for
  hairlines (stroke thickness, 1-2 px gaps).
- **AnchorPoint** matches the corner you position from (`Vector2.new(1, 0)` for top-right,
  `0.5, 0.5` for centered modals).
- **UIAspectRatioConstraint** on anything that must keep its shape (buttons, icons, cards).
- **UISizeConstraint** / **UITextSizeConstraint** to keep things readable on small screens
  and not huge on 4K; use `TextScaled = true` with a `UITextSizeConstraint` max.
- **UIScale** on a root frame for a global scale knob (e.g. 0.85 on phones if needed).
- **Layouts:** `UIListLayout` (rows/columns, set `SortOrder = LayoutOrder`),
  `UIGridLayout` (shops/inventories, use `CellSize` in scale), `UIPadding` in scale.
- **Safe areas:** keep `IgnoreGuiInset = false` for HUDs so nothing sits under the top bar;
  `ScreenGui.ScreenInsets` defaults to `CoreUISafeInsets` on new ScreenGuis - leave it.
- **Thumb zones:** on touch devices the thumbstick is bottom-left and the jump button
  bottom-right. Keep HUD at top/edges; put primary action buttons right-center, large
  (>= ~10% of screen height).
- **Readable text:** high contrast against the palette, bold weight for numbers, avoid
  thin fonts. Use `FontFace = Font.fromName("BuilderSans", Enum.FontWeight.Bold)` or the
  spec font.
- `ResetOnSpawn = false` for persistent HUDs; modals start `Enabled = false` or
  `Visible = false`.
- `ZIndexBehavior = Sibling` and explicit `ZIndex` for overlays.

## Wiring

- UI logic lives in client controllers (`StarterPlayerScripts.Controllers.HudController`
  etc.), not in LocalScripts inside the ScreenGui - one client entry point (`ClientMain`).
- Controllers find UI with `player.PlayerGui:WaitForChild("Hud")` (StarterGui contents are
  cloned into PlayerGui on join).
- Data comes from server events (`CoinsChanged`) or attributes/leaderstats; buttons fire
  *intent* remotes (`RequestUnlock`) - the server validates (see `roblox-code`).
- Feedback: `TweenService` for pops/fades (0.1-0.25 s, `Enum.EasingStyle.Quad`), and
  disable buttons while a request is pending.
- Support gamepad/keyboard where cheap: `GuiService.SelectedObject` for modals, set
  `Selectable` on buttons, bind Escape/B to close via `ContextActionService`.

## Verify

1. `search_game_tree` filtered to `StarterGui` to confirm the hierarchy and names.
2. Start a playtest (`start_stop_play`) and `screen_capture` the HUD. If the client exposes
   device emulation (ask the Studio MCP `skill` tool about "device simulation"), capture a
   phone-sized viewport too; otherwise check math: no element should go off-screen at
   16:9, 19.5:9 (phones), and 4:3 (tablets).
3. Click through modals with `user_mouse_input` targeting the button instances, confirm the
   expected remote fired (server log) and the UI updated.
4. Set `ui.screens[].status` -> `built` after creation, `verified` after the playtest check.
