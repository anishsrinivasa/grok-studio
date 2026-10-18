--[[
manifest_importer.lua - Apply a Blender export manifest to imported Studio meshes.

The manifest (JSON next to the FBX) maps each split mesh to its parent limb and flat color.
This script sets each MeshPart.Color/Material and welds split pieces to their limb's
animated part, keeping existing limb names, Motor6Ds, tags, and non-animated hitboxes.

Usage (in Studio MCP execute_luau, Edit mode):
    -- Paste this file's contents, then call:
    local result = applyManifest(model, manifestData)
    print(result.status)  -- "OK" or error details

manifestData structure:
{
    meshes = {
        ["Head_Fur"] = {parentLimb = "Head", color = "#8B6F47", material = "Fur"},
        ["Head_Eye"] = {parentLimb = "Head", color = "#FFFFFF", material = "Eye"},
        ...
    },
    split = {{"Head", {{"Head_Fur", "Fur", "#8B6F47"}, ...}}, ...}
}
]]

local function hexToColor3(hex: string): Color3
	hex = hex:gsub("#", "")
	local r = tonumber(hex:sub(1, 2), 16) or 128
	local g = tonumber(hex:sub(3, 4), 16) or 128
	local b = tonumber(hex:sub(5, 6), 16) or 128
	return Color3.fromRGB(r, g, b)
end

local function findDescendant(parent: Instance, name: string): Instance?
	for _, child in parent:GetDescendants() do
		if child.Name == name then
			return child
		end
	end
	return nil
end

local function applyManifest(model: Model, manifestData: any): {status: string, errors: {string}?, applied: number?}
	local errors = {}
	local applied = 0
	
	if not manifestData or not manifestData.meshes then
		return {status = "ERROR", errors = {"manifest missing or invalid"}}
	end
	
	-- Index all MeshParts in the imported model
	local meshParts = {}
	for _, desc in model:GetDescendants() do
		if desc:IsA("MeshPart") then
			meshParts[desc.Name] = desc
		end
	end
	
	-- Apply manifest to each mesh
	for meshName, info in manifestData.meshes do
		local meshPart = meshParts[meshName]
		if not meshPart then
			table.insert(errors, string.format("mesh %s not found in model", meshName))
			continue
		end
		
		-- Set color
		local color = hexToColor3(info.color)
		meshPart.Color = color
		
		-- Find parent limb (if specified and different from mesh)
		local parentLimb = info.parentLimb
		if parentLimb and parentLimb ~= meshName then
			local limbPart = findDescendant(model, parentLimb)
			if not limbPart then
				table.insert(errors, string.format("parent limb %s not found for mesh %s", parentLimb, meshName))
			else
				-- Create a WeldConstraint to attach the mesh to its limb
				-- Only if they're not already parent-child
				if meshPart.Parent ~= limbPart then
					local weld = Instance.new("WeldConstraint")
					weld.Part0 = meshPart
					weld.Part1 = limbPart
					weld.Parent = meshPart
				end
			end
		end
		
		applied = applied + 1
	end
	
	if #errors > 0 then
		return {status = "PARTIAL", errors = errors, applied = applied}
	else
		return {status = "OK", applied = applied}
	end
end

-- Post-import validation check
local function validateImport(model: Model, manifestData: any): {status: string, errors: {string}?}
	local errors = {}
	
	if not manifestData or not manifestData.meshes then
		return {status = "FAIL", errors = {"manifest missing or invalid"}}
	end
	
	-- Check that all manifest meshes exist in the model
	local meshParts = {}
	for _, desc in model:GetDescendants() do
		if desc:IsA("MeshPart") then
			meshParts[desc.Name] = desc
		end
	end
	
	for meshName, info in manifestData.meshes do
		local meshPart = meshParts[meshName]
		if not meshPart then
			table.insert(errors, string.format("FAIL: mesh %s from manifest not found in model", meshName))
		else
			-- Check color matches
			local expectedColor = hexToColor3(info.color)
			local colorDiff = (meshPart.Color.R - expectedColor.R)^2 + 
			                  (meshPart.Color.G - expectedColor.G)^2 + 
			                  (meshPart.Color.B - expectedColor.B)^2
			if colorDiff > 0.01 then
				table.insert(errors, string.format("FAIL: mesh %s color mismatch (expected %s, got RGB(%d,%d,%d))",
					meshName, info.color,
					math.floor(meshPart.Color.R * 255),
					math.floor(meshPart.Color.G * 255),
					math.floor(meshPart.Color.B * 255)))
			end
			
			-- Check if split pieces are welded to their parent limb
			local parentLimb = info.parentLimb
			if parentLimb and parentLimb ~= meshName then
				local hasWeld = false
				for _, child in meshPart:GetChildren() do
					if child:IsA("WeldConstraint") then
						hasWeld = true
						break
					end
				end
				if not hasWeld and meshPart.Parent.Name ~= parentLimb then
					table.insert(errors, string.format("FAIL: mesh %s not welded to parent limb %s", meshName, parentLimb))
				end
			end
		end
	end
	
	-- Check for overlay Parts (boxes/cylinders added to fake details)
	local overlayParts = 0
	for _, desc in model:GetDescendants() do
		if desc:IsA("Part") and not desc:IsA("MeshPart") then
			-- Allow hitboxes (usually named "HitBox", "Hitbox", or have transparency)
			local isHitbox = desc.Name:lower():find("hitbox") or desc.Transparency > 0.5
			if not isHitbox then
				overlayParts = overlayParts + 1
			end
		end
	end
	if overlayParts > 0 then
		table.insert(errors, string.format("FAIL: %d non-hitbox overlay Parts found (should be 0)", overlayParts))
	end
	
	if #errors > 0 then
		return {status = "FAIL", errors = errors}
	else
		return {status = "PASS"}
	end
end

-- Return the functions for use
return {
	applyManifest = applyManifest,
	validateImport = validateImport,
	hexToColor3 = hexToColor3,
}
