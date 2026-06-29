import { env } from '../config/env.js'
import { outboundFetch } from '../lib/network.js'

type LatLng = { lat: number; lng: number }

export class GoogleMapsService {
  async geocode(address: string): Promise<{ ok: boolean; location?: LatLng; formattedAddress?: string; error?: string }> {
    if (!env.GOOGLE_MAPS_API_KEY) return { ok: false, error: 'missing_maps_key' }
    const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(address)}&key=${env.GOOGLE_MAPS_API_KEY}`
    const response = await outboundFetch(url)
    if (!response.ok) return { ok: false, error: `maps_http_${response.status}` }
    const payload = (await response.json()) as {
      status?: string
      results?: Array<{ formatted_address?: string; geometry?: { location?: LatLng } }>
      error_message?: string
    }

    if (payload.status !== 'OK' || !payload.results?.[0]?.geometry?.location) {
      return { ok: false, error: payload.error_message ?? payload.status ?? 'maps_geocode_failed' }
    }

    return {
      ok: true,
      location: payload.results[0].geometry.location,
      formattedAddress: payload.results[0].formatted_address,
    }
  }

  async distanceKm(origin: string, destination: string): Promise<{ ok: boolean; distanceKm?: number; error?: string }> {
    if (!env.GOOGLE_MAPS_API_KEY) return { ok: false, error: 'missing_maps_key' }
    const url =
      `https://maps.googleapis.com/maps/api/distancematrix/json?origins=${encodeURIComponent(origin)}&destinations=${encodeURIComponent(destination)}&key=${env.GOOGLE_MAPS_API_KEY}`
    const response = await outboundFetch(url)
    if (!response.ok) return { ok: false, error: `maps_http_${response.status}` }
    const payload = (await response.json()) as {
      status?: string
      rows?: Array<{ elements?: Array<{ status?: string; distance?: { value?: number } }> }>
      error_message?: string
    }
    const element = payload.rows?.[0]?.elements?.[0]
    if (payload.status !== 'OK' || element?.status !== 'OK' || typeof element.distance?.value !== 'number') {
      return { ok: false, error: payload.error_message ?? element?.status ?? payload.status ?? 'distance_failed' }
    }
    return { ok: true, distanceKm: Number((element.distance.value / 1000).toFixed(2)) }
  }
}
