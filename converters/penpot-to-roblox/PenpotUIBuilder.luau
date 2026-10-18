--!strict
--[[
PenpotUIBuilder.luau - builds a ScreenGui from a penpot-to-roblox spec (version 2).

Use (Studio MCP execute_luau, Edit mode). The file ends in `return M`, so wrap it:

    local Builder = (function()
        -- paste this whole file here
    end)()
    local screen, report = Builder.build([==[ <spec JSON> ]==], {
        images = { ["<image key>"] = "rbxassetid://123" },  -- from penpot/save_images.py; optional
        -- parent = game.StarterGui,  name = "<ScreenGui name>",  -- defaults: StarterGui, board name
    })
    print(Builder.report(report))

Idempotent: re-running replaces the ScreenGui it built before (marked with the attribute
PenpotBoardId). It refuses to replace a same-named ScreenGui it did not build.
Everything is scale-based (UDim2 scale), anchors and aspect constraints come from the spec;
text is TextScaled with a UITextSizeConstraint at the design size.
]]

local HttpService = game:GetService("HttpService")
local StarterGui = game:GetService("StarterGui")

local M = {}
M.SPEC_VERSION = 2

export type Options = { parent: Instance?, name: string?, images: { [string]: string }? }
export type Report = { screen: string, built: number, warnings: { string } }

type Ctx = { images: { [string]: string }, warnings: { string }, built: number }

local function udim2(d: any): UDim2
	return UDim2.new(d.scaleX or 0, d.offsetX or 0, d.scaleY or 0, d.offsetY or 0)
end

local function udim(d: any): UDim
	return UDim.new(d.scale or 0, d.offset or 0)
end

-- Enum item by name, or the fallback (never throws on unknown names).
local function enumItem(enum: any, name: string?, fallback: EnumItem): any
	if name == nil then
		return fallback
	end
	local ok, item = pcall(function()
		return enum[name]
	end)
	return if ok and item then item else fallback
end

-- Sets a property that newer Studio builds have; older ones just skip it.
local function trySet(inst: Instance, prop: string, value: any)
	pcall(function()
		(inst :: any)[prop] = value
	end)
end

local function decorate(inst: GuiObject, el: any)
	if el.corner then
		local c = Instance.new("UICorner")
		c.CornerRadius = udim(el.corner)
		c.Parent = inst
	end
	if el.stroke then
		local s = Instance.new("UIStroke")
		s.Thickness = el.stroke.thickness
		s.Color = Color3.fromHex(el.stroke.color)
		s.Transparency = el.stroke.transparency or 0
		s.ApplyStrokeMode = enumItem(Enum.ApplyStrokeMode, el.stroke.mode, Enum.ApplyStrokeMode.Border)
		trySet(s, "BorderStrokePosition", enumItem(Enum.BorderStrokePosition, el.stroke.position, Enum.BorderStrokePosition.Outer))
		s.Parent = inst
	end
	if el.gradient then
		local g = Instance.new("UIGradient")
		local colors = {}
		for _, k in el.gradient.color do
			table.insert(colors, ColorSequenceKeypoint.new(k.time, Color3.fromHex(k.color)))
		end
		local alphas = {}
		for _, k in el.gradient.transparency do
			table.insert(alphas, NumberSequenceKeypoint.new(k.time, k.value))
		end
		g.Color = ColorSequence.new(colors)
		g.Transparency = NumberSequence.new(alphas)
		g.Rotation = el.gradient.rotation or 0
		g.Parent = inst
	end
	if el.aspectRatio then
		local a = Instance.new("UIAspectRatioConstraint")
		a.AspectRatio = el.aspectRatio
		a.Parent = inst
	end
	if el.textScaled and el.textSize then
		local t = Instance.new("UITextSizeConstraint")
		t.MaxTextSize = math.max(1, math.floor(el.textSize + 0.5))
		t.MinTextSize = 1
		t.Parent = inst
	end
	local layout = el.layout
	if layout and layout.type == "List" then
		local l = Instance.new("UIListLayout")
		l.SortOrder = Enum.SortOrder.LayoutOrder
		l.FillDirection = enumItem(Enum.FillDirection, layout.fillDirection, Enum.FillDirection.Vertical)
		l.HorizontalAlignment = enumItem(Enum.HorizontalAlignment, layout.horizontalAlignment, Enum.HorizontalAlignment.Left)
		l.VerticalAlignment = enumItem(Enum.VerticalAlignment, layout.verticalAlignment, Enum.VerticalAlignment.Top)
		l.Padding = udim(layout.padding or {})
		trySet(l, "Wraps", layout.wraps == true)
		if layout.flex then
			local flex = enumItem(Enum.UIFlexAlignment, layout.flex, Enum.UIFlexAlignment.None)
			trySet(l, if layout.fillDirection == "Horizontal" then "HorizontalFlex" else "VerticalFlex", flex)
		end
		l.Parent = inst
	elseif layout and layout.type == "Grid" then
		local l = Instance.new("UIGridLayout")
		l.SortOrder = Enum.SortOrder.LayoutOrder
		l.FillDirection = enumItem(Enum.FillDirection, layout.fillDirection, Enum.FillDirection.Horizontal)
		l.CellSize = udim2(layout.cellSize)
		l.CellPadding = udim2(layout.cellPadding)
		l.StartCorner = Enum.StartCorner.TopLeft
		l.Parent = inst
	end
	if el.padding then
		local p = Instance.new("UIPadding")
		p.PaddingTop = udim(el.padding.top)
		p.PaddingRight = udim(el.padding.right)
		p.PaddingBottom = udim(el.padding.bottom)
		p.PaddingLeft = udim(el.padding.left)
		p.Parent = inst
	end
