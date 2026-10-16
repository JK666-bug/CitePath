import { FormEvent, useState } from 'react'
import './App.css'

type StoredPage = {
  page_number: number
  chapter: string
  usable: boolean
  excerpt: string
}

type UploadResult = {
  document_id: number
  plan_id: number
  filename: string
  ingest_status: string
  plan_status: string
  student_brief: string
  page_count: number
  usable_page_count: number
  milvus_segments: number
  pages: StoredPage[]
}

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [brief, setBrief] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<UploadResult | null>(null)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult(null)
    if (!file) {
      setError('请选择一份 PDF 讲义')
      return
    }
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('请上传 PDF 文件')
      return
    }
    const text = brief.trim()
    if (!text) {
      setError('请用一段话写下学习目标和日期')
      return
    }

    const body = new FormData()
    body.append('file', file)
    body.append('student_brief', text)
    setSubmitting(true)
    try {
      const response = await fetch('/api/uploads', { method: 'POST', body })
      const payload = await response.json()
      if (!response.ok) {
        setError(typeof payload.detail === 'string' ? payload.detail : '保存失败')
        return
      }
      setResult(payload)
    } catch {
      setError('无法连接服务器')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page">
      <header>
        <p className="eyebrow">CitePath</p>
        <h1>上传讲义</h1>
        <p className="lead">
          选择课程 PDF，并用一段话写下学习目标和日期。这段话会原样存进数据库，稍后再用来生成学习任务。
        </p>
      </header>

      <form className="card" onSubmit={onSubmit}>
        <label>
          讲义 PDF
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          学习说明
          <textarea
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            rows={6}
            placeholder="例如：我想在 11 月 20 日前掌握排序和哈希，每周能学 6 小时，重点看考试会考的部分。"
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? '正在保存…' : '保存到数据库'}
        </button>
        {error ? <p className="error">{error}</p> : null}
      </form>

      {result ? (
        <section className="card result">
          <h2>已保存</h2>
          <p>
            文档 {result.document_id}，计划 {result.plan_id}，状态 {result.plan_status}。共 {result.page_count} 页，其中 {result.usable_page_count} 页可以引用。Milvus 写入 {result.milvus_segments} 条，按文档编号和页码对应原文。
          </p>
          <p className="brief">{result.student_brief}</p>
          <ul>
            {result.pages.map((page) => (
              <li key={page.page_number}>
                <strong>第 {page.page_number} 页</strong>
                <span>{page.chapter}</span>
                <span>{page.usable ? page.excerpt || '（无摘录）' : '抽不出文字'}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  )
}
