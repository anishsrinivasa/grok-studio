#!/usr/bin/env node
// files-server.mjs - the bridge's file drop: lets a cloud agent put files on this PC.
//
// Two modes, one file, no dependencies (Node 18+):
//
//   node files-server.mjs              MCP server over stdio (newline-delimited JSON-RPC).
//                                      supergateway serves it at /files/mcp behind the
//                                      bridge's API key. Tools: put_file, list_files,
//                                      delete_file. One process per client session.
//   node files-server.mjs --http PORT  Read-only HTTP server on 127.0.0.1:PORT for the same
//                                      folder, so Roblox Studio (on this PC) can fetch a
//                                      dropped image for upload_image. GET/HEAD only, no
//                                      listing, loopback only, a per-session token in the
//                                      path. One process per bridge run.
//
// Environment (set by start-bridge.ps1 / start-bridge.sh):
//   GROK_STUDIO_DROP_DIR    the drop folder (default ~/grok-studio/drop)
//   GROK_STUDIO_DROP_DIR_DISPLAY  (WSL) the same folder as Windows sees it, used for localPath
//   GROK_STUDIO_HTTP_BASE   http://127.0.0.1:<port>/<token> - returned as httpUrl by put_file
//   GROK_STUDIO_HTTP_TOKEN  the token the --http mode requires as its first path segment
//
// IMPORTANT: in stdio mode, stdout is the MCP channel. Diagnostics go to stderr only.

import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import process from "node:process";

const DROP_DIR = path.resolve(process.env.GROK_STUDIO_DROP_DIR || path.join(os.homedir(), "grok-studio", "drop"));
const HTTP_BASE = (process.env.GROK_STUDIO_HTTP_BASE || "").replace(/\/+$/, "");
const HTTP_TOKEN = process.env.GROK_STUDIO_HTTP_TOKEN || "";
// Under WSL the drop folder is a Linux path but Studio runs on Windows: when this is set,
// localPath is reported in the Windows form (e.g. \\wsl.localhost\<distro>\home\me\grok-studio\drop).
const DISPLAY_DIR = (process.env.GROK_STUDIO_DROP_DIR_DISPLAY || "").replace(/[\\/]+$/, "");

const MAX_FILE_BYTES = 200 * 1024 * 1024; // a dropped file may grow to 200 MB through appends
const MAX_CHUNK_BASE64 = 16 * 1024 * 1024; // one put_file call carries at most ~12 MB
const WINDOWS_RESERVED = /^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$/i;

function log(msg) {
  process.stderr.write(`[grok-studio/files] ${msg}\n`);
}

// Turn a client-supplied relative path into an absolute path inside DROP_DIR, or throw.
function resolveInDrop(rel) {
  if (typeof rel !== "string" || rel.length === 0 || rel.length > 400) throw new Error("path must be a non-empty relative path (max 400 chars)");
  if (rel.includes("\0")) throw new Error("path contains a NUL byte");
  const norm = rel.replace(/\\/g, "/");
  if (norm.startsWith("/") || /^[a-zA-Z]:/.test(norm)) throw new Error("path must be relative to the drop folder");
  const parts = norm.split("/").filter((p) => p.length > 0);
  if (parts.length === 0) throw new Error("path is empty");
  for (const p of parts) {
    if (p === "." || p === "..") throw new Error("path must not contain '.' or '..' segments");
    if (/[<>:"|?*\x00-\x1f]/.test(p)) throw new Error(`invalid character in path segment '${p}'`);
    if (WINDOWS_RESERVED.test(p)) throw new Error(`reserved file name '${p}'`);
    if (/[. ]$/.test(p)) throw new Error(`path segment '${p}' must not end with a dot or space`);
  }
  const abs = path.resolve(DROP_DIR, ...parts);
  if (abs !== DROP_DIR && !abs.startsWith(DROP_DIR + path.sep)) throw new Error("path escapes the drop folder");
  return { abs, rel: parts.join("/") };
}

function displayPath(abs, rel) {
  if (!DISPLAY_DIR) return abs;
  const sep = DISPLAY_DIR.includes("\\") ? "\\" : "/";
  return DISPLAY_DIR + sep + rel.split("/").join(sep);
}

function httpUrlFor(rel) {
  if (!HTTP_BASE) return null;
  return `${HTTP_BASE}/${rel.split("/").map(encodeURIComponent).join("/")}`;
}

// ---------------------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------------------
const TOOLS = [
  {
    name: "put_file",
    description:
      "Write a file into the grok-studio drop folder on the user's PC. Send big files in chunks: " +
      "the first call with append=false (creates/truncates), the rest with append=true. Returns " +
      "localPath (an absolute path on the PC, e.g. for Studio's store_image or the 3D Importer) and " +
      "httpUrl (reachable from Roblox Studio on the PC only, e.g. for upload_image).",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Relative path inside the drop folder, e.g. 'lava-leap/icons/coin.png'." },
        base64: { type: "string", description: "File content (or this chunk of it), base64-encoded." },
        append: { type: "boolean", description: "Append to the file instead of replacing it. Default false." },
      },
      required: ["path", "base64"],
    },
  },
  {
    name: "list_files",
    description: "List files in the drop folder (relative path, size, modified time). At most 500 entries.",
    inputSchema: {
      type: "object",
      properties: { prefix: { type: "string", description: "Only list paths starting with this relative prefix." } },
    },
  },
  {
    name: "delete_file",
    description: "Delete one file from the drop folder.",
    inputSchema: {
      type: "object",
      properties: { path: { type: "string", description: "Relative path inside the drop folder." } },
      required: ["path"],
    },
  },
];

