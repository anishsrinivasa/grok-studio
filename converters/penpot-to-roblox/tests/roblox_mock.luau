-- roblox_mock.luau - a small fake of the Roblox API, enough to run PenpotUIBuilder and
-- PenpotUIVerifier outside Studio with the `luau` CLI. tests/luau.test.js fills the three
-- markers below (builder, verifier, specs) and runs it. Not runnable on its own.
-- Absolute layout is simulated: scale Position/Size, AnchorPoint and UIAspectRatioConstraint
-- (FitWithinMaxSize) against a viewport, so phone/tablet sizes can be checked.

local VIEWPORT = { x = 1920, y = 1080 }

---------------------------------------------------------------- value types
local function frozenType(name, ctor)
	return setmetatable({}, { __index = function(_, k) return ctor[k] end, __tostring = function() return name end })
end

local UDimMT = {}
UDimMT.__index = UDimMT
local UDim = { new = function(s, o) return setmetatable({ Scale = s or 0, Offset = o or 0 }, UDimMT) end }
local UDim2MT = {}
UDim2MT.__index = UDim2MT
local UDim2 = {
	new = function(xs, xo, ys, yo) return setmetatable({ X = UDim.new(xs, xo), Y = UDim.new(ys, yo) }, UDim2MT) end,
}
UDim2.fromScale = function(x, y) return UDim2.new(x, 0, y, 0) end
local V2MT = { __tostring = function(v) return `{v.X}, {v.Y}` end }
V2MT.__index = V2MT
V2MT.__sub = function(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y }, V2MT) end
local Vector2 = { new = function(x, y) return setmetatable({ X = x or 0, Y = y or 0 }, V2MT) end }

