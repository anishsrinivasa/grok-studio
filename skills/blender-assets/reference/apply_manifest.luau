--!strict
--[[
apply_manifest.luau - grok-studio (Builder)

After insert_asset (or the user's File > Import 3D), make the imported model match its
manifest: model name, per-MeshPart Color / Material / Anchored / CanCollide /
CollisionFidelity, PrimaryPart, a bottom-centre WorldPivot (the manifest's pivot) and the
BuiltBy / GsAssetId attributes.

Usage: execute_luau with datamodel_type "Edit". Send this whole file with the two values
below filled in. It returns a JSON report; run post_import_check.luau next. Running it twice
gives the same result. It changes only the model at MODEL_PATH (Builder's subtree).
  MANIFEST_JSON  the contents of exports/<id>.manifest.json
  MODEL_PATH     dot path from game, e.g. "Workspace.lava_rock"
]]

local MANIFEST_JSON = [==[
PASTE THE CONTENTS OF exports/<id>.manifest.json HERE
]==]
local MODEL_PATH = "Workspace.Model"
local OPTIONS = {
	clearTextures = true, -- flat-colour assets: drop TextureID / SurfaceAppearance so Color shows
	builtBy = "Builder GrokBot",
}

local HttpService = game:GetService("HttpService")

local function resolve(path: string): Instance?
	local node: Instance? = game
	for segment in string.gmatch(path, "[^%.]+") do
		if node == nil then
			return nil
		end
		if not (segment == "game" and node == game) then
			node = (node :: Instance):FindFirstChild(segment)
		end
	end
	return node
end

local function meshParts(root: Instance): { MeshPart }
	local list = {}
	for _, d in root:GetDescendants() do
		if d:IsA("MeshPart") then
			table.insert(list, d)
		end
	end
	return list
end

local function sortedDims(v: Vector3): { number }
	local t = { v.X, v.Y, v.Z }
	table.sort(t)
	return t
end

-- Find the MeshPart for a manifest part: exact name, case-insensitive, contained name
-- (importers add prefixes/suffixes), then closest size among the unmatched ones.
local function findPart(parts: { MeshPart }, spec: any, taken: { [MeshPart]: boolean }): (MeshPart?, string)
	local name: string = spec.name
	local lower = string.lower(name)
	for _, p in parts do
		if not taken[p] and p.Name == name then
			return p, "exact"
		end
	end
	for _, p in parts do
		if not taken[p] and string.lower(p.Name) == lower then
			return p, "case"
		end
	end
	for _, p in parts do
		local n = string.lower(p.Name)
		if not taken[p] and (string.find(n, lower, 1, true) or string.find(lower, n, 1, true)) then
			return p, "partial"
		end
	end
	local want = { spec.size[1], spec.size[2], spec.size[3] }
	table.sort(want)
	local best: MeshPart? = nil
	local bestErr = math.huge
	for _, p in parts do
		if not taken[p] then
			local have = sortedDims(p.Size)
			local err = 0
			for i = 1, 3 do
				err = math.max(err, math.abs(have[i] - want[i]) / math.max(want[i], 0.1))
			end
			if err < bestErr then
				best, bestErr = p, err
			end
		end
	end
	if best and bestErr < 0.1 then
		return best, "size"
	end
	return nil, "missing"
end

-- Axis-aligned bounds of parts in `frame`'s space.
local function bounds(parts: { BasePart }, frame: CFrame): (Vector3, Vector3)
	local lx, ly, lz = math.huge, math.huge, math.huge
	local hx, hy, hz = -math.huge, -math.huge, -math.huge
	for _, p in parts do
		local half = p.Size / 2
		for _, sx in { -1, 1 } do
			for _, sy in { -1, 1 } do
				for _, sz in { -1, 1 } do
					local w = p.CFrame:PointToWorldSpace(Vector3.new(half.X * sx, half.Y * sy, half.Z * sz))
					local l = frame:PointToObjectSpace(w)
					lx, ly, lz = math.min(lx, l.X), math.min(ly, l.Y), math.min(lz, l.Z)
					hx, hy, hz = math.max(hx, l.X), math.max(hy, l.Y), math.max(hz, l.Z)
				end
			end
		end
	end
	return Vector3.new(lx, ly, lz), Vector3.new(hx, hy, hz)
end

local function applyManifest(): { [string]: any }
	local manifest = HttpService:JSONDecode(MANIFEST_JSON)
	local model = resolve(MODEL_PATH)
	if model == nil or not model:IsA("Model") then
		return { ok = false, error = `no Model at {MODEL_PATH}` }
	end
	local m = model :: Model
	local parts = meshParts(m)
	local taken: { [MeshPart]: boolean } = {}
	local applied, missing, warnings = {}, {}, {}
	local byName: { [string]: MeshPart } = {}

	for _, spec in manifest.parts do
		local part, how = findPart(parts, spec, taken)
		if part == nil then
			table.insert(missing, spec.name)
			continue
		end
		local p = part :: MeshPart
		taken[p] = true
		local from = p.Name
		p.Name = spec.name
		p.Color = Color3.fromHex(spec.hex)
		local okMat, mat = pcall(function()
			return (Enum.Material :: any)[spec.robloxMaterial]
		end)
		if okMat and mat then
			p.Material = mat
		else
			p.Material = Enum.Material.SmoothPlastic
			table.insert(warnings, `{spec.name}: unknown Material '{spec.robloxMaterial}', used SmoothPlastic`)
		end
		p.Anchored = manifest.anchored
		p.CanCollide = manifest.canCollide
		local okCol = pcall(function()
			p.CollisionFidelity = (Enum.CollisionFidelity :: any)[manifest.collisionFidelity]
		end)
		if not okCol then
			table.insert(warnings, `{spec.name}: could not set CollisionFidelity {manifest.collisionFidelity}`)
		end
		p.RenderFidelity = Enum.RenderFidelity.Automatic
		if math.max(p.Size.X, p.Size.Y, p.Size.Z) < 1 then
			p.CastShadow = false -- tiny props: shadows cost more than they show
		end
		if OPTIONS.clearTextures then
			local okTex = pcall(function()
				p.TextureID = ""
			end)
			if not okTex then
				table.insert(warnings, `{spec.name}: could not clear TextureID`)
			end
			for _, c in p:GetChildren() do
				if c:IsA("SurfaceAppearance") then
					c:Destroy()
				end
			end
		end
		byName[spec.name] = p
		table.insert(applied, { name = spec.name, from = from, matchedBy = how })
	end

	local extra = {}
	for _, p in parts do
		if not taken[p] then
			table.insert(extra, p:GetFullName())
		end
	end

	m.Name = manifest.id
	local primary: MeshPart? = byName[manifest.primaryPart]
	if not primary then
		local biggest = -1
		for _, p in byName do
			local v = p.Size.X * p.Size.Y * p.Size.Z
			if v > biggest then
				primary, biggest = p, v
			end
		end
	end
	if primary then
		m.PrimaryPart = primary
		-- Pivot = bottom centre of the bounds, in the primary part's orientation.
		local frame = primary.CFrame - primary.CFrame.Position
		local all: { BasePart } = {}
		for _, p in parts do
			table.insert(all, p)
		end
		local lo, hi = bounds(all, frame)
		m.WorldPivot = frame * CFrame.new((lo.X + hi.X) / 2, lo.Y, (lo.Z + hi.Z) / 2)
	end
	m:SetAttribute("BuiltBy", OPTIONS.builtBy)
	m:SetAttribute("GsAssetId", manifest.id)
	m:SetAttribute("GsManifestVersion", manifest.version)
	m:SetAttribute("GsTriangles", manifest.triangles)

	return {
		ok = #missing == 0 and #extra == 0,
		model = m:GetFullName(),
		applied = applied,
		missing = missing,
		extra = extra,
		warnings = warnings,
	}
end

return HttpService:JSONEncode(applyManifest())
