import type { AgentStatus, Preferences, Report, ReportPage, Tag } from './types'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options)
  if (!response.ok) {
    let message = `Erro HTTP ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((item: { msg?: string }) => item.msg || 'Dados inválidos').join('; ')
    } catch { /* resposta sem JSON */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function listReports(params: { page: number; q: string; tag: Tag | ''; fromDate: string; toDate: string }): Promise<ReportPage> {
  const query = new URLSearchParams({ page: String(params.page), page_size: '9' })
  if (params.q) query.set('q', params.q)
  if (params.tag) query.set('tag', params.tag)
  if (params.fromDate) query.set('from_date', params.fromDate)
  if (params.toDate) query.set('to_date', params.toDate)
  return request(`/api/reports?${query}`)
}

export const getReport = (id: string) => request<Report>(`/api/reports/${id}`)
export const getAgentStatus = () => request<AgentStatus>('/api/agent/status')
export const getPreferences = () => request<Preferences>('/api/settings')
export const savePreferences = (data: Pick<Preferences, 'enabled_sources' | 'enabled_topics' | 'web_domains'>, key: string) => request<Preferences>('/api/settings', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json', ...(key ? { 'X-API-Key': key } : {}) },
  body: JSON.stringify(data),
})
export const triggerAgent = (key: string) => request<{ message: string }>('/api/trigger-agent', {
  method: 'POST',
  headers: key ? { 'X-API-Key': key } : {},
})

