local seed = assets.image('/objects/behaviorlab/constantlight/constantlight.png')
assert(seed:size()[1] == 8 and seed:size()[2] == 8)
local image = seed:subImage({0, 0}, {1, 1}):process('?scale=16')
assert(image:size()[1] == 16 and image:size()[2] == 16)
for y = 0, 15 do
  for x = 0, 15 do image:set(x, y, {224, 160, 32, 255}) end
end
assets.add('/behaviorlab/shell-result.png', image)
