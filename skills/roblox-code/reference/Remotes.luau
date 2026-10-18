--!strict
-- ReplicatedStorage.Shared.Remotes
-- Single place that creates (server) or waits for (client) every remote by name.
-- Names must match game-spec.json remotes[].name.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local FOLDER_NAME = "Remotes"
local IS_SERVER = RunService:IsServer()

local folder: Folder
if IS_SERVER then
	local existing = ReplicatedStorage:FindFirstChild(FOLDER_NAME)
	if existing and existing:IsA("Folder") then
		folder = existing
	else
		folder = Instance.new("Folder")
		folder.Name = FOLDER_NAME
		folder.Parent = ReplicatedStorage
	end
else
	folder = ReplicatedStorage:WaitForChild(FOLDER_NAME) :: Folder
end

local Remotes = {}

local function getOrCreate<T>(name: string, className: string): T
	if IS_SERVER then
		local inst: Instance? = folder:FindFirstChild(name)
		if not inst then
			local created: Instance = Instance.new(className :: any)
			created.Name = name
			created.Parent = folder
			inst = created
		end
		return (inst :: any) :: T
	end
	return (folder:WaitForChild(name, 10) :: any) :: T
end

function Remotes.event(name: string): RemoteEvent
	return getOrCreate(name, "RemoteEvent")
end

function Remotes.unreliable(name: string): UnreliableRemoteEvent
	return getOrCreate(name, "UnreliableRemoteEvent")
end

function Remotes.func(name: string): RemoteFunction
	return getOrCreate(name, "RemoteFunction")
end

return Remotes
