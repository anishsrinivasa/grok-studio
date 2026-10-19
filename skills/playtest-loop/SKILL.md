---
name: playtest-loop
description: Automated playtest-and-fix loop for Roblox games through the Studio MCP - start/stop play, simulate player input and navigation, inspect server/client state with Luau, read console output, take screenshots, fix errors, and repeat until the game runs error-free and every acceptance test in game-spec.json passes (bounded iterations, written report). Use after writing or changing game code, or as the final gate of a one-shot build.
---

# Playtest loop

Prove the game works. Run the acceptance tests from `game-spec.json`, fix what fails, and
stop with a report. This is the orchestrator's **definition-of-done gate**.

**Team mode (`team-protocol`): only the Lead runs this skill.** Before starting play, take
the `studio-play` lock and send `[GS] PLAY ON` to every specialist. After stopping, release
it and send `[GS] PLAY OFF`. In step 3 you don't fix other owners' work: send each failure
as `[GS] FIX #n` to its owner (scripts to Coding, UI to Designer, world and models to
Builder, animations to Animator) with the evidence, wait for their `DONE`, then replay.
The iteration limits below count those rounds.

## Tools (Studio MCP, https://create.roblox.com/docs/studio/mcp)

`get_studio_state`, `start_stop_play`, `get_console_output`, `execute_luau`
(`datamodel_type`: `Edit` | `Server` | `Client`), `screen_capture` (optional camera
position/look-at), `character_navigation`, `user_keyboard_input`, `user_mouse_input`,
`search_game_tree`, `inspect_instance`, `script_read`, `multi_edit`, and `subagent` (type
`playtest` can run a gameplay scenario autonomously - useful for long scenarios; still
verify its claims with your own state checks). Every call needs `studio_id`: get it from `list_roblox_studios` at the start of the run,
matching the game's place id. It changes whenever Studio restarts, so never reuse a saved one.

## Limits

- **Max 8 fix iterations** per run (an iteration = playtest -> diagnose -> fix -> replay).
  Max 3 attempts on the same error signature before changing approach (rewrite the
  function, simplify the mechanic, or mark it blocked).
- Keep each `get_console_output` read focused (only new lines since the last read; note the
  last line you saw).
- Never "fix" a test by weakening it. If the spec was wrong, edit the spec (and note it in
  `meta.assumptions`) - then the code.

## Procedure

### 0. Pre-flight (Edit mode)
1. `get_studio_state` - if playing, `start_stop_play` to stop.
2. Require-check every ModuleScript (see `roblox-code` > Writing scripts, step 4). Fix all
   `ERR` lines before playing.
3. Static scan with `script_grep` for common bugs: `wait(` (use `task.wait`),
   `:connect(`, `game.Players.LocalPlayer` in server Scripts, `InvokeClient`,
   `loadstring`, `getfenv`. Fix hits.
4. Clear noise: note the current end of `get_console_output` so later reads only consider
   new output.

### 1. Boot test
1. `start_stop_play` (start). Wait ~3-5 s (use `get_studio_state` until it reports play).
2. `get_console_output`: any red error (stack traces, "attempt to index nil",
   "Infinite yield possible") is a failure. Infinite-yield warnings are failures if they
   reference your own instances. Save the output to a file (MCP `write_to_file`) and run
   `python3 <plugin>/scripts/console_classify.py <file> [--marker <a line your scripts
   print>]`: it drops Roblox/CorePackages/plugin noise and lists fail / warn / expected
   lines. For a `ContentId ... failed` warning, `<plugin>/scripts/find_asset_refs.luau`
   tells whether the place references that id at all.
3. Server snapshot via `execute_luau` (`Server`):
   ```lua
   local out = {}
   for _, p in game:GetService("Players"):GetPlayers() do
       local ls = p:FindFirstChild("leaderstats")
       local stats = {}
       if ls then for _, v in ls:GetChildren() do table.insert(stats, v.Name .. "=" .. tostring((v :: any).Value)) end end
       table.insert(out, p.Name .. " char=" .. tostring(p.Character ~= nil) .. " " .. table.concat(stats, ","))
   end
   return table.concat(out, "\n")
   ```
