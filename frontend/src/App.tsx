import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, BookOpen, CalendarDays, Check, ChevronLeft, ChevronRight, CircleHelp, Clipboard, ExternalLink, Filter, LayoutDashboard, Menu, Moon, Play, Radio, Search, Sparkles, Sun, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { getAgentStatus, getReport, listReports, triggerAgent } from './api'
import type { AgentStatus, Report, ReportPage, Tag } from './types'

const TOPICS: { label: string; value: Tag | '' }[] = [
  { label: 'Todos', value: '' }, { label: 'SLM', value: 'SLM' }, { label: 'RAG', value: 'RAG' }, { label: 'IA na Educação', value: 'EdTech' },
]

function formatDate(value: string, long = false) {
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: long ? 'long' : 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T12:00:00Z`))
}

function labels(tags: string[]) {
  return [...new Set(tags)].map(tag => <span className={`tag tag-${tag.toLowerCase()}`} key={tag}>{tag === 'EdTech' ? 'IA na Educação' : tag}</span>)
}

function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem('pulse-theme') || 'dark')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('pulse-theme', theme)
  }, [theme])
  return { theme, toggle: () => setTheme(current => current === 'dark' ? 'light' : 'dark') }
}

function Shell({ children, theme, onTheme }: { children: ReactNode; theme: string; onTheme: () => void }) {
  const [mobileNav, setMobileNav] = useState(false)
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Radio size={22} strokeWidth={2.4} /></div><div><strong>Academic Pulse</strong><span>INTELLIGENCE DESK</span></div></div>
      <div className="sidebar-section">WORKSPACE</div>
      <Link className="nav-item active" to="/" onClick={() => setMobileNav(false)}><LayoutDashboard size={18} /> Visão geral</Link>
      <div className="sidebar-bottom"><div className="sidebar-note"><Sparkles size={18} /><span>Seu radar científico, atualizado todos os dias.</span></div><div className="sidebar-footer"><span className="live-dot" /> AGENTE LOCAL <span className="version">v1.0</span></div></div>
    </aside>
    {mobileNav && <button className="mobile-overlay" aria-label="Fechar menu" onClick={() => setMobileNav(false)} />}
    <div className="main-area">
      <header className="topbar"><button className="icon-button mobile-menu" aria-label="Abrir menu" onClick={() => setMobileNav(true)}><Menu size={20} /></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={15} /><strong>Radar de pesquisa</strong></div><div className="top-actions"><span className="system-label"><span className="live-dot" /> SISTEMA ONLINE</span><button className="icon-button" aria-label={`Ativar tema ${theme === 'dark' ? 'claro' : 'escuro'}`} onClick={onTheme}>{theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}</button></div></header>
      {children}
    </div>
  </div>
}

function ReportCard({ report }: { report: Report }) {
  const top = report.papers.slice().sort((a, b) => b.relevance_score - a.relevance_score)[0]
  return <Link to={`/reports/${report.id}`} className="report-card">
    <div className="card-top"><span className="date-label"><CalendarDays size={15} /> {formatDate(report.run_date)}</span><ArrowRight size={18} className="card-arrow" /></div>
    <h3>{report.title}</h3><p>{report.overview}</p>
    <div className="card-tags">{labels(report.papers.map(p => p.category))}</div>
    <div className="card-bottom"><span><BookOpen size={15} /> {report.papers.length} artigos</span><span>{top ? `Maior relevância ${Math.round(top.relevance_score)}/100` : 'Sem artigos'}</span></div>
  </Link>
}

function Dashboard() {
  const [data, setData] = useState<ReportPage | null>(null)
  const [agent, setAgent] = useState<AgentStatus | null>(null)
  const [queryInput, setQueryInput] = useState('')
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState<Tag | ''>('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => { const timer = window.setTimeout(() => { setPage(1); setQuery(queryInput.trim()) }, 300); return () => clearTimeout(timer) }, [queryInput])
  useEffect(() => {
    let alive = true
    setLoading(true)
    listReports({ page, q: query, tag, fromDate, toDate }).then(value => { if (alive) { setData(value); setError('') } }).catch(err => { if (alive) setError(err.message) }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [page, query, tag, fromDate, toDate, agent?.running])
  useEffect(() => {
    const update = () => getAgentStatus().then(setAgent).catch(() => undefined)
    update()
    const timer = window.setInterval(update, 5000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => { if (agent?.last_error) setNotice(`Falha no agente: ${agent.last_error}`) }, [agent?.last_error])

  async function runAgent() {
    const key = sessionStorage.getItem('pulse-api-key') || ''
    try {
      await triggerAgent(key)
      setNotice('Agente iniciado. O relatório aparecerá aqui ao concluir.')
      setAgent(current => current ? { ...current, running: true } : { running: true, last_started_at: null, last_finished_at: null, last_report_id: null, last_error: null })
    } catch (err) {
      if (err instanceof Error && err.message.includes('Chave de API')) {
        const entered = window.prompt('Informe TRIGGER_API_KEY configurada no backend:')
        if (entered) { sessionStorage.setItem('pulse-api-key', entered); await runAgent() }
      } else setNotice(err instanceof Error ? err.message : 'Falha ao iniciar o agente')
    }
  }

  const highlights = useMemo(() => data?.items.filter(report => Date.now() - new Date(`${report.run_date}T12:00:00Z`).getTime() < 7 * 86400000).slice(0, 3) || [], [data])
  const totalPapers = data?.items.reduce((sum, report) => sum + report.papers.length, 0) || 0

  return <main className="content">
    <div className="eyebrow"><span className="eyebrow-line" /> RESEARCH INTELLIGENCE <span className="eyebrow-line" /></div>
    <section className="hero"><div><p className="kicker">SEU RADAR ACADÊMICO</p><h1>Conhecimento em <em>movimento.</em></h1><p className="hero-subtitle">Descubra o que importa em SLM, RAG e IA na Educação. Pesquisa filtrada, sintetizada e organizada para você.</p><div className="hero-actions"><button className="primary-button" onClick={runAgent} disabled={agent?.running}><Play size={16} fill="currentColor" /> {agent?.running ? 'Agente em execução...' : 'Executar agente agora'}</button><span className="hero-hint"><span className="live-dot" /> {agent?.running ? 'Processando artigos' : 'Pronto para pesquisar'}</span></div></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-1" /><div className="orbit orbit-2" /><div className="orbit orbit-3" /><div className="orb orb-1" /><div className="orb orb-2" /><div className="orb orb-3" /><div className="hero-art-center"><Radio size={44} strokeWidth={1.3} /></div></div></section>
    {notice && <div className="notice" role="status">{notice}<button aria-label="Fechar aviso" onClick={() => setNotice('')}><X size={16} /></button></div>}
    <div className="stats-grid"><div className="stat-card"><span>RELATÓRIOS NO ACERVO</span><strong>{data?.total ?? '—'}</strong><small>Insights organizados por dia</small></div><div className="stat-card"><span>ARTIGOS NESTA PÁGINA</span><strong>{data ? totalPapers : '—'}</strong><small>Fontes analisadas pelo Gemma 3</small></div><div className="stat-card"><span>FOCO DE PESQUISA</span><strong>03</strong><small>SLM · RAG · IA na Educação</small></div></div>
    {highlights.length > 0 && <section className="highlights"><div className="section-heading"><div><span className="section-overline">EM DESTAQUE</span><h2>Esta semana</h2></div><span className="section-caption">Seleção recente do radar</span></div><div className="highlight-grid">{highlights.map((report, index) => <Link to={`/reports/${report.id}`} className="highlight-card" key={report.id}><span className="highlight-number">0{index + 1}</span><span className="highlight-date">{formatDate(report.run_date)}</span><strong>{report.title}</strong><span className="highlight-link">Explorar relatório <ArrowRight size={15} /></span></Link>)}</div></section>}
    <section className="timeline"><div className="section-heading"><div><span className="section-overline">ARQUIVO DE PESQUISA</span><h2>Timeline de descobertas</h2></div><span className="section-caption">Do mais recente ao mais antigo</span></div><div className="toolbar"><div className="search-box"><Search size={18} /><input aria-label="Buscar relatórios" placeholder="Buscar por tema, artigo ou palavra-chave..." value={queryInput} onChange={e => setQueryInput(e.target.value)} /></div><button className={`filter-button ${showFilters ? 'selected' : ''}`} onClick={() => setShowFilters(!showFilters)}><Filter size={17} /> Filtros</button></div>{showFilters && <div className="date-filters"><label>De <input type="date" value={fromDate} onChange={e => { setPage(1); setFromDate(e.target.value) }} /></label><label>Até <input type="date" value={toDate} onChange={e => { setPage(1); setToDate(e.target.value) }} /></label><button onClick={() => { setFromDate(''); setToDate('') }}>Limpar datas</button></div>}<div className="tabs">{TOPICS.map(topic => <button className={tag === topic.value ? 'tab active' : 'tab'} key={topic.label} onClick={() => { setTag(topic.value); setPage(1) }}>{topic.label}</button>)}</div>
      {error ? <div className="empty-state"><CircleHelp size={30} /><h3>Não foi possível carregar os relatórios</h3><p>{error}</p></div> : loading ? <div className="loading">Carregando relatórios...</div> : data?.items.length ? <div className="report-grid">{data.items.map(report => <ReportCard key={report.id} report={report} />)}</div> : <div className="empty-state"><BookOpen size={34} /><h3>Nenhum relatório encontrado</h3><p>{query || tag || fromDate || toDate ? 'Ajuste os filtros para ampliar a busca.' : 'Execute o agente para criar o primeiro relatório.'}</p></div>}
      {data && data.pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /> Anterior</button><span>Página {page} de {data.pages}</span><button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Próxima <ChevronRight size={16} /></button></div>}
    </section>
    <footer className="footer">Academic Pulse AI <span>·</span> Pesquisa com contexto, todos os dias.</footer>
  </main>
}

function Detail() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  useEffect(() => { getReport(id).then(setReport).catch(err => setError(err.message)) }, [id])
  async function copy() {
    if (!report) return
    try { await navigator.clipboard.writeText(report.markdown); setCopied(true); window.setTimeout(() => setCopied(false), 2000) }
    catch { setError('Não foi possível copiar o resumo.') }
  }
  if (error) return <main className="content"><button className="back-button" onClick={() => navigate('/')}><ArrowLeft size={17} /> Voltar</button><div className="empty-state"><h3>{error}</h3></div></main>
  if (!report) return <main className="content"><div className="loading">Carregando relatório...</div></main>
  return <main className="content detail-content"><Link className="back-button" to="/"><ArrowLeft size={17} /> Voltar ao radar</Link><div className="detail-header"><div><span className="section-overline">RELATÓRIO DIÁRIO · {formatDate(report.run_date, true)}</span><h1>{report.title}</h1><p>{report.overview}</p><div className="card-tags">{labels(report.papers.map(p => p.category))}</div></div><button className="secondary-button" onClick={copy}>{copied ? <Check size={16} /> : <Clipboard size={16} />}{copied ? 'Copiado!' : 'Copiar resumo'}</button></div><div className="detail-grid"><article className="markdown-card"><div className="panel-label"><Sparkles size={16} /> SÍNTESE DO DIA</div><div className="markdown-body"><ReactMarkdown components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children} <ExternalLink size={13} /></a> }}>{report.markdown}</ReactMarkdown></div></article><aside className="paper-panel"><div className="panel-label"><BookOpen size={16} /> FONTES ANALISADAS</div><p className="paper-count">{report.papers.length} artigos neste relatório</p>{report.papers.slice().sort((a, b) => b.relevance_score - a.relevance_score).map(paper => <a key={paper.id} className="paper-item" href={paper.url} target="_blank" rel="noopener noreferrer"><span className="paper-item-top"><span className={`tag tag-${paper.category.toLowerCase()}`}>{paper.category === 'EdTech' ? 'IA na Educação' : paper.category}</span><span className="score">{Math.round(paper.relevance_score)}/100</span></span><strong>{paper.title}</strong><span className="paper-source">{paper.source} <ExternalLink size={13} /></span></a>)}<div className="score-note">A nota indica relevância temática estimada pelo modelo; não mede citações ou impacto científico.</div></aside></div><footer className="footer">Academic Pulse AI <span>·</span> Pesquisa com contexto, todos os dias.</footer></main>
}

export default function App() {
  const { theme, toggle } = useTheme()
  return <Shell theme={theme} onTheme={toggle}><Routes><Route path="/" element={<Dashboard />} /><Route path="/reports/:id" element={<Detail />} /><Route path="*" element={<main className="content"><div className="empty-state"><h3>Página não encontrada</h3><Link to="/">Voltar ao radar</Link></div></main>} /></Routes></Shell>
}

