function proof()
  -- This is the normal game Root binding, not metadata supplied by the harness.
  local value = root.getConfiguration("optionParserProof")
  local c = value.color
  assert(#c == 4)
  for _, v in ipairs(c) do assert(v >= 0 and v <= 255 and v % 1 == 0) end
  assert(type(value.label) == "string")
  return {
    configuration = value,
    imagePath = "/behaviorlab/option-parser.png?multiply=" .. string.format("%02x%02x%02x%02x", c[1], c[2], c[3], c[4]),
    color = c,
    label = value.label,
    scale = 4
  }
end
