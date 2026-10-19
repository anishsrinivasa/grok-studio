# Welcome to Grok Studio!

Your team is ready to build. Here's who's on it:

{{#activeRoles}}
## {{name}}
*{{description}}*

**What {{name}} can do:**
{{#keyCapabilities}}
- {{.}}
{{/keyCapabilities}}

**Using:** {{integration}}

---
{{/activeRoles}}

{{#disabledRoles}}
## {{name}} (Disabled)
*{{description}}*

**What it needs:** {{requirements}}

---
{{/disabledRoles}}

{{#setupSummary}}
**Your setup:**
- **Studio:** {{studioConnection}} ({{placeInfo}})
- **Blender:** {{blenderPath}}
{{#figmaStatus}}
- **Figma:** {{figmaStatus}}
{{/figmaStatus}}
{{#openCloudKey}}
- **Open Cloud:** {{openCloudKey}}
{{/openCloudKey}}
{{/setupSummary}}

**Next steps:**
1. Describe your game idea here or message **Lead GrokBot** directly
2. The team works in parallel and reports back through Lead
3. Lead runs playtests and the final gate before handoff

**Commands:**
- `/setup-bridge` - rerun setup (fixes connection issues)
- Message any specialist Bot to "disconnect Studio" to stop

Let's build something great! 🎮
