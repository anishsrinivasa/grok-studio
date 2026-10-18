--!strict
--[[
PenpotUIVerifier.luau - checks a built ScreenGui against its penpot-to-roblox spec (v2).

Use (Studio MCP execute_luau, Edit mode), after PenpotUIBuilder:

    local Verifier = (function()
        -- paste this whole file here
    end)()
    local result = Verifier.verify(game.StarterGui.<ScreenName>, [==[ <spec JSON> ]==])
    print(Verifier.report(result))   -- first line: PASS or FAIL

FAIL when: an element is missing, duplicated or of the wrong class; Position, Size or
AnchorPoint differ (scale, 0.002 tolerance); colours / transparencies / text / font /
visibility / layout order differ; a UICorner, UIStroke, UIGradient, UIAspectRatioConstraint,
UIListLayout/UIGridLayout, UIPadding or UITextSizeConstraint from the spec is missing or
wrong; or a visible element lies outside the screen in the current viewport.
Warnings (not failures): images not uploaded yet, extra GuiObjects not in the spec, text
that does not fit its box.
]]

local HttpService = game:GetService("HttpService")

local M = {}

export type Result = { status: string, checks: number, errors: { string }, warnings: { string } }

local TOL = 0.002
local COLOR_TOL = 1.5 / 255

local function near(a: number, b: number, tol: number?): boolean
	return math.abs(a - b) <= (tol or TOL)
end

local function udimNear(u: UDim, d: any): boolean
	return near(u.Scale, d.scale or 0) and near(u.Offset, d.offset or 0, 0.5)
end

local function udim2Near(u: UDim2, d: any): boolean
	return near(u.X.Scale, d.scaleX or 0) and near(u.Y.Scale, d.scaleY or 0)
		and near(u.X.Offset, d.offsetX or 0, 0.5) and near(u.Y.Offset, d.offsetY or 0, 0.5)
end

local function colorNear(c: Color3, h: string): boolean
	local e = Color3.fromHex(h)
	return near(c.R, e.R, COLOR_TOL) and near(c.G, e.G, COLOR_TOL) and near(c.B, e.B, COLOR_TOL)
end

local function fmt(u: UDim2): string
	return string.format("{%.4f,%g},{%.4f,%g}", u.X.Scale, u.X.Offset, u.Y.Scale, u.Y.Offset)
end

type Ctx = { errors: { string }, warnings: { string }, checks: number, screenPos: Vector2?, screenSize: Vector2?, factor: Vector2? }

local function check(ctx: Ctx, ok: boolean, msg: string)
	ctx.checks += 1
	if not ok then
		table.insert(ctx.errors, msg)
	end
end

local function guiChildren(inst: Instance): { [string]: { GuiObject } }
	local byName: { [string]: { GuiObject } } = {}
	for _, c in inst:GetChildren() do
		if c:IsA("GuiObject") then
			byName[c.Name] = byName[c.Name] or {}
			table.insert(byName[c.Name], c)
		end
	end
	return byName
end

