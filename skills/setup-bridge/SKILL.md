---
name: setup-bridge
description: >-
  The one command that takes a fresh grok-studio install on Grok Bot to a working team.
  Loads the skills, collects keys through the secret prompt, installs cloud Blender,
  connects the user's Roblox Studio through a persistent bridge, creates the Lead, Coding,
  Designer, Builder and Animator GrokBots, then runs a readiness gate (every Bot reaches
  Studio and Blender, a Blender-to-Studio model round trip, a Luau play test, screen
  capture). It only says ready when the gate passes. Safe to re-run: it checks, repairs
  and reconnects. Use right after installing the plugin, for "setup bridge", "set up grok
  studio", "connect Studio", or when anything in the team stops working.
user-invocable: true
argument-hint: "[--no-figma] [--pc-blender]"
---

# /setup-bridge: from install to ready

One command, then the team is ready to build. Automate everything a person doesn't have
to do. For each failure, retry once, then tell the user the **exact** fix and retry after
they've done it. Before each step, say in one short line what you're on. Re-running is
safe: every step checks first and only fixes what is missing.

`<plugin>` = `/workspace/grok-studio/plugin`. `GS` = `/workspace/grok-studio`.

## What only the user does

Ask for these only when a step needs them, and only if they aren't already done:
1. Install the plugin. Until it is on the marketplace, use the bootstrap in the README.
2. Install and open **Roblox Studio**, sign in, open or create a place, and turn on
   **Team Create** (Home > Collaborate, or File > Team Create). Team Create saves every
   edit to Roblox, so nothing the Bots build is lost if Studio closes.
3. Paste keys into Grok Bot's **secret prompt**, never into chat (Step 2).
4. Approve the PC and app permission prompts the first time: local commands and the
   firewall.
5. Create a sidebar section named **Grok Studio** if it doesn't exist. Bots can't create
   sections.

## Step 1 - Plugin files and skills

```bash
GS=/workspace/grok-studio; mkdir -p "$GS/games" "$GS/.tools"
if [ ! -f "$GS/plugin/skills/setup-bridge/lead-bot.md" ]; then
  SRC_ROOT=""   # fill in: the folder this SKILL.md was loaded from, two levels up, if you know it
  [ -z "$SRC_ROOT" ] && SRC_ROOT=$(timeout 60 find / -xdev -path '*/skills/setup-bridge/lead-bot.md' \
      -not -path "$GS/*" 2>/dev/null | head -n1 | sed 's#/skills/setup-bridge/lead-bot.md##')
  if [ -n "$SRC_ROOT" ]; then ln -sfn "$SRC_ROOT" "$GS/plugin"
  else
    for REF in tags/v0.2.0 heads/multi-bot-team heads/main; do
      rm -rf "$GS/plugin.tmp" && mkdir -p "$GS/plugin.tmp"
      curl -fsSL "https://github.com/anishsrinivasa/grok-studio/archive/refs/$REF.tar.gz" |
        tar -xz -C "$GS/plugin.tmp" --strip-components=1 2>/dev/null &&
        [ -f "$GS/plugin.tmp/skills/setup-bridge/lead-bot.md" ] && break
    done
    rm -rf "$GS/plugin" && mv "$GS/plugin.tmp" "$GS/plugin"
  fi
fi
ls "$GS/plugin/skills"
```

**Skills:** every folder in `<plugin>/skills/` must be available as a skill. That's
automatic when the plugin is installed from the marketplace. After a bootstrap install,
import each missing one: save `<plugin>/skills/<name>/SKILL.md` as a skill named `<name>`,
and keep it pointing at its folder for the reference files. Skills are shared by all
Bots, so this happens once.

Then start the cloud Blender install in the background. It takes a minute or two, so
Steps 2-4 run meanwhile:

```bash
B="$GS/plugin/skills/blender-assets/reference/cloud_blender.sh"
bash "$B" version >/dev/null 2>&1 || nohup bash "$B" install > "$GS/.tools/blender-install.log" 2>&1 &
```

