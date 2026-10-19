--!strict
--[[
find_asset_refs.luau - grok-studio: where is an asset id used in this place? Read-only.

Usage: execute_luau (Edit, or Server / Client during a play test) with ASSET_ID set. It reads
EVERY property of every instance (through ReflectionService, so no property list to keep up
to date), every attribute and every script's source, and returns JSON:
  {"assetId": "...", "scanned": n, "hits": ["Workspace.X [Decal].Texture=rbxassetid://..."], "errs": []}

An empty "hits" in Edit, Server and Client means the place doesn't reference the id: a console
line such as "ContentId: rbxassetid://<id> failed due to: Asset type does not match requested
type" then comes from a Studio plugin or Roblox itself, not from the game (seen live, Oct 2026:
203785492, an Audio asset "Pop Close Sound", loaded at play start by something outside the
place).
]]
local ASSET_ID = "203785492"

local ReflectionService = game:GetService("ReflectionService")
local cache: { [string]: { string } } = {}
local function propsOf(className: string): { string }
	local names = cache[className]
	if names then
		return names
	end
	names = {}
	local ok, list = pcall(function()
		return (ReflectionService :: any):GetPropertiesOfClass(className)
	end)
	if ok and list then
		for _, p in list do
			table.insert(names, p.Name)
		end
	end
	cache[className] = names
	return names
end

local hits: { string } = {}
local errs: { string } = {}
local scanned = 0
local function check(inst: Instance)
	scanned += 1
	for _, prop in propsOf(inst.ClassName) do
		local ok, v = pcall(function()
			return (inst :: any)[prop]
		end)
		if ok and v ~= nil then
			local t = typeof(v)
			local s: string? = nil
			if t == "string" or t == "number" then
				s = tostring(v)
			elseif t == "Content" then
				local ok2, uri = pcall(function()
					return (v :: any).Uri
				end)
				s = if ok2 then tostring(uri) else tostring(v)
			end
			if s and string.find(s, ASSET_ID, 1, true) then
				table.insert(hits, `{inst:GetFullName()} [{inst.ClassName}].{prop}={s}`)
			end
		end
	end
	if inst:IsA("LuaSourceContainer") then
		local ok, src = pcall(function()
			return (inst :: any).Source
		end)
		if ok and type(src) == "string" and string.find(src, ASSET_ID, 1, true) then
			table.insert(hits, `{inst:GetFullName()} [{inst.ClassName}] source`)
		end
	end
	for name, value in inst:GetAttributes() do
		if string.find(tostring(value), ASSET_ID, 1, true) then
			table.insert(hits, `{inst:GetFullName()} attribute {name}={tostring(value)}`)
		end
	end
end

for _, service in game:GetChildren() do
	local ok, e = pcall(function()
		check(service)
		for i, d in service:GetDescendants() do
			check(d)
			if i % 2000 == 0 then
				task.wait()
			end
		end
	end)
	if not ok then
		table.insert(errs, `{service.Name}: {e}`)
	end
end
return game:GetService("HttpService"):JSONEncode({ assetId = ASSET_ID, scanned = scanned, hits = hits, errs = errs })
