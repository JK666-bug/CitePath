import { useState } from 'react'
import type { FormEvent } from 'react'

import { useStudy } from '../../shared/StudyProvider'
import { Link } from '../../shared/router'

import {
  DemoNotice,
  Empty,
  Notice,
  PageHeader,
} from '../../shared/components/UI'

import { demoQuestions } from '../course/demo'

import QuestionCard from './QuestionCard'
import PracticeResult from './PracticeResult'

import './practice.css'

export default function PracticeSessionPage({
  courseId,
  chapterId,
}: {
  courseId: string
  chapterId: string
}) {
  const {
    demo,
    startPractice,
    setAnswer,
    submitPractice,
    storageError,
  } = useStudy()

  const [error, setError] = useState('')

  if (courseId !== 'demo') {
    return (
      <Empty title="Practice service not connected">
        <p>
          Real practice sessions require B’s
          existing module and API contract.
        </p>

        <Link href="/practice">
          Back to chapter practice
        </Link>
      </Empty>
    )
  }

  const chapter =
    demo.plan.chapters.find(
      (item) => item.id === chapterId,
    )

  if (!chapter) {
    return (
      <Empty title="Chapter not found">
        <Link href="/practice?course=demo">
          Back to sample practice
        </Link>
      </Empty>
    )
  }

  const session =
    demo.sessions[chapterId]

  const questions = demoQuestions(
    demo,
    chapterId,
    session?.round || 1,
  )

  if (!session) {
    return (
      <div className="practice-session">
        <PageHeader
          eyebrow="Interface demo"
          title={chapter.title}
        />

        <DemoNotice />

        <section className="panel stack">
          <h2>Before you begin</h2>

          <p>
            This fixed sample has one
            multiple-choice and one short-answer
            question. Each question has equal
            weight. The sample chapter pass
            mark is 80%.
          </p>

          <p className="muted">
            The short answer uses a simple
            keyword check for the interface
            demo. The real B module remains
            responsible for AI grading and
            evidence-based feedback.
          </p>

          <div className="actions">
            <button
              className="button"
              onClick={() =>
                startPractice(chapterId)
              }
            >
              Start sample practice
            </button>

            <Link href="/courses/demo/plan">
              Back to plan
            </Link>
          </div>
        </section>
      </div>
    )
  }

  if (
    session.status !== 'Answering'
  ) {
    return (
      <PracticeResult
        chapterId={chapterId}
      />
    )
  }

  const answered = questions.filter(
    (question) =>
      session.answers[
        question.id
      ]?.trim(),
  ).length

  function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const missing = questions.find(
      (question) =>
        !session.answers[
          question.id
        ]?.trim(),
    )

    if (missing) {
      setError(
        'Please answer every question before submitting.',
      )

      document
        .getElementById(missing.id)
        ?.focus()

      return
    }

    setError('')
    submitPractice(chapterId)
  }

  return (
    <div className="practice-session">
      <PageHeader
        eyebrow={
          `Interface demo · Round ${session.round} of 2`
        }
        title={chapter.title}
        subtitle={
          `${answered} of ${questions.length} questions answered`
        }
        actions={
          <Link
            className="button secondary"
            href="/courses/demo/plan"
          >
            Back to plan
          </Link>
        }
      />

      <DemoNotice />

      <div
        className="practice-save-status"
        role="status"
      >
        {storageError
          ? 'Local saving is unavailable. Keep this tab open.'
          : 'Answers are saved locally in this browser. Refresh to resume the same questions.'}
      </div>

      <form
        className="stack"
        noValidate
        onSubmit={submit}
      >
        {questions.map(
          (question, index) => (
            <QuestionCard
              key={question.id}
              question={question}
              index={index}
              answer={
                session.answers[
                  question.id
                ] || ''
              }
              onChange={(answer) => {
                setAnswer(
                  chapterId,
                  question.id,
                  answer,
                )
                setError('')
              }}
            />
          ),
        )}

        {error && (
          <Notice tone="error">
            {error}
          </Notice>
        )}

        <div className="actions spread">
          <span className="muted small">
            Submission locks this round’s
            answers. No live model is called.
          </span>

          <button className="button">
            Submit sample answers
          </button>
        </div>
      </form>
    </div>
  )
}