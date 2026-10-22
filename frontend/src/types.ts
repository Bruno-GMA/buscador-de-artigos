export type Tag = 'SLM' | 'RAG' | 'EdTech'

export interface Paper {
  id: number
  title: string
  authors: string
  original_abstract: string
  generated_summary: string
  category: Tag
  url: string
  relevance_score: number
  source: string
  published_at: string | null
}

export interface Report {
  id: number
  run_date: string
  title: string
  overview: string
  markdown: string
  created_at: string
  papers: Paper[]
}

export interface ReportPage {
  items: Report[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AgentStatus {
  running: boolean
  last_started_at: string | null
  last_finished_at: string | null
  last_report_id: number | null
  last_error: string | null
}

