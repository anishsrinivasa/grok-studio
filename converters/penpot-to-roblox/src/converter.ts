import type {
  PenpotBoard,
  PenpotShape,
  PenpotFill,
  PenpotStroke,
  RobloxUISpec,
  RobloxElement,
  RobloxGradient,
} from './types.js';
import { createHash } from 'crypto';

/**
 * Font mapping from common design fonts to Roblox fonts
 */
const FONT_MAPPING: Record<string, { family: string; weight: string }> = {
  // Sans-serif
  'Inter': { family: 'BuilderSans', weight: 'Regular' },
  'Roboto': { family: 'BuilderSans', weight: 'Regular' },
  'Arial': { family: 'Arial', weight: 'Regular' },
  'Helvetica': { family: 'Arial', weight: 'Regular' },
  'Open Sans': { family: 'BuilderSans', weight: 'Regular' },
  'Lato': { family: 'BuilderSans', weight: 'Regular' },
  
  // Monospace
  'Roboto Mono': { family: 'RobotoMono', weight: 'Regular' },
  'Courier': { family: 'Code', weight: 'Regular' },
  'Source Code Pro': { family: 'RobotoMono', weight: 'Regular' },
  
  // Display
  'Fredoka': { family: 'FredokaOne', weight: 'Regular' },
  'Creepster': { family: 'Creepster', weight: 'Regular' },
  
  // Default fallback
  'default': { family: 'BuilderSans', weight: 'Regular' },
};

/**
 * Weight mapping
 */
const WEIGHT_MAPPING: Record<string, string> = {
  '100': 'Thin',
  '200': 'ExtraLight',
  '300': 'Light',
  '400': 'Regular',
  '500': 'Medium',
  '600': 'SemiBold',
  '700': 'Bold',
  '800': 'ExtraBold',
  '900': 'Heavy',
  'thin': 'Thin',
  'light': 'Light',
  'regular': 'Regular',
  'medium': 'Medium',
  'semibold': 'SemiBold',
  'bold': 'Bold',
  'extrabold': 'ExtraBold',
  'black': 'Heavy',
};

/**
 * Converts a Penpot hex color to RGB (0-1 range)
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  // Remove # if present
  hex = hex.replace(/^#/, '');
  
  // Parse hex values
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;
  
  return { r, g, b };
}

/**
 * Determines if a shape should be a button based on its name
 */
function isButton(name: string): boolean {
  const lowerName = name.toLowerCase();
  return lowerName.includes('button') || lowerName.includes('btn');
}

/**
 * Converts Penpot shape type to Roblox element type
 */
function getRobloxType(shape: PenpotShape): RobloxElement['type'] {
  const hasText = shape.type === 'text' || (shape.content && shape.content.length > 0);
  const hasImage = shape.fills?.some(f => f.type === 'image');
  const needsButton = isButton(shape.name);
  const needsCanvas = (shape.opacity !== undefined && shape.opacity < 1) || 
                      (shape.children && shape.children.length > 0 && shape.rotation);
  
  if (hasImage && needsButton) return 'ImageButton';
  if (hasImage) return 'ImageLabel';
  if (hasText && needsButton) return 'TextButton';
  if (hasText) return 'TextLabel';
  if (needsCanvas) return 'CanvasGroup';
  return 'Frame';
}

/**
 * Extracts the primary fill color from Penpot fills
 */
function getPrimaryColor(fills?: PenpotFill[]): { r: number; g: number; b: number } | undefined {
  if (!fills || fills.length === 0) return undefined;
  
  const solidFill = fills.find(f => f.type === 'solid');
  if (solidFill && solidFill.color) {
    return hexToRgb(solidFill.color);
  }
  
  return undefined;
}

/**
 * Converts Penpot gradient to Roblox gradient
 */
