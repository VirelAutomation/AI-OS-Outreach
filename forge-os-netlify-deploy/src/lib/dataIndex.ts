export type ForgeCollectionName =
  | 'calls'
  | 'campaigns'
  | 'meetings'
  | 'deals'
  | 'products'
  | 'settings'

export type IndexedRecord = {
  id: string
  collection: ForgeCollectionName
  title: string
  subtitle: string
  searchText: string
  payload: unknown
  hash: string
}

export type ForgeDataIndex = {
  records: Map<string, IndexedRecord>
  prefixIndex: Map<string, Set<string>>
  collectionRoots: Record<ForgeCollectionName, string>
  globalRoot: string
  stats: {
    records: number
    lookupTerms: number
    collectionCount: number
  }
}

type SourceState = {
  calls: unknown[]
  campaigns: unknown[]
  meetings: unknown[]
  deals: unknown[]
  products: unknown[]
  settings: Record<string, unknown>
}

const EMPTY_ROOT = hashString('empty')
const collections: ForgeCollectionName[] = ['calls', 'campaigns', 'meetings', 'deals', 'products', 'settings']

export function buildForgeDataIndex(source: SourceState): ForgeDataIndex {
  const records = new Map<string, IndexedRecord>()
  const prefixIndex = new Map<string, Set<string>>()

  const addRecord = (record: Omit<IndexedRecord, 'hash'>) => {
    const hash = hashString(stableStringify(record.payload))
    const indexedRecord = { ...record, hash }
    records.set(record.id, indexedRecord)

    tokenize(record.searchText).forEach((token) => {
      for (let length = 2; length <= Math.min(token.length, 18); length += 1) {
        const prefix = token.slice(0, length)
        const bucket = prefixIndex.get(prefix) ?? new Set<string>()
        bucket.add(record.id)
        prefixIndex.set(prefix, bucket)
      }
    })
  }

  source.calls.forEach((item, index) => {
    const row = item as Record<string, unknown>
    const prospect = String(row.prospect ?? `Call ${index + 1}`)
    const company = String(row.company ?? 'Unknown company')
    addRecord({
      id: `calls:${String(row.id ?? index)}`,
      collection: 'calls',
      title: prospect,
      subtitle: `${company} · ${String(row.outcome ?? 'Call')}`,
      searchText: `${prospect} ${company} ${String(row.vertical ?? '')} ${String(row.outcome ?? '')} ${String(row.notes ?? '')}`,
      payload: item,
    })
  })

  source.campaigns.forEach((item, index) => {
    const row = item as Record<string, unknown>
    const name = String(row.name ?? `Campaign ${index + 1}`)
    addRecord({
      id: `campaigns:${String(row.id ?? index)}`,
      collection: 'campaigns',
      title: name,
      subtitle: `${String(row.vertical ?? 'Campaign')} · ${String(row.replyRate ?? 0)}% replies`,
      searchText: `${name} ${String(row.vertical ?? '')}`,
      payload: item,
    })
  })

  source.meetings.forEach((item, index) => {
    const row = item as Record<string, unknown>
    const prospect = String(row.prospect ?? `Meeting ${index + 1}`)
    const company = String(row.company ?? 'Unknown company')
    addRecord({
      id: `meetings:${String(row.id ?? index)}`,
      collection: 'meetings',
      title: prospect,
      subtitle: `${company} · ${String(row.type ?? 'Meeting')}`,
      searchText: `${prospect} ${company} ${String(row.vertical ?? '')} ${String(row.type ?? '')} ${String(row.notes ?? '')}`,
      payload: item,
    })
  })

  source.deals.forEach((item, index) => {
    const row = item as Record<string, unknown>
    const prospect = String(row.prospect ?? `Deal ${index + 1}`)
    const company = String(row.company ?? 'Unknown company')
    addRecord({
      id: `deals:${String(row.id ?? index)}`,
      collection: 'deals',
      title: prospect,
      subtitle: `${company} · ${String(row.stage ?? 'Pipeline')}`,
      searchText: `${prospect} ${company} ${String(row.vertical ?? '')} ${String(row.stage ?? '')}`,
      payload: item,
    })
  })

  source.products.forEach((item, index) => {
    const row = item as Record<string, unknown>
    const name = String(row.name ?? `Product ${index + 1}`)
    addRecord({
      id: `products:${String(row.id ?? index)}`,
      collection: 'products',
      title: name,
      subtitle: String(row.price ?? 'No price'),
      searchText: `${name} ${String(row.description ?? '')} ${String(row.price ?? '')}`,
      payload: item,
    })
  })

  addRecord({
    id: 'settings:active',
    collection: 'settings',
    title: 'FORGE Settings',
    subtitle: 'Revenue target, operators, verticals',
    searchText: stableStringify(source.settings),
    payload: source.settings,
  })

  const collectionRoots = collections.reduce<Record<ForgeCollectionName, string>>((acc, collection) => {
    const leaves = [...records.values()]
      .filter((record) => record.collection === collection)
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((record) => hashString(`${record.id}:${record.hash}`))
    acc[collection] = sparseMerkleRoot(leaves)
    return acc
  }, {} as Record<ForgeCollectionName, string>)

  const globalRoot = sparseMerkleRoot(
    collections.map((collection) => hashString(`${collection}:${collectionRoots[collection]}`)),
  )

  return {
    records,
    prefixIndex,
    collectionRoots,
    globalRoot,
    stats: {
      records: records.size,
      lookupTerms: prefixIndex.size,
      collectionCount: collections.length,
    },
  }
}

export function searchForgeIndex(index: ForgeDataIndex, query: string, limit = 8) {
  const tokens = tokenize(query)
  if (tokens.length === 0) return []

  const candidateScores = new Map<string, number>()

  tokens.forEach((token) => {
    const bucket = index.prefixIndex.get(token.slice(0, Math.min(token.length, 18)))
    bucket?.forEach((id) => {
      const record = index.records.get(id)
      if (!record) return
      const exactBoost = record.searchText.toLowerCase().includes(token) ? 2 : 1
      candidateScores.set(id, (candidateScores.get(id) ?? 0) + exactBoost)
    })
  })

  return [...candidateScores.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id, score]) => ({ ...index.records.get(id)!, score }))
    .slice(0, limit)
}

export function shortRoot(root: string) {
  return `${root.slice(0, 10)}…${root.slice(-6)}`
}

function sparseMerkleRoot(leaves: string[]) {
  if (leaves.length === 0) return EMPTY_ROOT

  const nextPowerOfTwo = 2 ** Math.ceil(Math.log2(Math.max(1, leaves.length)))
  let level = [...leaves]

  while (level.length < nextPowerOfTwo) {
    level.push(EMPTY_ROOT)
  }

  while (level.length > 1) {
    const next: string[] = []
    for (let index = 0; index < level.length; index += 2) {
      next.push(hashString(`${level[index]}:${level[index + 1]}`))
    }
    level = next
  }

  return level[0]
}

function tokenize(value: string) {
  return value
    .toLowerCase()
    .split(/[^a-z0-9]+/i)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2)
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`

  const object = value as Record<string, unknown>
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(object[key])}`)
    .join(',')}}`
}

function hashString(value: string) {
  // FNV-1a 64-bit style deterministic hash. Fast enough for local indexes and stable across browsers.
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

function toHex(value: number) {
  return (value >>> 0).toString(16).padStart(8, '0')
}
