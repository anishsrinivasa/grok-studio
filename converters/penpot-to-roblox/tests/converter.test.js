// Converter tests. Fixtures are in the exact format penpot/extract_board.js returns
// (Penpot plugin API field names, absolute page coordinates); test 1 checks that.
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readFileSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { convertPenpotToRoblox } from '../dist/converter.js';

const load = (n) => JSON.parse(readFileSync(`fixtures/${n}.json`, 'utf-8'));
const convert = (n) => convertPenpotToRoblox(load(n));
const find = (els, path) => {
  let cur = { children: els };
  for (const name of path.split('/')) {
    cur = cur.children.find(c => c.name === name);
    assert(cur, `element ${path} (${name}) not found`);
  }
  return cur;
};
const close = (a, b, msg) => assert(Math.abs(a - b) < 1e-3, `${msg}: ${a} != ${b}`);

// Value sets from @penpot/plugin-types 1.4 (index.d.ts).
const ENUMS = {
  type: ['board', 'group', 'boolean', 'rectangle', 'path', 'text', 'ellipse', 'svg-raw', 'image'],
  constraintsHorizontal: ['left', 'right', 'leftright', 'center', 'scale'],
  constraintsVertical: ['top', 'bottom', 'topbottom', 'center', 'scale'],
  growType: ['fixed', 'auto-width', 'auto-height'],
  align: ['left', 'center', 'right', 'justify', null],
  verticalAlign: ['top', 'center', 'bottom', null],
};
const SHAPE_KEYS = new Set(['id', 'name', 'type', 'x', 'y', 'width', 'height', 'parentX', 'parentY', 'center', 'rotation',
  'opacity', 'hidden', 'blendMode', 'proportionLock', 'constraintsHorizontal', 'constraintsVertical', 'borderRadius',
  'borderRadiusTopLeft', 'borderRadiusTopRight', 'borderRadiusBottomRight', 'borderRadiusBottomLeft', 'fills', 'strokes',
  'shadows', 'blur', 'layoutChild', 'component', 'clipContent', 'flex', 'grid', 'characters', 'growType', 'fontFamily',
  'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing', 'textTransform', 'align', 'verticalAlign',
  'children', 'extractor', 'page']);
const FILL_KEYS = new Set(['fillColor', 'fillOpacity', 'fillColorGradient', 'fillColorRefFile', 'fillColorRefId', 'fillImage']);

function validateShape(s, parent, path) {
  for (const k of Object.keys(s)) assert(SHAPE_KEYS.has(k), `${path}: unknown key ${k}`);
  for (const [k, vals] of Object.entries(ENUMS)) if (k in s) assert(vals.includes(s[k]), `${path}: ${k}=${s[k]}`);
  for (const f of Array.isArray(s.fills) ? s.fills : []) for (const k of Object.keys(f)) assert(FILL_KEYS.has(k), `${path}: fill key ${k}`);
  for (const st of s.strokes) for (const k of Object.keys(st)) assert(k.startsWith('stroke'), `${path}: stroke key ${k}`);
  if (s.type === 'text') assert.strictEqual(typeof s.fontSize, 'string', `${path}: fontSize is a string in the plugin API`);
  if (parent) {
    close(s.x - parent.x, s.parentX, `${path}: x must be absolute (x - parent.x == parentX)`);
    close(s.y - parent.y, s.parentY, `${path}: y must be absolute`);
  }
  for (const c of s.children ?? []) validateShape(c, s, `${path}/${c.name}`);
}

describe('fixtures', () => {
  for (const n of ['hud', 'menu', 'shop']) {
    test(`${n}.json matches the plugin API shape`, () => {
      const b = load(n);
      assert.strictEqual(b.type, 'board');
      assert(b.x !== 0 || b.y !== 0, 'boards sit away from the page origin so absolute coordinates are exercised');
      validateShape(b, null, b.name);
    });
  }
});

