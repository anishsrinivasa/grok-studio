// extract_board.js - body for the Penpot MCP `execute_code` tool (plugin API, @penpot/plugin-types 1.4).
// Returns one board as plain JSON for converters/penpot-to-roblox. Read-only.
// Set BOARD to a top-level board name, or leave it "" to use the board around the selection.
// Save the returned JSON as games/<slug>/penpot/<Board>.json, then run the converter.
const BOARD = "";
// (JSDoc types such as Shape are declared by `npm run check:snippets`, which type-checks this
// file against @penpot/plugin-types. Never write the import-call syntax here, not even in a
// comment: the plugin sandbox (SES) rejects the whole script.)

/** @param {any} obj @param {string[]} keys */
const pick = (obj, keys) => {
  /** @type {Record<string, any>} */
  const out = {};
  for (const k of keys) {
    const v = obj[k];
    if (v !== undefined && typeof v !== "function") out[k] = v;
  }
  return out;
};

/** @param {Gradient | undefined} g */
const copyGradient = (g) =>
  g ? { ...pick(g, ["type", "startX", "startY", "endX", "endY", "width"]), stops: g.stops.map((s) => ({ ...s })) } : undefined;

/** @param {Fill[] | "mixed"} fills */
const copyFills = (fills) =>
  fills === "mixed"
    ? "mixed"
    : (fills || []).map((f) => ({
        ...pick(f, ["fillColor", "fillOpacity", "fillColorRefFile", "fillColorRefId"]),
        fillColorGradient: copyGradient(f.fillColorGradient),
        fillImage: f.fillImage ? pick(f.fillImage, ["id", "name", "width", "height", "mtype", "keepAspectRatio"]) : undefined,
      }));

const LAYOUT_KEYS = ["alignItems", "alignContent", "justifyItems", "justifyContent", "rowGap", "columnGap",
  "topPadding", "rightPadding", "bottomPadding", "leftPadding", "horizontalSizing", "verticalSizing"];

const TEXT_KEYS = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing",
  "textTransform", "align", "verticalAlign"];

/** @param {Shape} shape @returns {Record<string, any>} */
function extract(shape) {
  const d = pick(shape, ["id", "name", "type", "x", "y", "width", "height", "parentX", "parentY", "rotation",
    "opacity", "hidden", "blendMode", "proportionLock", "constraintsHorizontal", "constraintsVertical",
    "borderRadius", "borderRadiusTopLeft", "borderRadiusTopRight", "borderRadiusBottomRight", "borderRadiusBottomLeft"]);
  d.center = { x: shape.center.x, y: shape.center.y };
  d.fills = copyFills(shape.fills);
  // strokes/shadows can be null at runtime (text shapes) although the typings say arrays.
  d.strokes = (shape.strokes || []).map((s) => ({
    ...pick(s, ["strokeColor", "strokeOpacity", "strokeStyle", "strokeWidth", "strokeAlignment"]),
    strokeColorGradient: copyGradient(s.strokeColorGradient),
  }));
  d.shadows = (shape.shadows || []).map((s) => pick(s, ["style", "hidden", "offsetX", "offsetY", "blur", "spread"]));
  if (shape.blur) d.blur = pick(shape.blur, ["value", "hidden"]);
  if (shape.layoutChild) {
    d.layoutChild = pick(shape.layoutChild, ["absolute", "zIndex", "horizontalSizing", "verticalSizing", "alignSelf"]);
  }
  if (shape.isComponentInstance()) {
    const c = shape.component();
    if (c) d.component = { id: c.id, name: c.name, path: c.path };
  }
  if (shape.type === "board") {
    d.clipContent = shape.clipContent;
    if (shape.flex) d.flex = pick(shape.flex, ["dir", "wrap", ...LAYOUT_KEYS]);
    if (shape.grid) {
      d.grid = {
        ...pick(shape.grid, ["dir", ...LAYOUT_KEYS]),
        rows: shape.grid.rows.map((t) => ({ type: t.type, value: t.value })),
        columns: shape.grid.columns.map((t) => ({ type: t.type, value: t.value })),
      };
    }
  }
  if (shape.type === "text") {
    d.characters = shape.characters;
    d.growType = shape.growType;
    // Mixed styles: take the first character's style (the converter has one style per label).
    const first = shape.characters.length ? shape.getRange(0, 1) : null;
    for (const k of TEXT_KEYS) {
      const v = shape[/** @type {keyof PText} */ (k)];
      d[k] = v === "mixed" && first ? first[/** @type {keyof PTextRange} */ (k)] : v;
    }
    if (shape.fills === "mixed" && first) d.fills = copyFills(first.fills);
  }
  const kids = /** @type {any} */ (shape).children;
  if (Array.isArray(kids) && shape.type !== "boolean") {
    d.children = kids.map(extract);
  }
  return d;
}

const page = penpot.currentPage;
if (!page) throw new Error("no page is open in Penpot");
const rootId = penpot.root ? penpot.root.id : null;
/** @type {Shape | null} */
let board = null;
if (BOARD) {
  const found = page.findShapes({ name: BOARD, type: "board" }).filter((s) => !s.parent || s.parent.id === rootId);
  if (found.length !== 1) throw new Error(`${found.length} top-level boards named "${BOARD}" on page "${page.name}"`);
  board = found[0];
} else {
  /** @type {Shape | null} */
  let s = penpot.selection[0] || null;
  while (s && s.parent && s.parent.id !== rootId) s = s.parent;
  if (!s || s.type !== "board") throw new Error("select a shape inside the screen's board, or set BOARD");
  board = s;
}
return { extractor: "grok-studio extract_board.js v2", page: page.name, ...extract(board) };
