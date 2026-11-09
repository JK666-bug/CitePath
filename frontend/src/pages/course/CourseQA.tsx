import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import type { CourseDetail, QARecord } from './types'
import { askCourse, getQuestionHistory } from './api'
import { messageOf } from '../../shared/request'
import { Link } from '../../shared/router'
import { Notice, Sources } from '../../shared/components/UI'

type QuestionRequest = {
  question: string
  status: 'pending' | 'failed'
  error?: string
}

function mergeRecords(current: QARecord[], incoming: QARecord[]): QARecord[] {
  const records = new Map(
    [...current, ...incoming].map((record) => [record.qa_id, record]),
  )
  return [...records.values()].sort((first, second) => second.qa_id - first.qa_id)
}

export default function CourseQA({
  courseId,
  course,
}: {
  courseId: string
  course: CourseDetail
}) {
  const demo = courseId === 'demo'
  const usable = course.documents.some(
    (material) => material.ingest_status === 'complete' && material.usable_page_count > 0,
  )

  const [question, setQuestion] = useState('')
  const [records, setRecords] = useState<QARecord[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [pending, setPending] = useState<QuestionRequest | null>(null)
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(!demo)
  const [historyError, setHistoryError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)
  const [nextBeforeId, setNextBeforeId] = useState<number | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const busy = pending?.status === 'pending'

  useEffect(() => {
    if (demo) {
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setHistoryError('')
    setRecords([])
    setSelectedId(null)
    setPending(null)
    setNextBeforeId(null)

    void getQuestionHistory(course.id, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        const restored = mergeRecords([], result.records)
        setRecords(restored)
        setSelectedId(restored[0]?.qa_id ?? null)
        setNextBeforeId(result.next_before_id)
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setHistoryError(messageOf(reason))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    // 切换课程或离开页面时，避免旧历史请求覆盖当前页面。
    return () => controller.abort()
  }, [course.id, demo, reloadCount])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || loading || historyError || !usable || demo) return

    const text = question.trim()
    if (!text || Array.from(text).length > 2000) {
      setFormError('Enter a question of 1–2,000 characters.')
      return
    }

    setFormError('')
    setQuestion('')
    // 新问题立即显示在输入框下方，上一条问答此时进入右侧历史。
    setSelectedId(null)
    setPending({ question: text, status: 'pending' })

    try {
      const response = await askCourse(course.id, text)
      const record: QARecord = {
        ...response,
        question: response.question ?? text,
      }
      setRecords((current) => mergeRecords(current, [record]))
      setSelectedId(record.qa_id)
      setPending(null)
    } catch (reason) {
      // 请求失败不伪造历史记录，保留问题以便检查历史后重试。
      setPending({
        question: text,
        status: 'failed',
        error: `${messageOf(reason)} Reload history before retrying if the result is uncertain.`,
      })
      setQuestion(text)
    }
  }

  async function loadMore() {
    if (nextBeforeId === null || loadingMore || busy || loading) return
    setLoadingMore(true)
    setHistoryError('')
    try {
      const result = await getQuestionHistory(course.id, { beforeId: nextBeforeId })
      setRecords((current) => mergeRecords(current, result.records))
      setNextBeforeId(result.next_before_id)
    } catch (reason) {
      setHistoryError(messageOf(reason))
    } finally {
      setLoadingMore(false)
    }
  }

  const currentRecord: QARecord | undefined = demo
    ? {
        qa_id: -1,
        course_name: course.name,
        question: 'What is a binary tree?',
        answer: 'A binary tree is a tree in which a node has at most two children, conventionally called left and right.',
        cited_pages: [{ document_id: 101, filename: 'Algorithms-L6.pdf', page_number: 2 }],
        refused: false,
      }
    : records.find((record) => record.qa_id === selectedId)

  const history = records.filter((record) => record.qa_id !== selectedId)

  return (
    <div className="qa-page">
      <div className="qa-main stack">
        <section className="panel">
          <h2>Ask your course materials</h2>
          <p className="muted">
            Answers use this course’s uploaded PDFs and include source references.
            Questions do not change your practice scores.
          </p>

          {demo && (
            <Notice>
              This demo shows a fixed example. Live Q&A is available in real courses.
            </Notice>
          )}
          {!usable && !demo && (
            <Notice>
              No usable material is available.{' '}
              <Link href={`/courses/${courseId}/info`}>Upload a readable PDF first</Link>.
            </Notice>
          )}

          <form className="stack" noValidate onSubmit={submit}>
            <label className="field">
              <span>Your question</span>
              <textarea
                rows={4}
                value={question}
                maxLength={2000}
                disabled={busy || demo}
                onChange={(event) => {
                  setQuestion(event.target.value)
                  setFormError('')
                }}
                placeholder="Ask about this course’s materials."
              />
            </label>
            {formError && <Notice tone="error">{formError}</Notice>}
            <div className="actions">
              <button
                type="submit"
                className="button"
                disabled={busy || loading || Boolean(historyError) || !usable || demo}
              >
                {busy ? 'Searching your materials…' : 'Ask question'}
              </button>
              <small className="muted">Questions and answers are saved to this course.</small>
            </div>
          </form>
        </section>

        {pending ? (
          <section className="panel qa-answer" aria-busy={busy}>
            <p className="eyebrow">Your question</p>
            <h3>{pending.question}</h3>
            {busy ? (
              <p className="muted" role="status">Searching your materials…</p>
            ) : (
              <Notice tone="error">{pending.error}</Notice>
            )}
          </section>
        ) : currentRecord ? (
          <section className="panel qa-answer">
            <p className="eyebrow">Your question</p>
            <h3>{currentRecord.question}</h3>
            <span className={`badge ${currentRecord.refused ? 'warning' : ''}`}>
              {demo ? 'Fixed example' : currentRecord.refused ? 'Insufficient evidence' : 'Answer from your materials'}
            </span>
            <p className="answer-text">{currentRecord.answer}</p>
            <Sources materials={course.documents} sources={currentRecord.cited_pages} />
          </section>
        ) : (
          <p className="muted">{loading ? 'Loading question history…' : 'Ask a question to start.'}</p>
        )}
      </div>

      <aside className="panel qa-history" aria-labelledby="qa-history-title" aria-busy={loading || loadingMore}>
        <div className="actions spread">
          <h2 id="qa-history-title">Question history</h2>
          {!demo && (
            <button
              type="button"
              className="text-button"
              disabled={busy || loading || loadingMore}
              onClick={() => setReloadCount((current) => current + 1)}
            >
              Reload
            </button>
          )}
        </div>

        {historyError && <Notice tone="error">{historyError}</Notice>}
        {loading ? (
          <p className="muted">Loading history…</p>
        ) : history.length === 0 ? (
          <p className="muted small">
            {demo ? 'History is available in real courses.' : 'Earlier questions will appear here.'}
          </p>
        ) : (
          <ul className="qa-history-list">
            {history.map((record) => (
              <li key={record.qa_id}>
                <button
                  type="button"
                  className="qa-history-item"
                  disabled={busy}
                  title={record.question}
                  onClick={() => {
                    setSelectedId(record.qa_id)
                    setPending(null)
                    setFormError('')
                  }}
                >
                  <span>{record.question}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {!demo && nextBeforeId !== null && (
          <button
            type="button"
            className="button small secondary"
            disabled={busy || loadingMore || loading}
            onClick={() => void loadMore()}
          >
            {loadingMore ? 'Loading…' : 'Load older questions'}
          </button>
        )}
      </aside>
    </div>
  )
}
