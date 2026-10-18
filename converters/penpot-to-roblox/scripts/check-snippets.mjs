// Type-checks penpot/*.js (MCP execute_code bodies) against @penpot/plugin-types:
// each body is wrapped the way the Penpot MCP plugin runs it, (async () => { <body> })(),
// with `penpot` typed as the plugin API's Penpot. Exit code 1 on any type error.
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const dir = '.snippet-check';
rmSync(dir, { recursive: true, force: true });
mkdirSync(dir);
const files = readdirSync('penpot').filter(f => f.endsWith('.js'));
for (const f of files) {
  const body = readFileSync(join('penpot', f), 'utf-8');
  writeFileSync(join(dir, f), `// @ts-check\n/** @type {import("@penpot/plugin-types").Penpot} */\nvar penpot;\nexport const run = async () => {\n${body}\n};\n`);
}
writeFileSync(join(dir, 'tsconfig.json'), JSON.stringify({
  compilerOptions: { allowJs: true, checkJs: true, noEmit: true, strict: true, target: 'ES2022',
    module: 'ES2022', moduleResolution: 'node', lib: ['ES2022', 'DOM'], skipLibCheck: false, types: [] },
  include: ['*.js'],
}));
try {
  execFileSync(process.execPath, ['node_modules/typescript/bin/tsc', '-p', dir], { stdio: 'inherit' });
  console.log(`snippets OK against @penpot/plugin-types: ${files.join(', ')}`);
} catch {
  process.exitCode = 1;
} finally {
  rmSync(dir, { recursive: true, force: true });
}
