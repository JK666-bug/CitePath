import { useState } from 'react'
import type { FormEvent } from 'react'

import type {
  CourseDetail,
  QAResponse,
} from './types'

import { askCourse } from './api'
import { messageOf } from '../../shared/request'
import { Link } from '../../shared/router'

import {
  Notice,
  Sources,
} from '../../shared/components/UI'

export default function CourseQA({
  courseId,
  course,
}: {
  courseId: string
  course: CourseDetail
}) {
  const demo = courseId === 'demo'

  const usable =
    course.documents.some(
      (material) =>
        material.ingest_status ===
          'complete' &&
        material.usable_page_count > 0,
    )

  const [question, setQuestion] =
    useState('')

  const [records, setRecords] = useState<
    {
      question: string
      response: QAResponse
    }[]
  >([])

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (busy || !usable || demo) return

    const text = question.trim()

    if (
      !text ||
      Array.from(text).length > 2000
    ) {
      setError(
        'Enter a question of 1–2,000 characters.',
      )
      return
    }

    setBusy(true)
    setError('')

    try {
      const response = await askCourse(
        course.id,
        text,
      )

      setRecords((current) => [
        ...current,
        {
          question: text,
          response,
        },
      ])

      setQuestion('')
    } catch (reason) {
      setError(messageOf(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="qa-page stack">
      <section className="panel">
        <h2>Ask your course materials</h2>

        <p className="muted">
          Answers use this course’s uploaded
          PDFs and include source references.
          Questions do not change your
          practice scores.
        </p>

        {demo && (
          <Notice>
            Live Q&A is available in real
            courses. This demo shows a fixed
            example only; submitting questions
            is disabled.
          </Notice>
        )}

        {!usable && (
          <Notice>
            No usable material is available.
            {' '}
            <Link
              href={
                `/courses/${courseId}/info`
              }
            >
              Upload a readable PDF first
            </Link>.
          </Notice>
        )}

        <form
          className="stack"
          noValidate
          onSubmit={submit}
        >
          <label className="field">
            <span>Your question</span>

            <textarea
              rows={4}
              value={question}
              maxLength={2000}
              disabled={busy || demo}
              onChange={(event) => {
                setQuestion(
                  event.target.value,
                )
                setError('')
              }}
              placeholder="What does this lecture say about breadth-first search?"
            />
          </label>

          {error && (
            <Notice tone="error">
              {error}
            </Notice>
          )}

          <div className="actions">
            <button
              className="button"
              disabled={
                busy || !usable || demo
              }
            >
              {busy
                ? 'Searching your materials…'
                : 'Ask question'}
            </button>

            <small className="muted">
              Answers in this view are not
              restored after refresh.
            </small>
          </div>
        </form>
      </section>

      {demo && (
        <section className="panel qa-answer">
          <span className="badge">
            Fixed example
          </span>

          <h3>What is a binary tree?</h3>

          <p>
            A binary tree is a tree in which a
            node has at most two children,
            conventionally called left and
            right.
          </p>

          <Sources
            sources={[
              {
                document_id: 101,
                filename:
                  'Algorithms-L6.pdf',
                page_number: 2,
              },
            ]}
          />
        </section>
      )}

      {records.map((record, index) => (
        <section
          className="panel qa-answer"
          key={
            `${record.response.qa_id}-${index}`
          }
        >
          <p className="eyebrow">
            Your question
          </p>

          <h3>{record.question}</h3>

          <span
            className={
              `badge ${
                record.response.refused
                  ? 'warning'
                  : ''
              }`
            }
          >
            {record.response.refused
              ? 'Insufficient evidence'
              : 'Answer from your materials'}
          </span>

          <p className="answer-text">
            {record.response.answer}
          </p>

          <Sources
            sources={
              record.response.cited_pages
            }
          />

          <small className="muted">
            Record {record.response.qa_id}
            {' · '}
            {record.response.course_name}
          </small>
        </section>
      ))}
    </div>
  )
}