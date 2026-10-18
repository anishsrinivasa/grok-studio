---
name: thumbnail-and-icon
description: Produces a Roblox game icon (512x512) and 16:9 thumbnails (1920x1080) from real game content - composing a hero shot via a Blender render or Studio screen capture, optional AI polish, sizing/cropping to spec - and guides upload via the Creator Dashboard. Use when the user needs marketing images, an icon, or thumbnails for a Roblox experience, or Stage 7 of a one-shot build.
---

# Thumbnail and icon

Create `marketing/icon-512.png` and `marketing/thumb-<n>.png` from
`game-spec.json` -> `marketing`, using real game content.

## Specs (verified Oct 2026)

| Image | Spec | Source |
|---|---|---|
| Icon | square, **512x512** template; previews at ~150x150 must stay legible; one per locale; moderated | [Icons](https://create.roblox.com/docs/production/publishing/experience-icons) |
| Thumbnails | **16:9**, ideally **1920x1080**; `.jpg .gif .png .tga .bmp`; Creator Dashboard upload says keep under **3 MB** and 1920x1080; up to **10** images/videos per game; non-16:9 uploads get stretched | [Thumbnails](https://create.roblox.com/docs/production/publishing/thumbnails) |

Content rules (same pages): thumbnails and videos must represent the actual game, no
misleading gameplay/UI; everything is moderated against the Community Rules. Avoid
real-brand logos, other games' characters, and fake "UPDATE"/"FREE ROBUX" style bait.

## Design brief

- **Icon:** one bold subject (signature object or character pose), strong silhouette,
  2-3 dominant colors from the style guide, high contrast rim light, no small text (a 1-2
  word title max if it stays legible at 150 px). Fill the frame - no thin borders.
- **Thumbnail:** an action moment from the core loop, character at rule-of-thirds, clear
  depth (foreground/mid/background), saturated but true-to-game colors, optional short
  title top-center. Make 2-3 variants (different moments) so the user can A/B them on the
  Creator Dashboard.

## Path 1 - Blender render (best control, exact resolution)

Requires the Blender MCP. Rebuild a small diorama from the game's own assets (they were
modeled in Blender during `blender-assets`; re-open or re-import the exported FBX files),
plus a simple blocky R15-proportioned stand-in avatar posed mid-action.

Through `execute_blender_code`:
1. New scene/collection `Marketing`; import or link the assets; arrange the hero shot.
2. Camera: 35-50 mm focal length for thumbnails, 50-85 mm for the icon; frame with
   `look` (`camera` view) until composition is right.
3. Lighting: key (sun or area) + rim light in the accent color + world color/HDRI matching
   the game's time of day. EEVEE is fast enough; enable bloom/glare-ish compositing
   only if the game itself has bloom.
4. Render settings: `scene.render.resolution_x/y` = 1920x1080 (thumb) and 512x512 (icon,
   separate camera), `resolution_percentage = 100`, PNG RGB. Render to a file in the
   project's `marketing/` folder on the machine running Blender (rendering and saving work
   with Blender MCP safe mode on).
5. `look` the rendered image to check it, iterate on composition.

## Path 2 - Studio screen capture (most authentic)

1. Start a playtest, stage the moment (navigate the character, trigger an animation, open
   a UI only if it helps), then `screen_capture` with an explicit camera position and
   look-at target for cinematic angles. Hide HUD clutter first if it distracts (set
   `ScreenGui.Enabled = false` via `execute_luau` `Client`, and restore afterwards).
2. The capture size equals the Studio viewport. For a crisp 1920x1080 result, ask the user
   to maximize Studio, or ask them to take the shot themselves with Studio's free camera
   (Left Shift + P during a solo playtest, per the Thumbnails doc) and save it.
3. If the capture comes back as image data in your context but you can't write it to disk,
   describe the shot to the user and let them save it, or use Path 1.

## Post-process (any path)

Use `reference/make_marketing_images.py` (Pillow) to crop to aspect, resize with Lanczos,
add an optional outlined title, and enforce the 3 MB thumbnail limit:
```bash
uv run --with pillow python <plugin>/skills/thumbnail-and-icon/reference/make_marketing_images.py thumb raw/shot1.png marketing/thumb-1.png --title "Lava Leap"
uv run --with pillow python <plugin>/skills/thumbnail-and-icon/reference/make_marketing_images.py icon  raw/hero.png  marketing/icon-512.png
```

## Optional AI polish

If your client has an image generation/editing tool and the user agrees, you may polish a
real capture/render (lighting, color grade, background haze, title lettering) using it as
the reference image. Keep the gameplay, characters, UI, and environment **as they are in
the game** - the Roblox thumbnail rules forbid misrepresenting gameplay. Never generate a
thumbnail from scratch that shows things the game doesn't have. Re-run the post-process
script on the result to guarantee exact sizes.

## Upload

- **Creator Dashboard (default):** the user uploads. Icon: Creator Dashboard > game >
  Configurations > Places > start place > **Icon** > Change > Save Changes. Thumbnails:
  game > Configurations > Places > place > **Thumbnails** > **Home Page** and
  **Experience Detail Page** tabs. Give them the exact file paths.
- **Automation (flagged, not default):** Open Cloud's Assets API
  (`POST https://apis.roblox.com/assets/v1/assets`, `assetType: "Decal"`/`"Image"`) can
  upload the images as *assets*, but that does not set them as the game's icon/thumbnails.
  The documented thumbnail/icon upload endpoints in the Roblox API reference are legacy
  endpoints (cookie auth) - **do not** ask for or use a user's `.ROBLOSECURITY` cookie.
  If Roblox exposes an API-key route for game media in the future, verify it in the
  Open Cloud reference (https://create.roblox.com/docs/cloud) before using it.

Write the file paths into `marketing.icon.file` / `marketing.thumbnails[].file`, also
draft the game description from `marketing.description`, and list the upload as a manual
step in the final handoff.
