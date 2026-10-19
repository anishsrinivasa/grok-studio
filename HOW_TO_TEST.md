# How to Test PR #5 End-to-End

## Prerequisites
- Roblox Studio installed (Windows or macOS)
- Grok Bot account with execution on local computer enabled
- Ngrok account with authtoken and static domain (free tier OK)
- Roblox Open Cloud API key with correct scopes

## Test Sequence

### 1. Install Plugin (5 min)
```
# In any Grok Bot:
Run curl -fsSL https://raw.githubusercontent.com/anishsrinivasa/grok-studio/cursor/extensible-roles-setup-df5f/scripts/bootstrap.sh | bash and do what it prints.
```

**Expected:** Plugin downloads to `/workspace/grok-studio/plugin`, skills linked.

### 2. Setup Studio (5 min)
- Open or create a place in Roblox Studio
- Enable **Team Create** (File > Game Settings > Security)
- Enable **Assistant > ... > Manage MCP Servers > Enable Studio as MCP server**
- In Grok Bot: Settings > General > Bot > Execution on Local Computer = "Ask every time"

### 3. Run Automatic Setup (10-15 min)
```
# Message Lead GrokBot:
Hi! Let's set up grok-studio.
```

**Expected flow:**
1. Lead auto-detects environment (Studio, bridge, Blender, API keys)
2. Shows you step cards for missing requirements:
   - If Studio MCP not enabled: card with instructions
   - If no API key: card with Open Cloud link and required scopes
   - If ngrok not set up: card asking for authtoken and domain
3. Asks capability questions (Figma seat, X posting, animation planning)
4. Collects approvals (upload models, publish animations)
5. Generates dynamic welcome message listing all 8 bots with capabilities

**Expected result:** Welcome message showing:
- 8 active bots (Lead, Coding, Designer, Builder, Animator, VFX, SFX, Marketing)
- Each bot's capabilities (full or fallback)
- Any disabled bots with requirements

### 4. Test Role Discovery (1 min)
```
# On cloud computer or locally:
cd /workspace
uv run scripts/roles.py validate
uv run scripts/roles.py list
```

**Expected:** All 8 roles valid, no conflicts.

### 5. Test Setup Resolver Headless (2 min)
```
cd /workspace
uv run scripts/selftest.py --scenario has-figma
uv run scripts/selftest.py --scenario no-figma
```

**Expected:** Both scenarios pass, welcome messages generated.

### 6. Test Simple Build Task (30-60 min, optional)
```
# In Lead GrokBot:
Make a simple coin collection game: player walks around and collects 10 gold coins to win. Low-poly style, mobile UI. Just the basic mechanics, no polish.
```

**Expected:** Lead creates spec, dispatches tasks to Coding, Designer, Builder. Each specialist reports DONE. Lead runs playtest.

## Validation Commands

### Local Validation (anytime)
```bash
cd /workspace

# Validate all 8 roles
uv run scripts/roles.py validate

# Test setup resolver with fixtures
uv run scripts/setup.py --self-check

# Validate example spec
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('skills/game-spec/example.game-spec.json')), json.load(open('skills/game-spec/schema.json'))); print('✓ valid')"

# Test gate validator (needs a game with spec)
python3 scripts/validate-spec-gates.py <slug>

# Test MCP healing (safe, kills only caller's children)
bash scripts/heal-mcp-session.sh

# Run complete selftest
uv run scripts/selftest.py
```

## Known Gaps & Limitations

### ⚠️ Not Yet Implemented (but system ready for them)
1. **Lead automatic setup execution** - Setup definitions (steps.yaml), resolver, and welcome template are complete and tested. Lead skill needs rewrite to execute the flow (detect → steps → questions → resolve → welcome).

2. **Readiness gates (G1-G5)** - Gate definitions exist in steps.yaml but automated execution pending.

3. **VFX/SFX/Marketing task routing** - Roles are fully defined, manifests complete, skills written. Need testing in actual game builds.

### ✅ Fully Working
- Role discovery and validation (8 roles)
- Setup resolver with capability resolution
- Dynamic welcome message generation
- General acceptance framework (extensible, game-agnostic)
- All 7 playtest failure fixes with rules, patterns, checks
- Team protocol with 8-bot coordination
- Example spec with new fields (vfx[], marketing)

## Success Criteria
- [ ] Plugin installs successfully
- [ ] Studio MCP bridge connects
- [ ] Lead responds to setup request
- [ ] All 8 roles discovered and active
- [ ] Welcome message shows all bots with capabilities
- [ ] Validation commands pass
- [ ] (Optional) Simple build task completes with DONE reports

## Troubleshooting

**Plugin doesn't install:**
- Check internet connection
- Verify bootstrap.sh URL is correct
- Try manual clone: `git clone https://github.com/anishsrinivasa/grok-studio.git /workspace/grok-studio`

**Setup hangs:**
- Check Studio is running with place open
- Verify Team Create is ON
- Check Studio MCP toggle is enabled
- Run `bash scripts/heal-mcp-session.sh` if Studio tools fail

**Roles don't validate:**
- Ensure you're on branch `cursor/extensible-roles-setup-df5f`
- Pull latest: `git pull origin cursor/extensible-roles-setup-df5f`
- Check for JSON syntax errors: `python3 -m json.tool roles/*/manifest.json`

**Welcome message missing bots:**
- Check detection fixture matches your environment
- Verify all role manifests have valid capabilities
- Run `uv run scripts/setup.py --self-check` to see resolution

## Report Issues
If something doesn't work:
1. Run all validation commands and include output
2. Check `/tmp/cursor/async-install/install-user.log` for setup errors
3. Include Lead GrokBot's response to setup request
4. Note which step failed (install, detect, questions, resolve, welcome)
