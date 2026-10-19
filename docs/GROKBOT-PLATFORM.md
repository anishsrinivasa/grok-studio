# Grok Bot Platform Capabilities

**For contributors developing grok-studio on Grok Bot**

This document describes what the Grok Bot platform provides, so you design features using real capabilities (not hypothetical ones). Updated Oct 2026 based on observed platform behavior.

---

## Core Architecture

### Multi-Bot System (Host-Provided)
- **Multiple separate bot agents**, each with:
  - Own chat interface
  - Own persona and instructions
  - Own memory and context
  - Independent turns (no shared state during execution)
  
- **Asynchronous messaging between bots**:
  - Priority messages wake the recipient immediately
  - Non-priority messages wait until recipient's next turn
  - No synchronous calls (can't wait for reply in same turn)
  - Message format: `[GS] <TYPE> <payload>` (team convention)

### Shared Infrastructure (Host-Provided)
- **One shared persistent Linux machine** for all bots:
  - Shared filesystem (`/workspace`)
  - Shared tools: Python, uv, Node.js, git, gh CLI
  - Shared installs: headless Blender, npm packages
  - Per-bot desktop and browser (separate X sessions)
  - All bots see same files and can coordinate via filesystem

- **User's PC access** (with approval):
  - Commands run on user's PC via "Execution on Local Computer"
  - User approves each command (can't be bypassed)
  - File transfer: cloud → PC (via bridge drop) and PC → cloud (manual upload)
  - Bridge exposes user's Roblox Studio via HTTPS + MCP

---

## Available Integrations

### MCP Connectors (Host-Provided)
- **Roblox Studio MCP** (via local bridge on user's PC)
- **GitHub** (read/write repos, PRs, issues)
- **Figma** (remote MCP, paid plans with Full seat for write)
- **X (Twitter)** (read-only with built-in tools)
- **Other MCPs** (user-installable via connector registration)

### External Services (User Credentials Required)
- **Roblox Open Cloud API** (user provides API key)
- **Ngrok** (user provides authtoken + static domain)
- **X API** (user provides, pay-per-use ~$0.015/post, or use scheduling connector)
- **Scheduling connectors** (Buffer, Postiz, BulkPublish - if user has them)

---

## In-Chat UI Capabilities

### ✅ CAN Use

#### 1. Question Cards (Host-Provided)
```
Question: "Do you have a Figma Professional plan with a Full seat?"
Options:
  [ ] Yes (Full seat, can write to Figma)
  [ ] No (Starter/free or View/Collab seat)
Optional: Free text field for details
```
- One question per card
- Up to 6 options
- Single-select or multi-select
- Optional free text input
- **Ends the bot's turn** (waits for user response)

#### 2. Masked Secret Entry (Host-Provided)
```
Secret: ROBLOX_OPEN_CLOUD_API_KEY
[masked input field - user types, bot never sees raw value]
```
- One value per card
- Stored as environment variable
- Bot can use the env var but never see the actual value
- Security: values may be redacted in tool results (`[REDACTED]`)
- **Limitation:** Cannot collect multiple secrets in one card

#### 3. Multi-Field Forms (Host-Provided)
```
Form: "Create Open Cloud Key"
Fields:
  - Key name: [text input]
  - Scopes: [checkboxes]
  - Expiration: [date picker]
Submit button
```
- Multiple fields of various types
- Can include validation
- Submit action returns structured data

#### 4. Saved-Login Fill (Host-Provided)
- Auto-fill credentials from user's saved logins
- Triggered when bot requests auth to a known service

#### 5. File and Image Attachments (Host-Provided)
- User can attach files/images to messages
- Bot receives file path on shared machine
- Bot can send files/images back (screenshots, renders, exports)

### ❌ CANNOT Use

#### Custom UI Beyond Cards
- ❌ No custom panels, sidebars, or webviews
- ❌ No custom buttons in chat beyond card options
- ❌ No live-updating displays or progress bars
- ❌ No embedded interactive widgets
- ❌ Specialist bots cannot pop UI into Lead's chat (must route through Lead)

#### Multi-Step Interactions in One Turn
- ❌ Cannot show question card and wait for answer in same turn
- ❌ Cannot show multiple sequential cards in one turn
- ❌ No wizard-style UI flows within a single bot turn

---

## Coordination & Workflow

### ✅ CAN Do

#### Bot-to-Bot Messaging (Host-Provided)
- Send priority messages (wakes recipient)
- Send non-priority messages (queues for next turn)
- Message any bot by name
- Track message history in shared files (convention)

#### Shared Filesystem Coordination (Host-Provided)
- Lock files for exclusive access (`/workspace/grok-studio/games/<slug>/locks/`)
- Shared state in JSON files
- Message queues via files
- Checkpoint and handoff tracking

#### Scheduled/Event-Triggered Routines (Host-Provided)
- Bots can run on schedule (cron-like)
- Bots can trigger on events (PR created, file changed, etc.)
- Used for monitoring, polling, periodic checks

#### Global Skills Library (Host-Provided)
- `SKILL.md` files in `skills/` folder
- Shared across all bots
- Referenced by name in bot instructions
- **Limitation:** New skills don't appear instantly (refresh delay)

#### Memory (Host-Provided)
- Per-bot memory (chat history, context)
- Shared memory (facts, decisions stored in files)
- No cross-bot memory access (only via messages or files)

### ❌ CANNOT Do

#### Live Back-and-Forth
- ❌ No synchronous call-and-response between bots
- ❌ Cannot wait for another bot's reply in same turn
- ❌ No "pair programming" where two bots edit together
- Must use: send message → wait for next turn → receive reply

#### Instant Skills Refresh
- ❌ Skills don't appear in bot's catalog immediately after creation
- ❌ Can't dynamically load skills mid-conversation
- Must use: create skill → bot reloads later → skill available

---

## User PC Interactions

### ✅ CAN Do (With Approval)
- **Run commands on user's PC** (Windows, macOS, Linux via WSL)
  - User approves each command individually
  - PowerShell, bash, etc.
  - Install software, run scripts, check status
  
- **File transfer**:
  - Cloud → PC: `scripts/send-to-pc.py` (via bridge file drop)
  - PC → Cloud: User uploads file via chat attachment
  
- **Bridge to Studio**:
  - Expose Roblox Studio MCP over HTTPS
  - Persistent service (survives restarts)
  - One key, one static URL
  - All Studio operations via MCP tools

### ❌ CANNOT Do
- ❌ Bypass per-command approval (security policy)
- ❌ Open or click inside Roblox Studio GUI (only via MCP tools)
- ❌ Access user's PC without "Execution on Local Computer" enabled
- ❌ Install unapproved software silently
- ❌ Modify user's files without command approval

---

## Roblox Platform Interactions

### ✅ CAN Do (With User Approval)
- **Open Cloud API** (user provides key):
  - Upload models, meshes, animations
  - Publish assets
  - Read place data
  - Manage datastores (if key has scope)

- **Creator Store** (via Studio MCP):
  - Search assets
  - Insert assets into Studio
  - Inspect asset contents

### ❌ CANNOT Do Without Explicit User Yes
- ❌ Publish anything to Roblox (needs approval)
- ❌ Spend Robux (needs approval)
- ❌ Change game settings (needs approval)
- ❌ Invite collaborators (needs approval)
- ❌ Enable Team Create (user does it manually)

---

## Content Generation

### ✅ CAN Do (Host-Provided)
- **Image generation**:
  - Icons, thumbnails, concept art
  - Multiple styles and sizes
  - Can iterate based on feedback

- **Video generation** (Host-Provided):
  - Short clips from descriptions
  - Can combine with game footage

- **Code generation**:
  - Scripts, configs, data files
  - Can use cloud coding agents for repo work

### ❌ CANNOT Do
- ❌ Watch videos directly (can only read transcripts if provided)
- ❌ Record video from Studio (can take screenshots via MCP)

---

## External Communications

### ✅ CAN Do
- **Web search and fetch** (Host-Provided)
- **GitHub** (via gh CLI or MCP):
  - Create/update PRs and issues
  - Read CI logs
  - Manage repos
  
- **X (Twitter) read-only** (Host-Provided):
  - Read tweets
  - Search
  - Cannot post with built-in tools

### ❌ CANNOT Do (Without External Service)
- ❌ Post to X with built-in tools (read-only)
  - Options: Scheduling connector (Buffer, Postiz, BulkPublish), X API (~$0.015/post), or manual drafts
- ❌ Send email directly
- ❌ Post to Discord, Slack without connectors

---

## Design Implications for Grok Studio

### Setup Flow
✅ **Must use supported UI:**
- Question cards for capability questions (Figma seat, X posting route)
- Masked secret entry for API keys (one per card)
- Multi-field forms for complex inputs
- **Fallback:** Plain numbered checklist when widgets unavailable

✅ **User-only steps as templated cards:**
```yaml
# From setup/steps.yaml
- id: install_studio
  type: manual
  title: "Install Roblox Studio"
  steps:
    - Download from roblox.com
    - Sign in
    - Open or create a place
  confirmPrompt: "Studio installed and place open?"
```

### Team Coordination
✅ **All user contact through Lead:**
- Specialists send `[GS] ASK`, `[GS] BLOCKED` to Lead
- Lead shows question cards to user
- Lead relays answers back to specialists

✅ **Async messaging:**
- Lead sends `[GS] TASK` (non-priority)
- Specialist works, sends `[GS] DONE` (priority)
- Lead wakes up, processes result

❌ **Cannot do:**
- Designer cannot pop Figma preview into Lead's chat
- Builder cannot show approval widget directly to user
- No live progress bars during long builds

### Studio Operations
✅ **All via MCP tools:**
- `execute_luau`, `multi_edit`, `screen_capture`
- `generate_procedural_model`, `generate_mesh`
- `start_stop_play`, `get_console_output`

❌ **Cannot:**
- Click buttons in Studio GUI
- Open dialogs or windows
- Drag-and-drop assets

### Publishing & Approvals
✅ **Collect approvals upfront:**
- Setup asks: "Allow uploading models?" → saved in spec
- Setup asks: "Allow publishing animations?" → saved in spec
- Lead checks approval before executing gated actions

❌ **Cannot:**
- Publish without user's explicit yes (even if already approved in setup)
- Spend Robux without confirmation
- Auto-enable Team Create

---

## Verification Notes

**Host-Provided** = Confirmed available via platform documentation or observed behavior
**User Credentials Required** = Needs external account/keys
**Convention** = grok-studio team protocol, not platform feature

Items marked (Host-Provided) are platform capabilities. Anything requiring external services, credentials, or connectors is noted explicitly.

---

## For Contributors

When adding features:
1. **Use question cards** for user choices (not free text prompts)
2. **Use masked secret entry** for credentials (one per card)
3. **Route all user contact through Lead** (specialists never show UI)
4. **Design for async messaging** (no synchronous bot calls)
5. **Provide plain text fallbacks** when widgets unavailable
6. **Collect approvals upfront** (setup phase)
7. **Use MCP tools for Studio** (never simulate GUI clicks)
8. **Check platform docs** before assuming a feature exists

See **CLAUDE.md** for repo orientation and development workflow.
