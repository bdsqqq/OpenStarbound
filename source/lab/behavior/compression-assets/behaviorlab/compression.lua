-- Three real operations: normal image PNG producer, zlib consumer, fixed gzip consumer.
local fixture = assets.json('/behaviorlab/compression.json')
local source = assets.image('/objects/behaviorlab/constantlight/constantlight.png'):subImage({0, 0}, {1, 1})
source:set(0, 0, {96, 192, 224, 255})
source = source:process('?scalenearest=16;16')
local function check(image)
  local size = image:size()
  assert(size[1] == 16 and size[2] == 16)
  for y = 0, 15 do
    for x = 0, 15 do
      local c = image:get(x, y)
      -- Opaque Color -> Lua omits alpha; native checks all four channels.
      assert(c[1] == 96 and c[2] == 192 and c[3] == 224 and (c[4] or 255) == 255)
    end
  end
end
check(source)
local path = source:embed('Zlib')
local zlibImage = assets.image(path)
check(zlibImage)
local gzipImage = assets.image(fixture.gzipPath)
check(gzipImage)
-- Register the actual decoded image; do not repaint or regenerate it.
assets.add('/behaviorlab/compression-result.png', gzipImage)
-- LAST: native rows/counters/pixels must all exist before proof completion.
assets.recordCompressionLabProof({
  imagePath = '/behaviorlab/compression-result.png', scale = 4, label = 'COMPRESS'
})
