// Typed calls to every API route (PLAN.md task 2.8). The dev server proxies /api to
// the FastAPI app and strips the prefix, so /api/quote reaches POST /quote.
import type {
  Item,
  Path,
  QuoteRequest,
  RankedOffer,
  ScanKind,
  ScanResult,
  ShopFilters,
  ShopRankRequest,
  Source,
} from './contracts'

export const API_BASE = '/api'

// A request with no full answer after this long is stopped (PLAN.md task 2.8.1).
export const TIMEOUT_MS = 15_000
export const TIMEOUT_MESSAGE = 'No answer after 15 seconds. Check your connection and try again.'
// A scan waits on a Grok read, which can outlast the ordinary 15 second limit (task 3.10).
export const SCAN_TIMEOUT_MS = 60_000
export const SCAN_TIMEOUT_MESSAGE = 'No answer after 60 seconds. Check your connection and try again.'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// FastAPI puts validation problems in `detail`: a string, or a list of `{ msg }`.
function detailText(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  const { detail } = body as { detail: unknown }
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (typeof d === 'object' && d !== null && 'msg' in d ? String(d.msg) : ''))
      .filter(Boolean)
    return msgs.length ? msgs.join('; ') : null
  }
  return null
}

// The timer covers reading the body too, so a response that stalls halfway also stops.
async function request<T>(path: string, init?: RequestInit, timeoutMs = TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal })
    if (!res.ok) {
      const body: unknown = await res.json().catch(() => null)
      throw new ApiError(res.status, detailText(body) ?? `Request failed (${res.status})`)
    }
    return (await res.json()) as T
  } catch (err) {
    if (controller.signal.aborted) throw new Error(timeoutMs === SCAN_TIMEOUT_MS ? SCAN_TIMEOUT_MESSAGE : TIMEOUT_MESSAGE)
    throw err
  } finally {
    clearTimeout(timer)
  }
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function health(): Promise<{ ok: boolean }> {
  return request('/health')
}

export function categories(): Promise<string[]> {
  return request('/categories')
}

export function sources(): Promise<Source[]> {
  return request('/sources')
}

export function quote(req: QuoteRequest): Promise<Path[]> {
  return postJson('/quote', req)
}

export function checkItem(item: Item): Promise<Item> {
  return postJson('/item', item)
}

export function scan(kind: ScanKind, image: Blob): Promise<ScanResult> {
  const form = new FormData()
  form.append('kind', kind)
  form.append('image', image)
  // No Content-Type header: the browser sets the multipart boundary.
  return request('/scan', { method: 'POST', body: form }, SCAN_TIMEOUT_MS)
}

export function parseShopRequest(text: string): Promise<ShopFilters> {
  return postJson('/shop/parse', { text })
}

export function rankShopOffers(req: ShopRankRequest): Promise<RankedOffer[]> {
  return postJson('/shop/rank', req)
}
