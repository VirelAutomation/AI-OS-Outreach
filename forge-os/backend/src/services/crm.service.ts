import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { runtimeStore } from '../lib/runtimeStore.js'

export class CrmService {
  async listProspects() {
    const supabase = getSupabaseAdmin()
    if (!supabase) return this.runtimeProspects()

    const { data, error } = await supabase
      .from('prospects')
      .select('id, full_name, email, company_name, industry, city, status, source, created_at')
      .order('created_at', { ascending: false })
      .limit(200)

    if (error || !data) return this.runtimeProspects()
    return data
  }

  async dashboardSummary() {
    const prospects = await this.listProspects()
    return {
      totalProspects: prospects.length,
      activeProspects: prospects.filter((item) => ['new', 'contacted', 'qualified'].includes(String(item.status))).length,
      industries: [...new Set(prospects.map((item) => String(item.industry ?? 'Unknown')))],
      newest: prospects.slice(0, 5),
    }
  }

  private runtimeProspects() {
    return [...runtimeStore.all.leads]
      .sort((left, right) => (right.enrichedAt ?? '').localeCompare(left.enrichedAt ?? ''))
      .map((lead) => ({
        id: lead.id,
        full_name: lead.fullName,
        email: lead.email,
        company_name: lead.companyName,
        industry: lead.industry ?? 'Unknown',
        city: lead.city ?? null,
        status: 'runtime_captured',
        source: 'runtime_store',
        created_at: lead.enrichedAt ?? new Date().toISOString(),
      }))
  }
}
