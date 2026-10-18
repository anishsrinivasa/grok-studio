// Runs PenpotUIBuilder + PenpotUIVerifier against tests/roblox_mock.luau (a fake Roblox API)
// for every fixture: spec -> build -> verify PASS at desktop, phone and tablet viewports, plus
// a deliberately broken build that must FAIL. Needs a `luau` CLI (PATH or $LUAU); skipped if absent.
import { test } from 'node:test';
import assert from 'node:assert';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { convertPenpotToRoblox } from '../dist/converter.js';

function findLuau() {
  if (process.env.LUAU) return process.env.LUAU;
  const r = spawnSync('sh', ['-c', 'command -v luau'], { encoding: 'utf-8' });
  return r.status === 0 ? r.stdout.trim() : null;
}

const luau = findLuau();
const longString = (s) => `[==[${s}]==]`;

test('Luau builder + verifier against a fake Roblox API', { skip: luau ? false : 'no luau CLI (github.com/luau-lang/luau/releases)' }, () => {
  const wrap = (f) => `(function()\n${readFileSync(f, 'utf-8')}\nend)()`;
  const specs = ['hud', 'menu', 'shop']
    .map(n => `${n} = ${longString(JSON.stringify(convertPenpotToRoblox(JSON.parse(readFileSync(`fixtures/${n}.json`, 'utf-8')))))}`)
    .join(',\n');
  const src = readFileSync('tests/roblox_mock.luau', 'utf-8')
    .replace('--@@BUILDER@@', wrap('PenpotUIBuilder.luau'))
    .replace('--@@VERIFIER@@', wrap('PenpotUIVerifier.luau'))
    .replace('--@@SPECS@@', `{\n${specs}\n}`);
  const dir = mkdtempSync(join(tmpdir(), 'penpot-luau-'));
  try {
    writeFileSync(join(dir, 'run.luau'), src);
    let out;
    try {
      out = execFileSync(luau, [join(dir, 'run.luau')], { encoding: 'utf-8' });
    } catch (e) {
      assert.fail(`luau run failed:\n${e.stdout ?? ''}${e.stderr ?? ''}`);
    }
    if (process.env.VERBOSE) console.log(out);
    assert.match(out, /=== PASS ===/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
