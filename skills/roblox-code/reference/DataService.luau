--!strict
-- ServerScriptService.Server.Services.DataService
-- Minimal, safe player persistence: load with retries, autosave, save on leave and on
-- shutdown, never overwrite good data with defaults after a failed load.
-- For production-scale games consider a battle-tested library (e.g. ProfileStore) - this
-- module is intentionally small so an agent can read and adapt it.

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local STORE_NAME = "Game_PlayerData_v1" -- set from game-spec.json progression.persistence.dataStoreName
local MAX_ATTEMPTS = 5
local AUTOSAVE_SECONDS = 120

export type Profile = {
	schemaVersion: number,
	coins: number,
	unlocked: { [string]: boolean },
}

local TEMPLATE: Profile = {
	schemaVersion = 1,
	coins = 0,
	unlocked = {},
}

local DataService = {}

local profiles: { [Player]: Profile } = {}
local loadedOk: { [Player]: boolean } = {}

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(STORE_NAME)
	end)
	if ok then
		store = result
	else
		-- Happens in Studio when "Enable Studio Access to API Services" is off.
		warn(`[DataService] DataStores unavailable, running without persistence: {result}`)
	end
end

local function deepCopy<T>(value: T): T
	if type(value) ~= "table" then
		return value
	end
	local out = {}
	for k, v in value :: any do
		out[k] = deepCopy(v)
	end
	return (out :: any) :: T
end

local function reconcile(data: any): Profile
	local profile = deepCopy(TEMPLATE) :: any
	if type(data) == "table" then
		for k, v in data do
			profile[k] = v
		end
	end
	-- Migrations go here: if profile.schemaVersion < N then ... end
	return profile :: Profile
end

local function withRetries<T>(label: string, fn: () -> T): (boolean, T?)
	for attempt = 1, MAX_ATTEMPTS do
		local ok, result = pcall(fn)
		if ok then
			return true, result
		end
		warn(`[DataService] {label} failed (attempt {attempt}/{MAX_ATTEMPTS}): {result}`)
		task.wait(math.min(2 ^ attempt, 16))
	end
	return false, nil
end

local function keyFor(player: Player): string
	return `player_{player.UserId}`
end

function DataService.get(player: Player): Profile?
	return profiles[player]
end

function DataService.waitFor(player: Player, timeout: number?): Profile?
	local deadline = os.clock() + (timeout or 15)
	while not profiles[player] and player.Parent and os.clock() < deadline do
		task.wait(0.1)
	end
	return profiles[player]
end

local function load(player: Player)
	if not store then
		profiles[player] = deepCopy(TEMPLATE)
		loadedOk[player] = false -- never save: we don't know the real data
		return
	end
	local ds = store :: DataStore
	local ok, data = withRetries("load", function()
		return ds:GetAsync(keyFor(player))
	end)
	if not player.Parent then
		return
	end
	profiles[player] = reconcile(if ok then data else nil)
	loadedOk[player] = ok
	if not ok then
		warn(`[DataService] Could not load data for {player.Name}; progress this session will NOT be saved.`)
	end
end

local function save(player: Player)
	local profile = profiles[player]
	if not store or not profile or not loadedOk[player] then
		return
	end
	local ds = store :: DataStore
	withRetries("save", function()
		ds:UpdateAsync(keyFor(player), function(_old)
			return profile
		end)
		return true
	end)
end

function DataService.start()
	Players.PlayerAdded:Connect(load)
	for _, p in Players:GetPlayers() do
		task.spawn(load, p)
	end
	Players.PlayerRemoving:Connect(function(player)
		save(player)
		profiles[player] = nil
		loadedOk[player] = nil
	end)
	task.spawn(function()
		while true do
			task.wait(AUTOSAVE_SECONDS)
			for player in profiles do
				task.spawn(save, player)
			end
		end
	end)
	game:BindToClose(function()
		if RunService:IsStudio() and not store then
			return
		end
		local pending = 0
		for player in profiles do
			pending += 1
			task.spawn(function()
				save(player)
				pending -= 1
			end)
		end
		local deadline = os.clock() + 25
		while pending > 0 and os.clock() < deadline do
			task.wait(0.1)
		end
	end)
end

return DataService