local C3 = {}
C3.__index = C3
local Color3 = {}
function Color3.new(r, g, b) return setmetatable({ R = r, G = g, B = b }, C3) end
function Color3.fromRGB(r, g, b) return Color3.new(r / 255, g / 255, b / 255) end
function Color3.fromHex(h)
	h = string.gsub(h, "#", "")
	assert(#h == 6, "Unable to convert characters to hex value")
	return Color3.fromRGB(tonumber(string.sub(h, 1, 2), 16), tonumber(string.sub(h, 3, 4), 16), tonumber(string.sub(h, 5, 6), 16))
end
function C3:ToHex() return string.format("%02X%02X%02X", math.round(self.R * 255), math.round(self.G * 255), math.round(self.B * 255)) end

local function seq(kind)
	return {
		new = function(points)
			assert(points[1].Time == 0 and points[#points].Time == 1, kind .. " time must start at 0 and end at 1")
			return { Keypoints = points }
		end,
	}
end
local ColorSequence, NumberSequence = seq("ColorSequence"), seq("NumberSequence")
local ColorSequenceKeypoint = { new = function(t, c) return { Time = t, Value = c } end }
local NumberSequenceKeypoint = { new = function(t, v) return { Time = t, Value = v } end }

-- Enums: indexing an unknown item throws, like Roblox.
local function mkEnum(name, items)
	local e = { _name = name }
	for _, it in items do e[it] = { Name = it, EnumType = name } end
	return setmetatable(e, { __index = function(_, k) error(`{k} is not a valid member of "Enum.{name}"`) end })
end
local Enum = {
	FontWeight = mkEnum("FontWeight", { "Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Heavy" }),
	FontStyle = mkEnum("FontStyle", { "Normal", "Italic" }),
	TextXAlignment = mkEnum("TextXAlignment", { "Left", "Center", "Right" }),
	TextYAlignment = mkEnum("TextYAlignment", { "Top", "Center", "Bottom" }),
	ApplyStrokeMode = mkEnum("ApplyStrokeMode", { "Border", "Contextual" }),
	BorderStrokePosition = mkEnum("BorderStrokePosition", { "Outer", "Center", "Inner" }),
	SortOrder = mkEnum("SortOrder", { "LayoutOrder", "Name" }),
	FillDirection = mkEnum("FillDirection", { "Horizontal", "Vertical" }),
	HorizontalAlignment = mkEnum("HorizontalAlignment", { "Left", "Center", "Right" }),
	VerticalAlignment = mkEnum("VerticalAlignment", { "Top", "Center", "Bottom" }),
	UIFlexAlignment = mkEnum("UIFlexAlignment", { "None", "Fill", "SpaceAround", "SpaceBetween", "SpaceEvenly" }),
	StartCorner = mkEnum("StartCorner", { "TopLeft" }),
	ScaleType = mkEnum("ScaleType", { "Stretch", "Fit", "Crop", "Tile", "Slice" }),
	ZIndexBehavior = mkEnum("ZIndexBehavior", { "Global", "Sibling" }),
	ScreenInsets = mkEnum("ScreenInsets", { "None", "DeviceSafeInsets", "CoreUISafeInsets", "TopbarSafeInsets" }),
}

local Font = {
	fromName = function(name, weight, style)
		return { Family = `rbxasset://fonts/families/{name}.json`, Weight = weight or Enum.FontWeight.Regular, Style = style or Enum.FontStyle.Normal }
	end,
}

---------------------------------------------------------------- instances
local SUPER = {
	ScreenGui = "LayerCollector", LayerCollector = "Instance", Folder = "Instance", StarterGui = "Instance",
	Frame = "GuiObject", CanvasGroup = "GuiObject", TextLabel = "GuiObject", TextButton = "GuiButton",
	ImageLabel = "GuiObject", ImageButton = "GuiButton", GuiButton = "GuiObject", GuiObject = "Instance",
	UICorner = "UIComponent", UIStroke = "UIComponent", UIGradient = "UIComponent", UIPadding = "UIComponent",
	UIAspectRatioConstraint = "UIComponent", UITextSizeConstraint = "UIComponent",
	UIListLayout = "UIComponent", UIGridLayout = "UIComponent", UIComponent = "Instance",
}
local DEFAULTS = {
	GuiObject = function(p)
		p.Position = UDim2.new(0, 0, 0, 0); p.Size = UDim2.new(0, 100, 0, 100); p.AnchorPoint = Vector2.new(0, 0)
		p.ZIndex = 1; p.Visible = true; p.BackgroundTransparency = 0; p.BackgroundColor3 = Color3.fromRGB(163, 162, 165)
		p.BorderSizePixel = 1; p.Rotation = 0; p.LayoutOrder = 0; p.ClipsDescendants = false
	end,
	TextLabel = function(p) p.Text = "Label"; p.TextSize = 14; p.TextScaled = false; p.TextWrapped = false; p.TextColor3 = Color3.new(0, 0, 0)
		p.TextTransparency = 0; p.TextXAlignment = Enum.TextXAlignment.Center; p.TextYAlignment = Enum.TextYAlignment.Center
		p.FontFace = Font.fromName("SourceSansPro"); p.LineHeight = 1; p.TextFits = true end,
	ImageLabel = function(p) p.Image = ""; p.ScaleType = Enum.ScaleType.Stretch end,
	CanvasGroup = function(p) p.GroupTransparency = 0 end,
	GuiButton = function(p) p.AutoButtonColor = true end,
}
DEFAULTS.TextButton = DEFAULTS.TextLabel
DEFAULTS.ImageButton = DEFAULTS.ImageLabel

local function isA(class, want)
	local k = class
	while k do
		if k == want then return true end
		k = SUPER[k]
	end
	return false
end

local Instance = {}
local InstMT = {}

local function absRect(self)
	local props = rawget(self, "_p")
	if self.ClassName == "ScreenGui" then
		return Vector2.new(0, 0), Vector2.new(VIEWPORT.x, VIEWPORT.y)
	end
	local parent = props.Parent
	if not parent or not isA(parent.ClassName, "GuiObject") and parent.ClassName ~= "ScreenGui" then
		return Vector2.new(0, 0), Vector2.new(0, 0)
	end
	local pp, ps = absRect(parent)
	local s, p, a = props.Size, props.Position, props.AnchorPoint
	local w, h = s.X.Scale * ps.X + s.X.Offset, s.Y.Scale * ps.Y + s.Y.Offset
	for _, c in rawget(self, "_c") do
		if c.ClassName == "UIAspectRatioConstraint" then -- FitWithinMaxSize
			local r = rawget(c, "_p").AspectRatio
			if w / h > r then w = h * r else h = w / r end
		end
	end
	local x = pp.X + p.X.Scale * ps.X + p.X.Offset - a.X * w
	local y = pp.Y + p.Y.Scale * ps.Y + p.Y.Offset - a.Y * h
	return Vector2.new(x, y), Vector2.new(w, h)
end

InstMT.__index = function(self, k)
	local m = Instance[k]
	if m then return m end
	if k == "AbsolutePosition" then return (absRect(self)) end
	if k == "AbsoluteSize" then local _, s = absRect(self); return s end
	local v = rawget(self, "_p")[k]
	if v == nil and k ~= "Parent" then error(`{k} is not a valid member of {self.ClassName} "{rawget(self, "_p").Name}"`) end
	return v
end
InstMT.__newindex = function(self, k, v)
	local props = rawget(self, "_p")
	if k == "Parent" then
		local old = props.Parent
		if old then
			local list = rawget(old, "_c")
			local i = table.find(list, self)
			if i then table.remove(list, i) end
		end
		props.Parent = v
		if v then table.insert(rawget(v, "_c"), self) end
		return
	end
	if props[k] == nil and k ~= "Name" and not (k == "Wraps" or k == "HorizontalFlex" or k == "VerticalFlex"
		or k == "BorderStrokePosition" or k == "ScreenInsets") and not props._open then
		error(`{k} is not a valid member of {self.ClassName}`)
	end
	props[k] = v
end

function Instance.new(class)
	assert(SUPER[class], `Unable to create an Instance of type "{class}"`)
	local self = setmetatable({ _p = { ClassName = class, Name = class, _attrs = {} }, _c = {} }, InstMT)
	local props = rawget(self, "_p")
	local k = class
	local chain = {}
	while k do table.insert(chain, 1, k); k = SUPER[k] end
	for _, c in chain do if DEFAULTS[c] then DEFAULTS[c](props) end end
	if not isA(class, "GuiObject") then props._open = true end -- non-GUI: accept any property
	return self
end
function Instance:IsA(c) return isA(self.ClassName, c) end
function Instance:GetChildren() return table.clone(rawget(self, "_c")) end
function Instance:GetDescendants()
	local out = {}
	local function walk(n) for _, c in rawget(n, "_c") do table.insert(out, c); walk(c) end end
	walk(self)
	return out
end
function Instance:FindFirstChild(name) for _, c in rawget(self, "_c") do if c.Name == name then return c end end return nil end
function Instance:FindFirstChildOfClass(cl) for _, c in rawget(self, "_c") do if c.ClassName == cl then return c end end return nil end
function Instance:SetAttribute(k, v) rawget(self, "_p")._attrs[k] = v end
function Instance:GetAttribute(k) return rawget(self, "_p")._attrs[k] end
function Instance:Destroy() self.Parent = nil end
function Instance:GetFullName() return "StarterGui." .. self.Name end

---------------------------------------------------------------- JSON (for HttpService:JSONDecode)
local function jsonDecode(s)
	local i = 1
	local function ws() i = string.find(s, "[^ \t\r\n]", i) or #s + 1 end
	local value
	local function str()
		local out, j = {}, i + 1
		while true do
			local c = string.sub(s, j, j)
			if c == '"' then i = j + 1; return table.concat(out) end
			if c == "\\" then
				local n = string.sub(s, j + 1, j + 1)
				if n == "u" then table.insert(out, utf8.char(tonumber(string.sub(s, j + 2, j + 5), 16))); j += 6
				else table.insert(out, ({ n = "\n", t = "\t", r = "\r", b = "\b", f = "\f" })[n] or n); j += 2 end
			else table.insert(out, c); j += 1 end
		end
	end
	function value()
		ws()
		local c = string.sub(s, i, i)
		if c == "{" then
			local t = {}; i += 1; ws()
			if string.sub(s, i, i) == "}" then i += 1; return t end
			while true do
				ws(); local k = str(); ws(); i += 1 -- ':'
				t[k] = value(); ws()
				local d = string.sub(s, i, i); i += 1
				if d == "}" then return t end
			end
		elseif c == "[" then
			local t = {}; i += 1; ws()
			if string.sub(s, i, i) == "]" then i += 1; return t end
			while true do
				table.insert(t, value()); ws()
				local d = string.sub(s, i, i); i += 1
				if d == "]" then return t end
			end
		elseif c == '"' then return str()
		elseif string.sub(s, i, i + 3) == "true" then i += 4; return true
		elseif string.sub(s, i, i + 4) == "false" then i += 5; return false
		elseif string.sub(s, i, i + 3) == "null" then i += 4; return nil
		else
			local num = string.match(s, "^-?%d+%.?%d*[eE]?[-+]?%d*", i)
			i += #num
			return tonumber(num)
		end
	end
	return value()
end

local StarterGuiService = setmetatable({ _p = { ClassName = "StarterGui", Name = "StarterGui", _attrs = {}, _open = true }, _c = {} }, InstMT)
game = {
	GetService = function(_, name)
		if name == "HttpService" then return { JSONDecode = function(_, s) return jsonDecode(s) end } end
		if name == "StarterGui" then return StarterGuiService end
		error("no service " .. name)
	end,
}

---------------------------------------------------------------- modules under test
local Builder = --@@BUILDER@@
local Verifier = --@@VERIFIER@@
local SPECS = --@@SPECS@@

---------------------------------------------------------------- tests
local fails = 0
local function check(ok, msg)
	print((if ok then "  ok   " else "  FAIL ") .. msg)
	if not ok then fails += 1 end
end
local function has(list, pat)
	for _, s in list do if string.find(s, pat, 1, true) then return true end end
	return false
end
local VIEWPORTS = { { "desktop 1920x1080", 1920, 1080 }, { "phone 844x390", 844, 390 }, { "tablet 1024x768", 1024, 768 } }

for _, name in { "hud", "menu", "shop" } do
	print(`{name}:`)
	local specJson = SPECS[name]
	local screen, rep = Builder.build(specJson, { name = "PenpotTest" })
	check(screen.Parent == StarterGuiService and screen.Name == "PenpotTest", `built ScreenGui PenpotTest ({rep.built} elements)`)
	for _, vp in VIEWPORTS do
		VIEWPORT.x, VIEWPORT.y = vp[2], vp[3]
		local r = Verifier.verify(screen, specJson)
		check(r.status == "PASS", `{vp[1]}: verify {r.status} ({r.checks} checks)`)
		if r.status ~= "PASS" then print(Verifier.report(r)) end
	end
	VIEWPORT.x, VIEWPORT.y = 1920, 1080
	local again = Builder.build(specJson, { name = "PenpotTest" })
	local count = 0
	for _, c in StarterGuiService:GetChildren() do if c.Name == "PenpotTest" then count += 1 end end
	check(count == 1 and again ~= screen, "rebuild replaces the old ScreenGui (idempotent)")
	again:Destroy()
end

print("broken build -> FAIL:")
local hud = SPECS.hud
local screen = Builder.build(hud, { name = "PenpotTest" })
local coin = screen:FindFirstChild("CoinCounter")
coin:FindFirstChild("Amount").Text = "0"                         -- wrong text
screen:FindFirstChild("HealthBar").BackgroundColor3 = Color3.fromHex("#FF0000") -- wrong colour
screen:FindFirstChild("PauseButton").Position = UDim2.new(1.2, 0, 0.97, 0)      -- pushed off-screen
coin:FindFirstChildOfClass("UICorner"):Destroy()               -- decoration lost
screen:FindFirstChild("Toast"):Destroy()                        -- element missing
local overlay = Instance.new("Frame"); overlay.Name = "FakeBorder"; overlay.Parent = coin -- hand-made extra
local r = Verifier.verify(screen, hud)
print(Verifier.report(r))
check(r.status == "FAIL", "verify FAILs on a broken build")
check(has(r.errors, "Amount: Text"), "reports wrong text")
check(has(r.errors, "HealthBar: BackgroundColor3"), "reports wrong colour")
check(has(r.errors, "PauseButton: outside the screen"), "reports off-screen element")
check(has(r.errors, "CoinCounter: UICorner"), "reports missing UICorner")
check(has(r.errors, "Toast: missing"), "reports missing element")
check(has(r.warnings, "FakeBorder: not in the spec"), "warns about the hand-added Frame")

print("safety:")
local foreign = Instance.new("ScreenGui"); foreign.Name = "MainHud"; foreign.Parent = StarterGuiService
local ok, err = pcall(Builder.build, hud, { name = "MainHud" })
check(not ok and string.find(tostring(err), "refusing to replace", 1, true) ~= nil, "refuses to replace a ScreenGui it did not build")
local ok2 = pcall(Builder.build, '{"version":1,"board":{},"elements":[]}')
check(not ok2, "rejects a version 1 spec")

print(if fails == 0 then "=== PASS ===" else `=== FAIL ({fails}) ===`)
if fails > 0 then error("luau tests failed") end
