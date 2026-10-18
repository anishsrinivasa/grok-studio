--!strict
-- PenpotUIBuilder: Builds Roblox ScreenGuis from Penpot-derived UI specifications
-- Usage: Load this in execute_luau (datamodel_type "Edit"), then call buildFromSpec(spec)

local HttpService = game:GetService("HttpService")
local StarterGui = game:GetService("StarterGui")

type UDim2Data = { scaleX: number, scaleY: number, offsetX: number, offsetY: number }
type Vector2Data = { x: number, y: number }
type Color3Data = { r: number, g: number, b: number }

type RobloxUISpec = {
	version: string,
	board: { name: string, width: number, height: number },
	elements: { RobloxElement },
	warnings: { string }
}

type RobloxElement = {
	id: string,
	name: string,
	type: string,
	position: UDim2Data,
	size: UDim2Data,
	anchorPoint: Vector2Data?,
	zIndex: number?,
	
	backgroundColor: Color3Data?,
	backgroundTransparency: number?,
	
	corner: { radius: number }?,
	stroke: { thickness: number, color: Color3Data, transparency: number? }?,
	gradient: any?,
	aspectRatio: number?,
	
	text: string?,
	font: { family: string, weight: string }?,
	fontSize: number?,
	textColor: Color3Data?,
	textXAlignment: string?,
	textYAlignment: string?,
	textWrapped: boolean?,
	textScaled: boolean?,
	
	image: { contentHash: string, sourceUrl: string?, rbxAssetId: string? }?,
	
	layout: any?,
	padding: any?,
	
	children: { RobloxElement }?
}

-- Convert data structures to Roblox types
local function toUDim2(data: UDim2Data): UDim2
	return UDim2.new(data.scaleX, data.offsetX, data.scaleY, data.offsetY)
end

local function toVector2(data: Vector2Data): Vector2
	return Vector2.new(data.x, data.y)
end

local function toColor3(data: Color3Data): Color3
	return Color3.new(data.r, data.g, data.b)
end

