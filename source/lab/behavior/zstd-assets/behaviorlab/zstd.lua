-- Do not load the embedded path here: its first consumer is native TCP -> Assets.
assets.beginZstdLabProof()
local source = assets.image('/objects/behaviorlab/constantlight/constantlight.png'):subImage({0, 0}, {1, 1})
source:set(0, 0, {224, 160, 64, 255})
source = source:process('?scalenearest=16;16')
local path = source:embed('Zstd')
assert(type(path) == 'string' and path:sub(1, 22) == '/opensb_data;bin;zstd;')
