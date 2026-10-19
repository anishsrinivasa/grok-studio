--!strict
--[[
	Acceptance Test Framework: Generic, extensible acceptance checks driven by game-spec.json
	
	Principles:
	- Every interaction must work through real player input
	- Spec numbers must match runtime measurements
	- Every attached element is verified on the rig
	- Every DONE claim is backed by machine-checkable artifacts
	- Never assume a load succeeded; verify, timeout, fallback, warn
	
	Usage:
		local framework = AcceptanceFramework.new(gameSpec)
		framework:RegisterCheck("animations", CheckAnimationsLoad)
		framework:RegisterCheck("interactions", CheckInteractionsReachable)
		framework:RegisterCheck("tunables", CheckTunablesMatch)
		framework:RunAll()
]]

local AcceptanceFramework = {}
AcceptanceFramework.__index = AcceptanceFramework

export type TestResult = {
	id: string,
	description: string,
	status: "pass" | "fail" | "skip",
	expected: string?,
	actual: string?,
	evidence: string?
}

export type AcceptanceCheck = (spec: any, context: any) -> TestResult

function AcceptanceFramework.new(gameSpec: any)
	local self = setmetatable({}, AcceptanceFramework)
	self.gameSpec = gameSpec
	self.checks = {} :: {[string]: AcceptanceCheck}
	self.results = {} :: {TestResult}
	return self
end

function AcceptanceFramework:RegisterCheck(checkId: string, checkFn: AcceptanceCheck)
	self.checks[checkId] = checkFn
end

function AcceptanceFramework:RunAll(context: any?): {TestResult}
	self.results = {}
	
	for checkId, checkFn in pairs(self.checks) do
		local success, result = pcall(checkFn, self.gameSpec, context or {})
		if success then
			table.insert(self.results, result)
		else
			table.insert(self.results, {
				id = checkId,
				description = checkId,
				status = "fail",
				expected = "check to complete",
				actual = "error: " .. tostring(result)
			})
		end
	end
	
	return self.results
end

function AcceptanceFramework:GetSummary(): {passed: number, failed: number, skipped: number}
	local passed, failed, skipped = 0, 0, 0
	for _, result in ipairs(self.results) do
		if result.status == "pass" then
			passed += 1
		elseif result.status == "fail" then
			failed += 1
		else
			skipped += 1
		end
	end
	return {passed = passed, failed = failed, skipped = skipped}
end

--[[
	Generic Check: Asset Loading
	Verifies that every declared asset (animations, sounds, meshes, images) actually loaded
]]
function AcceptanceFramework.CheckAssetLoading(spec: any, context: any): TestResult
	local failures = {}
	
	-- Check animations
	for _, anim in ipairs(spec.animations or {}) do
		if anim.assetId and context.animator then
			local animation = Instance.new("Animation")
			animation.AnimationId = anim.assetId
			
			local success, track = pcall(function()
				return context.animator:LoadAnimation(animation)
			end)
			
			if not success or not track or track.Length <= 0 then
				table.insert(failures, string.format(
					"Animation '%s' (%s) failed to load or has Length=0",
					anim.name, anim.assetId
				))
			else
				track:Destroy()
			end
			
			animation:Destroy()
		end
	end
	
	-- Check sounds
	for _, audio in ipairs(spec.audio or {}) do
		if audio.assetId and context.soundService then
			local sound = Instance.new("Sound")
			sound.SoundId = audio.assetId
			sound.Parent = context.soundService
			
			task.wait(0.5)  -- Brief wait for load
			
			if not sound.IsLoaded then
				table.insert(failures, string.format(
					"Sound '%s' (%s) failed to load",
					audio.id, audio.assetId
				))
			end
			
			sound:Destroy()
		end
	end
	
	if #failures > 0 then
		return {
			id = "asset_loading",
			description = "All declared assets load successfully",
			status = "fail",
			expected = "All assets loaded",
			actual = table.concat(failures, "; ")
		}
	end
	
	return {
		id = "asset_loading",
		description = "All declared assets load successfully",
		status = "pass"
	}
end

--[[
	Generic Check: Interactions Reachable
	Verifies every interactive element works through real player input
]]
function AcceptanceFramework.CheckInteractionsReachable(spec: any, context: any): TestResult
	local failures = {}
	local CollectionService = game:GetService("CollectionService")
	
	-- Get all interaction types from mechanics
	local interactionTags = {}
	for _, mechanic in ipairs(spec.mechanics or {}) do
		-- Extract tags that imply interaction (heuristic: contains "pickup", "button", "trigger", "zone", etc.)
		if mechanic.id:match("pickup") or mechanic.id:match("button") or 
		   mechanic.id:match("trigger") or mechanic.id:match("zone") then
			table.insert(interactionTags, mechanic.id)
		end
	end
	
	-- Check each interaction type
	for _, tag in ipairs(interactionTags) do
		local objects = CollectionService:GetTagged(tag)
		for _, obj in ipairs(objects) do
			-- Test reachability based on interaction type
			if obj:IsA("BasePart") then
				-- Raycast test: can a camera ray reach this from expected angles?
				local testOrigins = {
					obj.Position + Vector3.new(0, 5, 5),  -- Above and in front
					obj.Position + Vector3.new(5, 0, 0),  -- Side
					obj.Position + Vector3.new(0, 0, 5)   -- Front
				}
				
				local reachable = false
				for _, origin in ipairs(testOrigins) do
					local direction = (obj.Position - origin).Unit * 100
					local raycastParams = RaycastParams.new()
					raycastParams.FilterType = Enum.RaycastFilterType.Blacklist
					raycastParams.FilterDescendantsInstances = {context.character}
					
					local result = workspace:Raycast(origin, direction, raycastParams)
					if result and result.Instance:IsDescendantOf(obj) then
						reachable = true
						break
					end
				end
				
				if not reachable then
					table.insert(failures, string.format(
						"'%s' tagged '%s' not reachable via raycast from expected angles",
						obj:GetFullName(), tag
					))
				end
			end
		end
	end
	
	if #failures > 0 then
		return {
			id = "interactions_reachable",
			description = "All interactions work through real player input",
			status = "fail",
			expected = "All tagged elements reachable",
			actual = table.concat(failures, "; "),
			evidence = "Check CanQuery, CanTouch, collision settings on decorative geometry"
		}
	end
	
	return {
		id = "interactions_reachable",
		description = "All interactions work through real player input",
		status = "pass"
	}