describe('HUD', () => {
  const spec = convert('hud');
  test('spec header and images', () => {
    assert.strictEqual(spec.version, 2);
    assert.deepStrictEqual(spec.board, { id: load('hud').id, name: 'GameHUD', width: 1920, height: 1080 });
    assert.deepStrictEqual(spec.images.map(i => [i.source, i.key]), [['fill', '6b1f3a52-0d4e-80a1-8006-2c9b1e7d0a11']]);
    assert(spec.warnings.some(w => w.includes('own fill is a design backdrop')));
    assert(spec.warnings.some(w => w.includes('PauseButton') && w.includes('shadows')));
  });
  test('absolute page coordinates become parent-relative scale', () => {
    const c = find(spec.elements, 'CoinCounter');
    close(c.position.scaleX, 32 / 1920, 'x'); close(c.position.scaleY, 32 / 1080, 'y');
    close(c.size.scaleX, 300 / 1920, 'w'); close(c.size.scaleY, 86 / 1080, 'h');
    assert.deepStrictEqual(c.anchorPoint, { x: 0, y: 0 });
  });
  test('fills, stroke, corner', () => {
    const c = find(spec.elements, 'CoinCounter');
    assert.strictEqual(c.backgroundColor, '#1E1B2E');
    close(c.backgroundTransparency, 0.15, 'fillOpacity 0.85');
    assert.deepStrictEqual(c.stroke, { thickness: 3, color: '#FFD23F', transparency: 0, mode: 'Border', position: 'Inner' });
    assert.deepStrictEqual(c.corner, { scale: 0.5, offset: 0 }, 'radius 43 on an 86-high pill = scale 0.5');
  });
  test('flex row -> UIListLayout + UIPadding relative to the container itself', () => {
    const c = find(spec.elements, 'CoinCounter');
    assert.strictEqual(c.layout.type, 'List');
    assert.strictEqual(c.layout.fillDirection, 'Horizontal');
    assert.strictEqual(c.layout.verticalAlignment, 'Center');
    close(c.layout.padding.scale, 16 / 300, 'columnGap / width');
    close(c.padding.left.scale, 8 / 300, 'left / width'); close(c.padding.top.scale, 8 / 86, 'top / height');
    close(c.padding.right.scale, 24 / 300, 'right / width');
    assert.deepStrictEqual(c.children.map(k => [k.name, k.layoutOrder, k.anchorPoint.x]), [['Icon', 1, 0], ['Amount', 2, 0]]);
  });
  test('text: colour from fills, no background, plugin strings parsed', () => {
    const a = find(spec.elements, 'CoinCounter/Amount');
    assert.strictEqual(a.type, 'TextLabel');
    assert.strictEqual(a.text, '1,250');
    assert.strictEqual(a.textColor, '#FFFFFF');
    assert.strictEqual(a.backgroundTransparency, 1);
    assert.strictEqual(a.backgroundColor, undefined);
    assert.deepStrictEqual(a.font, { family: 'SourceSansPro', weight: 'Bold', style: 'Normal' });
    assert.strictEqual(a.textSize, 48);
    assert.strictEqual(a.textScaled, true);
    assert.strictEqual(a.textYAlignment, 'Top');
    const l = find(spec.elements, 'HealthBar/Label');
    assert.strictEqual(l.text, 'HP 70/100', 'textTransform uppercase applied');
    assert.strictEqual(l.textXAlignment, 'Center');
    assert.strictEqual(l.textYAlignment, 'Center');
  });
  test('image fill -> ImageLabel with aspect lock', () => {
    const i = find(spec.elements, 'CoinCounter/Icon');
    assert.strictEqual(i.type, 'ImageLabel');
    assert.deepStrictEqual(i.image, { key: '6b1f3a52-0d4e-80a1-8006-2c9b1e7d0a11', scaleType: 'Fit' });
    assert.strictEqual(i.aspectRatio, 1);
  });
  test('constraints -> anchors; hidden kept invisible', () => {
    const hp = find(spec.elements, 'HealthBar');
    assert.deepStrictEqual(hp.anchorPoint, { x: 1, y: 0 });
    close(hp.position.scaleX, (1488 + 400) / 1920, 'right edge');
    const p = find(spec.elements, 'PauseButton');
    assert.strictEqual(p.type, 'TextButton');
    assert.deepStrictEqual(p.anchorPoint, { x: 1, y: 1 });
    assert.deepStrictEqual(p.corner, { scale: 0.5, offset: 0 }, 'ellipse');
    const t = find(spec.elements, 'Toast');
    assert.strictEqual(t.visible, false);
    assert.deepStrictEqual(t.anchorPoint, { x: 0.5, y: 1 }, 'inferred: bottom centre');
  });
  test('linear gradient -> white background + UIGradient', () => {
    const f = find(spec.elements, 'HealthBar/Fill');
    assert.strictEqual(f.backgroundColor, '#FFFFFF');
    assert.strictEqual(f.backgroundTransparency, 0);
    assert.strictEqual(f.gradient.rotation, 0, 'left -> right');
    assert.deepStrictEqual(f.gradient.color, [{ time: 0, color: '#FF4D6D' }, { time: 1, color: '#FFB347' }]);
  });
});