## Step 2 - Keys (secret prompt only)

Check what's already there: `for k in ROBLOX_OPEN_CLOUD_API_KEY NGROK_AUTHTOKEN; do
test -n "${!k}" && echo "$k set" || echo "$k missing"; done`. Then open the secret prompt
for each missing key, with these exact instructions:

- **`ROBLOX_OPEN_CLOUD_API_KEY`**: needed for automatic model uploads.
  1. Go to https://create.roblox.com/dashboard/credentials > **Create API key**.
  2. Add the **Assets** API with **read and write** (`asset:read`, `asset:write`) for
     your account (or the group that will own the game).
  3. Set **Accepted IP addresses** to `0.0.0.0/0` (the cloud computer's IP isn't fixed),
     and set an expiry if you like.
  4. Copy the key and paste it into the secret prompt.

  Then check it without printing it: `python3 <plugin>/scripts/opencloud_upload.py
  introspect`. It reports the scopes, the expiry and the owner's user id. If it says
  `asset:write` is missing, tell the user exactly that. Save the owner id as the secret or
  setting `ROBLOX_CREATOR_USER_ID`, or `ROBLOX_CREATOR_GROUP_ID` for group keys. If the
  user declines the key, continue: model imports then need one Import 3D click per batch,
  and gate check G2 is marked *skipped*.
- **`NGROK_AUTHTOKEN`**: only if ngrok on the PC isn't set up yet (`connect-studio`
  checks this in Step 4). Get it at https://dashboard.ngrok.com/get-started/your-authtoken.
  Also ask for the free **static domain** from https://dashboard.ngrok.com/domains (it
  looks like `xxx.ngrok-free.dev`). That isn't secret and can go in chat. It keeps the
  Studio connector's URL the same forever.
- **Figma** (optional, skip with `--no-figma`): nothing to paste. The Figma connector
  signs in with one **Authorize** click. Free Figma plans are read-only, about 20 calls a
  month, so Designer builds UI directly in Studio either way.

## Step 3 - Roblox Studio on the PC (persistent bridge)

Run the **`connect-studio`** skill here; the user approves its PC commands in this chat.
It:
- installs what's missing on the PC (Node.js, the bridge files, the pinned supergateway)
- sets up ngrok with the static domain
- installs the bridge as a background service that survives restarts and restarts itself
- uses one stable key, stored once on the PC
- registers or updates the shared `roblox-studio` connector in place, so nothing is
  duplicated
- writes `$GS/.bridge.json` (mode 600)

Then pick the place: `list_roblox_studios`. If several Studio windows are open, ask which
one. Check it with `execute_luau` (Edit):

```lua
return game:GetService("HttpService"):JSONEncode({
    placeId = game.PlaceId, name = game.Name,
    published = game.PlaceId ~= 0,
    teamCreate = game:FindService("NetworkClient") ~= nil, -- heuristic: Team Create edit sessions are network clients
})
```

If `published` is false or `teamCreate` looks false, ask the user to turn on Team Create
(it publishes the place), then check again. If the heuristic is wrong, the user can just
confirm. Add `studio_id`, `place_id`, `place_name` and `creator_user_id` to
`.bridge.json`.

`--pc-blender`: if the user also has Blender open on the PC with the MCP add-on, ask
`connect-studio` to expose it as the `blender` connector too. Otherwise Blender stays in
the cloud.

## Step 4 - The team

1. **Sidebar section:** if no section named **Grok Studio** exists, ask the user to
   create one (Bots can't), and wait.
2. **Bots:** create the five below in that section, skipping any that already exist with
   the same name. Set only the name and the instructions: the text of the listed file
   without its `---` frontmatter block, copied exactly. If an existing Bot's instructions
   differ (an older plugin version), ask once whether to update them all. Never delete a
   Bot.

| Name | Instructions file |
|---|---|
| Lead GrokBot | `<plugin>/skills/setup-bridge/lead-bot.md` |
| Coding GrokBot | `<plugin>/agents/coder.md` |
| Designer GrokBot | `<plugin>/agents/designer.md` |
| Builder GrokBot | `<plugin>/agents/builder.md` |
| Animator GrokBot | `<plugin>/agents/animator.md` |

3. Message each Bot: `[GS] HELLO from setup. Load team-protocol and your role skills, then
   reply "READY <role>".` Collect the replies while Step 5 runs.

## Step 5 - Cloud Blender

Wait for the background install (`tail -n 5 "$GS/.tools/blender-install.log"`), then run
`bash "$B" probe`. It renders a test scene headless and picks the engine. If the install
failed, show the log's last lines and the fix: usually missing system libraries or disk
space. Retry once.

## Step 6 - Readiness gate

Run every check, even after a failure. For each failure, give the exact fix, retry, and
only then mark it failed.

| # | Check | Who | How |
|---|---|---|---|
| G1 | Every Bot reaches the same Studio place and Blender | all five | `[GS] TASK ping`: `get_studio_state` with `studio_id` from `.bridge.json`, and `cloud_blender.sh version`. Reply `DONE ping <place> <state> <blender version>`. All replies must name the same place. |
| G2 | Blender -> Studio round trip | Builder | `[GS] TASK smoke-model`: `cloud_blender.sh run <plugin>/skills/blender-assets/reference/smoke_test.py` (a 2-material mesh: split by colour, audit, FBX + manifest), then `python3 <plugin>/scripts/opencloud_upload.py upload <fbx> --name GrokStudioSmoke` (waits for processing, prints the asset id), `insert_asset`, `apply_manifest.luau`, `post_import_check.luau` (must pass, no overlay Parts; result saved to `reports/smoke_import.json`), and a `screen_capture` compared with the Blender render. If the capture can't be saved as a file, compare by eye and say so. Then **delete the test model from the place**. *Skipped* without an Open Cloud key. |
| G3 | Luau + play mode | Coding writes, setup plays | Coding creates `ServerScriptService.GrokStudioSmoke` (a Script that prints `GROK_STUDIO_SMOKE_OK`). Then you take the `studio-play` lock, tell the user "running a 5-second test play", start play, wait 5 s, read `get_console_output` (the marker must be present, with no errors), stop play, release the lock, and Coding deletes the script. Never start play while the user is playing: check `get_studio_state` first. |
| G4 | Screen capture | you | `screen_capture` returns an image. Look at it: it should show the place. |

Use the locks and message formats from `team-protocol`, so the gate also tests the
team's real workflow.

Then show the user one table. Every row is **pass**, **fail: <fix>** or **skipped:
<why>**:

| | Studio | Blender | Notes |
|---|---|---|---|
| Lead / Coding / Designer / Builder / Animator GrokBot | pass | pass | |
| Connector `roblox-studio` | pass | | "<place name>", Team Create on |
| Bridge service | pass | | static URL, survives restarts |
| Cloud Blender | | pass | version, render engine |
| G2 model round trip / G3 Luau play / G4 capture | pass | | |
| Open Cloud key / Figma | pass / skipped | | owner id, scopes |

Say **ready** only if every row is pass or an accepted skip.

## Step 7 - Ready to build

- **Build:** the user describes the game here, or in Lead GrokBot. If they describe it
  here, send it to Lead GrokBot as `[GS] NEW GAME from the user: <their words, verbatim>`
  with the place name, then say "Lead GrokBot is on it. Follow along there."
- **Stays working:** the bridge restarts itself, and every task starts with a health check
  that reconnects if needed (`team-protocol`). If the PC is off or Studio is closed, the
  Lead asks the user.
- **Stop:** tell any grok-studio Bot "disconnect Studio" (`connect-studio`).
- **Anytime something is off:** run `/setup-bridge` again. It re-checks everything and
  only repairs what's broken.