end

--[[
	Generic Check: Spec Tunables Match Runtime
	Measures runtime values and compares to spec targets within tolerance
]]
function AcceptanceFramework.CheckTunablesMatch(spec: any, context: any): TestResult
	local failures = {}
	local TOLERANCE = 0.15  -- 15% tolerance
	
	for _, mechanic in ipairs(spec.mechanics or {}) do
		if mechanic.tunables then
			for tunableName, specValue in pairs(mechanic.tunables) do
				-- Get runtime value from Config or measurement
				local runtimeValue = context.measuredTunables and 
				                    context.measuredTunables[mechanic.id] and 
				                    context.measuredTunables[mechanic.id][tunableName]
				
				if runtimeValue and type(specValue) == "number" then
					local diff = math.abs(runtimeValue - specValue)
					local relativeError = diff / math.max(specValue, 0.001)
					
					if relativeError > TOLERANCE then
						table.insert(failures, string.format(
							"'%s.%s': spec=%.3f, measured=%.3f (%.1f%% error)",
							mechanic.id, tunableName, specValue, runtimeValue, relativeError * 100
						))
					end
				end
			end
		end
	end
	
	if #failures > 0 then
		return {
			id = "tunables_match",
			description = "Spec numbers match runtime measurements",
			status = "fail",
			expected = "All tunables within 15% tolerance",
			actual = table.concat(failures, "; ")
		}
	end
	
	return {
		id = "tunables_match",
		description = "Spec numbers match runtime measurements",
		status = "pass"
	}
end

--[[
	Generic Check: New Player Experience
	Freshly joined player isn't killed/stuck/overwhelmed within grace window
]]
function AcceptanceFramework.CheckNewPlayerExperience(spec: any, context: any): TestResult
	-- Grace window from spec or default
	local graceWindow = spec.progression and spec.progression.newPlayerGraceSeconds or 5
	
	if not context.newPlayerSurvived or not context.newPlayerIdleTime then
		return {
			id = "new_player_experience",
			description = "New player survives idle grace period",
			status = "skip",
			expected = string.format("Survives %.1f seconds idle", graceWindow)
		}
	end
	
	if context.newPlayerIdleTime < graceWindow then
		return {
			id = "new_player_experience",
			description = "New player survives idle grace period",
			status = "fail",
			expected = string.format("Survives %.1f seconds idle", graceWindow),
			actual = string.format("Died/stuck at %.1f seconds", context.newPlayerIdleTime),
			evidence = context.newPlayerFailReason or "unknown"
		}
	end
	
	return {
		id = "new_player_experience",
		description = "New player survives idle grace period",
		status = "pass"
	}
end

--[[
	Generic Check: Rig Attachments
	Everything attached to/held by a character has correct orientation on R15
]]
function AcceptanceFramework.CheckRigAttachments(spec: any, context: any): TestResult
	local failures = {}
	
	if not context.character or not context.character:FindFirstChild("Humanoid") then
		return {
			id = "rig_attachments",
			description = "All character attachments correctly oriented",
			status = "skip"
		}
	end
	
	-- Check tools
	for _, tool in ipairs(context.character:GetChildren()) do
		if tool:IsA("Tool") then
			-- Verify tool points along character's look vector
			local rightHand = context.character:FindFirstChild("RightHand")
			if rightHand then
				-- Get tool forward axis in world space
				local toolCFrame = rightHand.CFrame * tool.Grip
				local toolForward = toolCFrame.LookVector
				local charForward = context.character.PrimaryPart.CFrame.LookVector
				
				local dot = toolForward:Dot(charForward)
				if dot < 0.8 then  -- Should be nearly aligned
					table.insert(failures, string.format(
						"Tool '%s' not aligned with character LookVector (dot=%.2f, expected>0.8)",
						tool.Name, dot
					))
				end
			end
		end
	end
	
	if #failures > 0 then
		return {
			id = "rig_attachments",
			description = "All character attachments correctly oriented",
			status = "fail",
			expected = "Tools aligned with character LookVector",
			actual = table.concat(failures, "; "),
			evidence = "Check Tool.Grip CFrame and R15 attachment points"
		}
	end
	
	return {
		id = "rig_attachments",
		description = "All character attachments correctly oriented",
		status = "pass"
	}
end

return AcceptanceFramework
