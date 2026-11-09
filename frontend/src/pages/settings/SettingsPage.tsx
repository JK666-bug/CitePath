import { useState } from 'react'
import { Loading, Notice, PageHeader } from '../../shared/components/UI'
import { duration } from '../../shared/format'
import { messageOf } from '../../shared/request'
import { useStudy } from '../../shared/StudyProvider'
import {
  DEFAULT_AVAILABILITY,
  MAX_DAILY_MINUTES,
  type StudyAvailability,
} from './availability'
import './settings.css'

const DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

const STEP_MINUTES = 15

export default function SettingsPage() {
  const {
    studyAvailability,
    studyAvailabilitySaved,
    browserStudyAvailability,
    availabilityError,
    retryStudyAvailability,
    updateStudyAvailability,
  } = useStudy()

  // Only offer the old browser values if this account has never saved settings.
  const browserDraft = studyAvailabilitySaved ? null : browserStudyAvailability

  return (
    <div className="study-settings stack">
      <PageHeader title="Settings" />

      {availabilityError ? (
        <div className="stack">
          <Notice tone="error">{availabilityError}</Notice>
          <div className="actions">
            <button
              className="button secondary"
              type="button"
              onClick={retryStudyAvailability}
            >
              Try again
            </button>
          </div>
        </div>
      ) : studyAvailability === null ? (
        <Loading text="Loading study availability…" />
      ) : (
        <AvailabilityForm
          availability={studyAvailability}
          saved={studyAvailabilitySaved}
          browserDraft={browserDraft}
          onSave={updateStudyAvailability}
        />
      )}
    </div>
  )
}

function AvailabilityForm({
  availability,
  saved,
  browserDraft,
  onSave,
}: {
  availability: StudyAvailability
  saved: boolean
  browserDraft: StudyAvailability | null
  onSave: (value: StudyAvailability) => Promise<void>
}) {
  // Mount after the account response so the draft starts from real settings.
  const [draft, setDraft] = useState(() => [...(browserDraft ?? availability)])
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{
    tone: 'success' | 'error'
    text: string
  } | null>(null)

  const weeklyMinutes = draft.reduce((sum, minutes) => sum + minutes, 0)
  const changed = draft.some(
    (minutes, index) => minutes !== availability[index],
  )

  function adjustDay(index: number, change: number) {
    setFeedback(null)

    setDraft((current) => current.map((minutes, day) =>
      day === index
        ? Math.min(MAX_DAILY_MINUTES, Math.max(0, minutes + change))
        : minutes,
    ))
  }

  async function save() {
    setFeedback(null)
    setSaving(true)
    try {
      await onSave(draft)
      setFeedback({ tone: 'success', text: 'Study availability saved.' })
    } catch (error) {
      setFeedback({ tone: 'error', text: messageOf(error) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="panel stack" aria-labelledby="availability-title">
      <div className="actions spread">
        <div>
          <h2 id="availability-title">Study availability</h2>
          <p className="muted small">
            Set a daily time limit shared by all your courses.
          </p>
        </div>

        <strong>{duration(weeklyMinutes)} / week</strong>
      </div>

      {browserDraft && (
        <Notice>
          Previous settings from this browser are shown below. Save them to your account.
        </Notice>
      )}

      <div className="availability-grid">
        {DAYS.map((day, index) => (
          <div className="availability-day" key={day}>
            <strong>{day}</strong>

            <div className="availability-stepper" role="group" aria-label={day}>
              <button
                className="icon-button"
                type="button"
                aria-label={`Decrease ${day} by 15 minutes`}
                disabled={saving || draft[index] === 0}
                onClick={() => adjustDay(index, -STEP_MINUTES)}
              >
                −
              </button>

              <output aria-label={`${day} available study time`}>
                {duration(draft[index])}
              </output>

              <button
                className="icon-button"
                type="button"
                aria-label={`Increase ${day} by 15 minutes`}
                disabled={saving || draft[index] === MAX_DAILY_MINUTES}
                onClick={() => adjustDay(index, STEP_MINUTES)}
              >
                +
              </button>
            </div>

            <button
              className="text-button"
              type="button"
              disabled={saving || draft[index] === 0}
              onClick={() => adjustDay(index, -draft[index])}
            >
              Set as rest day
            </button>
          </div>
        ))}
      </div>

      <p className="muted small">
        Days set to zero are rest days. Settings are saved to your account.
      </p>

      {feedback && <Notice tone={feedback.tone}>{feedback.text}</Notice>}

      <div className="actions">
        <button
          className="button"
          type="button"
          onClick={() => void save()}
          disabled={saving || (saved && !changed)}
        >
          {saving ? 'Saving…' : 'Save availability'}
        </button>

        <button
          className="button secondary"
          type="button"
          disabled={saving}
          onClick={() => {
            setDraft([...DEFAULT_AVAILABILITY])
            setFeedback(null)
          }}
        >
          Reset to defaults
        </button>
      </div>
    </section>
  )
}