function toolPutFile(args) {
  const { abs, rel } = resolveInDrop(args.path);
  if (typeof args.base64 !== "string") throw new Error("base64 must be a string");
  if (args.base64.length > MAX_CHUNK_BASE64) throw new Error(`chunk too large (max ${MAX_CHUNK_BASE64} base64 chars); send smaller chunks with append=true`);
  if (!/^[A-Za-z0-9+/=_-]*$/.test(args.base64)) throw new Error("base64 contains invalid characters");
  const data = Buffer.from(args.base64.replace(/-/g, "+").replace(/_/g, "/"), "base64");
  const append = args.append === true;
  const before = append && fs.existsSync(abs) ? fs.statSync(abs).size : 0;
  if (before + data.length > MAX_FILE_BYTES) throw new Error(`file would exceed ${MAX_FILE_BYTES} bytes`);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  if (append) fs.appendFileSync(abs, data);
  else fs.writeFileSync(abs, data);
  const bytes = fs.statSync(abs).size;
  return { localPath: displayPath(abs, rel), httpUrl: httpUrlFor(rel), bytes, path: rel };
}

function toolListFiles(args) {
  const prefix = typeof args?.prefix === "string" ? args.prefix.replace(/\\/g, "/") : "";
  const out = [];
  const walk = (dir, relDir) => {
    let entries = [];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (out.length >= 500) return;
      const rel = relDir ? `${relDir}/${e.name}` : e.name;
      const abs = path.join(dir, e.name);
      if (e.isDirectory()) walk(abs, rel);
      else if (e.isFile() && rel.startsWith(prefix)) {
        const st = fs.statSync(abs);
        out.push({ path: rel, bytes: st.size, modified: st.mtime.toISOString() });
      }
    }
  };
  walk(DROP_DIR, "");
  return { dropDir: DISPLAY_DIR || DROP_DIR, files: out, truncated: out.length >= 500 };
}

function toolDeleteFile(args) {
  const { abs, rel } = resolveInDrop(args.path);
  if (!fs.existsSync(abs)) return { path: rel, deleted: false };
  if (!fs.statSync(abs).isFile()) throw new Error("not a file");
  fs.unlinkSync(abs);
  return { path: rel, deleted: true };
}

const HANDLERS = { put_file: toolPutFile, list_files: toolListFiles, delete_file: toolDeleteFile };

// ---------------------------------------------------------------------------------------
// MCP over stdio
// ---------------------------------------------------------------------------------------
const SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

