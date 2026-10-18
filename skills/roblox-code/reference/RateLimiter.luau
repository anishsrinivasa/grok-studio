--!strict
-- ServerScriptService.Server.Util.RateLimiter
-- Token bucket per player per key. Use on every client->server remote.

local Players = game:GetService("Players")

export type RateLimiter = {
	allow: (self: RateLimiter, player: Player) -> boolean,
}

local RateLimiter = {}
RateLimiter.__index = RateLimiter

type State = { tokens: number, last: number }

function RateLimiter.new(perSecond: number, burst: number?): RateLimiter
	local self = setmetatable({}, RateLimiter)
	self._rate = perSecond
	self._burst = burst or math.max(1, math.ceil(perSecond))
	self._state = {} :: { [Player]: State }
	Players.PlayerRemoving:Connect(function(player)
		self._state[player] = nil
	end)
	return (self :: any) :: RateLimiter
end

function RateLimiter.allow(self: any, player: Player): boolean
	local now = os.clock()
	local s: State? = self._state[player]
	if not s then
		s = { tokens = self._burst, last = now }
		self._state[player] = s
	end
	local st = s :: State
	st.tokens = math.min(self._burst, st.tokens + (now - st.last) * self._rate)
	st.last = now
	if st.tokens >= 1 then
		st.tokens -= 1
		return true
	end
	return false
end

return RateLimiter
