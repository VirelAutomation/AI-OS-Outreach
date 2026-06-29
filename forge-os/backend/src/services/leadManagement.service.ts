import { ProductionDataService } from './productionData.service.js'

export type ReplyIntent = 'interested' | 'neutral' | 'unsubscribe' | 'objection' | 'meeting_intent'

function classifyIntent(text: string): ReplyIntent {
  const value = text.toLowerCase()
  if (/(unsubscribe|remove me|stop emailing|opt out)/.test(value)) return 'unsubscribe'
  if (/(book|schedule|calendar|call|demo|meet|tomorrow|next week)/.test(value)) return 'meeting_intent'
  if (/(interested|send more|sounds good|tell me more|pricing)/.test(value)) return 'interested'
  if (/(not interested|already have|too expensive|no budget|later)/.test(value)) return 'objection'
  return 'neutral'
}

export class LeadManagementService {
  private readonly productionData = new ProductionDataService()

  async triageReply(input: { leadId: string; replyText: string }) {
    const intent = classifyIntent(input.replyText)
    const event = await this.productionData.createReplyEvent({
      leadId: input.leadId,
      intent,
      rawText: input.replyText,
    })
    const nextAction = this.nextActionFor(intent)
    return { ok: true, intent, event, nextAction }
  }

  async bookMeeting(input: { leadId: string; value?: number }) {
    const meeting = await this.productionData.createMeeting({ leadId: input.leadId, value: input.value ?? 0 })
    return { ok: true, meeting }
  }

  async digest() {
    return this.productionData.leadManagementDigest()
  }

  private nextActionFor(intent: ReplyIntent) {
    if (intent === 'meeting_intent') return 'Create meeting and send booking link immediately.'
    if (intent === 'interested') return 'Send short qualification reply and propose a 15-minute call.'
    if (intent === 'objection') return 'Route to objection handling and follow up within 24 hours.'
    if (intent === 'unsubscribe') return 'Suppress contact and stop all future sends.'
    return 'Keep in nurture and schedule a light follow-up.'
  }
}
