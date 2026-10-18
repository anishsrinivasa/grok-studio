/**
 * Penpot board data types (based on Penpot Plugin API)
 */

export interface PenpotBoard {
  id: string;
  name: string;
  width?: number;
  height?: number;
  fills?: PenpotFill[];
  children?: PenpotShape[];
}

export interface PenpotShape {
  id: string;
  name: string;
  type: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  rotation?: number;
  opacity?: number;
  fills?: PenpotFill[];
  strokes?: PenpotStroke[];
  cornerRadius?: number | { topLeft?: number; topRight?: number; bottomLeft?: number; bottomRight?: number };
  proportionLock?: boolean;
  constraints?: PenpotConstraints;
  layoutChild?: PenpotLayoutChild;
  layout?: PenpotLayout;
  children?: PenpotShape[];
  
  // Text-specific
  content?: string;
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: string | number;
  textAlign?: string;
  lineHeight?: number;
  characters?: string;
  
  // Component
  componentId?: string;
  componentFile?: string;
}

export interface PenpotFill {
  type: 'solid' | 'gradient' | 'image';
  color?: string;
  opacity?: number;
  gradient?: PenpotGradient;
  imageUrl?: string;
}

export interface PenpotGradient {
  type: 'linear' | 'radial';
  stops: Array<{ color: string; offset: number; opacity?: number }>;
  startX?: number;
  startY?: number;
  endX?: number;
  endY?: number;
}

export interface PenpotStroke {
  color?: string;
  width?: number;
  opacity?: number;
  alignment?: 'center' | 'inner' | 'outer';
}

export interface PenpotConstraints {
  horizontal?: 'left' | 'right' | 'center' | 'leftRight' | 'scale';
  vertical?: 'top' | 'bottom' | 'center' | 'topBottom' | 'scale';
}

export interface PenpotLayoutChild {
  absolute?: boolean;
  zIndex?: number;
}

export interface PenpotLayout {
  type?: 'flex' | 'grid';
  dir?: 'row' | 'column';
  alignItems?: 'start' | 'end' | 'center' | 'stretch';
  justifyContent?: 'start' | 'end' | 'center' | 'space-between' | 'space-around';
  gap?: number;
  padding?: { top?: number; right?: number; bottom?: number; left?: number };
  wrap?: boolean;
  
  // Grid-specific
  columns?: number;
  rows?: number;
}

/**
 * Roblox UI specification types
 */

export interface RobloxUISpec {
  version: string;
  board: {
    name: string;
    width: number;
    height: number;
  };
  elements: RobloxElement[];
  warnings: string[];
}

export interface RobloxElement {
  id: string;
  name: string;
  type: 'Frame' | 'CanvasGroup' | 'TextLabel' | 'TextButton' | 'ImageLabel' | 'ImageButton';
  position: { scaleX: number; scaleY: number; offsetX: number; offsetY: number };
  size: { scaleX: number; scaleY: number; offsetX: number; offsetY: number };
  anchorPoint?: { x: number; y: number };
  zIndex?: number;
  
  // Styling
  backgroundColor?: { r: number; g: number; b: number };
  backgroundTransparency?: number;
  
  // Children properties
  corner?: { radius: number };
  stroke?: { thickness: number; color: { r: number; g: number; b: number }; transparency?: number };
  gradient?: RobloxGradient;
  aspectRatio?: number;
  
  // Text properties
  text?: string;
  font?: { family: string; weight: string };
  fontSize?: number;
  textColor?: { r: number; g: number; b: number };
  textXAlignment?: 'Left' | 'Center' | 'Right';
  textYAlignment?: 'Top' | 'Center' | 'Bottom';
  textWrapped?: boolean;
  textScaled?: boolean;
  
  // Image properties
  image?: {
    contentHash: string;
    sourceUrl?: string;
    rbxAssetId?: string;
  };
  
  // Layout properties
  layout?: {
    type: 'List' | 'Grid';
    fillDirection?: 'Horizontal' | 'Vertical';
    horizontalAlignment?: 'Left' | 'Center' | 'Right';
    verticalAlignment?: 'Top' | 'Center' | 'Bottom';
    sortOrder?: 'LayoutOrder' | 'Name';
    padding?: { scale: number; offset: number };
    gap?: { scale: number; offset: number };
    
    // Grid-specific
    cellSize?: { scaleX: number; scaleY: number };
    cellPadding?: { scaleX: number; scaleY: number };
  };
  
  padding?: {
    top: { scale: number; offset: number };
    right: { scale: number; offset: number };
    bottom: { scale: number; offset: number };
    left: { scale: number; offset: number };
  };
  
  children?: RobloxElement[];
}

export interface RobloxGradient {
  type: 'linear';
  rotation: number;
  stops: Array<{ color: { r: number; g: number; b: number }; position: number; transparency?: number }>;
}
