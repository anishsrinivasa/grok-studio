--!strict
--[[
	GuardedAnimationLoader: Safe animation loading with fallback
	
	Prevents silent animation failures by:
	- Waiting for track.Length > 0 with timeout
	- Retrying on failure
	- Warning once per clip
	- Treating zero-length as missing (use fallback)
	
	Usage:
		local loader = GuardedAnimationLoader.new(humanoid.Animator)
		local track = loader:LoadAnimationSafe(animationId, "BlasterFire")
		if track then
			track:Play()
		else
			-- Use tween/procedural fallback
			applyRecoilFallback()
		end
]]

local GuardedAnimationLoader = {}
GuardedAnimationLoader.__index = GuardedAnimationLoader

local LOAD_TIMEOUT = 3  -- seconds to wait for Length > 0
local RETRY_COUNT = 2
local warned = {}  -- Track warned clips to warn only once

function GuardedAnimationLoader.new(animator: Animator)
	local self = setmetatable({}, GuardedAnimationLoader)
	self.animator = animator
	self.loadedTracks = {}  -- Cache tracks by animation ID
	return self
end

function GuardedAnimationLoader:LoadAnimationSafe(animationId: string, clipName: string): AnimationTrack?
	-- Check cache first
	if self.loadedTracks[animationId] then
		local track = self.loadedTracks[animationId]
		if track.Length > 0 then
			return track
		end
	end
	
	-- Create Animation instance
	local animation = Instance.new("Animation")
	animation.AnimationId = animationId
	
	-- Try loading with retries
	for attempt = 1, RETRY_COUNT do
		local success, track = pcall(function()
			return self.animator:LoadAnimation(animation)
		end)
		
		if success and track then
			-- Wait for Length > 0
			local startTime = os.clock()
			while track.Length <= 0 and (os.clock() - startTime) < LOAD_TIMEOUT do
				task.wait(0.1)
			end
			
			if track.Length > 0 then
				-- Success!
				self.loadedTracks[animationId] = track
				animation:Destroy()
				return track
			elseif attempt < RETRY_COUNT then
				-- Retry: destroy and reload
				track:Destroy()
				task.wait(0.5)
			else
				-- Final attempt failed
				track:Destroy()
			end
		end
	end
	
	-- Failed to load
	animation:Destroy()
	if not warned[clipName] then
		warned[clipName] = true
		warn(string.format(
			"[AnimationLoader] Failed to load '%s' (%s) after %d attempts - using fallback",
			clipName, animationId, RETRY_COUNT
		))
	end
	return nil
end

function GuardedAnimationLoader:PreloadAnimations(animationIds: {[string]: string})
	-- Preload all animations at init
	for name, id in pairs(animationIds) do
		self:LoadAnimationSafe(id, name)
	end
end

function GuardedAnimationLoader:GetTrack(animationId: string): AnimationTrack?
	return self.loadedTracks[animationId]
end

return GuardedAnimationLoader
