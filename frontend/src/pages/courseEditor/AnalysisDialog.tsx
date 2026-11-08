import { LoaderCircle } from 'lucide-react'

import { Link } from '../../shared/router'

import {
  Modal,
  Notice,
} from '../../shared/components/UI'

export default function AnalysisDialog({
  open,
  busy,
  status,
  error,
  demo,
  courseId,
  onClose,
}: {
  open: boolean
  busy: boolean
  status: string
  error: string
  demo: boolean
  courseId: string
  onClose: () => void
}) {
  const title = busy
    ? 'Preparing your course'
    : error
      ? 'Action required'
      : demo
        ? 'Sample schedule updated'
        : 'Course saved'

  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      closeable={!busy}
    >
      <div className="stack">
        {busy && (
          <LoaderCircle
            className="spin"
            size={26}
          />
        )}

        <p aria-live="polite">
          {status}
        </p>

        {error ? (
          <Notice tone="error">
            {error}
          </Notice>
        ) : (
          !busy && (
            <Notice>
              {demo
                ? 'The sample schedule was recalculated locally. Completed tasks were preserved. No AI analysis was performed.'
                : 'Your course is saved. Automatic study-time estimation and plan generation require the planning service, which is not connected yet.'}
            </Notice>
          )
        )}

        {!busy && (
          <div className="actions">
            {demo ? (
              <Link
                className="button"
                href="/calendar?course=demo"
              >
                View sample calendar
              </Link>
            ) : (
              courseId && (
                <Link
                  className="button"
                  href={
                    `/courses/${courseId}/info`
                  }
                >
                  View saved course
                </Link>
              )
            )}

            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              {error
                ? 'Back to form'
                : 'Close'}
            </button>
          </div>
        )}
      </div>
    </Modal>
  )
}