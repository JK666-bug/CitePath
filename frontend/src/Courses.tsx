import { useEffect, useState } from 'react'
import './App.css'
import { readJson } from './api'
import { Bar } from './Bar'

type Course = {
  id: number
  name: string
  student_brief: string
  created_at: string
  document_count: number
}

export default function Courses({ username }: { username: string }) {
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/courses')
      .then(readJson)
      .then((payload) => setCourses(payload.courses ?? []))
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="page">
      <Bar username={username} />
      <div className="title-row">
        <header>
          <p className="eyebrow">Courses</p>
          <h1>My courses</h1>
          <p className="lead">Choose a course to continue, or start a new one and upload lectures.</p>
        </header>
        <a className="button-link" href="/courses/new">
          New course
        </a>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p className="lead">Loading courses…</p> : null}
      {!loading && courses.length === 0 ? <p className="card empty">No courses yet.</p> : null}
      <div className="course-list">
        {courses.map((course) => (
          <a key={course.id} className="card course-card" href={`/courses/${course.id}`}>
            <span className="pill">
              {course.document_count} {course.document_count === 1 ? 'PDF' : 'PDFs'}
            </span>
            <strong>{course.name}</strong>
            <span className="meta">{course.created_at}</span>
            <span className="brief">{course.student_brief}</span>
          </a>
        ))}
      </div>
    </main>
  )
}
