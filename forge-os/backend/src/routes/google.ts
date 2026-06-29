import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { GoogleMapsService } from '../services/googleMaps.service.js'
import { GoogleStackService } from '../services/googleStack.service.js'

const geocodeSchema = z.object({
  address: z.string().min(3),
})

const distanceSchema = z.object({
  origin: z.string().min(3),
  destination: z.string().min(3),
})

export async function registerGoogleRoutes(app: FastifyInstance) {
  const maps = new GoogleMapsService()
  const stack = new GoogleStackService()

  app.get('/api/google/readiness', async () => {
    return stack.readiness()
  })

  app.post('/api/google/maps/geocode', async (request, reply) => {
    const parsed = geocodeSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const result = await maps.geocode(parsed.data.address)
    return result
  })

  app.post('/api/google/maps/distance', async (request, reply) => {
    const parsed = distanceSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const result = await maps.distanceKm(parsed.data.origin, parsed.data.destination)
    return result
  })
}
