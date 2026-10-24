-- A real 16x16 normal Assets image; configuration is read later, after Root loads.
local source = assets.image('/objects/behaviorlab/constantlight/constantlight.png'):subImage({0, 0}, {1, 1})
source:set(0, 0, {255, 255, 255, 255})
source = source:process('?scalenearest=16;16')
assets.add('/behaviorlab/option-parser.png', source)