end

local function create(el: any, ctx: Ctx): GuiObject
	local inst = Instance.new(el.type :: any) :: GuiObject
	inst.Name = el.name
	inst.Position = udim2(el.position)
	inst.Size = udim2(el.size)
	inst.AnchorPoint = Vector2.new(el.anchorPoint.x, el.anchorPoint.y)
	inst.ZIndex = el.zIndex or 1
	inst.Visible = el.visible ~= false
	inst.BorderSizePixel = 0
	inst.BackgroundTransparency = el.backgroundTransparency or 1
	if el.backgroundColor then
		inst.BackgroundColor3 = Color3.fromHex(el.backgroundColor)
	end
	if el.rotation then
		inst.Rotation = el.rotation
	end
	if el.layoutOrder then
		inst.LayoutOrder = el.layoutOrder
	end
	if el.clipsDescendants then
		inst.ClipsDescendants = true
	end
	if inst:IsA("CanvasGroup") then
		inst.GroupTransparency = el.groupTransparency or 0
	end
	inst:SetAttribute("PenpotId", el.id)

	if inst:IsA("TextLabel") or inst:IsA("TextButton") then
		local t = inst :: any
		t.Text = el.text or ""
		if el.font then
			t.FontFace = Font.fromName(el.font.family,
				enumItem(Enum.FontWeight, el.font.weight, Enum.FontWeight.Regular),
				enumItem(Enum.FontStyle, el.font.style, Enum.FontStyle.Normal))
		end
		t.TextSize = el.textSize or 14
		-- Order matters: setting TextWrapped = false turns TextScaled off in Roblox.
		t.TextWrapped = el.textWrapped ~= false
		t.TextScaled = el.textScaled == true
		if el.textColor then
			t.TextColor3 = Color3.fromHex(el.textColor)
		end
		t.TextTransparency = el.textTransparency or 0
		t.TextXAlignment = enumItem(Enum.TextXAlignment, el.textXAlignment, Enum.TextXAlignment.Center)
		t.TextYAlignment = enumItem(Enum.TextYAlignment, el.textYAlignment, Enum.TextYAlignment.Center)
		if el.lineHeight then
			t.LineHeight = el.lineHeight
		end
		if inst:IsA("TextButton") then
			inst.AutoButtonColor = true
		end
	end

	if el.image and (inst:IsA("ImageLabel") or inst:IsA("ImageButton")) then
		local i = inst :: any
		local asset = ctx.images[el.image.key]
		if asset then
			i.Image = asset
		else
			table.insert(ctx.warnings, `{el.name}: image {el.image.key} not uploaded yet (no entry in images)`)
		end
		i.ScaleType = enumItem(Enum.ScaleType, el.image.scaleType, Enum.ScaleType.Fit)
	end

	decorate(inst, el)
	for _, child in el.children or {} do
		create(child, ctx).Parent = inst
	end
	ctx.built += 1
	return inst
end

-- Build (or rebuild) the ScreenGui. spec: JSON string or decoded table.
function M.build(spec: any, options: Options?): (ScreenGui, Report)
	local opts: Options = options or {}
	if type(spec) == "string" then
		spec = HttpService:JSONDecode(spec)
	end
	assert(type(spec) == "table" and spec.board and spec.elements, "not a penpot-to-roblox spec")
	assert(spec.version == M.SPEC_VERSION, `spec version {spec.version}; this builder reads version {M.SPEC_VERSION} (re-run the converter)`)
	local parent: Instance = opts.parent or StarterGui
	local name = opts.name or spec.board.name
	local existing = parent:FindFirstChild(name)
	if existing and existing:GetAttribute("PenpotBoardId") == nil then
		error(`refusing to replace {existing:GetFullName()}: it was not built by PenpotUIBuilder (pass another name)`)
	end

	local ctx: Ctx = { images = opts.images or {}, warnings = {}, built = 0 }
	local screen = Instance.new("ScreenGui")
	screen.Name = name
	screen.ResetOnSpawn = false
	screen.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	screen.IgnoreGuiInset = false
	trySet(screen, "ScreenInsets", Enum.ScreenInsets.CoreUISafeInsets)
	screen:SetAttribute("PenpotBoardId", spec.board.id)
	screen:SetAttribute("PenpotBoard", spec.board.name)
	screen:SetAttribute("PenpotSpecVersion", spec.version)
	for _, el in spec.elements do
		create(el, ctx).Parent = screen
	end
	for _, w in spec.warnings or {} do
		table.insert(ctx.warnings, "converter: " .. w)
	end
	if existing then
		existing:Destroy()
	end
	screen.Parent = parent -- parent last: one atomic swap
	return screen, { screen = screen:GetFullName(), built = ctx.built, warnings = ctx.warnings }
end

function M.report(r: Report): string
	local lines = { `built {r.screen}: {r.built} elements, {#r.warnings} warning(s)` }
	for _, w in r.warnings do
		table.insert(lines, "  warning: " .. w)
	end
	return table.concat(lines, "\n")
end

return M
