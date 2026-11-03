import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import type { ReactNode } from 'react'

import { getCourses } from '../pages/courses/api'
import type { CourseSummary } from '../pages/courses/api'

import { getCourse } from '../pages/course/api'

import {
  createDemo,
  nextDemoRound,
  scheduleDemo,
  startDemoSession,
  submitDemo,
} from '../pages/course/demo'

import type {
  CourseConfig,
  CourseDetail,
  DemoState,
} from '../pages/course/types'

import { encodeBrief } from '../pages/courseEditor/brief'
import { messageOf } from './request'

function loadDemo(key: string): DemoState {
  try {
    const raw = localStorage.getItem(key)

    if (raw) {
      const value = JSON.parse(raw) as DemoState

      if (
        value.schema === 1 &&
        value.course?.id === -1 &&
        Array.isArray(value.course.documents) &&
        Array.isArray(value.plan?.tasks) &&
        Array.isArray(value.plan.chapters) &&
        value.sessions &&
        typeof value.sessions === 'object'
      ) {
        return value
      }
    }
  } catch {
    // Start a fresh demo if storage is unavailable.
  }

  return createDemo()
}

function useStudyValue(userId: number) {
  const key =
    `citepath-interface-demo-v1-${userId}`

  const [courses, setCourses] =
    useState<CourseSummary[]>([])

  const [coursesLoading, setCoursesLoading] =
    useState(true)

  const [coursesError, setCoursesError] =
    useState('')

  const [details, setDetails] = useState<
    Record<number, CourseDetail>
  >({})

  const [demo, setDemo] = useState<DemoState>(
    () => loadDemo(key),
  )

  const [storageError, setStorageError] =
    useState('')

  const refreshCourses = useCallback(async () => {
    setCoursesLoading(true)
    setCoursesError('')

    try {
      setCourses(await getCourses())
    } catch (error) {
      setCoursesError(messageOf(error))
    } finally {
      setCoursesLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshCourses()
  }, [refreshCourses])

  useEffect(() => {
    try {
      localStorage.setItem(
        key,
        JSON.stringify(demo),
      )

      setStorageError('')
    } catch {
      setStorageError(
        'Demo changes cannot be saved in this browser. Keep this tab open to retain your current session.',
      )
    }
  }, [demo, key])

  const loadCourse = useCallback(
    async (id: number) => {
      const result = await getCourse(id)

      setDetails((current) => ({
        ...current,
        [id]: result,
      }))

      return result
    },
    [],
  )

  function editDemo(
    name: string,
    config: CourseConfig,
  ) {
    setDemo((current) => ({
      ...current,
      course: {
        ...current.course,
        name,
        student_brief: encodeBrief(config),
      },
      plan: scheduleDemo(
        current.plan,
        config,
        'Sample course settings changed; completed tasks were preserved.',
      ),
    }))
  }

  function completeTask(id: string) {
    setDemo((current) => ({
      ...current,
      plan: {
        ...current.plan,
        tasks: current.plan.tasks.map((task) =>
          task.id === id &&
          task.kind !== 'Practice'
            ? { ...task, status: 'Completed' }
            : task,
        ),
      },
    }))
  }

  function setAnswer(
    chapterId: string,
    questionId: string,
    answer: string,
  ) {
    setDemo((current) => {
      const session =
        current.sessions[chapterId]

      if (
        !session ||
        session.status !== 'Answering'
      ) {
        return current
      }

      return {
        ...current,
        sessions: {
          ...current.sessions,
          [chapterId]: {
            ...session,
            answers: {
              ...session.answers,
              [questionId]: answer,
            },
          },
        },
      }
    })
  }

  return {
    courses,
    coursesLoading,
    coursesError,
    refreshCourses,
    details,
    loadCourse,
    demo,
    storageError,
    editDemo,
    completeTask,
    setAnswer,

    startPractice: (id: string) =>
      setDemo((current) =>
        startDemoSession(current, id),
      ),

    submitPractice: (id: string) =>
      setDemo((current) =>
        submitDemo(current, id),
      ),

    nextRound: (id: string) =>
      setDemo((current) =>
        nextDemoRound(current, id),
      ),

    resetDemo: () => setDemo(createDemo()),
  }
}

const StudyContext = createContext<
  ReturnType<typeof useStudyValue> | null
>(null)

export function StudyProvider({
  userId,
  children,
}: {
  userId: number
  children: ReactNode
}) {
  const value = useStudyValue(userId)

  return (
    <StudyContext.Provider value={value}>
      {children}
    </StudyContext.Provider>
  )
}

export function useStudy() {
  const value = useContext(StudyContext)

  if (!value) {
    throw new Error(
      'StudyProvider is required.',
    )
  }

  return value
}

export function useCourse(id: string) {
  const {
    demo,
    details,
    loadCourse,
  } = useStudy()

  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  const valid =
    id === 'demo' ||
    /^[1-9]\d*$/.test(id)

  useEffect(() => {
    if (id === 'demo' || !valid) {
      return
    }

    let active = true
    setError('')

    loadCourse(Number(id)).catch((reason) => {
      if (active) {
        setError(messageOf(reason))
      }
    })

    return () => {
      active = false
    }
  }, [id, valid, loadCourse, attempt])

  return {
    course:
      id === 'demo'
        ? demo.course
        : details[Number(id)],

    error: !valid
      ? 'This course could not be found.'
      : error,

    retry: () =>
      setAttempt((current) => current + 1),

    isDemo: id === 'demo',
  }
}