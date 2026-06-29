import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { runtimeStore } from '../lib/runtimeStore.js'

export class MeetingsService {
  async listMeetings() {
    const supabase = getSupabaseAdmin()
    if (!supabase) return this.runtimeMeetings()

    const { data, error } = await supabase
      .from('meetings')
      .select('id, prospect_name, company_name, meeting_type, start_at, status, value_estimate')
      .order('start_at', { ascending: true })
      .limit(100)

    if (error || !data) return this.runtimeMeetings()
    return data
  }

  async createBooking(input: {
    fullName: string
    email: string
    companyName?: string
    requestedAt: string
    source?: string
    notes?: string
  }) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return {
        booked: true,
        mode: 'mock',
        booking: {
          id: `booking-${Date.now()}`,
          ...input,
          status: 'requested',
        },
      }
    }

    const { data, error } = await supabase
      .from('booking_requests')
      .insert({
        full_name: input.fullName,
        email: input.email,
        company_name: input.companyName ?? null,
        requested_at: input.requestedAt,
        source: input.source ?? 'landing_page_chat',
        notes: input.notes ?? null,
        status: 'requested',
      })
      .select()
      .single()

    if (error) {
      return {
        booked: false,
        mode: 'error',
        error: error.message,
      }
    }

    return {
      booked: true,
      mode: 'database',
      booking: data,
    }
  }

  private runtimeMeetings() {
    return [...runtimeStore.all.meetings]
      .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
      .map((meeting) => {
        const lead = runtimeStore.all.leads.find((item) => item.id === meeting.leadId)
        return {
          id: meeting.id,
          prospect_name: lead?.fullName ?? 'Unknown Prospect',
          company_name: lead?.companyName ?? '',
          meeting_type: 'Discovery',
          start_at: meeting.createdAt,
          status: 'booked_pending_schedule',
          value_estimate: meeting.value,
        }
      })
  }
}
