"""
Extract Penpot board data using MCP tools

This script provides example extraction snippets that the Designer bot
can use with the Penpot MCP to extract board data.

The actual extraction is done through the Penpot MCP's code execution tools.
"""

# Example 1: Extract basic board structure
EXTRACT_BOARD_STRUCTURE = '''
// Get the current board
const board = penpot.currentBoard;
if (!board) {
  return { error: "No board selected" };
}

// Helper to extract shape data
function extractShape(shape) {
  const data = {
    id: shape.id,
    name: shape.name,
    type: shape.type,
    x: shape.x,
    y: shape.y,
    width: shape.width,
    height: shape.height,
  };
  
  // Rotation
  if (shape.rotation) {
    data.rotation = shape.rotation;
  }
  
  // Opacity
  if (shape.opacity !== undefined && shape.opacity !== 1) {
    data.opacity = shape.opacity;
  }
  
  // Fills
  if (shape.fills && shape.fills.length > 0) {
    data.fills = shape.fills.map(fill => {
      const fillData = { type: fill.fillType };
      if (fill.fillColor) {
        fillData.color = fill.fillColor;
      }
      if (fill.fillOpacity !== undefined && fill.fillOpacity !== 1) {
        fillData.opacity = fill.fillOpacity;
      }
      if (fill.fillGradient) {
        fillData.gradient = fill.fillGradient;
      }
      if (fill.fillImage) {
        fillData.imageUrl = fill.fillImage.dataUri || fill.fillImage.url;
      }
      return fillData;
    });
  }
  
  // Strokes
  if (shape.strokes && shape.strokes.length > 0) {
    data.strokes = shape.strokes.map(stroke => ({
      color: stroke.strokeColor,
      width: stroke.strokeWidth,
      opacity: stroke.strokeOpacity,
      alignment: stroke.strokeAlignment,
    }));
  }
  
  // Corner radius
  if (shape.borderRadius) {
    data.cornerRadius = shape.borderRadius;
  }
  
  // Constraints
  if (shape.constraints) {
    data.constraints = {
      horizontal: shape.constraints.horizontal,
      vertical: shape.constraints.vertical,
    };
  }
  
  // Layout
  if (shape.layoutChild) {
    data.layoutChild = {
      absolute: shape.layoutChild.absolute,
      zIndex: shape.layoutChild.zIndex,
    };
  }
  
  if (shape.layout) {
    data.layout = {
      type: shape.layout.layoutType,
      dir: shape.layout.dir,
      alignItems: shape.layout.alignItems,
      justifyContent: shape.layout.justifyContent,
      gap: shape.layout.gap,
      padding: shape.layout.padding,
      wrap: shape.layout.wrap,
    };
    
    if (shape.layout.layoutType === 'grid') {
      data.layout.columns = shape.layout.columns;
      data.layout.rows = shape.layout.rows;
    }
  }
  
  // Text content
  if (shape.characters) {
    data.content = shape.characters;
    data.fontFamily = shape.fontFamily;
    data.fontSize = shape.fontSize;
    data.fontWeight = shape.fontWeight;
    data.textAlign = shape.textAlign;
    data.lineHeight = shape.lineHeight;
  }
  
  // Component
  if (shape.componentId) {
    data.componentId = shape.componentId;
    data.componentFile = shape.componentFile;
  }
  
  // Children
  if (shape.children && shape.children.length > 0) {
    data.children = shape.children.map(extractShape);
  }
  
  return data;
}

// Extract board data
const boardData = {
  id: board.id,
  name: board.name,
  width: board.width,
  height: board.height,
};

if (board.fills) {
  boardData.fills = board.fills.map(fill => ({
    type: fill.fillType,
    color: fill.fillColor,
    gradient: fill.fillGradient,
  }));
}

if (board.children) {
  boardData.children = board.children.map(extractShape);
}

return boardData;
'''

# Example 2: Export board as PNG (for comparison)
EXPORT_BOARD_PNG = '''
const board = penpot.currentBoard;
if (!board) {
  return { error: "No board selected" };
}

// Export the board as PNG
const pngData = await board.export({ type: 'png', scale: 1 });

return {
  boardName: board.name,
  pngDataUri: pngData,
};
'''

# Example 3: Get all boards in file
LIST_BOARDS = '''
const file = penpot.currentFile;
if (!file) {
  return { error: "No file open" };
}

const boards = [];
for (const page of file.pages) {
  for (const child of page.children) {
    if (child.type === 'board' || child.type === 'frame') {
      boards.push({
        id: child.id,
        name: child.name,
        page: page.name,
        width: child.width,
        height: child.height,
      });
    }
  }
}

return { boards };
'''

if __name__ == '__main__':
    import sys
    
    print("Penpot MCP Extraction Snippets")
    print("=" * 50)
    print()
    print("Use these code snippets with the Penpot MCP's code execution tool:")
    print()
    print("1. Extract Board Structure (copy to MCP):")
    print("-" * 50)
    print(EXTRACT_BOARD_STRUCTURE)
    print()
    print("2. Export Board as PNG:")
    print("-" * 50)
    print(EXPORT_BOARD_PNG)
    print()
    print("3. List All Boards:")
    print("-" * 50)
    print(LIST_BOARDS)
