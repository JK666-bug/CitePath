import { useStudy } from '../../shared/StudyProvider'
import { Link } from '../../shared/router'

import {
  DemoNotice,
  Notice,
  PageHeader,
  Sources,
} from '../../shared/components/UI'

import { demoQuestions } from '../course/demo'

export default function PracticeResult({
  chapterId,
}: {
  chapterId: string
}) {
  const {
    demo,
    completeTask,
    nextRound,
  } = useStudy()

  const session =
    demo.sessions[chapterId]

  const chapter =
    demo.plan.chapters.find(
      (item) => item.id === chapterId,
    )!

  const result =
    session.history.at(-1)!

  const questions = demoQuestions(
    demo,
    chapterId,
    result.round,
  )

  const review =
    demo.plan.tasks.find(
      (task) =>
        task.id === `review-${chapterId}`,
    )

  return (
    <div className="practice-session">
      <PageHeader
        eyebrow={
          `Sample result · Round ${result.round} of 2`
        }
        title={chapter.title}
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

      <section className="panel result-summary">
        <div className="result-score">
          {result.score}
          <span>%</span>
        </div>

        <div>
          <span
            className={
              `badge ${
                result.passed
                  ? ''
                  : 'warning'
              }`
            }
          >
            {result.passed
              ? 'Chapter passed'
              : session.status === 'Ended'
                ? 'Practice ended · Not yet passed'
                : 'Review recommended'}
          </span>

          <h2>
            {result.passed
              ? 'A clear step forward.'
              : 'Let’s revisit the weak concepts.'}
          </h2>

          <p className="muted small">
            Chapter pass mark: 80%.
            Short-answer point coverage: 80%.
            Sample questions are equally
            weighted.
          </p>
        </div>
      </section>

      <div className="stack result-questions">
        {questions.map(
          (question, index) => {
            const marked =
              result.questions.find(
                (item) =>
                  item.questionId ===
                  question.id,
              )!

            return (
              <section
                className="panel"
                key={question.id}
              >
                <div className="actions spread">
                  <h3>
                    Question {index + 1}
                  </h3>

                  <span
                    className={
                      `badge ${
                        marked.correct
                          ? ''
                          : 'warning'
                      }`
                    }
                  >
                    {marked.correct
                      ? 'Correct'
                      : 'Needs review'}
                  </span>
                </div>

                <p>{question.prompt}</p>

                <p className="muted answer-text">
                  <strong>
                    Your answer:
                  </strong>{' '}
                  {result.answers[
                    question.id
                  ]}
                </p>

                {question.kind ===
                  'short' && (
                  <p className="small muted">
                    Scoring points matched:
                    {' '}{marked.hits.length}
                    /{question.rubric.length}
                  </p>
                )}

                {!marked.correct && (
                  <div className="wrong-feedback">
                    <h3>
                      Review explanation
                    </h3>

                    <p>
                      {marked.explanation}
                    </p>

                    {question.kind ===
                      'mcq' && (
                      <p className="small">
                        Expected answer:
                        {' '}{question.correct}
                      </p>
                    )}

                    {question.kind ===
                      'short' && (
                      <p className="small">
                        Review points:
                        {' '}
                        {question.rubric.join(
                          ', ',
                        )}.
                      </p>
                    )}

                    <Sources
                      materials={demo.course.documents}
                      sources={
                        question.sources
                      }
                    />
                  </div>
                )}
              </section>
            )
          },
        )}
      </div>

      {session.status ===
        'Review required' && (
        <section className="panel stack">
          <h2>Review before round 2</h2>

          <p className="muted">
            Revisit{' '}
            {chapter.concepts.join(' and ')}
            {' '}using the sample source
            reference. The next round is
            available after review.
          </p>

          <Sources
            materials={demo.course.documents}
            sources={chapter.sources}
          />

          <div className="actions">
            <button
              className="button secondary"
              disabled={
                review?.status ===
                'Completed'
              }
              onClick={() =>
                review &&
                completeTask(review.id)
              }
            >
              {review?.status === 'Completed'
                ? 'Review completed'
                : 'Mark sample review complete'}
            </button>

            <button
              className="button"
              disabled={
                review?.status !==
                'Completed'
              }
              onClick={() =>
                nextRound(chapterId)
              }
            >
              Start round 2
            </button>
          </div>
        </section>
      )}

      {session.status === 'Ended' && (
        <Notice>
          {result.passed
            ? 'This sample chapter is complete. Your remaining sample tasks have been rescheduled.'
            : 'Two rounds are complete. This practice session has ended; there is no third round. Remaining weak concepts appear in the report.'}
        </Notice>
      )}

      <div className="actions">
        <Link
          className="button"
          href={
            `/practice/demo/${chapterId}/report`
          }
        >
          View chapter report
        </Link>

        <Link
          className="button secondary"
          href="/calendar?course=demo"
        >
          View sample calendar
        </Link>
      </div>
    </div>
  )
}
