#!/usr/bin/env node
/**
 * penpot-to-roblox CLI: Penpot board export (penpot/extract_board.js output) -> Roblox UI spec.
 *
 *   node dist/cli.js <board.json> [spec.json]
 *
 * Writes the spec to spec.json (or stdout). Warnings always go to stderr, one per line.
 * Exit code 1 on unreadable input. No dependencies: runs with plain Node 18+.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { convertPenpotToRoblox } from './converter.js';
const args = process.argv.slice(2);
if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
    console.error('usage: node dist/cli.js <board.json> [spec.json]');
    process.exit(args.length === 0 ? 1 : 0);
}
try {
    const board = JSON.parse(readFileSync(args[0], 'utf-8'));
    const spec = convertPenpotToRoblox(board);
    const out = JSON.stringify(spec, null, 2) + '\n';
    if (args[1]) {
        writeFileSync(args[1], out, 'utf-8');
        console.error(`converted "${spec.board.name}" -> ${args[1]} (${spec.images.length} image(s) to upload)`);
    }
    else {
        process.stdout.write(out);
    }
    for (const w of spec.warnings)
        console.error(`warning: ${w}`);
}
catch (error) {
    console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
}