local function verifyElement(inst: GuiObject, el: any, path: string, ctx: Ctx)
	check(ctx, inst.ClassName == el.type, `{path}: class {inst.ClassName}, spec {el.type}`)
	check(ctx, udim2Near(inst.Position, el.position), `{path}: Position {fmt(inst.Position)} differs from spec`)
	check(ctx, udim2Near(inst.Size, el.size), `{path}: Size {fmt(inst.Size)} differs from spec`)
	check(ctx, near(inst.AnchorPoint.X, el.anchorPoint.x) and near(inst.AnchorPoint.Y, el.anchorPoint.y),
		`{path}: AnchorPoint {inst.AnchorPoint} differs from spec`)
	check(ctx, inst.Visible == (el.visible ~= false), `{path}: Visible is {inst.Visible}`)
	check(ctx, near(inst.BackgroundTransparency, el.backgroundTransparency or 1, 0.01),
		`{path}: BackgroundTransparency {inst.BackgroundTransparency}, spec {el.backgroundTransparency}`)
	if el.backgroundColor then
		check(ctx, colorNear(inst.BackgroundColor3, el.backgroundColor),
			`{path}: BackgroundColor3 #{inst.BackgroundColor3:ToHex()}, spec {el.backgroundColor}`)
	end
	if el.layoutOrder then
		check(ctx, inst.LayoutOrder == el.layoutOrder, `{path}: LayoutOrder {inst.LayoutOrder}, spec {el.layoutOrder}`)
	end
	if el.rotation then
		check(ctx, near(inst.Rotation, el.rotation, 0.01), `{path}: Rotation {inst.Rotation}, spec {el.rotation}`)
	end
	if el.groupTransparency and inst:IsA("CanvasGroup") then
		check(ctx, near(inst.GroupTransparency, el.groupTransparency, 0.01), `{path}: GroupTransparency differs`)
	end

	if inst:IsA("TextLabel") or inst:IsA("TextButton") then
		local t = inst :: any
		check(ctx, t.Text == (el.text or ""), `{path}: Text "{t.Text}", spec "{el.text}"`)
		if el.textColor then
			check(ctx, colorNear(t.TextColor3, el.textColor), `{path}: TextColor3 #{t.TextColor3:ToHex()}, spec {el.textColor}`)
		end
		if el.font then
			local family = string.match(t.FontFace.Family, "families/([%w_]+)%.json$")
			check(ctx, family == el.font.family and t.FontFace.Weight.Name == el.font.weight,
				`{path}: font {family} {t.FontFace.Weight.Name}, spec {el.font.family} {el.font.weight}`)
		end
		check(ctx, t.TextScaled == (el.textScaled == true), `{path}: TextScaled is {t.TextScaled}`)
		if el.textXAlignment then
			check(ctx, t.TextXAlignment.Name == el.textXAlignment, `{path}: TextXAlignment {t.TextXAlignment.Name}`)
		end
		if el.textScaled and el.textSize then
			local c = inst:FindFirstChildOfClass("UITextSizeConstraint")
			check(ctx, c ~= nil and c.MaxTextSize == math.clamp(math.floor(el.textSize + 0.5), 1, 100),
				`{path}: UITextSizeConstraint MaxTextSize {el.textSize} missing`)
		end
		if t.Text ~= "" and t.TextFits == false and inst.Visible then
			table.insert(ctx.warnings, `{path}: text does not fit its box at this viewport size`)
		end
	end
	if el.image and (inst:IsA("ImageLabel") or inst:IsA("ImageButton")) then
		if (inst :: any).Image == "" then
			table.insert(ctx.warnings, `{path}: no image yet (key {el.image.key}); upload it and rebuild`)
		end
	end

	if el.corner then
		local c = inst:FindFirstChildOfClass("UICorner")
		check(ctx, c ~= nil and udimNear(c.CornerRadius, el.corner), `{path}: UICorner missing or radius differs`)
	end
	if el.stroke then
		local s = inst:FindFirstChildOfClass("UIStroke")
		check(ctx, s ~= nil and near(s.Thickness, el.stroke.thickness, 0.01) and colorNear(s.Color, el.stroke.color),
			`{path}: UIStroke missing or differs`)
	end
	if el.gradient then
		check(ctx, inst:FindFirstChildOfClass("UIGradient") ~= nil, `{path}: UIGradient missing`)
	end
	if el.aspectRatio then
		local a = inst:FindFirstChildOfClass("UIAspectRatioConstraint")
		check(ctx, a ~= nil and near(a.AspectRatio, el.aspectRatio, 0.001), `{path}: UIAspectRatioConstraint missing or differs`)
	end
	if el.layout then
		local cls = if el.layout.type == "Grid" then "UIGridLayout" else "UIListLayout"
		local l = inst:FindFirstChildOfClass(cls :: any)
		check(ctx, l ~= nil, `{path}: {cls} missing`)
		if l and el.layout.type == "List" then
			check(ctx, udimNear((l :: any).Padding, el.layout.padding), `{path}: UIListLayout.Padding differs`)
		elseif l then
			check(ctx, udim2Near((l :: any).CellSize, el.layout.cellSize), `{path}: UIGridLayout.CellSize differs`)
		end
	end
	if el.padding then
		local p = inst:FindFirstChildOfClass("UIPadding")
		check(ctx, p ~= nil and udimNear(p.PaddingLeft, el.padding.left) and udimNear(p.PaddingTop, el.padding.top),
			`{path}: UIPadding missing or differs`)
	end

	-- On screen (current viewport), for visible elements only.
	if inst.Visible and ctx.screenSize and ctx.screenPos and ctx.screenSize.X > 0 then
		local p, s = inst.AbsolutePosition - ctx.screenPos, inst.AbsoluteSize
		local slack = 2
		check(ctx, p.X >= -slack and p.Y >= -slack and p.X + s.X <= ctx.screenSize.X + slack
			and p.Y + s.Y <= ctx.screenSize.Y + slack,
			string.format("%s: outside the screen (%.0f,%.0f %.0fx%.0f in %.0fx%.0f)", path, p.X, p.Y, s.X, s.Y,
				ctx.screenSize.X, ctx.screenSize.Y))
	end

	-- Rendered size = design size stretched to this screen (fitted for aspect-locked elements).
	-- Catches layout effects the properties alone don't show, e.g. UIPadding shrinking children.
	-- ctx.factor = how much the parent was stretched from the design (screen/board at the top).
	local factor = ctx.factor
	local childFactor: Vector2? = nil
	if el.design and inst.Visible and ctx.screenSize and factor and ctx.screenSize.X > 0 and (el.rotation or 0) == 0 then
		local sx, sy = factor.X, factor.Y
		local ew, eh = el.design.width * sx, el.design.height * sy
		if el.aspectRatio then
			if ew / math.max(eh, 1e-6) > el.aspectRatio then ew = eh * el.aspectRatio else eh = ew / el.aspectRatio end
		end
		local s = inst.AbsoluteSize
		local tol = function(v: number) return 2 + v * 0.01 end
		check(ctx, math.abs(s.X - ew) <= tol(ew) and math.abs(s.Y - eh) <= tol(eh),
			string.format("%s: renders %.0fx%.0f, design says %.0fx%.0f on this screen", path, s.X, s.Y, ew, eh))
		if el.design.width > 0 and el.design.height > 0 then
			childFactor = Vector2.new(s.X / el.design.width, s.Y / el.design.height)
		end
	end

	ctx.factor = childFactor

	M._children(inst, el.children or {}, path, ctx, inst.Visible)
	ctx.factor = factor
