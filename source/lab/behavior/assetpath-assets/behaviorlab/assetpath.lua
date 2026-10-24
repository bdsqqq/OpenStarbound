-- FIRST: no atlas or frames fetch may warm these two image loads.
local namedImage = assets.image('/behaviorlab/assetpath-atlas.png:right?multiply=80ff80')
local aliasImage = assets.image('/behaviorlab/assetpath-atlas.png:alias?multiply=80ff80')
for _, image in ipairs({namedImage, aliasImage}) do
  local size = image:size()
  assert(size[1] == 16 and size[2] == 16)
  for y = 0, 15 do
    for x = 0, 15 do
      local pixel = image:get(x, y)
      -- Opaque Color -> Lua intentionally omits alpha; native proof records RGBA.
      assert(pixel[1] == 32 and pixel[2] == 128 and pixel[3] == 96 and (pixel[4] or 255) == 255)
    end
  end
end
-- Use the actual processed frame, never a repainted/generated replacement.
assets.add('/behaviorlab/assetpath-result.png', namedImage)
local color = namedImage:get(0, 0)
color[4] = color[4] or 255
-- LAST: swallowed postLoad errors must not produce an accepted proof.
assets.recordAssetPathLabProof({
  imagePath = '/behaviorlab/assetpath-result.png',
  color = color, size = namedImage:size(), label = 'ASSETPATH'
})
