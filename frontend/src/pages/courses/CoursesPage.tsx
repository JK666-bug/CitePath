import { useState } from 'react'
import { Plus } from 'lucide-react'

import { useStudy } from '../../shared/StudyProvider'
import { Link } from '../../shared/router'

import {
  Empty,
  Loading,
  Notice,
  PageHeader,
} from '../../shared/components/UI'

import { decodeBrief } from '../courseEditor/brief'
import CourseCard from './CourseCard'

import './courses.css'

export default function CoursesPage() {
  const {
    courses,
    coursesLoading,
    coursesError,
    refreshCourses,
    demo,
  } = useStudy()

  const [deadlineFirst, setDeadlineFirst] =
    useState(true)

  const [showDemo, setShowDemo] =
    useState(false)

  const sorted = [...courses].sort(
    (a, b) =>
      deadlineFirst
        ? (
            decodeBrief(a.student_brief)
              .deadline || '9999'
          ).localeCompare(
            decodeBrief(b.student_brief)
              .deadline || '9999',
          ) || b.id - a.id
        : b.id - a.id,
  )

  return (
    <div className="courses-page">
      <PageHeader
        eyebrow="Your study space"
        title="My courses"
        subtitle="A clear overview of your goals, materials, and next steps."
        actions={
          <Link
            className="button"
            href="/courses/new"
          >
            <Plus size={16} />
            New course
          </Link>
        }
      />

      <div className="courses-toolbar">
        <p className="muted">
          {courses.length}{' '}
          {courses.length === 1
            ? 'course'
            : 'courses'}
          {' · '}
          {courses.reduce(
            (sum, course) =>
              sum + course.document_count,
            0,
          )}{' '}
          saved materials
        </p>

        <label className="toggle-label">
          <input
            type="checkbox"
            checked={deadlineFirst}
            onChange={(event) =>
              setDeadlineFirst(
                event.target.checked,
              )
            }
          />
          Deadline first
        </label>
      </div>

      {coursesError && (
        <Notice tone="error">
          {coursesError}{' '}
          <button
            className="text-button"
            onClick={() =>
              void refreshCourses()
            }
          >
            Try again
          </button>
        </Notice>
      )}

      {coursesLoading ? (
        <Loading text="Loading your courses…" />
      ) : sorted.length ? (
        <div className="course-grid">
          {sorted.map((course, index) => (
            <CourseCard
              key={course.id}
              course={course}
              index={index}
            />
          ))}
        </div>
      ) : (
        !coursesError && (
          <Empty title="Your first course starts here">
            <p>
              Add your course materials, goals,
              and available study time.
            </p>

            <div className="actions centered">
              <Link
                className="button"
                href="/courses/new"
              >
                Create a course
              </Link>
            </div>
          </Empty>
        )
      )}

      <section className="demo-preview">
        <div className="actions spread">
          <div>
            <h2>
              Preview the complete interface
            </h2>

            <p className="muted small">
              Explore a sample calendar, plan,
              practice session, and report.
              No sample data is added to your
              real courses.
            </p>
          </div>

          <button
            className="button secondary"
            onClick={() =>
              setShowDemo((value) => !value)
            }
          >
            {showDemo
              ? 'Hide sample card'
              : 'Show sample card'}
          </button>
        </div>

        {showDemo && (
          <div className="course-grid">
            <CourseCard
              demo
              course={{
                ...demo.course,
                document_count:
                  demo.course.documents.length,
              }}
              plan={demo.plan}
            />
          </div>
        )}

        <Link
          href="/courses/demo/plan"
          className="text-button"
        >
          Open interface demo
        </Link>
      </section>
    </div>
  )
}