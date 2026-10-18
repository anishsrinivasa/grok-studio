--!strict
-- PenpotUIVerifier: Verifies a built ScreenGui matches its spec
-- Usage: Load in execute_luau (datamodel_type "Edit"), then call verifyScreen(screenName, specJson)

local HttpService = game:GetService("HttpService")
local StarterGui = game:GetService("StarterGui")

type VerifyResult = {
	passed: boolean,
	checks: number,
	failures: { string }
}

local TOLERANCE = 0.01 -- Allow 1% position/size variance

local function colorMatch(c1: Color3, c2: Color3): boolean
	return math.abs(c1.R - c2.R) < 0.02 
		and math.abs(c1.G - c2.G) < 0.02 
		and math.abs(c1.B - c2.B) < 0.02
end

local function numberMatch(n1: number, n2: number, tolerance: number?): boolean
	local tol = tolerance or TOLERANCE
	return math.abs(n1 - n2) < tol
end

local function verifyElement(inst: Instance, element: any, failures: { string }, checks: { number })
	checks[1] = checks[1] + 1
	
	-- Name
	if inst.Name ~= element.name then
		table.insert(failures, string.format("Name mismatch: expected '%s', got '%s'", element.name, inst.Name))
		return
	end
	
	-- Type
	if inst.ClassName ~= element.type then
		table.insert(failures, string.format("%s: Type mismatch: expected '%s', got '%s'", 
			element.name, element.type, inst.ClassName))
		return
	end
	
	local guiObj = inst :: GuiObject
	
	-- Position (scale)
	local pos = guiObj.Position
	if not numberMatch(pos.X.Scale, element.position.scaleX) or
	   not numberMatch(pos.Y.Scale, element.position.scaleY) then
		table.insert(failures, string.format("%s: Position mismatch: expected (%.3f, %.3f), got (%.3f, %.3f)",
			element.name, element.position.scaleX, element.position.scaleY, pos.X.Scale, pos.Y.Scale))
	end
	
	-- Size (scale)
	local size = guiObj.Size
	if not numberMatch(size.X.Scale, element.size.scaleX) or
	   not numberMatch(size.Y.Scale, element.size.scaleY) then
		table.insert(failures, string.format("%s: Size mismatch: expected (%.3f, %.3f), got (%.3f, %.3f)",
			element.name, element.size.scaleX, element.size.scaleY, size.X.Scale, size.Y.Scale))
	end
	
	-- Background color
	if element.backgroundColor then
		local expectedColor = Color3.new(
			element.backgroundColor.r,
			element.backgroundColor.g,
			element.backgroundColor.b
		)
		if not colorMatch(guiObj.BackgroundColor3, expectedColor) then
			table.insert(failures, string.format("%s: Background color mismatch", element.name))
		end
	end
	
	-- Text (if applicable)
	if element.text and (guiObj:IsA("TextLabel") or guiObj:IsA("TextButton")) then
		local textObj = guiObj :: TextLabel
		if textObj.Text ~= element.text then
			table.insert(failures, string.format("%s: Text mismatch: expected '%s', got '%s'",
				element.name, element.text, textObj.Text))
		end
		
		if element.textColor then
			local expectedColor = Color3.new(
				element.textColor.r,
				element.textColor.g,
				element.textColor.b
			)
			if not colorMatch(textObj.TextColor3, expectedColor) then
				table.insert(failures, string.format("%s: Text color mismatch", element.name))
			end
		end
	end
	
	-- Children count
	if element.children then
		local childCount = 0
		for _, child in inst:GetChildren() do
			if child:IsA("GuiObject") then
				childCount = childCount + 1
			end
		end
		
		if childCount ~= #element.children then
			table.insert(failures, string.format("%s: Child count mismatch: expected %d, got %d",
				element.name, #element.children, childCount))
		else
			-- Recursively verify children
			for _, childElement in element.children do
				local childInst = inst:FindFirstChild(childElement.name)
				if childInst then
					verifyElement(childInst, childElement, failures, checks)
				else
					table.insert(failures, string.format("%s: Child '%s' not found",
						element.name, childElement.name))
				end
			end
		end
	end
	
	-- Check for off-screen elements (within parent bounds or screen)
	local absPos = guiObj.AbsolutePosition
	local absSize = guiObj.AbsoluteSize
	
	if absPos.X + absSize.X < 0 or absPos.Y + absSize.Y < 0 then
		table.insert(failures, string.format("%s: Element is off-screen (negative position)", element.name))
	end
end

local function verifyScreen(screenName: string, specJson: string): VerifyResult
	local spec = HttpService:JSONDecode(specJson) :: any
	local screen = StarterGui:FindFirstChild(screenName) :: ScreenGui?
	
	local failures: { string } = {}
	local checks = { 0 }
	
	if not screen then
		table.insert(failures, string.format("ScreenGui '%s' not found in StarterGui", screenName))
		return { passed = false, checks = 0, failures = failures }
	end
	
	-- Verify all top-level elements
	for _, element in spec.elements do
		local inst = screen:FindFirstChild(element.name)
		if inst then
			verifyElement(inst, element, failures, checks)
		else
			table.insert(failures, string.format("Element '%s' not found in ScreenGui", element.name))
		end
	end
	
	local passed = #failures == 0
	return { passed = passed, checks = checks[1], failures = failures }
end

-- Run verification and print results
local function runVerification(screenName: string, specJson: string)
	print("=== Verifying " .. screenName .. " ===")
	local result = verifyScreen(screenName, specJson)
	
	print(string.format("Checks: %d", result.checks))
	
	if result.passed then
		print("PASS: All checks passed")
	else
		print(string.format("FAIL: %d failures", #result.failures))
		for _, failure in result.failures do
			print("  - " .. failure)
		end
	end
	
	return result.passed
end

return {
	verifyScreen = verifyScreen,
	runVerification = runVerification
}