describe('Menu', () => {
  const spec = convert('menu');
  test('vertical flex: LayoutOrder from laid-out position, not array order', () => {
    const b = find(spec.elements, 'Buttons');
    assert.strictEqual(b.layout.fillDirection, 'Vertical');
    assert.strictEqual(b.layout.horizontalAlignment, 'Center');
    close(b.layout.padding.scale, 24 / 412, 'rowGap / height');
    const order = Object.fromEntries(b.children.map(c => [c.name, c.layoutOrder]));
    assert.deepStrictEqual(order, { PlayButton: 1, ShopButton: 2, QuitButton: 3 });
    for (const c of b.children) {
      assert.strictEqual(c.type, 'TextButton');
      assert.strictEqual(c.text, '');
      assert.strictEqual(c.children[0].type, 'TextLabel');
    }
  });
  test('background gradient top -> bottom, font mapping', () => {
    assert.strictEqual(find(spec.elements, 'Background').gradient.rotation, 90);
    assert.strictEqual(find(spec.elements, 'Title').font.family, 'FredokaOne');
  });
});

describe('Shop', () => {
  const spec = convert('shop');
  test('uniform grid -> UIGridLayout', () => {
    const g = find(spec.elements, 'Panel/Items');
    assert.strictEqual(g.layout.type, 'Grid');
    close(g.layout.cellSize.scaleX, 258 / 1104, 'cell w'); close(g.layout.cellSize.scaleY, 300 / 624, 'cell h');
    close(g.layout.cellPadding.scaleX, 24 / 1104, 'gap x');
    assert.deepStrictEqual(g.children.map(c => c.layoutOrder), [1, 2, 3, 4, 5, 6]);
  });
  test('images and buttons', () => {
    assert.strictEqual(spec.images.filter(i => i.source === 'fill').length, 6);
    const closeBtn = find(spec.elements, 'Panel/CloseButton');
    assert.strictEqual(closeBtn.type, 'ImageButton', 'path named *Button -> ImageButton');
    assert.strictEqual(closeBtn.image.key, `shape:${closeBtn.id}`);
    assert(spec.images.some(i => i.source === 'shape' && i.shapeId === closeBtn.id));
    const buy = find(spec.elements, 'Panel/Items/Jetpack/BuyButton');
    assert.strictEqual(buy.type, 'TextButton');
    assert.strictEqual(find(spec.elements, 'Panel/Items/Jetpack/BuyButton/Price').text, '900');
    assert.strictEqual(find(spec.elements, 'Panel/Title').font.family, 'LuckiestGuy');
  });
});