function convertGradient(fill: PenpotFill, warnings: string[]): RobloxGradient | undefined {
  if (fill.type !== 'gradient' || !fill.gradient) return undefined;
  
  if (fill.gradient.type !== 'linear') {
    warnings.push(`Radial gradients are not supported, using linear approximation`);
  }
  
  // Calculate rotation from start/end points
  const startX = fill.gradient.startX ?? 0;
  const startY = fill.gradient.startY ?? 0;
  const endX = fill.gradient.endX ?? 1;
  const endY = fill.gradient.endY ?? 1;
  
  const angle = Math.atan2(endY - startY, endX - startX);
  const rotation = (angle * 180 / Math.PI) + 90; // Convert to Roblox rotation
  
  return {
    type: 'linear',
    rotation,
    stops: fill.gradient.stops.map(stop => ({
      color: hexToRgb(stop.color),
      position: stop.offset,
      transparency: stop.opacity !== undefined ? 1 - stop.opacity : undefined,
    })),
  };
}

/**
 * Converts Penpot stroke to Roblox stroke
 */
function convertStroke(stroke: PenpotStroke): RobloxElement['stroke'] | undefined {
  if (!stroke.color || !stroke.width) return undefined;
  
  return {
    thickness: stroke.width,
    color: hexToRgb(stroke.color),
    transparency: stroke.opacity !== undefined ? 1 - stroke.opacity : undefined,
  };
}

/**
 * Maps font family to Roblox font
 */
function mapFont(fontFamily?: string, fontWeight?: string | number): { family: string; weight: string } {
  const mappedFamily = fontFamily && FONT_MAPPING[fontFamily] 
    ? FONT_MAPPING[fontFamily] 
    : FONT_MAPPING['default'];
  
  let weight = mappedFamily.weight;
  if (fontWeight) {
    const weightStr = String(fontWeight);
    weight = WEIGHT_MAPPING[weightStr] || weight;
  }
  
  return { family: mappedFamily.family, weight };
}

/**
 * Calculates content hash for image deduplication
 */
function calculateImageHash(imageUrl: string): string {
  return createHash('sha256').update(imageUrl).digest('hex').substring(0, 16);
}

/**
 * Converts a single Penpot shape to Roblox element
 */