-- Create a GuiObject from element spec
local function createElement(element: RobloxElement, imageCache: { [string]: string }): Instance
	local className = element.type
	local inst: Instance = Instance.new(className :: any)
	
	-- Common properties
	inst.Name = element.name
	(inst :: any).Position = toUDim2(element.position)
	(inst :: any).Size = toUDim2(element.size)
	
	if element.anchorPoint then
		(inst :: any).AnchorPoint = toVector2(element.anchorPoint)
	end
	
	if element.zIndex then
		(inst :: any).ZIndex = element.zIndex
	end
	
	-- Background
	if element.backgroundColor then
		(inst :: any).BackgroundColor3 = toColor3(element.backgroundColor)
	else
		(inst :: any).BackgroundTransparency = 1
	end
	
	if element.backgroundTransparency then
		(inst :: any).BackgroundTransparency = element.backgroundTransparency
	end
	
	-- Border (set to none, we use UIStroke)
	if (inst :: any).BorderSizePixel then
		(inst :: any).BorderSizePixel = 0
	end
	
	-- Text properties
	if element.text and (className == "TextLabel" or className == "TextButton") then
		(inst :: any).Text = element.text
		
		if element.font then
			local weight = (Enum.FontWeight :: any)[element.font.weight] or Enum.FontWeight.Regular
			(inst :: any).FontFace = Font.fromName(element.font.family, weight)
		end
		
		if element.fontSize then
			(inst :: any).TextSize = element.fontSize
		end
		
		if element.textColor then
			(inst :: any).TextColor3 = toColor3(element.textColor)
		end
		
		if element.textXAlignment then
			local align = element.textXAlignment
			(inst :: any).TextXAlignment = (Enum.TextXAlignment :: any)[align] or Enum.TextXAlignment.Left
		end
		
		if element.textYAlignment then
			local align = element.textYAlignment
			(inst :: any).TextYAlignment = (Enum.TextYAlignment :: any)[align] or Enum.TextYAlignment.Center
		end
		
		if element.textWrapped ~= nil then
			(inst :: any).TextWrapped = element.textWrapped
		end
		
		if element.textScaled ~= nil then
			(inst :: any).TextScaled = element.textScaled
		end
	end
	
	-- Image properties
	if element.image and (className == "ImageLabel" or className == "ImageButton") then
		local assetId = element.image.rbxAssetId or imageCache[element.image.contentHash]
		if assetId then
			(inst :: any).Image = assetId
		else
			warn("Image not uploaded yet for element: " .. element.name .. " (hash: " .. element.image.contentHash .. ")")
		end
		(inst :: any).BackgroundTransparency = 1
	end
	
	-- Children: corner, stroke, gradient, constraints
	if element.corner then
		local corner = Instance.new("UICorner")
		corner.CornerRadius = UDim.new(0, element.corner.radius)
		corner.Parent = inst
	end
	
	if element.stroke then
		local stroke = Instance.new("UIStroke")
		stroke.Thickness = element.stroke.thickness
		stroke.Color = toColor3(element.stroke.color)
		if element.stroke.transparency then
			stroke.Transparency = element.stroke.transparency
		end
		stroke.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
		stroke.Parent = inst
	end
	
	if element.gradient and element.gradient.type == "linear" then
		local gradient = Instance.new("UIGradient")
		gradient.Rotation = element.gradient.rotation
		
		local keypoints = {}
		for i, stop in element.gradient.stops do
			local color = toColor3(stop.color)
			local transparency = stop.transparency or 0
			table.insert(keypoints, ColorSequenceKeypoint.new(stop.position, color))
		end
		gradient.Color = ColorSequence.new(keypoints)
		gradient.Parent = inst
	end
	
	if element.aspectRatio then
		local constraint = Instance.new("UIAspectRatioConstraint")
		constraint.AspectRatio = element.aspectRatio
		constraint.Parent = inst
	end
	
	-- Layout
	if element.layout then
		local layout = element.layout
		
		if layout.type == "List" then
			local listLayout = Instance.new("UIListLayout")
			
			if layout.fillDirection then
				listLayout.FillDirection = (Enum.FillDirection :: any)[layout.fillDirection] or Enum.FillDirection.Horizontal
			end
			
			if layout.horizontalAlignment then
				listLayout.HorizontalAlignment = (Enum.HorizontalAlignment :: any)[layout.horizontalAlignment] or Enum.HorizontalAlignment.Left
			end
			
			if layout.verticalAlignment then
				listLayout.VerticalAlignment = (Enum.VerticalAlignment :: any)[layout.verticalAlignment] or Enum.VerticalAlignment.Top
			end
			
			if layout.sortOrder then
				listLayout.SortOrder = (Enum.SortOrder :: any)[layout.sortOrder] or Enum.SortOrder.LayoutOrder
			end
			
			if layout.padding then
				listLayout.Padding = UDim.new(layout.padding.scale, layout.padding.offset)
			end
			
			listLayout.Parent = inst
			
		elseif layout.type == "Grid" then
			local gridLayout = Instance.new("UIGridLayout")
			
			if layout.sortOrder then
				gridLayout.SortOrder = (Enum.SortOrder :: any)[layout.sortOrder] or Enum.SortOrder.LayoutOrder
			end
			
			if layout.cellSize then
				gridLayout.CellSize = UDim2.fromScale(layout.cellSize.scaleX, layout.cellSize.scaleY)
			end
			
			if layout.cellPadding then
				gridLayout.CellPadding = UDim2.fromScale(layout.cellPadding.scaleX, layout.cellPadding.scaleY)
			end
			
			gridLayout.Parent = inst
		end
	end
	
	-- Padding
	if element.padding then
		local padding = Instance.new("UIPadding")
		local p = element.padding
		padding.PaddingTop = UDim.new(p.top.scale, p.top.offset)
		padding.PaddingRight = UDim.new(p.right.scale, p.right.offset)
		padding.PaddingBottom = UDim.new(p.bottom.scale, p.bottom.offset)
		padding.PaddingLeft = UDim.new(p.left.scale, p.left.offset)
		padding.Parent = inst
	end
	
	return inst
end

-- Recursively build element tree
local function buildElement(element: RobloxElement, imageCache: { [string]: string }): Instance
	local inst = createElement(element, imageCache)
	
	if element.children then
		for _, child in element.children do
			local childInst = buildElement(child, imageCache)
			childInst.Parent = inst
		end
	end
	
	return inst
end

-- Main entry point: build ScreenGui from spec
local function buildFromSpec(specJson: string, imageCache: { [string]: string }?): ScreenGui
	local cache = imageCache or {}
	local spec: RobloxUISpec = HttpService:JSONDecode(specJson) :: any
	
	-- Create or replace ScreenGui
	local screenName = spec.board.name
	local existing = StarterGui:FindFirstChild(screenName)
	if existing then
		existing:Destroy()
	end
	
	local screen = Instance.new("ScreenGui")
	screen.Name = screenName
	screen.ResetOnSpawn = false
	screen.IgnoreGuiInset = false
	screen.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	screen.Parent = StarterGui
	
	-- Build all top-level elements
	for _, element in spec.elements do
		local inst = buildElement(element, cache)
		inst.Parent = screen
	end
	
	-- Report warnings
	if #spec.warnings > 0 then
		warn("Penpot conversion warnings for " .. screenName .. ":")
		for _, warning in spec.warnings do
			warn("  - " .. warning)
		end
	end
	
	print("Built " .. screenName .. " with " .. #spec.elements .. " top-level element(s)")
	return screen
end

-- Export
return {
	buildFromSpec = buildFromSpec
}
