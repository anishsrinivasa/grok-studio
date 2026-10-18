--!strict
--[[
post_import_check.luau - grok-studio (Builder): is the imported model what Blender made?

Run after apply_manifest.luau. Read-only: it changes nothing.
Usage: execute_luau with datamodel_type "Edit". Send this whole file with MANIFEST_JSON and
MODEL_PATH filled in (same values as for apply_manifest.luau). Returns JSON:
  {"pass": bool, "failed": [check names], "checks": [{"name", "pass", "detail"}], "model": path}
A failed check blocks status "placed": fix the cause (re-export, re-apply), then run it again.

Checks: model, partCount, partNames, onlyMeshParts, sizes, positions, colors, materials,
textures, physics, noOverlays (no plain Parts layered on / coincident with the MeshParts,
no duplicate coincident parts), nothingOutside (no loose copies of the asset's parts, and the
model's bounds match the manifest), noScripts, pivot.
]]

local MANIFEST_JSON = [==[
PASTE THE CONTENTS OF exports/<id>.manifest.json HERE
]==]
local MODEL_PATH = "Workspace.Model"
local TOL = {
	sizeAbs = 0.05, -- studs
	sizeRel = 0.03, -- of the dimension
	posAbs = 0.1, -- studs
	posRel = 0.02, -- of the asset's largest dimension
	color = 3 / 255, -- per channel
	overlay = 0.5, -- share of another part's volume inside one of ours that counts as layered on
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

local function vec(t: { number }): Vector3
	return Vector3.new(t[1], t[2], t[3])
end

local function fmt(v: Vector3): string
	return string.format("(%.3f, %.3f, %.3f)", v.X, v.Y, v.Z)
end

local function close(a: number, b: number, abs: number, rel: number): boolean
	return math.abs(a - b) <= abs + rel * math.max(math.abs(a), math.abs(b))
end

-- World-axis bounding box (min, max) of a part.
local function aabb(p: BasePart): (Vector3, Vector3)
	local cf, half = p.CFrame, p.Size / 2
	local r, u, l = cf.RightVector, cf.UpVector, cf.LookVector
	local ext = Vector3.new(
		math.abs(r.X) * half.X + math.abs(u.X) * half.Y + math.abs(l.X) * half.Z,
		math.abs(r.Y) * half.X + math.abs(u.Y) * half.Y + math.abs(l.Y) * half.Z,
		math.abs(r.Z) * half.X + math.abs(u.Z) * half.Y + math.abs(l.Z) * half.Z
	)
	return cf.Position - ext, cf.Position + ext
end

local function volume(lo: Vector3, hi: Vector3): number
	local d = hi - lo
	return math.max(d.X, 0) * math.max(d.Y, 0) * math.max(d.Z, 0)
end

local function overlap(alo: Vector3, ahi: Vector3, blo: Vector3, bhi: Vector3): number
	local lo = Vector3.new(math.max(alo.X, blo.X), math.max(alo.Y, blo.Y), math.max(alo.Z, blo.Z))
	local hi = Vector3.new(math.min(ahi.X, bhi.X), math.min(ahi.Y, bhi.Y), math.min(ahi.Z, bhi.Z))
	return volume(lo, hi)
end

local function boundsIn(parts: { BasePart }, frame: CFrame): (Vector3, Vector3)
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

local function check(): { [string]: any }
	local manifest = HttpService:JSONDecode(MANIFEST_JSON)
	local checks = {}
	local function add(name: string, ok: boolean, detail: any?)
		table.insert(checks, { name = name, pass = ok, detail = detail or "" })
	end
	local function result(modelPath: string?)
		local failed = {}
		for _, c in checks do
			if not c.pass then
				table.insert(failed, c.name)
			end
		end
		return { pass = #failed == 0, failed = failed, checks = checks, model = modelPath }
	end

	local root = resolve(MODEL_PATH)
	if root == nil or not root:IsA("Model") then
		add("model", false, `no Model at {MODEL_PATH}`)
		return result(nil)
	end
	local model = root :: Model
	add("model", true, model:GetFullName())

	-- What the model contains
	local meshParts: { [string]: MeshPart } = {}
	local allParts: { BasePart } = {}
	local meshList: { MeshPart } = {}
	local nonMesh, scripts = {}, {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			table.insert(allParts, d)
			if d:IsA("MeshPart") then
				meshParts[d.Name] = d
				table.insert(meshList, d)
			else
				table.insert(nonMesh, `{d.Name} ({d.ClassName})`)
			end
		elseif d:IsA("LuaSourceContainer") then
			table.insert(scripts, d:GetFullName())
		end
	end

	add("partCount", #meshList == #manifest.parts, `{#meshList} MeshParts, manifest has {#manifest.parts}`)

	local missingNames, expected = {}, {}
	for _, spec in manifest.parts do
		expected[spec.name] = true
		if not meshParts[spec.name] then
			table.insert(missingNames, spec.name)
		end
	end
	local unexpected = {}
	for _, p in meshList do
		if not expected[p.Name] then
			table.insert(unexpected, p.Name)
		end
	end
	add("partNames", #missingNames == 0 and #unexpected == 0, { missing = missingNames, unexpected = unexpected })
	add("onlyMeshParts", #nonMesh == 0, #nonMesh == 0 and "" or { extraParts = nonMesh })
	add("noScripts", #scripts == 0, #scripts == 0 and "" or scripts)

	-- Per-part comparisons
	local size = vec(manifest.size)
	local maxDim = math.max(size.X, size.Y, size.Z)
	local pivot = model.WorldPivot
	local sizeBad, posBad, colorBad, matBad, texBad, physBad = {}, {}, {}, {}, {}, {}
	for _, spec in manifest.parts do
		local p = meshParts[spec.name]
		if not p then
			continue
		end
		local want = vec(spec.size)
		local ok = close(p.Size.X, want.X, TOL.sizeAbs, TOL.sizeRel)
			and close(p.Size.Y, want.Y, TOL.sizeAbs, TOL.sizeRel)
			and close(p.Size.Z, want.Z, TOL.sizeAbs, TOL.sizeRel)
		if not ok then
			local a, b = { p.Size.X, p.Size.Y, p.Size.Z }, { want.X, want.Y, want.Z }
			table.sort(a)
			table.sort(b)
			local sameSorted = close(a[1], b[1], TOL.sizeAbs, TOL.sizeRel)
				and close(a[2], b[2], TOL.sizeAbs, TOL.sizeRel)
				and close(a[3], b[3], TOL.sizeAbs, TOL.sizeRel)
			table.insert(
				sizeBad,
				`{spec.name}: {fmt(p.Size)} vs {fmt(want)}{sameSorted and " (axes swapped: rotated import?)" or ""}`
			)
		end
		local rel = pivot:PointToObjectSpace(p.CFrame.Position)
		local wantPos = vec(spec.position)
		if (rel - wantPos).Magnitude > TOL.posAbs + TOL.posRel * maxDim then
			table.insert(posBad, `{spec.name}: {fmt(rel)} vs {fmt(wantPos)}`)
		end
		local c = Color3.fromHex(spec.hex)
		if
			math.abs(p.Color.R - c.R) > TOL.color
			or math.abs(p.Color.G - c.G) > TOL.color
			or math.abs(p.Color.B - c.B) > TOL.color
		then
			table.insert(colorBad, `{spec.name}: #{p.Color:ToHex()} vs {spec.hex}`)
		end
		if p.Material.Name ~= spec.robloxMaterial then
			table.insert(matBad, `{spec.name}: {p.Material.Name} vs {spec.robloxMaterial}`)
		end
		if p.TextureID ~= "" or p:FindFirstChildWhichIsA("SurfaceAppearance") then
			table.insert(texBad, `{spec.name}: a texture/SurfaceAppearance hides Color`)
		end
		local fid = p.CollisionFidelity.Name
		if
			p.Anchored ~= manifest.anchored
			or p.CanCollide ~= manifest.canCollide
			or fid ~= manifest.collisionFidelity
		then
			table.insert(
				physBad,
				`{spec.name}: Anchored={p.Anchored} CanCollide={p.CanCollide} CollisionFidelity={fid}`
			)
		end
	end
	add("sizes", #sizeBad == 0, sizeBad)
	add("positions", #posBad == 0, posBad)
	add("colors", #colorBad == 0, colorBad)
	add("materials", #matBad == 0, matBad)
	add("textures", #texBad == 0, texBad)
	add("physics", #physBad == 0, physBad)

	-- Pivot and bounds: bottom centre, and the model is exactly the manifest's size.
	if #allParts > 0 then
		local frame = pivot - pivot.Position
		local lo, hi = boundsIn(allParts, frame)
		local base = frame * CFrame.new((lo.X + hi.X) / 2, lo.Y, (lo.Z + hi.Z) / 2)
		add(
			"pivot",
			(base.Position - pivot.Position).Magnitude <= TOL.posAbs + TOL.posRel * maxDim,
			`pivot {fmt(pivot.Position)}, bottom centre {fmt(base.Position)}`
		)
		local got = hi - lo
		local boundsOk = close(got.X, size.X, 0.1, TOL.sizeRel)
			and close(got.Y, size.Y, 0.1, TOL.sizeRel)
			and close(got.Z, size.Z, 0.1, TOL.sizeRel)

		-- Loose copies of this asset's parts outside any copy of the asset.
		local stray = {}
		local function inAssetCopy(inst: Instance): boolean
			local a = inst.Parent
			while a do
				if a:IsA("Model") and a:GetAttribute("GsAssetId") == manifest.id then
					return true
				end
				a = a.Parent
			end
			return false
		end
		-- Plain parts layered on / coincident with ours, and duplicate coincident parts.
		local overlays, dupes = {}, {}
		local boxes = {}
		for _, p in meshList do
			local blo, bhi = aabb(p)
			table.insert(boxes, { part = p, lo = blo - Vector3.one * 0.05, hi = bhi + Vector3.one * 0.05 })
		end
		for i = 1, #meshList do
			for j = i + 1, #meshList do
				local a, b = meshList[i], meshList[j]
				if (a.CFrame.Position - b.CFrame.Position).Magnitude < 0.02 and (a.Size - b.Size).Magnitude < 0.02 then
					table.insert(dupes, `{a.Name} and {b.Name} coincide`)
				end
			end
		end
		-- Only a model in the world can collide with world parts: a template in ReplicatedStorage
		-- or ServerStorage sits at arbitrary coordinates, so skip the world scan for it.
		local inWorld = model:IsDescendantOf(workspace)
		local count = 0
		local scan: { Instance } = if inWorld then workspace:GetDescendants() else {}
		for _, d in scan do
			count += 1
			if count % 5000 == 0 then
				task.wait()
			end
			if not d:IsA("BasePart") or d:IsDescendantOf(model) or d:IsA("Terrain") then
				continue
			end
			if expected[d.Name] and not inAssetCopy(d) then
				table.insert(stray, d:GetFullName())
			end
			local dlo, dhi = aabb(d)
			local dv = volume(dlo, dhi)
			-- A thin plate laid exactly on a surface barely overlaps it: widen the box for those.
			local thin = math.min(d.Size.X, d.Size.Y, d.Size.Z) <= 0.25
			local grow = if thin then Vector3.one * 0.3 else Vector3.zero
			for _, box in boxes do
				local ov = overlap(dlo, dhi, box.lo - grow, box.hi + grow)
				if ov > 0 and dv > 0 and ov / dv >= TOL.overlay then
					local p = box.part
					if
						(d.CFrame.Position - p.CFrame.Position).Magnitude < 0.02
						and (d.Size - p.Size).Magnitude < 0.02
					then
						table.insert(dupes, `{d:GetFullName()} coincides with {p.Name}`)
					elseif not d:IsA("MeshPart") then
						table.insert(overlays, `{d:GetFullName()} ({d.ClassName}) sits on/in {p.Name}`)
					end
				end
			end
		end
		add("noOverlays", #overlays == 0 and #dupes == 0, {
			overlays = overlays,
			duplicates = dupes,
			worldChecked = inWorld,
		})
		add(
			"nothingOutside",
			boundsOk and #stray == 0,
			{ bounds = `{fmt(got)} vs manifest {fmt(size)}`, boundsOk = boundsOk, loose = stray }
		)
	end

	return result(model:GetFullName())
end

return HttpService:JSONEncode(check())