function convertShape(
  shape: PenpotShape,
  boardWidth: number,
  boardHeight: number,
  warnings: string[],
  parentWidth?: number,
  parentHeight?: number
): RobloxElement {
  const width = parentWidth ?? boardWidth;
  const height = parentHeight ?? boardHeight;
  
  const x = shape.x ?? 0;
  const y = shape.y ?? 0;
  const w = shape.width ?? 100;
  const h = shape.height ?? 100;
  
  // Convert to scale-based positioning
  const element: RobloxElement = {
    id: shape.id,
    name: shape.name,
    type: getRobloxType(shape),
    position: {
      scaleX: x / width,
      scaleY: y / height,
      offsetX: 0,
      offsetY: 0,
    },
    size: {
      scaleX: w / width,
      scaleY: h / height,
      offsetX: 0,
      offsetY: 0,
    },
  };
  
  // Anchor point (default top-left)
  element.anchorPoint = { x: 0, y: 0 };
  
  // Z-index from layout
  if (shape.layoutChild?.zIndex !== undefined) {
    element.zIndex = shape.layoutChild.zIndex;
  }
  
  // Background color and transparency
  const primaryColor = getPrimaryColor(shape.fills);
  if (primaryColor) {
    element.backgroundColor = primaryColor;
  }
  
  if (shape.opacity !== undefined && shape.opacity < 1) {
    element.backgroundTransparency = 1 - shape.opacity;
  }
  
  // Gradient
  const gradientFill = shape.fills?.find(f => f.type === 'gradient');
  if (gradientFill) {
    element.gradient = convertGradient(gradientFill, warnings);
  }
  
  // Corner radius
  if (shape.cornerRadius !== undefined) {
    const radius = typeof shape.cornerRadius === 'number' 
      ? shape.cornerRadius 
      : Math.max(
          shape.cornerRadius.topLeft ?? 0,
          shape.cornerRadius.topRight ?? 0,
          shape.cornerRadius.bottomLeft ?? 0,
          shape.cornerRadius.bottomRight ?? 0
        );
    
    if (radius > 0) {
      element.corner = { radius };
    }
    
    if (typeof shape.cornerRadius !== 'number') {
      warnings.push(`Shape "${shape.name}": individual corner radii not fully supported, using maximum`);
    }
  }
  
  // Stroke
  if (shape.strokes && shape.strokes.length > 0) {
    const stroke = convertStroke(shape.strokes[0]);
    if (stroke) {
      element.stroke = stroke;
    }
    
    if (shape.strokes.length > 1) {
      warnings.push(`Shape "${shape.name}": multiple strokes not supported, using first only`);
    }
  }
  
  // Aspect ratio constraint
  if (shape.proportionLock) {
    element.aspectRatio = w / h;
  }
  
  // Text properties
  if (element.type === 'TextLabel' || element.type === 'TextButton') {
    element.text = shape.content || shape.characters || '';
    element.font = mapFont(shape.fontFamily, shape.fontWeight);
    element.fontSize = shape.fontSize;
    
    // Text alignment
    const align = shape.textAlign?.toLowerCase();
    element.textXAlignment = align === 'center' ? 'Center' 
                           : align === 'right' ? 'Right' 
                           : 'Left';
    element.textYAlignment = 'Center';
    
    element.textWrapped = true;
    element.textScaled = false;
    
    // Text color (from first fill)
    const textColor = getPrimaryColor(shape.fills);
    if (textColor) {
      element.textColor = textColor;
    }
  }
  
  // Image properties
  const imageFill = shape.fills?.find(f => f.type === 'image');
  if (imageFill && imageFill.imageUrl && (element.type === 'ImageLabel' || element.type === 'ImageButton')) {
    element.image = {
      contentHash: calculateImageHash(imageFill.imageUrl),
      sourceUrl: imageFill.imageUrl,
    };
  }
  
  // Layout (flex/grid)
  if (shape.layout) {
    const layout = shape.layout;
    
    if (layout.type === 'flex') {
      element.layout = {
        type: 'List',
        fillDirection: layout.dir === 'column' ? 'Vertical' : 'Horizontal',
        horizontalAlignment: 
          layout.alignItems === 'center' ? 'Center' :
          layout.alignItems === 'end' ? 'Right' : 'Left',
        verticalAlignment:
          layout.alignItems === 'center' ? 'Center' :
          layout.alignItems === 'end' ? 'Bottom' : 'Top',
        sortOrder: 'LayoutOrder',
        padding: layout.gap ? { scale: 0, offset: layout.gap } : undefined,
      };
    } else if (layout.type === 'grid') {
      element.layout = {
        type: 'Grid',
        sortOrder: 'LayoutOrder',
        cellSize: { scaleX: 1 / (layout.columns || 1), scaleY: 1 / (layout.rows || 1) },
        cellPadding: layout.gap ? { scaleX: layout.gap / width, scaleY: layout.gap / height } : undefined,
      };
    }
    
    // Padding
    if (layout.padding) {
      const p = layout.padding;
      element.padding = {
        top: { scale: (p.top ?? 0) / height, offset: 0 },
        right: { scale: (p.right ?? 0) / width, offset: 0 },
        bottom: { scale: (p.bottom ?? 0) / height, offset: 0 },
        left: { scale: (p.left ?? 0) / width, offset: 0 },
      };
    }
  }
  
  // Recursively convert children
  if (shape.children && shape.children.length > 0) {
    element.children = shape.children.map(child => 
      convertShape(child, boardWidth, boardHeight, warnings, w, h)
    );
  }
  
  return element;
}

/**
 * Converts a Penpot board export to Roblox UI specification
 */
export function convertPenpotToRoblox(board: PenpotBoard): RobloxUISpec {
  const warnings: string[] = [];
  
  // Board dimensions (default to 1920x1080 if not specified)
  const boardWidth = board.width ?? 1920;
  const boardHeight = board.height ?? 1080;
  
  const spec: RobloxUISpec = {
    version: '1.0.0',
    board: {
      name: board.name,
      width: boardWidth,
      height: boardHeight,
    },
    elements: [],
    warnings,
  };
  
  // Convert all top-level shapes
  if (board.children && board.children.length > 0) {
    spec.elements = board.children.map(child => 
      convertShape(child, boardWidth, boardHeight, warnings)
    );
  }
  
  return spec;
}
