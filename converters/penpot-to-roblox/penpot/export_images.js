// export_images.js - body for the Penpot MCP `execute_code` tool. Read-only.
// Returns the PNG bytes (base64) of every image a converted spec needs, so they can be
// uploaded to Roblox. Paste the spec's "images" array as IMAGES (or a part of it if the
// result gets large). Fill images come out at their original resolution; vector shapes
// ("shape:<id>") are rendered with shape.export at SCALE.
// Save the result as JSON and run: python3 save_images.py <result.json> <outdir>
/** @type {{key: string, source: "fill" | "shape", shapeId: string}[]} */
const IMAGES = []; // e.g. [{"key":"7a1c...","source":"fill","shapeId":"..."}, {"key":"shape:...","source":"shape","shapeId":"..."}]
const SCALE = 2;

const page = penpot.currentPage;
if (!page) throw new Error("no page is open in Penpot");
/** @param {Uint8Array} bytes */
const toBase64 = (bytes) => {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
};
const out = [];
for (const img of IMAGES) {
  const shape = page.getShapeById(img.shapeId);
  if (!shape) { out.push({ key: img.key, error: "shape not found on the current page" }); continue; }
  /** @type {Uint8Array} */
  let bytes;
  if (img.source === "fill") {
    const fills = shape.fills === "mixed" ? [] : shape.fills;
    const fill = fills.find((f) => f.fillImage && f.fillImage.id === img.key);
    if (!fill || !fill.fillImage) { out.push({ key: img.key, error: "image fill not found" }); continue; }
    bytes = await fill.fillImage.data();
  } else {
    bytes = await shape.export({ type: "png", scale: SCALE });
  }
  out.push({ key: img.key, name: shape.name, png: toBase64(bytes) });
}
return out;
