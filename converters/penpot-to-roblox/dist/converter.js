/*
 * Penpot board (as returned by penpot/extract_board.js) -> RobloxUISpec v2.
 *
 * Sizing is scale-based: every Position/Size is a fraction of the parent, so the UI
 * follows the screen on phone, tablet and desktop. Anchors come from Penpot constraints
 * (right/center/bottom), or, for the default left/top, from where the element sits in its
 * parent, so edge-hugging elements stay on their edge when the aspect ratio changes.
 * Shapes with proportionLock and all images get a UIAspectRatioConstraint; text uses
 * TextScaled capped at the design size (UITextSizeConstraint).
 */
/** Roblox font families (Font.fromName) for Penpot / Google font names, compared lower-case without spaces. */
const FONT_FAMILIES = {
    sourcesanspro: 'SourceSansPro', sourcesans3: 'SourceSansPro', // Penpot's default font
    arial: 'Arial', helvetica: 'Arial', roboto: 'Roboto', robotomono: 'RobotoMono',
    montserrat: 'Montserrat', nunito: 'Nunito', oswald: 'Oswald', ubuntu: 'Ubuntu',
    bangers: 'Bangers', luckiestguy: 'LuckiestGuy', permanentmarker: 'PermanentMarker',
    titilliumweb: 'TitilliumWeb', inconsolata: 'Inconsolata', merriweather: 'Merriweather',
    pressstart2p: 'PressStart2P', indieflower: 'IndieFlower', kalam: 'Kalam', denkone: 'DenkOne',
    josefinsans: 'JosefinSans', jura: 'Jura', amaticsc: 'AmaticSC', michroma: 'Michroma',
    fredoka: 'FredokaOne', fredokaone: 'FredokaOne', creepster: 'Creepster',
    gotham: 'GothamSSm', gothamssm: 'GothamSSm', buildersans: 'BuilderSans',
};
const DEFAULT_FAMILY = 'BuilderSans';
const FONT_WEIGHTS = {
    '100': 'Thin', '200': 'ExtraLight', '300': 'Light', '400': 'Regular', '500': 'Medium',
    '600': 'SemiBold', '700': 'Bold', '800': 'ExtraBold', '900': 'Heavy',
};
const BUTTON_NAME = /button|btn/i;
const VECTOR_TYPES = new Set(['path', 'boolean', 'svg-raw']);
const r4 = (n) => Math.round(n * 10000) / 10000;
const clamp01 = (n) => Math.min(1, Math.max(0, n));
function hex(color) {
    if (!color)
        return undefined;
    const h = color.replace(/^#/, '');
    const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h.slice(0, 6);
    return /^[0-9a-fA-F]{6}$/.test(full) ? '#' + full.toUpperCase() : undefined;
}
function fillsOf(shape) {
    return Array.isArray(shape.fills) ? shape.fills : [];
}
function udim2(sx, sy) {
    return { scaleX: r4(sx), offsetX: 0, scaleY: r4(sy), offsetY: 0 };
}
function udim(scale) {
    return { scale: r4(scale), offset: 0 };
}
/** Roblox-safe, unique-among-siblings instance name. */
function instanceName(raw, used, warn) {
    let name = (raw.split('/').pop() || raw).trim() || 'Shape';
    if (name !== raw)
        warn(`"${raw}": renamed to "${name}" (Roblox names can't hold a path)`);
    const n = (used.get(name) ?? 0) + 1;
    used.set(name, n);
    if (n > 1) {
        const unique = `${name}_${n}`;
        warn(`"${name}": duplicate sibling name, renamed to "${unique}" (names are the contract with Coding; rename it in Penpot)`);
        name = unique;
    }
    return name;
}
function convertGradient(g, fillOpacity, where, warn) {
    if (g.type !== 'linear')
        warn(`${where}: radial gradient approximated as linear`);
    // UIGradient Rotation: 0 = left->right, 90 = top->bottom (screen y points down), same as
    // Penpot's normalized start/end points. Default Penpot gradient (0.5,0)->(0.5,1) -> 90.
    const rotation = r4((Math.atan2(g.endY - g.startY, g.endX - g.startX) * 180) / Math.PI);
    let stops = [...g.stops].sort((a, b) => a.offset - b.offset);
    if (stops.length > 20) {
        warn(`${where}: gradient has ${stops.length} stops, Roblox allows 20; extra stops dropped`);
        stops = stops.slice(0, 20);
    }
    // ColorSequence / NumberSequence must start at time 0 and end at time 1.
    if (stops[0].offset > 0)
        stops.unshift({ ...stops[0], offset: 0 });
    if (stops[stops.length - 1].offset < 1)
        stops.push({ ...stops[stops.length - 1], offset: 1 });
    return {
        rotation,
        color: stops.map(s => ({ time: r4(clamp01(s.offset)), color: hex(s.color) ?? '#FFFFFF' })),
        transparency: stops.map(s => ({ time: r4(clamp01(s.offset)), value: r4(1 - (s.opacity ?? 1) * fillOpacity) })),
    };
}
function robloxClass(shape, isContainer) {
    const button = BUTTON_NAME.test(shape.name);
    const image = shape.type === 'image' || VECTOR_TYPES.has(shape.type) || fillsOf(shape).some(f => f.fillImage);
    if (shape.type === 'text')
        return button ? 'TextButton' : 'TextLabel';
    if (image && !isContainer)
        return button ? 'ImageButton' : 'ImageLabel';
    if (button)
        return 'TextButton'; // a button container: empty Text, children inside
    if (isContainer && (shape.opacity ?? 1) < 1)
        return 'CanvasGroup';
    return 'Frame';
}
/** Anchor (0, 0.5, 1) on one axis from the constraint, or from the position for the defaults. */
function anchorFor(constraint, start, size, parentSize) {
    if (constraint === 'right' || constraint === 'bottom')
        return 1;
    if (constraint === 'center')
        return 0.5;
    if (constraint === 'scale' || constraint === 'leftright' || constraint === 'topbottom')
        return 0;
    const mid = (start + size / 2) / parentSize; // default left/top: infer from placement
    return mid < 1 / 3 ? 0 : mid > 2 / 3 ? 1 : 0.5;
}
function convertShape(shape, parent, ctx, used, index, inLayout = false) {
    const warn = (m) => ctx.warnings.push(m);
    const name = instanceName(shape.name, used, warn);
    const where = `"${name}"`;
    const PW = parent.width || 1;
    const PH = parent.height || 1;
    const w = shape.width;
    const h = shape.height;
    const relX = shape.x - parent.x; // plugin x/y are absolute page coordinates
    const relY = shape.y - parent.y;
    const kids = (shape.children ?? []).filter(c => c);
    const isContainer = kids.length > 0 && !VECTOR_TYPES.has(shape.type);
    const type = robloxClass(shape, isContainer);
    const isText = type === 'TextLabel' || (type === 'TextButton' && shape.type === 'text');
    const rotation = shape.rotation ?? 0;
    // UI*Layouts place children by their top-left corner, so laid-out children keep anchor 0,0.
    let ax = inLayout ? 0 : anchorFor(shape.constraintsHorizontal, relX, w, PW);
    let ay = inLayout ? 0 : anchorFor(shape.constraintsVertical, relY, h, PH);
    let px = relX + ax * w;
    let py = relY + ay * h;
    if (rotation && !inLayout) {
        // Roblox rotates around the element's centre; place the centre exactly.
        ax = ay = 0.5;
        const c = shape.center ?? { x: shape.x + w / 2, y: shape.y + h / 2 };
        px = c.x - parent.x;
        py = c.y - parent.y;
        warn(`${where}: rotated ${rotation} deg; check it visually (Penpot reports the rotated bounding box)`);
    }
    const el = {
        id: shape.id,
        name,
        type,
        position: udim2(px / PW, py / PH),
        size: udim2(w / PW, h / PH),
        anchorPoint: { x: ax, y: ay },
        zIndex: 1 + index + (shape.layoutChild?.zIndex ?? 0),
        visible: !shape.hidden,
        backgroundTransparency: 1,
        children: [],
    };
    if (rotation)
        el.rotation = r4(rotation);
    const opacity = shape.opacity ?? 1;
    const leafOpacity = type === 'CanvasGroup' ? 1 : opacity; // CanvasGroup fades the whole subtree
    if (type === 'CanvasGroup')
        el.groupTransparency = r4(1 - opacity);
    else if (opacity < 1 && isContainer)
        warn(`${where}: opacity on a container applied to its own fill only`);
    // Fills. Penpot lists the top-most fill first.
    const fills = fillsOf(shape);
    if (shape.fills === 'mixed')
        warn(`${where}: mixed fills; using none`);
    if (fills.length > 1)
        warn(`${where}: ${fills.length} fills; Roblox has one background, using the top one`);
    const fill = fills[0];
    if (isText) {
        if (fill?.fillColor) {
            el.textColor = hex(fill.fillColor);
            el.textTransparency = r4(1 - (fill.fillOpacity ?? 1) * leafOpacity);
        }
        else {
            el.textColor = '#000000';
            el.textTransparency = r4(1 - leafOpacity);
        }
    }
    else if (fill?.fillColorGradient) {
        el.backgroundColor = '#FFFFFF'; // UIGradient multiplies the background colour
        el.backgroundTransparency = r4(1 - leafOpacity);
        el.gradient = convertGradient(fill.fillColorGradient, fill.fillOpacity ?? 1, where, warn);
    }
    else if (fill?.fillColor && !fill.fillImage) {
        el.backgroundColor = hex(fill.fillColor);
        el.backgroundTransparency = r4(1 - (fill.fillOpacity ?? 1) * leafOpacity);
    }
    // Images: fill images by Penpot media id; vector shapes need rasterizing (export_shape).
    if (type === 'ImageLabel' || type === 'ImageButton') {
        const img = fills.find(f => f.fillImage)?.fillImage;
        if (img) {
            ctx.images.set(img.id, { key: img.id, source: 'fill', shapeId: shape.id, name: img.name ?? name, width: img.width, height: img.height });
            el.image = { key: img.id, scaleType: img.keepAspectRatio === false ? 'Stretch' : 'Fit' };
        }
        else {
            const key = `shape:${shape.id}`;
            ctx.images.set(key, { key, source: 'shape', shapeId: shape.id, name, width: w, height: h });
            el.image = { key, scaleType: 'Fit' };
            if (VECTOR_TYPES.has(shape.type))
                warn(`${where}: ${shape.type} becomes an image; export it as PNG (penpot/export_images.js) and upload`);
        }
        el.backgroundTransparency = 1;
        el.aspectRatio = r4(w / h);
    }
    // Corners: scale of the shorter side, so the look survives any screen size.
    const radii = [shape.borderRadiusTopLeft, shape.borderRadiusTopRight, shape.borderRadiusBottomRight, shape.borderRadiusBottomLeft]
        .map(v => v ?? shape.borderRadius ?? 0);
    const radius = Math.max(shape.borderRadius ?? 0, ...radii);
    if (shape.type === 'ellipse') {
        el.corner = udim(0.5);
        if (Math.abs(w - h) > 0.5)
            warn(`${where}: non-circular ellipse drawn as a pill (UICorner 0.5)`);
    }
    else if (radius > 0 && !isText) {
        el.corner = udim(Math.min(0.5, radius / Math.min(w, h)));
        if (new Set(radii).size > 1)
            warn(`${where}: per-corner radii differ; Roblox UICorner is uniform, using the largest`);
    }
    // Strokes: UIStroke (thickness in pixels; Roblox has no scale for it).
    const strokes = (shape.strokes ?? []).filter(s => s.strokeStyle !== 'none' && (s.strokeWidth ?? 0) > 0);
    if (strokes.length) {
        const s = strokes[0];
        el.stroke = {
            thickness: r4(s.strokeWidth ?? 1),
            color: hex(s.strokeColor) ?? '#000000',
            transparency: r4(1 - (s.strokeOpacity ?? 1) * leafOpacity),
            mode: isText ? 'Contextual' : 'Border',
            // UIStroke.BorderStrokePosition (Roblox default Outer) from Penpot's stroke alignment.
            position: s.strokeAlignment === 'inner' ? 'Inner' : s.strokeAlignment === 'center' ? 'Center' : 'Outer',
        };
        if (strokes.length > 1)
            warn(`${where}: ${strokes.length} strokes; Roblox draws one, using the first`);
        if (s.strokeStyle && s.strokeStyle !== 'solid')
            warn(`${where}: ${s.strokeStyle} stroke drawn solid`);
        if (s.strokeColorGradient)
            warn(`${where}: gradient stroke drawn in one colour`);
    }
    if (shape.proportionLock && !el.aspectRatio && !isText)
        el.aspectRatio = r4(w / h);
    if ((shape.shadows ?? []).some(s => !s.hidden))
        warn(`${where}: shadows are not supported in Roblox UI (dropped)`);
    if (shape.blur && !shape.blur.hidden && (shape.blur.value ?? 0) > 0)
        warn(`${where}: blur dropped`);
    if (shape.blendMode && shape.blendMode !== 'normal')
        warn(`${where}: blend mode ${shape.blendMode} dropped`);
    // Text.
    if (isText || type === 'TextButton')
        el.text = '';
    if (isText) {
        let text = shape.characters ?? '';
        if (shape.textTransform === 'uppercase')
            text = text.toUpperCase();
        else if (shape.textTransform === 'lowercase')
            text = text.toLowerCase();
        else if (shape.textTransform === 'capitalize')
            text = text.replace(/\b\w/g, c => c.toUpperCase());
        el.text = text;
        const key = (shape.fontFamily ?? '').toLowerCase().replace(/[\s_-]+/g, '');
        const family = FONT_FAMILIES[key] ?? DEFAULT_FAMILY;
        if (!FONT_FAMILIES[key])
            warn(`${where}: font "${shape.fontFamily}" not in Roblox, using ${DEFAULT_FAMILY}`);
        el.font = {
            family,
            weight: FONT_WEIGHTS[String(shape.fontWeight ?? '400')] ?? 'Regular',
            style: shape.fontStyle === 'italic' ? 'Italic' : 'Normal',
        };
        const size = parseFloat(shape.fontSize ?? '14');
        el.textSize = Number.isFinite(size) ? Math.round(size) : 14;
        el.textScaled = true; // fit the scale-sized box on any screen, capped at textSize
        // Roblox ties these together: TextWrapped = false switches TextScaled off (seen in Studio).
        // A scaled auto-width box is sized to one line at the design size, so it stays one line.
        el.textWrapped = true;
        el.textXAlignment = shape.align === 'center' ? 'Center' : shape.align === 'right' ? 'Right' : 'Left';
        el.textYAlignment = shape.verticalAlign === 'center' ? 'Center' : shape.verticalAlign === 'bottom' ? 'Bottom' : 'Top';
        if (shape.align === 'justify')
            warn(`${where}: justified text drawn left-aligned`);
        const lh = parseFloat(shape.lineHeight ?? '');
        if (Number.isFinite(lh) && lh > 0 && Math.abs(lh - 1) > 0.01)
            el.lineHeight = r4(lh);
        const ls = parseFloat(shape.letterSpacing ?? '0');
        if (Number.isFinite(ls) && ls !== 0)
            warn(`${where}: letter spacing ${ls} dropped`);
    }
    // Boards clip by default in Penpot.
    if (shape.type === 'board' && shape.clipContent !== false && isContainer)
        el.clipsDescendants = true;
    // Layouts. UI*Layout positions every GuiObject child, so only use one when the Penpot
    // layout positions every child too (no absolute children) and, for grids, cells are uniform.
    const flow = kids.filter(k => !k.hidden);
    const hasAbsolute = flow.some(k => k.layoutChild?.absolute);
    let layoutUsed = false;
    if (shape.flex && isContainer) {
        const f = shape.flex;
        if (hasAbsolute) {
            warn(`${where}: flex layout has absolute children; built with fixed positions instead of UIListLayout`);
        }
        else {
            const row = f.dir.startsWith('row');
            const main = (v) => (v === 'center' ? 'Center' : v === 'end' ? 'End' : 'Start');
            const cross = (v) => (v === 'center' ? 'Center' : v === 'end' ? 'End' : 'Start');
            const jc = f.justifyContent;
            const along = main(jc);
            const across = cross(f.alignItems);
            const toH = (v) => (v === 'Center' ? 'Center' : v === 'End' ? 'Right' : 'Left');
            const toV = (v) => (v === 'Center' ? 'Center' : v === 'End' ? 'Bottom' : 'Top');
            const gap = row ? f.columnGap : f.rowGap;
            el.layout = {
                type: 'List',
                fillDirection: row ? 'Horizontal' : 'Vertical',
                horizontalAlignment: toH(row ? along : across),
                verticalAlignment: toV(row ? across : along),
                padding: udim((gap || 0) / (row ? w : h)),
                wraps: f.wrap === 'wrap',
            };
            if (jc === 'space-between')
                el.layout.flex = 'SpaceBetween';
            else if (jc === 'space-around')
                el.layout.flex = 'SpaceAround';
            else if (jc === 'space-evenly')
                el.layout.flex = 'SpaceEvenly';
            layoutUsed = true;
        }
    }
    else if (shape.grid && isContainer) {
        const g = shape.grid;
        const sizes = new Set(flow.map(k => `${Math.round(k.width)}x${Math.round(k.height)}`));
        if (hasAbsolute || sizes.size > 1) {
            warn(`${where}: grid cells are not uniform${hasAbsolute ? ' / has absolute children' : ''}; built with fixed positions instead of UIGridLayout`);
        }
        else if (flow.length) {
            el.layout = {
                type: 'Grid',
                fillDirection: g.dir === 'column' ? 'Vertical' : 'Horizontal',
                cellSize: udim2(flow[0].width / w, flow[0].height / h),
                cellPadding: udim2((g.columnGap || 0) / w, (g.rowGap || 0) / h),
            };
            layoutUsed = true;
        }
    }
    const lay = shape.flex ?? shape.grid;
    if (layoutUsed && lay) {
        const p = [lay.topPadding, lay.rightPadding, lay.bottomPadding, lay.leftPadding].map(v => v || 0);
        if (p.some(v => v > 0)) {
            // UIPadding scale is relative to the element itself: top/bottom of its height, left/right of its width.
            el.padding = { top: udim(p[0] / h), right: udim(p[1] / w), bottom: udim(p[2] / h), left: udim(p[3] / w) };
        }
    }
    // Children. Paint order = array order (index 0 at the back). Inside a layout the plugin may
    // expose children reversed, so LayoutOrder comes from the laid-out positions instead.
    const childUsed = new Map();
    el.children = kids.map((k, i) => convertShape(k, shape, ctx, childUsed, layoutUsed ? 0 : i, layoutUsed && !k.layoutChild?.absolute));
    if (layoutUsed) {
        const vertical = el.layout && el.layout.fillDirection === 'Vertical';
        const order = kids
            .map((k, i) => ({ i, primary: vertical ? k.y : k.x, secondary: vertical ? k.x : k.y }))
            .sort((a, b) => (shape.grid
            ? (vertical ? a.primary - b.primary || a.secondary - b.secondary : a.secondary - b.secondary || a.primary - b.primary)
            : a.primary - b.primary || a.secondary - b.secondary));
        order.forEach((o, rank) => { el.children[o.i].layoutOrder = rank + 1; });
    }
    return el;
}
/** Converts a Penpot board export (penpot/extract_board.js output) to a Roblox UI spec. */
export function convertPenpotToRoblox(board) {
    if (!board || typeof board !== 'object')
        throw new Error('input is not a Penpot board export');
    if (board.type !== 'board')
        throw new Error(`root shape must be a board (got type "${board.type}")`);
    if (!(board.width > 0 && board.height > 0))
        throw new Error('board has no width/height');
    const ctx = { warnings: [], images: new Map() };
    if (fillsOf(board).some(f => f.fillColor || f.fillImage || f.fillColorGradient)) {
        ctx.warnings.push(`board "${board.name}": its own fill is a design backdrop and is not built (it would cover the game); add a full-size rectangle named Background if the screen needs one`);
    }
    const used = new Map();
    const elements = (board.children ?? []).map((c, i) => convertShape(c, board, ctx, used, i));
    return {
        version: 2,
        source: 'penpot',
        board: { id: board.id, name: board.name, width: board.width, height: board.height },
        elements,
        images: [...ctx.images.values()],
        warnings: ctx.warnings,
    };
}