4. Client snapshot via `execute_luau` (`Client`): PlayerGui contents, visible screens.
5. `screen_capture` once for the record.

### 2. Acceptance tests
For each `acceptanceTests[]` item, in order:
1. Drive the steps with input tools:
   - Movement: `character_navigation` to a position or instance path (e.g. the first
     `Coin`-tagged part - get its path via `execute_luau` `Server` + `CollectionService`).
   - Jump/actions: `user_keyboard_input` (Space, E, etc.).
   - UI: `user_mouse_input` targeting the button instance.
   - Exploit tests: from `execute_luau` (`Client`), fire the remote with bad data, e.g.
     `game.ReplicatedStorage.Remotes.RequestUnlock:FireServer("stage3")` with 0 coins, or
     wrong types (`FireServer({})`, `FireServer(0/0)`), then check server state didn't
     change.
2. Assert with state, not vibes: read values via `execute_luau` on the side that owns the
   truth (server for currency/unlocks), and check `get_console_output` for new errors.
3. Use `screen_capture` when the expected result is visual (UI shows, animation plays,
   asset placed). Look at the image; describe what you see in the report.
4. Mark `status` = `pass` / `fail` with a one-line reason.

### 3. Diagnose and fix
For each failure:
1. Locate: error stack trace -> `script_read` the reported lines. No stack trace ->
   instrument: temporarily add `print("[DBG] ...")` lines, replay, read output, then remove
   them.
2. Classify: (a) script error, (b) logic bug, (c) missing instance/tag/asset, (d) timing
   (race on `WaitForChild`/character load), (e) spec mismatch.
3. **Stop play before editing** (`start_stop_play`) - edits made during play mode are lost
   when play stops. Fix with `multi_edit` (scripts) or `execute_luau` `Edit` (instances).
4. Re-run the require-check, then restart from **step 1 Boot test** (fixes can break other
   things). Re-run only failed tests plus a smoke of the core loop to save time, but do a
   full pass at the end.

### 4. Core-loop run
At least once, complete the core loop end-to-end exactly as a player would (simulated
input only, no teleport shortcuts) and capture 2-3 screenshots along the way. These are also
great thumbnail candidates.

### 5. Stop and report
`start_stop_play` (stop). Write the report to `playtest-report-<n>.md` in the project (and
reference it in `build.playtestReports`):

```markdown
# Playtest report <n> - <title> - <ISO time>
Result: PASS | FAIL (iterations used: x/8)

## Acceptance tests
| id | description | result | notes |
|----|-------------|--------|-------|

## Errors fixed
- <signature> -> <root cause> -> <fix> (file/path)

## Remaining issues / warnings
- ...

## Evidence
- Screenshots: <descriptions>
- Console: no errors in final run (last N lines summarized)

## Notes for the user
- Manual checks worth doing on a real phone; DataStore behavior needs API access enabled.
```

Update `scripts[].status = "verified"` for scripts exercised without errors and
`ui.screens[].status = "verified"` for screens checked visually.

## Playtest checklist (every integration run)

- [ ] `get_studio_state` is in Edit mode, nobody else is playing, and the `studio-play` lock is taken
- [ ] Require-check clean; console noted
- [ ] Boot: no red errors, character spawns, HUD visible
- [ ] Every acceptance test run and marked, with evidence
- [ ] Core loop completed once by simulated input; 2-3 captures
- [ ] At least one exploit attempt rejected by the server
- [ ] UI captured at desktop and phone sizes
- [ ] No overlay Parts or floating geometry seen in captures
- [ ] Play stopped, lock released, `PLAY OFF` sent, report written, `FIX` tasks sent

## Common Roblox failure patterns

- `Infinite yield possible on ...WaitForChild` -> instance never created or wrong name;
  check the builder ran in Edit and the name matches the spec.
- Remote fires but nothing happens -> server listener in a module whose `start()` never
  ran; check `Main` ORDER and console for the `[Main] Server started` line.
- Character-dependent code fails on respawn -> connect `CharacterAdded` and handle the
  current character too.
- UI not updating -> controller looks in `StarterGui` instead of `PlayerGui`.
- DataStore errors in Studio -> API access disabled; the DataService must degrade
  gracefully (warn, not error).
- Touch events firing many times -> debounce per player.
