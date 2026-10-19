# penpot-to-roblox

Penpot board → Roblox ScreenGui. The workflow for agents is in `skills/penpot-ui/SKILL.md`;
this file is for working on the converter itself.

```
penpot/extract_board.js    Penpot MCP execute_code body: board -> JSON (plugin API field names)
penpot/export_images.js    execute_code body: image fills / vector shapes -> base64 PNG
penpot/save_images.py      writes those images, optional Open Cloud upload -> images.json
src/ -> dist/              TypeScript converter: board JSON -> RobloxUISpec (spec version 2)
PenpotUIBuilder.luau       spec -> ScreenGui (run in Studio via execute_luau)
PenpotUIVerifier.luau      ScreenGui vs spec -> PASS/FAIL report
fixtures/                  HUD, menu and shop boards in extract_board.js format
scripts/studio_payload.py  spec (+ images.json) -> one execute_luau body: build + verify (or --delete)
```

`dist/` is committed on purpose: the converter has no runtime dependencies, so agents run
`node dist/cli.js board.json spec.json` with plain Node and setup needs no install or build.
A test fails if `dist/` is not the build of `src/`.

## Layout model

Everything is scale-based (`UDim2` scale, offsets 0) relative to the parent, so a 1920x1080
design fills any screen. Anchors come from Penpot constraints (right/bottom/center) or, for
the default left/top, from where the element sits (outer thirds hug that edge). Images keep
their aspect ratio (`UIAspectRatioConstraint`). Text is `TextScaled`, capped at the design
size with `UITextSizeConstraint`. Strokes stay in pixels. Flex boards become `UIListLayout`
(gap/padding as scale of the container), uniform grids `UIGridLayout`; LayoutOrder follows
laid-out position. Unsupported features produce warnings in the spec.

## Development

```bash
npm install                # dev tools only (typescript, @penpot/plugin-types)
npm run build              # src -> dist (commit dist)
npm test                   # converter tests + Luau end-to-end run (needs `luau` on PATH)
npm run check:snippets     # type-check penpot/*.js against @penpot/plugin-types
```

`tests/luau.test.js` runs the builder and verifier for every fixture inside
`tests/roblox_mock.luau`, a small fake of the Roblox API (UDim2, enums, instances, absolute
layout with anchors and aspect constraints): build → verify PASS at 1920x1080, 844x390 and
1024x768, and a deliberately broken build must FAIL. Get `luau` from
https://github.com/luau-lang/luau/releases. Static checks used in review:
`luau-lsp analyze --definitions=globalTypes.d.luau PenpotUI*.luau` (strict, Roblox types).
