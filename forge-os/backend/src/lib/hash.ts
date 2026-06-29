export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`

  const object = value as Record<string, unknown>
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(object[key])}`)
    .join(',')}}`
}

export function hashString(value: string) {
  let high = 0xcbf29ce4
  let low = 0x84222325

  for (let index = 0; index < value.length; index += 1) {
    low ^= value.charCodeAt(index)
    low += (low << 1) + (low << 4) + (low << 7) + (low << 8) + (low << 24)
    high ^= low >>> 24
    high += (high << 1) + (high << 4) + (high << 7) + (high << 8) + (high << 24)
  }

  return `${toHex(high)}${toHex(low)}`
}

export function sparseMerkleRoot(leaves: string[]) {
  const empty = hashString('empty')
  if (leaves.length === 0) return empty

  const nextPowerOfTwo = 2 ** Math.ceil(Math.log2(Math.max(1, leaves.length)))
  let level = [...leaves]

  while (level.length < nextPowerOfTwo) level.push(empty)

  while (level.length > 1) {
    const next: string[] = []
    for (let index = 0; index < level.length; index += 2) {
      next.push(hashString(`${level[index]}:${level[index + 1]}`))
    }
    level = next
  }

  return level[0]
}

function toHex(value: number) {
  return (value >>> 0).toString(16).padStart(8, '0')
}
