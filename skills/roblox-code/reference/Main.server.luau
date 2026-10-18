--!strict
-- ServerScriptService.Server.Main (Script)
-- Server bootstrap: require every service, then start them in dependency order.
-- Services are ModuleScripts under ServerScriptService.Server.Services that return a table
-- with an optional start() function.

local ServerScriptService = game:GetService("ServerScriptService")

local Services = ServerScriptService:WaitForChild("Server"):WaitForChild("Services")

-- Order matters: data first, then systems that read it. Mirror game-spec.json dependsOn.
local ORDER = { "DataService", "CoinService", "StageService" }

local started: { [string]: boolean } = {}
for _, name in ORDER do
	local module = Services:FindFirstChild(name)
	if module and module:IsA("ModuleScript") then
		local ok, err = pcall(function()
			local service = require(module) :: any
			if type(service.start) == "function" then
				service.start()
			end
		end)
		if ok then
			started[name] = true
		else
			warn(`[Main] {name} failed to start: {err}`)
		end
	else
		warn(`[Main] Missing service module: {name}`)
	end
end

print(`[Main] Server started: {table.concat(ORDER, ", ")}`)
