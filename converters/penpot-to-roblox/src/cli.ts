#!/usr/bin/env node
/**
 * CLI tool to convert Penpot board JSON to Roblox UI spec
 * 
 * Usage: node cli.js <penpot-board.json> [output.json]
 */

import { readFileSync, writeFileSync } from 'fs';
import { convertPenpotToRoblox } from './converter.js';

const args = process.argv.slice(2);

if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
  console.log(`
Penpot to Roblox UI Converter

Usage: node cli.js <penpot-board.json> [output.json]

Arguments:
  <penpot-board.json>  Input Penpot board export JSON
  [output.json]        Output file (defaults to stdout)

Examples:
  node cli.js board.json spec.json
  node cli.js board.json | jq .
`);
  process.exit(args.length === 0 ? 1 : 0);
}

const inputPath = args[0];
const outputPath = args[1];

try {
  // Read input
  const inputData = readFileSync(inputPath, 'utf-8');
  const board = JSON.parse(inputData);
  
  // Convert
  const spec = convertPenpotToRoblox(board);
  
  // Output
  const output = JSON.stringify(spec, null, 2);
  
  if (outputPath) {
    writeFileSync(outputPath, output, 'utf-8');
    console.error(`✓ Converted "${board.name}" to ${outputPath}`);
    
    if (spec.warnings.length > 0) {
      console.error(`\n⚠ Warnings:`);
      spec.warnings.forEach(w => console.error(`  - ${w}`));
    }
  } else {
    console.log(output);
  }
} catch (error) {
  if (error instanceof Error) {
    console.error(`Error: ${error.message}`);
  } else {
    console.error(`Error: ${String(error)}`);
  }
  process.exit(1);
}
