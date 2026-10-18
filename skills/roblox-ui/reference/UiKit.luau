--!strict
-- UiKit: tiny declarative helpers for building Roblox UI from Luau executed in Studio
-- (execute_luau, datamodel_type "Edit"). Paste this at the top of a builder script, then
-- describe screens with make(). Everything is scale-based for mobile.

local StarterGui = game:GetService("StarterGui")

type Props = { [string]: any }

local function make(className: string, props: Props?, children: { Instance }?): Instance
	local inst = Instance.new(className :: any)
	local p: Props = props or {}
	for k, v in p do
		if k ~= "Parent" then
			(inst :: any)[k] = v
		end
	end
	local kids: { Instance } = children or {}
	for _, child in kids do
		child.Parent = inst
	end
	if props and props.Parent then
		inst.Parent = props.Parent
	end
	return inst
end

local function hex(h: string): Color3
	return Color3.fromHex(h)
end

local function corner(px: number): Instance
	return make("UICorner", { CornerRadius = UDim.new(0, px) })
end

local function stroke(px: number, color: Color3): Instance
	return make("UIStroke", { Thickness = px, Color = color, ApplyStrokeMode = Enum.ApplyStrokeMode.Border })
end

local function padding(scale: number): Instance
	local u = UDim.new(scale, 0)
	return make("UIPadding", { PaddingTop = u, PaddingBottom = u, PaddingLeft = u, PaddingRight = u })
end

-- Recreate a ScreenGui idempotently (safe to re-run the builder).
local function screen(name: string): ScreenGui
	local old = StarterGui:FindFirstChild(name)
	if old then
		old:Destroy()
	end
	return make("ScreenGui", {
		Name = name,
		ResetOnSpawn = false,
		IgnoreGuiInset = false, -- keep clear of the top bar
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = StarterGui,
	}) :: ScreenGui
end

-- Example: HUD coin counter (top-left), built from the spec's style guide.
local palette = { surface = hex("#1E1B2E"), text = hex("#FFFFFF"), accent = hex("#FFD23F") }

local hud = screen("Hud")
make("Frame", {
	Name = "CoinCounter",
	AnchorPoint = Vector2.new(0, 0),
	Position = UDim2.fromScale(0.02, 0.03),
	Size = UDim2.fromScale(0.18, 0.08),
	BackgroundColor3 = palette.surface,
	BackgroundTransparency = 0.15,
	Parent = hud,
}, {
	corner(12),
	stroke(2, palette.accent),
	padding(0.08),
	make("UIAspectRatioConstraint", { AspectRatio = 3, DominantAxis = Enum.DominantAxis.Height }),
	make("UISizeConstraint", { MinSize = Vector2.new(120, 40) }),
	make("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		VerticalAlignment = Enum.VerticalAlignment.Center,
		Padding = UDim.new(0.05, 0),
		SortOrder = Enum.SortOrder.LayoutOrder,
	}),
	make("ImageLabel", {
		Name = "Icon",
		LayoutOrder = 1,
		Size = UDim2.fromScale(1, 1),
		SizeConstraint = Enum.SizeConstraint.RelativeYY,
		BackgroundTransparency = 1,
		Image = "", -- set to rbxassetid://<id> once the icon is uploaded
	}),
	make("TextLabel", {
		Name = "Amount",
		LayoutOrder = 2,
		Size = UDim2.fromScale(0.6, 1),
		BackgroundTransparency = 1,
		Text = "0",
		TextScaled = true,
		FontFace = Font.fromName("BuilderSans", Enum.FontWeight.Bold),
		TextColor3 = palette.text,
		TextXAlignment = Enum.TextXAlignment.Left,
	}, {
		make("UITextSizeConstraint", { MaxTextSize = 48, MinTextSize = 14 }),
	}),
})

return "built Hud"
