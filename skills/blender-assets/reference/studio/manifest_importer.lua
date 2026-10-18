--!strict
--[[
manifest_importer.lua - apply and verify a Blender export manifest in Roblox Studio.

Blender's export_fbx (roblox_export.py) splits every multi-material mesh into one mesh per
material, named <Object>_<Material>, and writes exports/<id>_manifest.json next to the FBX:

    {
      "version": 1, "colorSpace": "sRGB", "fbx": "<id>.fbx",
      "meshes": { "Head_Fur": {"limb": "Head", "main": true,  "material": "Fur", "color": "#F6C57F", "parent": null},
                  "Head_Eye": {"limb": "Head", "main": false, "material": "Eye", "color": "#3B2A40", "parent": null} },
      "limbs":  { "Head": {"main": "Head_Fur", "pieces": ["Head_Fur", "Head_Eye"]} }
    }

Colours are sRGB hex, i.e. exactly what Color3.fromHex / fromRGB expect.
Every piece of a limb has the same pivot (the limb's joint). The limb's MAIN piece is the
part the Animator gives the Motor6D; apply() welds the other pieces to it, so they follow.

Use (Studio MCP execute_luau, Edit mode). The file ends in `return M`, so wrap it:

    local M = (function()
        -- paste this whole file here
    end)()
    local manifest = M.decode([==[ <contents of exports/<id>_manifest.json> ]==])
    local model = game.ReplicatedStorage.Assets.Models.<id>
    print(M.report(M.apply(model, manifest)))     -- colours + welds, idempotent
    print(M.report(M.validate(model, manifest)))  -- post-import check; must say PASS

Or save it as a ModuleScript and `require` it. validate() fails when: a manifest mesh is
missing or duplicated, a colour is off by more than 1/255, a texture or SurfaceAppearance
would hide the colour, a non-main piece is not joined (Weld/WeldConstraint/Motor6D) to its
limb's main piece, or a non-hitbox, non-mesh Part was added (fake detail overlays).
]]

local HttpService = game:GetService("HttpService")

export type MeshInfo = {limb: string, main: boolean, material: string?, color: string, parent: string?}
export type Manifest = {version: number?, colorSpace: string?, fbx: string?,
	meshes: {[string]: MeshInfo}, limbs: {[string]: {main: string, pieces: {string}}}?}
export type Result = {status: string, errors: {string}, warnings: {string}, applied: number}

local M = {}

M.WELD_NAME = "ManifestWeld"

function M.decode(json: string): Manifest
	return HttpService:JSONDecode(json) :: Manifest
end

function M.hexToColor3(hex: string): Color3
	local h = string.gsub(hex, "#", "")
	return Color3.fromRGB(tonumber(string.sub(h, 1, 2), 16) or 0, tonumber(string.sub(h, 3, 4), 16) or 0,
		tonumber(string.sub(h, 5, 6), 16) or 0)
end

local function newResult(): Result
	return {status = "OK", errors = {}, warnings = {}, applied = 0}
end

-- name -> MeshPart, plus names that occur more than once
local function indexMeshParts(model: Instance): ({[string]: MeshPart}, {[string]: boolean})
	local parts: {[string]: MeshPart} = {}
	local dup: {[string]: boolean} = {}
	for _, d in model:GetDescendants() do
		if d:IsA("MeshPart") then
			if parts[d.Name] then
				dup[d.Name] = true
			end
			parts[d.Name] = d
		end
	end
	return parts, dup
end

-- main piece name for every limb (from "limbs", else from the per-mesh "main" flags)
local function mainOf(manifest: Manifest): {[string]: string}
	local out: {[string]: string} = {}
	if manifest.limbs then
		for limb, info in manifest.limbs do
			out[limb] = info.main
		end
	end
	for name, info in manifest.meshes do
		if info.main and out[info.limb] == nil then
			out[info.limb] = name
		end
	end
	return out
end

local function joined(a: BasePart, b: BasePart): boolean
	for _, part in {a, b} do
		for _, j in part:GetDescendants() do
			if j:IsA("WeldConstraint") or j:IsA("JointInstance") then
				local p0 = (j :: any).Part0
				local p1 = (j :: any).Part1
				if (p0 == a and p1 == b) or (p0 == b and p1 == a) then
					return true
				end
			end
		end
	end
	return false
end

-- Set each piece's Color from the manifest and weld non-main pieces to their limb's main piece.
function M.apply(model: Instance, manifest: Manifest): Result
	local r = newResult()
	if type(manifest) ~= "table" or type(manifest.meshes) ~= "table" then
		r.status = "ERROR"
		table.insert(r.errors, "manifest missing or has no meshes")
		return r
	end
	local parts, dup = indexMeshParts(model)
	local mains = mainOf(manifest)
	for name, info in manifest.meshes do
		local part = parts[name]
		if not part then
			table.insert(r.errors, `mesh {name} not found under {model:GetFullName()}`)
			continue
		end
		if dup[name] then
			table.insert(r.warnings, `several MeshParts are named {name}; only one was updated`)
		end
		part.Color = M.hexToColor3(info.color)
		local mainName = mains[info.limb]
		if not info.main and mainName then
			local main = parts[mainName]
			if not main then
				table.insert(r.errors, `main piece {mainName} of limb {info.limb} not found (needed by {name})`)
			elseif not joined(part, main) then
				local w = Instance.new("WeldConstraint")
				w.Name = M.WELD_NAME
				w.Part0 = main
				w.Part1 = part
				w.Parent = part
			end
		end
		r.applied += 1
	end
	if #r.errors > 0 then
		r.status = "PARTIAL"
	end
	return r
end

local function isHitboxOrRoot(p: BasePart): boolean
	local n = string.lower(p.Name)
	return string.find(n, "hitbox", 1, true) ~= nil or n == "root" or n == "humanoidrootpart"
		or p.Transparency >= 0.99
end

-- Post-import check. status = "PASS" or "FAIL"; errors list every problem found.
function M.validate(model: Instance, manifest: Manifest): Result
	local r = newResult()
	r.status = "PASS"
	if type(manifest) ~= "table" or type(manifest.meshes) ~= "table" then
		r.status = "FAIL"
		table.insert(r.errors, "manifest missing or has no meshes")
		return r
	end
	local parts, dup = indexMeshParts(model)
	local mains = mainOf(manifest)
	for name, info in manifest.meshes do
		local part = parts[name]
		if not part then
			table.insert(r.errors, `mesh {name} from the manifest is missing`)
			continue
		end
		if dup[name] then
			table.insert(r.errors, `mesh {name} exists more than once`)
		end
		local want = M.hexToColor3(info.color)
		local c = part.Color
		local tol = 1.5 / 255
		if math.abs(c.R - want.R) > tol or math.abs(c.G - want.G) > tol or math.abs(c.B - want.B) > tol then
			table.insert(r.errors, `mesh {name} colour is #{c:ToHex()}, manifest says {info.color}`)
		end
		if part.TextureID ~= "" or part:FindFirstChildWhichIsA("SurfaceAppearance") then
			table.insert(r.errors, `mesh {name} has a texture/SurfaceAppearance that hides its Color`)
		end
		local mainName = mains[info.limb]
		if not mainName then
			table.insert(r.errors, `limb {info.limb} has no main piece in the manifest`)
		elseif not info.main then
			local main = parts[mainName]
			if not main then
				table.insert(r.errors, `main piece {mainName} of limb {info.limb} is missing`)
			elseif not joined(part, main) then
				table.insert(r.errors, `mesh {name} is not welded to its limb's main piece {mainName}`)
			end
		end
		r.applied += 1
	end
	for name in parts do
		if manifest.meshes[name] == nil then
			table.insert(r.warnings, `MeshPart {name} is not in the manifest`)
		end
	end
	local overlays = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and not d:IsA("MeshPart") and not isHitboxOrRoot(d) then
			table.insert(overlays, d.Name)
		end
	end
	if #overlays > 0 then
		table.insert(r.errors, `{#overlays} non-hitbox overlay Parts (colour must come from the meshes): `
			.. table.concat(overlays, ", "))
	end
	if #r.errors > 0 then
		r.status = "FAIL"
	end
	return r
end

-- One printable block: status, then one line per error/warning.
function M.report(r: Result): string
	local lines = {`{r.status} ({r.applied} meshes)`}
	for _, e in r.errors do
		table.insert(lines, "  error: " .. e)
	end
	for _, w in r.warnings do
		table.insert(lines, "  warning: " .. w)
	end
	return table.concat(lines, "\n")
end

return M
