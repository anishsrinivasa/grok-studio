# Penpot to Roblox UI Converter

Converts Penpot design board exports into Roblox ScreenGuis via a neutral UI specification format.

## Architecture

1. **Extract**: Get board data from Penpot using the MCP plugin API
2. **Convert**: Transform Penpot shapes to Roblox UI spec (TypeScript/Node)
3. **Build**: Create ScreenGui in Roblox Studio from spec (Luau)
4. **Verify**: Check that built UI matches spec

## Components

### TypeScript Converter (`src/`)

- `converter.ts` - Main conversion logic
- `types.ts` - TypeScript types for Penpot and Roblox data
- `cli.ts` - Command-line interface
- `index.ts` - Public API exports

### Luau Modules

- `PenpotUIBuilder.luau` - Builds ScreenGui from UI spec JSON
- `PenpotUIVerifier.luau` - Verifies built UI matches spec

### Extraction

- `extract_board.py` - Example MCP code snippets for board extraction

## Usage

### 1. Extract Board from Penpot

Use the Penpot MCP plugin to execute JavaScript and extract board data:

```javascript
// In Penpot MCP code execution
const board = penpot.currentBoard;
const data = extractBoardData(board); // See extract_board.py
return data;
```

Save the result as `board.json`.

### 2. Convert to Roblox Spec

```bash
cd converters/penpot-to-roblox
npm install
npm run build
node dist/cli.js board.json spec.json
```

### 3. Build in Roblox Studio

Load the Luau builder in Studio via `execute_luau` (datamodel_type "Edit"):

```lua
local HttpService = game:GetService("HttpService")
local PenpotUIBuilder = loadstring(scriptContent)() -- Load PenpotUIBuilder.luau

-- Read spec JSON
local specJson = readfile("spec.json") -- or pass directly

-- Optional: image cache with uploaded asset IDs
local imageCache = {
  ["abc123hash"] = "rbxassetid://1234567890"
}

-- Build the ScreenGui
local screen = PenpotUIBuilder.buildFromSpec(specJson, imageCache)
```

### 4. Verify

```lua
local PenpotUIVerifier = loadstring(verifierContent)() -- Load PenpotUIVerifier.luau

local passed = PenpotUIVerifier.runVerification("GameHUD", specJson)
```

## Mapping

### Elements

| Penpot | Roblox | Notes |
|--------|--------|-------|
| Board/Frame | Frame | CanvasGroup if opacity < 1 or rotation |
| Rect | Frame | ImageLabel if has image fill |
| Text | TextLabel | TextButton if name contains "button" |
| Component (button) | TextButton/ImageButton | Based on name and content |

### Layout

| Penpot | Roblox | Notes |
|--------|--------|-------|
| Flex layout (row) | UIListLayout (Horizontal) | |
| Flex layout (column) | UIListLayout (Vertical) | |
| Grid layout | UIGridLayout | Cell size calculated from columns/rows |
| Padding | UIPadding | Converted to scale |
| Gap | UIListLayout.Padding or Grid.CellPadding | |

### Styling

| Penpot | Roblox | Notes |
|--------|--------|-------|
| Fill (solid) | BackgroundColor3 + Transparency | |
| Fill (gradient) | UIGradient | Linear only; radial approximated |
| Fill (image) | Image property | Upload via Open Cloud first |
| Stroke | UIStroke | First stroke only; border mode |
| Corner radius | UICorner | Uniform only; max of individual corners |
| Opacity | BackgroundTransparency or GroupTransparency | |

### Text

| Penpot | Roblox | Notes |
|--------|--------|-------|
| Font family | Font.fromName() | Mapped to Roblox fonts, see FONT_MAPPING |
| Font weight | FontWeight enum | Mapped to closest Roblox weight |
| Font size | TextSize | Direct mapping |
| Text align | TextXAlignment | left/center/right |
| Color | TextColor3 | From first fill |

### Constraints

| Penpot | Roblox | Notes |
|--------|--------|-------|
| Proportion lock | UIAspectRatioConstraint | Maintains aspect ratio |
| Position/size | UDim2.fromScale() | Scale-based for mobile |
| Constraints (horiz/vert) | AnchorPoint + Position | Best-effort mapping |

## Images

Images must be uploaded to Roblox before use:

```bash
python3 scripts/opencloud_upload.py image.png --name "Coin Icon" --type Image
# Returns: {"assetId": "123456789", ...}
```

Pass uploaded IDs in the `imageCache` parameter to `buildFromSpec`, keyed by content hash.

## Testing

### TypeScript Tests

```bash
npm test
```

Runs unit tests on fixtures in `fixtures/`.

### Luau Verification

Run `PenpotUIVerifier.runVerification()` in Studio after building.

## Fixtures

- `fixtures/hud.json` - Coin counter HUD
- `fixtures/menu.json` - Main menu with title and buttons
- `fixtures/shop.json` - Grid-based shop layout

## Limitations & Warnings

- **Multiple strokes**: Only first stroke used
- **Radial gradients**: Approximated as linear
- **Individual corner radii**: Uses maximum radius
- **Advanced text**: No rich text, text paths, or variable fonts
- **Shadows**: Not supported (UIStroke has no shadow)
- **Blend modes**: Not supported
- **Masks**: Not supported (use CanvasGroup clipping if needed)
- **Vector graphics**: Rasterize to images first

All unsupported features generate warnings in the spec output.

## License

Part of grok-studio. MIT.
