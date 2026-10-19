# Agent Development Resources

**For AI assistants and contributors developing grok-studio**

This repository is designed for development by Claude and other AI coding assistants on the Grok Bot platform.

## Primary Documentation

👉 **[CLAUDE.md](CLAUDE.md)** - Start here for repo orientation
- Repository layout and file structure
- How to add roles, skills, and setup steps
- Development workflow and validation commands
- Testing procedures and conventions
- Key files and quick reference

👉 **[docs/GROKBOT-PLATFORM.md](docs/GROKBOT-PLATFORM.md)** - Platform capabilities reference
- What Grok Bot CAN and CANNOT do
- Multi-agent architecture and coordination
- In-chat UI primitives (cards, forms, secrets)
- MCP connectors and integrations
- Design implications for setup, publishing, approvals
- Verification notes on host-provided features

## Additional Resources

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Complete guide to adding custom roles, "Lessons to Rules" section
- **[README.md](README.md)** - User-facing quick start (install, `/setup-bridge`, the 8 Bots)

---

**Quick Links:**
- Role schema: [`roles/role-manifest.schema.json`](roles/role-manifest.schema.json)
- Spec schema: [`skills/game-spec/schema.json`](skills/game-spec/schema.json)
- Team protocol: [`skills/team-protocol/SKILL.md`](skills/team-protocol/SKILL.md)
- Validation: [`scripts/validate.py`](scripts/validate.py), [`scripts/roles.py`](scripts/roles.py)
