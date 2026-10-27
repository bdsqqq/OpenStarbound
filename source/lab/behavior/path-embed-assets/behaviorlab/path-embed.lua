-- Leave the returned embedded path unconsumed: the future native TCP -> Assets
-- fixture must perform the first base-image and alias/crop acquisitions itself.
local seed = assets.image('/behaviorlab/path-embed-seed.png')
local reserved = 'reserved%:?;/'
local frames = {
  frameList = {
    [reserved] = {16, 0, 32, 16},
    wrong = {0, 0, 16, 16}
  },
  aliases = {crop = reserved}
}
local embedded = seed:embed('None', frames, 'text')
assert(embedded:sub(1, 19) == '/opensb_data;image;')
assert(embedded:find(';frames;text;', 1, true))
-- This literal exercises every escape in meaningful parsed frame names. It is
-- deliberately independent of the production byte-escaping implementation.
local escaped = 'reserved%%%c%q%s%b'
local first, last = embedded:find(escaped, 1, true)
assert(first)
local second = embedded:find(escaped, last + 1, true)
assert(second)
assert(not embedded:find(escaped, second + #escaped, true))
assets.add('/behaviorlab/path-embed-proof.json', {
  version = 1,
  basePath = embedded,
  cropPath = embedded .. ':crop',
  selectedAlias = 'crop',
  reservedFrameName = reserved,
  seedSize = {32, 16},
  selectedRect = {16, 0, 32, 16},
  wrongRect = {0, 0, 16, 16}
})
