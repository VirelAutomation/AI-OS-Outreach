import { hashString, sparseMerkleRoot, stableStringify } from '../lib/hash.js'

type RootableCollection = 'prospects' | 'campaigns' | 'meetings' | 'deals' | 'products' | 'content'

export class AnalyticsService {
  computeCollectionRoot<T extends { id?: string }>(collection: RootableCollection, items: T[]) {
    const leaves = items
      .map((item, index) => hashString(`${collection}:${item.id ?? index}:${stableStringify(item)}`))
      .sort()

    return sparseMerkleRoot(leaves)
  }

  computeGlobalRoot(input: Partial<Record<RootableCollection, unknown[]>>) {
    const entries = Object.entries(input).map(([collection, items]) => {
      const root = this.computeCollectionRoot(collection as RootableCollection, (items ?? []) as { id?: string }[])
      return hashString(`${collection}:${root}`)
    })

    return sparseMerkleRoot(entries)
  }

  scoreCampaigns(campaigns: Array<{ id: string; name: string; vertical?: string; replyRate?: number; positiveReplyRate?: number; meetingsBooked?: number }>) {
    return campaigns
      .map((campaign) => {
        const replyRate = campaign.replyRate ?? 0
        const positiveReplyRate = campaign.positiveReplyRate ?? 0
        const meetings = campaign.meetingsBooked ?? 0
        const score = replyRate * 0.45 + positiveReplyRate * 0.3 + meetings * 2.1

        return {
          id: campaign.id,
          name: campaign.name,
          vertical: campaign.vertical ?? 'Unknown',
          score: Number(score.toFixed(2)),
          diagnosis:
            replyRate < 5
              ? 'Poor resonance. Rework subject line and opener.'
              : positiveReplyRate < 3
                ? 'Interest exists but CTA is weak.'
                : 'Campaign is healthy. Increase qualified volume.',
        }
      })
      .sort((a, b) => b.score - a.score)
  }
}
