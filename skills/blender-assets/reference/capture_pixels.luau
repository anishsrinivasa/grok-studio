--!strict
--[[
capture_pixels.luau - grok-studio (Builder): the Gate D capture as data, for clients whose
screen_capture result can't be saved as a file (seen live, Oct 2026: a Grok Bot subagent got
"Saved this image to disk at file:///home/box/agent-data/.../assets/<hash>.jpg" but no such
file existed on the box).

Usage: execute_luau (Edit), after capture_booth.luau "setup", with CAM_POS / LOOK_AT = its
camera_position / look_at_position. It aims the edit camera there for one frame, takes a
CaptureService screenshot, restores the camera, reads the pixels through an EditableImage and
returns "GSPIX <w> <h> <outW> <outH> <base64 RGB>". Save the tool result to a file (MCP
write_to_file) and run:  python3 decode_capture.py <result.txt> renders/<id>_capture_<view>.png
OUT_W 192 keeps the result under ~85 KB (larger results get truncated by the MCP client).
Changes nothing in the place (the camera is put back).
]]
local CAM_POS = Vector3.new(0, 4002, 8)
local LOOK_AT = Vector3.new(0, 4001, 0)
local OUT_W = 192

local cam = workspace.CurrentCamera
local saved, savedFocus = cam.CFrame, cam.Focus
cam.CFrame = CFrame.lookAt(CAM_POS, LOOK_AT)
cam.Focus = CFrame.new(LOOK_AT)
task.wait(0.3)
local got: string? = nil
game:GetService("CaptureService"):CaptureScreenshot(function(id: string) got = id end)
local t = 0
while got == nil and t < 5 do task.wait(0.1); t += 0.1 end
cam.CFrame, cam.Focus = saved, savedFocus
assert(got, "no screenshot")
local img = game:GetService("AssetService"):CreateEditableImageAsync(Content.fromUri(got :: string))
local W, H = img.Size.X, img.Size.Y
local px = img:ReadPixelsBuffer(Vector2.zero, img.Size) -- RGBA8
local ow = OUT_W
local oh = math.floor(H * ow / W + 0.5)
local out = buffer.create(ow * oh * 3)
local k = 0
for y = 0, oh - 1 do
	local sy = math.floor((y + 0.5) * H / oh)
	for x = 0, ow - 1 do
		local sx = math.floor((x + 0.5) * W / ow)
		local i = (sy * W + sx) * 4
		buffer.writeu8(out, k, buffer.readu8(px, i)); buffer.writeu8(out, k + 1, buffer.readu8(px, i + 1)); buffer.writeu8(out, k + 2, buffer.readu8(px, i + 2))
		k += 3
	end
	if y % 64 == 0 then task.wait() end
end
img:Destroy()
local A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local chars = {}
for i = 1, 64 do chars[i - 1] = string.sub(A, i, i) end
local parts = {}
local n = buffer.len(out)
for i = 0, n - 1, 3 do
	local b0 = buffer.readu8(out, i)
	local b1 = if i + 1 < n then buffer.readu8(out, i + 1) else 0
	local b2 = if i + 2 < n then buffer.readu8(out, i + 2) else 0
	local v = b0 * 65536 + b1 * 256 + b2
	parts[#parts + 1] = chars[bit32.rshift(v, 18)] .. chars[bit32.band(bit32.rshift(v, 12), 63)] .. chars[bit32.band(bit32.rshift(v, 6), 63)] .. chars[bit32.band(v, 63)]
end
return string.format("GSPIX %d %d %d %d ", W, H, ow, oh) .. table.concat(parts)