end

local function intersects(ax: number, ay: number, aw: number, ah: number, bx: number, by: number, bw: number, bh: number, slack: number): boolean
	return math.min(ax + aw, bx + bw) - math.max(ax, bx) > slack and math.min(ay + ah, by + bh) - math.max(ay, by) > slack
end

-- Siblings that are apart in the design must not overlap on this screen (a layout broken
-- by the viewport's aspect ratio, e.g. a right-anchored bar running into a left one).
function M._overlaps(byName: { [string]: { GuiObject } }, elements: { any }, path: string, ctx: Ctx, visible: boolean)
	if not visible or not ctx.screenSize then
		return
	end
	local items = {}
	for _, el in elements do
		local found = byName[el.name]
		if el.design and el.visible ~= false and found and #found == 1 and found[1].Visible then
			table.insert(items, { el = el, inst = found[1] })
		end
	end
	for i = 1, #items do
		for j = i + 1, #items do
			local a, b = items[i], items[j]
			local da, db = a.el.design, b.el.design
			if not intersects(da.x, da.y, da.width, da.height, db.x, db.y, db.width, db.height, 1) then
				local pa, sa = a.inst.AbsolutePosition, a.inst.AbsoluteSize
				local pb, sb = b.inst.AbsolutePosition, b.inst.AbsoluteSize
				check(ctx, not intersects(pa.X, pa.Y, sa.X, sa.Y, pb.X, pb.Y, sb.X, sb.Y, 2),
					`{path}: {a.el.name} overlaps {b.el.name} on this screen (apart in the design)`)
			end
		end
	end
end

function M._children(parent: Instance, elements: { any }, path: string, ctx: Ctx, visible: boolean)
	local byName = guiChildren(parent)
	local expected: { [string]: boolean } = {}
	for _, el in elements do
		expected[el.name] = true
		local found = byName[el.name]
		local childPath = path .. "/" .. el.name
		if not found then
			check(ctx, false, `{childPath}: missing`)
		elseif #found > 1 then
			check(ctx, false, `{childPath}: {#found} GuiObjects share this name`)
		else
			local saved = ctx.screenSize
			if not visible then
				ctx.screenSize = nil -- hidden subtree: no on-screen check
			end
			verifyElement(found[1], el, childPath, ctx)
			ctx.screenSize = saved
		end
	end
	M._overlaps(byName, elements, path, ctx, visible)
	for name in byName do
		if not expected[name] then
			table.insert(ctx.warnings, `{path}/{name}: not in the spec (added by hand?)`)
		end
	end
end

function M.verify(screen: Instance?, spec: any): Result
	if type(spec) == "string" then
		spec = HttpService:JSONDecode(spec)
	end
	local ctx: Ctx = { errors = {}, warnings = {}, checks = 0 }
	if not screen then
		return { status = "FAIL", checks = 0, errors = { "ScreenGui not found" }, warnings = {} }
	end
	if type(spec) ~= "table" or spec.version ~= 2 then
		return { status = "FAIL", checks = 0, errors = { "not a version 2 penpot-to-roblox spec" }, warnings = {} }
	end
	if screen:IsA("ScreenGui") then
		local size = screen.AbsoluteSize
		ctx.screenPos = screen.AbsolutePosition
		ctx.screenSize = size
		if spec.board and spec.board.width and spec.board.height then
			ctx.factor = Vector2.new(size.X / spec.board.width, size.Y / spec.board.height)
		end
		check(ctx, screen:GetAttribute("PenpotBoardId") == spec.board.id, `{screen.Name}: PenpotBoardId differs (built from another board?)`)
	end
	M._children(screen, spec.elements, screen.Name, ctx, true)
	return { status = if #ctx.errors == 0 then "PASS" else "FAIL", checks = ctx.checks, errors = ctx.errors, warnings = ctx.warnings }
end

function M.report(r: Result): string
	local lines = { `{r.status} ({r.checks} checks, {#r.errors} failed, {#r.warnings} warning(s))` }
	for _, e in r.errors do
		table.insert(lines, "  error: " .. e)
	end
	for _, w in r.warnings do
		table.insert(lines, "  warning: " .. w)
	end
	return table.concat(lines, "\n")
end

return M
