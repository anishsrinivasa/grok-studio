#!/usr/bin/env node
// studio-mcp.mjs - cross-platform launcher for the Roblox Studio built-in MCP server.
//
// Why this exists: a plugin's mcp.json cannot be OS-conditional, but Roblox ships the
// Studio MCP server at a different location on each OS (see
// https://create.roblox.com/docs/studio/mcp):
//   Windows: cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat
//   macOS:   /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
// This launcher picks the right one at runtime and hands stdio straight through, so the
// MCP client talks to Studio exactly as if it had launched the binary itself.
//
// Override: set ROBLOX_STUDIO_MCP_PATH to a custom path (e.g. a non-default install).
//   - A path ending in .bat/.cmd is run through cmd.exe /c on Windows.
//   - Anything else is executed directly.
//
// IMPORTANT: stdout is the MCP protocol channel. Never print anything to stdout here;
// diagnostics go to stderr only.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";

function fail(message) {
  process.stderr.write(`[grok-studio/studio-mcp] ${message}\n`);
  process.exit(1);
}

function resolveCommand() {
  const override = process.env.ROBLOX_STUDIO_MCP_PATH;
  if (override) {
    if (!existsSync(override)) fail(`ROBLOX_STUDIO_MCP_PATH points to a missing file: ${override}`);
    if (process.platform === "win32" && /\.(bat|cmd)$/i.test(override)) {
      return { command: "cmd.exe", args: ["/c", override] };
    }
    return { command: override, args: [] };
  }

  if (process.platform === "win32") {
    const localAppData = process.env.LOCALAPPDATA;
    if (!localAppData) fail("LOCALAPPDATA is not set; cannot locate Roblox\\mcp.bat.");
    const bat = path.join(localAppData, "Roblox", "mcp.bat");
    if (!existsSync(bat)) {
      fail(
        `Not found: ${bat}. Install/update Roblox Studio, then enable ` +
          "Assistant > ... > Manage MCP Servers > 'Enable Studio as MCP server'."
      );
    }
    return { command: "cmd.exe", args: ["/c", bat] };
  }

  if (process.platform === "darwin") {
    const candidates = [
      "/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP",
      path.join(process.env.HOME ?? "", "Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
    ];
    const found = candidates.find((p) => p && existsSync(p));
    if (!found) {
      fail(
        `StudioMCP not found in: ${candidates.join(", ")}. Install/update Roblox Studio, ` +
          "or set ROBLOX_STUDIO_MCP_PATH."
      );
    }
    return { command: found, args: [] };
  }

  fail(
    `Roblox Studio only runs on Windows and macOS (this is ${process.platform}). ` +
      "If your agent runs on a remote Linux box, use bridge/start-bridge.(ps1|sh) on the PC " +
      "that runs Studio and connect to it as a remote MCP server instead."
  );
}

const { command, args } = resolveCommand();
const child = spawn(command, args, { stdio: "inherit", windowsHide: true });

child.on("error", (err) => fail(`Failed to start ${command}: ${err.message}`));
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});

// Forward termination so Studio's MCP process does not linger after the client quits.
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => {
    if (!child.killed) child.kill(sig);
  });
}
