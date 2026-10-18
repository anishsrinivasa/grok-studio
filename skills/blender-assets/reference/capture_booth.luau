--!strict
--[[
capture_booth.luau - grok-studio (Builder): a clean Studio shot to compare with the Blender render.

MODE "setup": clones the model at MODEL_PATH into Workspace._GS_CaptureBooth far above the map
(pivot at BOOTH_ORIGIN, unrotated, shadows off) in front of a flat backdrop, and returns the
screen_capture arguments:
  {"camera_position": [x,y,z], "look_at_position": [x,y,z], "fieldOfView": n, ...}
MODE "cleanup": removes the booth. Always run it after the capture.

Usage: execute_luau with datamodel_type "Edit". Fill in:
  MODEL_PATH   dot path from game, e.g. "Workspace.lava_rock" (after apply_manifest.luau)
  CAMERA_JSON  the "studio" object returned by compare_images.render_compare
  BACKDROP     the "backdrop" hex it returned (a colour far from every part colour)
Then call screen_capture with camera_position / look_at_position, save the image, run
compare_images, and run this again with MODE = "cleanup".
If the returned fieldOfView differs from CAMERA_JSON's, re-render in Blender with fov=<it>.
The booth lives in Workspace, the Builder's subtree; the original model is not touched.
]]

local MODEL_PATH = "Workspace.Model"
local MODE = "setup" -- or "cleanup"
local CAMERA_JSON = [==[
{"view": "front", "fieldOfView": 70, "position": [0, 2, 8], "lookAt": [0, 2, 0]}
]==]
local BACKDROP = "#FF00FF"
local BOOTH_ORIGIN = Vector3.new(0, 4000, 0)
local BOOTH_NAME = "_GS_CaptureBooth"

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

local function cleanup(): { [string]: any }
	local booth = workspace:FindFirstChild(BOOTH_NAME)
	if booth then
		booth:Destroy()
	end
	return { removed = booth ~= nil }
end

local function setup(): { [string]: any }
	cleanup()
	local found = resolve(MODEL_PATH)
	if found == nil or not found:IsA("Model") then
		return { ok = false, error = `no Model at {MODEL_PATH}` }
	end
	local cam = HttpService:JSONDecode(CAMERA_JSON)

	local booth = Instance.new("Folder")
	booth.Name = BOOTH_NAME
	local clone = (found :: Model):Clone()
	for _, d in clone:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
			d.CastShadow = false
		elseif d:IsA("LuaSourceContainer") then
			d:Destroy()
		end
	end
	clone.Parent = booth
	clone:PivotTo(CFrame.new(BOOTH_ORIGIN))

	local position = BOOTH_ORIGIN + Vector3.new(cam.position[1], cam.position[2], cam.position[3])
	local lookAt = BOOTH_ORIGIN + Vector3.new(cam.lookAt[1], cam.lookAt[2], cam.lookAt[3])
	local toCamera = position - lookAt
	local dist = toCamera.Magnitude
	local dir = toCamera.Unit

	-- Backdrop: a flat plate behind the model, facing the camera, big enough to fill the view.
	local _, extents = clone:GetBoundingBox()
	local behind = extents.Magnitude + 2
	local fov = workspace.CurrentCamera and workspace.CurrentCamera.FieldOfView or cam.fieldOfView
	local side = math.min(2048, 2 * (dist + behind) * math.tan(math.rad(fov) / 2) * 4)
	local backdrop = Instance.new("Part")
	backdrop.Name = "_Backdrop"
	backdrop.Anchored = true
	backdrop.CanCollide = false
	backdrop.CanQuery = false
	backdrop.CanTouch = false
	backdrop.CastShadow = false
	backdrop.Material = Enum.Material.SmoothPlastic
	backdrop.Color = Color3.fromHex(BACKDROP)
	backdrop.Size = Vector3.new(side, side, 0.2)
	local centre = lookAt - dir * behind
	backdrop.CFrame = CFrame.lookAt(centre, centre + dir)
	backdrop.Parent = booth
	booth.Parent = workspace

	local viewport = workspace.CurrentCamera and workspace.CurrentCamera.ViewportSize or Vector2.zero
	return {
		ok = true,
		camera_position = { position.X, position.Y, position.Z },
		look_at_position = { lookAt.X, lookAt.Y, lookAt.Z },
		fieldOfView = fov,
		expectedFieldOfView = cam.fieldOfView,
		fovMatches = math.abs(fov - cam.fieldOfView) < 0.5,
		viewport = { viewport.X, viewport.Y },
		backdrop = BACKDROP,
		booth = booth:GetFullName(),
	}
end

return HttpService:JSONEncode(if MODE == "cleanup" then cleanup() else setup())
