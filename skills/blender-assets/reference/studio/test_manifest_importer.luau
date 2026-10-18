-- test_manifest_importer.luau - runs manifest_importer.lua outside Studio against a tiny mock
-- of the Roblox API (Instance tree, Color3, WeldConstraint). Not runnable on its own:
-- reference/test_split_logic.py replaces the IMPORTER marker below with
-- `(function() <manifest_importer.lua> end)()` (the exact way the skill tells bots to paste it
-- into execute_luau) and runs the result with the `luau` CLI when one is installed.

local SUPER = {MeshPart = "BasePart", Part = "BasePart", WedgePart = "BasePart", BasePart = "Instance",
	WeldConstraint = "Instance", Motor6D = "JointInstance", Weld = "JointInstance", JointInstance = "Instance",
	SurfaceAppearance = "Instance", Model = "Instance", Instance = nil}

Color3 = {}
Color3.__index = Color3
function Color3.fromRGB(r, g, b) return setmetatable({R = r / 255, G = g / 255, B = b / 255}, Color3) end
function Color3:ToHex() return string.format("%02X%02X%02X", math.round(self.R * 255), math.round(self.G * 255), math.round(self.B * 255)) end

local Inst = {}
local function new(class, name, parent)
	local o = {ClassName = class, Name = name or class, _children = {}, Color = Color3.fromRGB(163, 162, 165),
		TextureID = "", Transparency = 0}
	setmetatable(o, {__index = Inst, __newindex = function(t, k, v)
		if k == "Parent" then
			rawset(t, "_parent", v)
			table.insert(v._children, t)
		else
			rawset(t, k, v)
		end
	end})
	if parent then o.Parent = parent end
	return o
end
function Inst:IsA(c) local k = self.ClassName while k do if k == c then return true end k = SUPER[k] end return false end
function Inst:GetDescendants()
	local out = {}
	local function walk(n) for _, ch in n._children do table.insert(out, ch) walk(ch) end end
	walk(self)
	return out
end
function Inst:FindFirstChildWhichIsA(c) for _, ch in self._children do if ch:IsA(c) then return ch end end return nil end
function Inst:GetFullName() return self.Name end

game = {GetService = function(_, _s) return {JSONDecode = function() error("JSONDecode not mocked") end} end}
Instance = {new = function(class) return new(class) end}

local M = --@@IMPORTER@@

local fails = 0
local function check(cond, msg)
	print((if cond then "  ok   " else "  FAIL ") .. msg)
	if not cond then fails += 1 end
end

local manifest = {
	version = 1, colorSpace = "sRGB",
	meshes = {
		Head_Fur = {limb = "Head", main = true, material = "Fur", color = "#F6C57F"},
		Head_Eye = {limb = "Head", main = false, material = "Eye", color = "#3B2A40"},
		Body_Fur = {limb = "Body", main = true, material = "Fur", color = "#F6C57F"},
		Body_Saddle = {limb = "Body", main = false, material = "Saddle", color = "#8FD6F0"},
	},
	limbs = {Head = {main = "Head_Fur", pieces = {"Head_Fur", "Head_Eye"}},
		Body = {main = "Body_Fur", pieces = {"Body_Fur", "Body_Saddle"}}},
}

local function build()
	local model = new("Model", "Lion")
	for name in manifest.meshes do new("MeshPart", name, model) end
	new("Part", "Root", model).Transparency = 1
	new("Part", "Hitbox", model)
	return model
end

print("fresh import (before apply):")
local model = build()
local v0 = M.validate(model, manifest)
check(v0.status == "FAIL", "validate FAILs before apply (default grey colours, no welds)")

print("apply:")
local a = M.apply(model, manifest)
print(M.report(a))
check(a.status == "OK" and a.applied == 4, "apply OK on 4 meshes")
local v = M.validate(model, manifest)
print(M.report(v))
check(v.status == "PASS", "validate PASS after apply")
local eye
for _, d in model:GetDescendants() do if d.Name == "Head_Eye" then eye = d end end
check(eye.Color:ToHex() == "3B2A40", "Head_Eye colour is #3B2A40")
local w = eye:FindFirstChildWhichIsA("WeldConstraint")
check(w ~= nil and w.Part0.Name == "Head_Fur" and w.Part1 == eye, "Head_Eye welded to main piece Head_Fur")

print("idempotent:")
M.apply(model, manifest)
local n = 0
for _, ch in eye._children do if ch:IsA("WeldConstraint") then n += 1 end end
check(n == 1, "second apply adds no duplicate weld")

print("failure cases:")
new("Part", "FakeNose", model)
local v2 = M.validate(model, manifest)
check(v2.status == "FAIL" and string.find(table.concat(v2.errors, "|"), "FakeNose", 1, true) ~= nil, "overlay Part is reported")
local m2 = build()
for _, d in m2:GetDescendants() do if d.Name == "Head_Eye" then d._parent = nil; table.remove(m2._children, table.find(m2._children, d)) end end
M.apply(m2, manifest)
local v3 = M.validate(m2, manifest)
check(v3.status == "FAIL" and string.find(table.concat(v3.errors, "|"), "Head_Eye from the manifest is missing", 1, true) ~= nil, "missing mesh is reported")
local m3 = build(); M.apply(m3, manifest)
for _, d in m3:GetDescendants() do if d.Name == "Body_Saddle" then d.TextureID = "rbxassetid://1" end end
check(M.validate(m3, manifest).status == "FAIL", "texture hiding the colour is reported")
check(M.hexToColor3("#FFFFFF"):ToHex() == "FFFFFF" and M.hexToColor3("00ff00"):ToHex() == "00FF00", "hexToColor3")
check(M.apply(model, {} :: any).status == "ERROR", "bad manifest -> ERROR")

print(if fails == 0 then "=== PASS ===" else `=== FAIL ({fails}) ===`)
if fails > 0 then error("manifest importer tests failed") end
