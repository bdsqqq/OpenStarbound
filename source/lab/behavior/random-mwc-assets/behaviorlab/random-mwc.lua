-- All values come from one normal Lua userdata; no global RNG is reseeded.
local r = sb.makeRandomSource(31415926)
local a = r:randu32()
local b = r:randu64()
local c = r:randu32()
r:addEntropy(27182818)
local d = r:randu32()
local e = r:randu64()
local f = r:randb()
r:init(31415926)
local reset = r:randu32()
assert(a == 2950892229 and c == 445970691 and d == 2992900064)
assert(reset == a and f == true)
local lua = {
  b = string.format('%d', b), e = string.format('%d', e), f = f,
  bInteger = math.type(b) == 'integer', eInteger = math.type(e) == 'integer'
}
assert(lua.b == '6090466678391964828' and lua.e == '-3117415037168400252')
assert(lua.bInteger and lua.eInteger)
local rgb = {a % 256, (a >> 8) % 256, (a >> 16) % 256}
local width = 32 + c % 33
-- Crop the normal shared asset to one pixel, color from the actual draw, then
-- enlarge through the production image API using the actual width draw.
local image = assets.image('/objects/behaviorlab/constantlight/constantlight.png'):subImage({0, 0}, {1, 1})
image:set(0, 0, {rgb[1], rgb[2], rgb[3], 255})
image = image:process(string.format('?scalenearest=%d;16', width))
local size = image:size()
assert(size[1] == width and size[2] == 16)
assets.add('/behaviorlab/random-result.png', image)
-- LAST: a swallowed postLoad failure cannot look like a complete proof.
assets.recordRandomMwcLabProof({lua = lua, visual = {
  rgb = rgb, width = width, height = 16, label = 'RANDOM',
  imagePath = '/behaviorlab/random-result.png'
}})