function handle(msg) {
  const isRequest = msg && typeof msg === "object" && "id" in msg && typeof msg.method === "string";
  if (!isRequest) return; // notifications (initialized, cancelled) and stray responses need no answer
  const reply = (result) => send({ jsonrpc: "2.0", id: msg.id, result });
  const fail = (code, message) => send({ jsonrpc: "2.0", id: msg.id, error: { code, message } });

  switch (msg.method) {
    case "initialize": {
      const asked = msg.params?.protocolVersion;
      reply({
        protocolVersion: SUPPORTED_VERSIONS.includes(asked) ? asked : SUPPORTED_VERSIONS[1],
        capabilities: { tools: {} },
        serverInfo: { name: "grok-studio-files", version: "0.2.0" },
        instructions: "File drop on the user's PC for the grok-studio bridge. Use put_file in chunks for big files.",
      });
      return;
    }
    case "ping":
      reply({});
      return;
    case "tools/list":
      reply({ tools: TOOLS });
      return;
    case "tools/call": {
      const name = msg.params?.name;
      const handler = HANDLERS[name];
      if (!handler) {
        fail(-32602, `Unknown tool: ${name}`);
        return;
      }
      try {
        const result = handler(msg.params?.arguments ?? {});
        reply({ content: [{ type: "text", text: JSON.stringify(result) }], structuredContent: result, isError: false });
      } catch (err) {
        reply({ content: [{ type: "text", text: `Error: ${err.message}` }], isError: true });
      }
      return;
    }
    default:
      fail(-32601, `Method not found: ${msg.method}`);
  }
}

function runStdio() {
  fs.mkdirSync(DROP_DIR, { recursive: true });
  let buf = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } });
        continue;
      }
      if (Array.isArray(msg)) msg.forEach(handle);
      else handle(msg);
    }
  });
  process.stdin.on("end", () => process.exit(0));
}

// ---------------------------------------------------------------------------------------
// Read-only HTTP for Studio
// ---------------------------------------------------------------------------------------
const TYPES = {
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp",
  ".tga": "image/x-tga", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
  ".gltf": "model/gltf+json", ".glb": "model/gltf-binary", ".fbx": "application/octet-stream",
  ".obj": "text/plain; charset=utf-8", ".rbxm": "application/octet-stream", ".rbxmx": "application/xml",
};

function runHttp(port) {
  if (!HTTP_TOKEN) {
    log("GROK_STUDIO_HTTP_TOKEN is not set; refusing to serve files without a path token.");
    process.exit(1);
  }
  fs.mkdirSync(DROP_DIR, { recursive: true });
  const allowedHosts = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);
  const server = http.createServer((req, res) => {
    const deny = (code, text) => {
      res.writeHead(code, { "content-type": "text/plain; charset=utf-8" });
      res.end(text);
    };
    if (!allowedHosts.has(String(req.headers.host || "").toLowerCase())) return deny(421, "wrong host");
    if (req.method !== "GET" && req.method !== "HEAD") return deny(405, "read-only");
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(req.url, `http://127.0.0.1:${port}`).pathname);
    } catch {
      return deny(400, "bad url");
    }
    const segs = pathname.split("/").filter(Boolean);
    if (segs.length < 2 || segs[0] !== HTTP_TOKEN) return deny(404, "not found");
    let target;
    try {
      target = resolveInDrop(segs.slice(1).join("/")).abs;
    } catch {
      return deny(404, "not found");
    }
    fs.stat(target, (err, st) => {
      if (err || !st.isFile()) return deny(404, "not found");
      res.writeHead(200, {
        "content-type": TYPES[path.extname(target).toLowerCase()] || "application/octet-stream",
        "content-length": st.size,
        "cache-control": "no-store",
      });
      if (req.method === "HEAD") return res.end();
      fs.createReadStream(target).pipe(res);
    });
  });
  server.on("error", (err) => {
    log(`HTTP server error: ${err.message}`);
    process.exit(1);
  });
  server.listen(port, "127.0.0.1", () => log(`serving ${DROP_DIR} read-only on http://127.0.0.1:${port}/<token>/...`));
  for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(sig, () => server.close(() => process.exit(0)));

  // Exit with the bridge script even if it is killed without running its cleanup.
  const parentFlag = process.argv.indexOf("--parent-pid");
  const parentPid = parentFlag >= 0 ? Number(process.argv[parentFlag + 1]) : 0;
  if (Number.isInteger(parentPid) && parentPid > 0) {
    setInterval(() => {
      try {
        process.kill(parentPid, 0);
      } catch {
        log(`bridge process ${parentPid} is gone; stopping.`);
        process.exit(0);
      }
    }, 2000).unref();
  }
}

const httpFlag = process.argv.indexOf("--http");
if (httpFlag >= 0) {
  const port = Number(process.argv[httpFlag + 1]);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    log("usage: node files-server.mjs --http <port>");
    process.exit(2);
  }
  runHttp(port);
} else {
  runStdio();
}