describe('edge cases', () => {
  const shape = (o) => ({ id: o.name, x: 0, y: 0, width: 100, height: 100, fills: [], strokes: [], shadows: [], ...o });
  const board = (children, o = {}) => ({ ...shape({ name: 'B', type: 'board', width: 1000, height: 500, x: 50, y: 50 }), children, ...o });
  test('duplicate and path names are made unique and warned', () => {
    const spec = convertPenpotToRoblox(board([shape({ name: 'Rect', type: 'rectangle', x: 60 }), shape({ name: 'Rect', type: 'rectangle', x: 80 }), shape({ name: 'Icons/Star', type: 'rectangle', x: 70 })]));
    assert.deepStrictEqual(spec.elements.map(e => e.name), ['Rect', 'Rect_2', 'Star']);
    assert.strictEqual(spec.warnings.length, 2);
  });
  test('flex with an absolute child keeps fixed positions', () => {
    const b = shape({ name: 'Row', type: 'board', x: 50, y: 50, width: 400, height: 100, flex: { dir: 'row', rowGap: 0, columnGap: 10, topPadding: 0, rightPadding: 0, bottomPadding: 0, leftPadding: 0 },
      children: [shape({ name: 'A', type: 'rectangle', x: 50, y: 50, layoutChild: { absolute: true, zIndex: 0 } })] });
    const spec = convertPenpotToRoblox(board([b]));
    assert.strictEqual(spec.elements[0].layout, undefined);
    assert(spec.warnings.some(w => w.includes('absolute children')));
  });
  test('gradient stops are padded to 0..1; mixed fills tolerated', () => {
    const g = { type: 'linear', startX: 0.5, startY: 0, endX: 0.5, endY: 1, width: 1, stops: [{ color: '#000000', offset: 0.2 }, { color: '#FFFFFF', offset: 0.8, opacity: 0.5 }] };
    const spec = convertPenpotToRoblox(board([shape({ name: 'G', type: 'rectangle', x: 50, y: 50, fills: [{ fillColorGradient: g }] }), shape({ name: 'T', type: 'text', x: 50, y: 50, characters: 'x', fills: 'mixed' })]));
    const t = spec.elements[0].gradient.color.map(k => k.time);
    assert.deepStrictEqual([t[0], t[t.length - 1]], [0, 1]);
    assert.strictEqual(spec.elements[0].gradient.transparency.at(-1).value, 0.5);
    assert.strictEqual(spec.elements[1].textColor, '#000000');
  });
  test('rotation positions the centre', () => {
    const spec = convertPenpotToRoblox(board([shape({ name: 'R', type: 'rectangle', x: 150, y: 150, rotation: 45, center: { x: 200, y: 200 } })]));
    const e = spec.elements[0];
    assert.deepStrictEqual(e.anchorPoint, { x: 0.5, y: 0.5 });
    close(e.position.scaleX, 150 / 1000, 'centre x'); assert.strictEqual(e.rotation, 45);
  });
  test('rejects a non-board root', () => {
    assert.throws(() => convertPenpotToRoblox(shape({ name: 'X', type: 'rectangle' })), /must be a board/);
  });
});

describe('phone / tablet aspect', () => {
  // Absolute rects for top-level elements, like Roblox: scale size, UIAspectRatioConstraint
  // (FitWithinMaxSize), AnchorPoint. Every element must stay on screen at every viewport.
  for (const n of ['hud', 'menu', 'shop']) {
    test(`${n}: top-level elements stay on screen at 1920x1080, 844x390, 1024x768, 1280x720`, () => {
      const spec = convert(n);
      for (const [W, H] of [[1920, 1080], [844, 390], [1024, 768], [1280, 720]]) {
        for (const e of spec.elements.filter(e => e.visible)) {
          let w = e.size.scaleX * W, h = e.size.scaleY * H;
          if (e.aspectRatio) { if (w / h > e.aspectRatio) w = h * e.aspectRatio; else h = w / e.aspectRatio; }
          const x = e.position.scaleX * W - e.anchorPoint.x * w, y = e.position.scaleY * H - e.anchorPoint.y * h;
          assert(x >= -0.5 && y >= -0.5 && x + w <= W + 0.5 && y + h <= H + 0.5, `${n}/${e.name} off screen at ${W}x${H}`);
        }
      }
    });
  }
});

test('dist/ is the build of src/ (run `npm run build` and commit)', () => {
  const out = mkdtempSync(join(tmpdir(), 'penpot-dist-'));
  try {
    execFileSync(process.execPath, ['node_modules/typescript/bin/tsc', '--outDir', out], { stdio: 'pipe' });
    for (const f of readdirSync(out)) {
      assert.strictEqual(readFileSync(join('dist', f), 'utf-8'), readFileSync(join(out, f), 'utf-8'), `dist/${f} is stale`);
    }
    assert.deepStrictEqual(readdirSync('dist').sort(), readdirSync(out).sort());
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});
