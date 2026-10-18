/**
 * Input: what penpot/extract_board.js returns from the Penpot MCP `execute_code` tool.
 * Field names and value sets are the Penpot Plugin API's own (@penpot/plugin-types 1.4):
 * Shape, Fill, Stroke, Gradient, ImageData, FlexLayout, GridLayout, LayoutChildProperties,
 * Text. The snippet copies them verbatim; it adds nothing except `component`.
 *
 * Coordinates: `x`/`y` are ABSOLUTE page coordinates of the shape's top-left corner (as in
 * the plugin API); the converter makes them relative to the parent itself.
 */
export {};
