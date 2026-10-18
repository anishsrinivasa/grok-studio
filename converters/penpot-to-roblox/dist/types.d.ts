/**
 * Input: what penpot/extract_board.js returns from the Penpot MCP `execute_code` tool.
 * Field names and value sets are the Penpot Plugin API's own (@penpot/plugin-types 1.4):
 * Shape, Fill, Stroke, Gradient, ImageData, FlexLayout, GridLayout, LayoutChildProperties,
 * Text. The snippet copies them verbatim; it adds nothing except `component`.
 *
 * Coordinates: `x`/`y` are ABSOLUTE page coordinates of the shape's top-left corner (as in
 * the plugin API); the converter makes them relative to the parent itself.
 */
export type PenpotShapeType = 'board' | 'group' | 'boolean' | 'rectangle' | 'path' | 'text' | 'ellipse' | 'svg-raw' | 'image';
export interface PenpotGradient {
    type: 'linear' | 'radial';
    startX: number;
    startY: number;
    endX: number;
    endY: number;
    width: number;
    stops: Array<{
        color: string;
        opacity?: number;
        offset: number;
    }>;
}
export interface PenpotImageData {
    id: string;
    name?: string;
    width: number;
    height: number;
    mtype?: string;
    keepAspectRatio?: boolean;
}
export interface PenpotFill {
    fillColor?: string;
    fillOpacity?: number;
    fillColorGradient?: PenpotGradient;
    fillColorRefFile?: string;
    fillColorRefId?: string;
    fillImage?: PenpotImageData;
}
export interface PenpotStroke {
    strokeColor?: string;
    strokeOpacity?: number;
    strokeStyle?: 'solid' | 'dotted' | 'dashed' | 'mixed' | 'none' | 'svg';
    strokeWidth?: number;
    strokeAlignment?: 'center' | 'inner' | 'outer';
    strokeColorGradient?: PenpotGradient;
}
export interface PenpotCommonLayout {
    alignItems?: 'start' | 'end' | 'center' | 'stretch';
    alignContent?: 'start' | 'end' | 'center' | 'space-between' | 'space-around' | 'space-evenly' | 'stretch';
    justifyItems?: 'start' | 'end' | 'center' | 'stretch';
    justifyContent?: 'start' | 'center' | 'end' | 'space-between' | 'space-around' | 'space-evenly' | 'stretch';
    rowGap: number;
    columnGap: number;
    topPadding: number;
    rightPadding: number;
    bottomPadding: number;
    leftPadding: number;
    horizontalSizing?: 'fit-content' | 'fill' | 'auto';
    verticalSizing?: 'fit-content' | 'fill' | 'auto';
}
export interface PenpotFlexLayout extends PenpotCommonLayout {
    dir: 'row' | 'row-reverse' | 'column' | 'column-reverse';
    wrap?: 'wrap' | 'nowrap';
}
export interface PenpotTrack {
    type: 'flex' | 'fixed' | 'percent' | 'auto';
    value: number | null;
}
export interface PenpotGridLayout extends PenpotCommonLayout {
    dir: 'column' | 'row';
    rows: PenpotTrack[];
    columns: PenpotTrack[];
}
export interface PenpotLayoutChild {
    absolute: boolean;
    zIndex: number;
    horizontalSizing?: 'auto' | 'fill' | 'fix';
    verticalSizing?: 'auto' | 'fill' | 'fix';
    alignSelf?: 'auto' | 'start' | 'center' | 'end' | 'stretch';
}
export interface PenpotShadow {
    style?: 'drop-shadow' | 'inner-shadow';
    hidden?: boolean;
}
export interface PenpotShape {
    id: string;
    name: string;
    type: PenpotShapeType;
    x: number;
    y: number;
    width: number;
    height: number;
    parentX?: number;
    parentY?: number;
    center?: {
        x: number;
        y: number;
    };
    rotation?: number;
    opacity?: number;
    hidden?: boolean;
    blendMode?: string;
    proportionLock?: boolean;
    constraintsHorizontal?: 'left' | 'right' | 'leftright' | 'center' | 'scale';
    constraintsVertical?: 'top' | 'bottom' | 'topbottom' | 'center' | 'scale';
    borderRadius?: number;
    borderRadiusTopLeft?: number;
    borderRadiusTopRight?: number;
    borderRadiusBottomRight?: number;
    borderRadiusBottomLeft?: number;
    fills?: PenpotFill[] | 'mixed';
    strokes?: PenpotStroke[];
    shadows?: PenpotShadow[];
    blur?: {
        value?: number;
        hidden?: boolean;
    } | null;
    layoutChild?: PenpotLayoutChild | null;
    clipContent?: boolean;
    flex?: PenpotFlexLayout | null;
    grid?: PenpotGridLayout | null;
    characters?: string;
    fontFamily?: string;
    fontSize?: string;
    fontWeight?: string;
    fontStyle?: 'normal' | 'italic' | null;
    lineHeight?: string;
    letterSpacing?: string;
    textTransform?: 'uppercase' | 'capitalize' | 'lowercase' | 'none' | null;
    align?: 'left' | 'center' | 'right' | 'justify' | null;
    verticalAlign?: 'top' | 'center' | 'bottom' | null;
    growType?: 'fixed' | 'auto-width' | 'auto-height';
    component?: {
        id: string;
        name: string;
        path: string;
    } | null;
    children?: PenpotShape[];
}
/** What extract_board.js returns: the board shape itself plus provenance. */
export interface PenpotBoardExport extends PenpotShape {
    type: 'board';
    extractor?: string;
    page?: string;
}
export interface UDim2Spec {
    scaleX: number;
    offsetX: number;
    scaleY: number;
    offsetY: number;
}
export interface UDimSpec {
    scale: number;
    offset: number;
}
export type RobloxClass = 'Frame' | 'CanvasGroup' | 'TextLabel' | 'TextButton' | 'ImageLabel' | 'ImageButton';
export interface RobloxElement {
    id: string;
    name: string;
    type: RobloxClass;
    position: UDim2Spec;
    size: UDim2Spec;
    anchorPoint: {
        x: number;
        y: number;
    };
    rotation?: number;
    /** Where the shape sits in the design, in px relative to its parent (for overlap checks). */
    design?: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
    zIndex: number;
    layoutOrder?: number;
    visible: boolean;
    clipsDescendants?: boolean;
    backgroundColor?: string;
    backgroundTransparency: number;
    groupTransparency?: number;
    corner?: UDimSpec;
    stroke?: {
        thickness: number;
        color: string;
        transparency: number;
        mode: 'Border' | 'Contextual';
        position: 'Inner' | 'Center' | 'Outer';
    };
    gradient?: {
        rotation: number;
        color: Array<{
            time: number;
            color: string;
        }>;
        transparency: Array<{
            time: number;
            value: number;
        }>;
    };
    aspectRatio?: number;
    text?: string;
    font?: {
        family: string;
        weight: string;
        style: 'Normal' | 'Italic';
    };
    textSize?: number;
    textScaled?: boolean;
    textWrapped?: boolean;
    textColor?: string;
    textTransparency?: number;
    textXAlignment?: 'Left' | 'Center' | 'Right';
    textYAlignment?: 'Top' | 'Center' | 'Bottom';
    lineHeight?: number;
    image?: {
        key: string;
        scaleType: 'Fit' | 'Stretch';
    };
    layout?: {
        type: 'List';
        fillDirection: 'Horizontal' | 'Vertical';
        horizontalAlignment: 'Left' | 'Center' | 'Right';
        verticalAlignment: 'Top' | 'Center' | 'Bottom';
        flex?: 'SpaceBetween' | 'SpaceAround' | 'SpaceEvenly';
        padding: UDimSpec;
        wraps: boolean;
    } | {
        type: 'Grid';
        fillDirection: 'Horizontal' | 'Vertical';
        cellSize: UDim2Spec;
        cellPadding: UDim2Spec;
    };
    padding?: {
        top: UDimSpec;
        right: UDimSpec;
        bottom: UDimSpec;
        left: UDimSpec;
    };
    children: RobloxElement[];
}
export interface RobloxImageRef {
    key: string;
    source: 'fill' | 'shape';
    shapeId: string;
    name: string;
    width: number;
    height: number;
}
export interface RobloxUISpec {
    version: 2;
    source: 'penpot';
    board: {
        id: string;
        name: string;
        width: number;
        height: number;
    };
    elements: RobloxElement[];
    images: RobloxImageRef[];
    warnings: string[];
}
