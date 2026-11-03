import { Link } from '../../shared/router'

import {
  useCourse,
  useStudy,
} from '../../shared/StudyProvider'

import {
  DemoNotice,
  Loading,
  Notice,
  PageHeader,
} from '../../shared/components/UI'

import CoursePlan from './CoursePlan'
import CourseInfo from './CourseInfo'
import CourseQA from './CourseQA'

import './course.css'

export default function CoursePage({
  courseId,
  tab,
}: {
  courseId: string
  tab: string
}) {
  const { resetDemo } = useStudy()

  const {
    course,
    error,
    retry,
    isDemo,
  } = useCourse(courseId)

  if (error) {
    return (
      <Notice tone="error">
        {error}{' '}
        <button
          className="text-button"
          onClick={retry}
        >
          Try again
        </button>
      </Notice>
    )
  }

  if (!course) {
    return (
      <Loading text="Loading your course…" />
    )
  }

  return (
    <div className="course-page">
      <PageHeader
        eyebrow={
          isDemo
            ? 'Interface demo course'
            : 'Your learning path'
        }
        title={course.name}
        actions={
          <>
            {isDemo && (
              <button
                className="button secondary"
                onClick={() => {
                  if (
                    window.confirm(
                      'Reset all sample settings, tasks, answers, and reports in this browser?',
                    )
                  ) {
                    resetDemo()
                  }
                }}
              >
                Reset demo
              </button>
            )}

            <Link
              className="button secondary"
              href={
                `/courses/${courseId}/edit`
              }
            >
              Edit course
            </Link>
          </>
        }
      />

      {isDemo && <DemoNotice />}

      <nav
        className="course-tabs"
        aria-label="Course sections"
      >
        {[
          ['plan', 'Plan'],
          ['info', 'Course information'],
          ['qa', 'Q&A'],
        ].map(([key, label]) => (
          <Link
            href={
              `/courses/${courseId}/${key}`
            }
            key={key}
            aria-current={
              tab === key
                ? 'page'
                : undefined
            }
          >
            {label}
          </Link>
        ))}
      </nav>

      {tab === 'plan' ? (
        <CoursePlan
          courseId={courseId}
          course={course}
        />
      ) : tab === 'info' ? (
        <CourseInfo
          courseId={courseId}
          course={course}
        />
      ) : (
        <CourseQA
          key={courseId}
          courseId={courseId}
          course={course}
        />
      )}
    </div>
  )
}