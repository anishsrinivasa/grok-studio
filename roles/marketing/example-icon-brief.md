# Example: Icon Brief

This example shows Marketing GrokBot composing a high-CTR game icon for a lava obby.

## Task from Lead

```
[GS] TASK #9 Lead -> Marketing
game: lava-leap   spec: /workspace/grok-studio/games/lava-leap/game-spec.json
do: icon (512x512) and thumbnail (1920x1080)
spec refs: marketing.icon, marketing.thumbnails
inputs: playtest captures (reports/playtest-*.png), Builder's coin render (renders/coin-preview.png)
done when: marketing/icon-512.png and marketing/thumb-1.png saved, upload steps in DONE
reply with: DONE #9
```

## Icon Brief (from spec)

> Single chunky gold coin mid-air above glowing lava, bold rim light, no text.

## Composition

1. **Source:** Builder's coin render (renders/coin-preview.png, 3/4 view, clean background)
2. **Background:** Solid gradient (dark at top #1E1B2E → bright orange at bottom #FF6B1A, lava glow)
3. **Coin placement:** Centered, large (60% of frame height), slight tilt (12 deg) for dynamism
4. **Rim light:** Strong orange-yellow highlight on the coin's edge (simulates lava glow below)
5. **No text:** Icon must read at 64px without any labels

## Post-Process

- Crop to 512x512
- High contrast: boost saturation +20%, sharpen edges
- Test at 64px: coin silhouette is clear, lava glow is obvious

## DONE Report

```
DONE #9 Marketing

Created: marketing/icon-512.png, marketing/thumb-1.png

Icon: 512x512, gold coin above lava gradient, rim-lit, no text.
Tested at 64px: clear silhouette, high contrast.

Thumbnail: 1920x1080, avatar mid-jump between platforms, lava below, coins trailing.

Manual upload steps:
1. Go to Creator Dashboard > [Place] > Icon
2. Upload marketing/icon-512.png
3. Go to Thumbnails, upload marketing/thumb-1.png

Open issues: none
```

User uploads via Creator Dashboard. CTR: high (bold, readable, on-brand).
