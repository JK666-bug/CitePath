import {
  addDays,
  dateKey,
  percent,
} from '../../shared/format.ts'

import {
  decodeBrief,
  encodeBrief,
} from '../courseEditor/brief.ts'

import type {
  CourseConfig,
  DemoState,
  Question,
  StudyPlan,
  Task,
} from './types.ts'

export function scheduleDemo(
  plan: StudyPlan,
  config: CourseConfig,
  reason: string,
): StudyPlan {
  let allocated = 0

  const dailyMinutes = Math.max(
    1,
    (config.weeklyHours * 60) / 7,
  )

  return {
    ...plan,
    version: plan.version + 1,
    reason,
    tasks: plan.tasks.map((task) => {
      if (task.status === 'Completed') {
        return task
      }

      const date = addDays(
        dateKey(),
        Math.floor(allocated / dailyMinutes),
      )

      allocated += task.minutes

      return { ...task, date }
    }),
  }
}

export function createDemo(): DemoState {
  const config: CourseConfig = {
    deadline: addDays(dateKey(), 21),
    weeklyHours: 6,
    earlyDays: 2,
    note:
      'Prepare for the algorithms exam. Focus on trees, graphs, and dynamic programming. I know basic Python.',
  }

  const chapters = [
    {
      id: 'trees',
      title: 'Binary trees',
      concepts: ['Binary tree', 'Traversal'],
      sources: [
        {
          document_id: 101,
          filename: 'Algorithms-L6.pdf',
          page_number: 2,
        },
      ],
    },
    {
      id: 'graphs',
      title: 'Graph search',
      concepts: [
        'Breadth-first search',
        'Queue',
      ],
      sources: [
        {
          document_id: 102,
          filename: 'Algorithms-L7.pdf',
          page_number: 4,
        },
      ],
    },
    {
      id: 'dp',
      title: 'Dynamic programming',
      concepts: [
        'Overlapping subproblems',
        'Memoization',
      ],
      sources: [
        {
          document_id: 103,
          filename: 'Algorithms-L8.pdf',
          page_number: 3,
        },
      ],
    },
  ]

  const tasks: Task[] = chapters.flatMap(
    (chapter) => [
      {
        id: `read-${chapter.id}`,
        chapterId: chapter.id,
        title: `Read: ${chapter.title}`,
        kind: 'Reading' as const,
        date: dateKey(),
        minutes: 35,
        status: 'Not started' as const,
        sources: chapter.sources,
        concepts: chapter.concepts,
      },
      {
        id: `practice-${chapter.id}`,
        chapterId: chapter.id,
        title: `Practice: ${chapter.title}`,
        kind: 'Practice' as const,
        date: dateKey(),
        minutes: 25,
        status: 'Not started' as const,
        sources: chapter.sources,
        concepts: chapter.concepts,
      },
    ],
  )

  return {
    schema: 1,
    course: {
      id: -1,
      name: 'Algorithms & Data Structures',
      student_brief: encodeBrief(config),
      created_at: dateKey(),
      documents: chapters.map(
        (chapter, index) => ({
          id: chapter.sources[0].document_id,
          filename: chapter.sources[0].filename,
          ingest_status: 'complete',
          page_count: 12 + index,
          usable_page_count: 12 + index,
        }),
      ),
    },
    plan: scheduleDemo(
      {
        version: 0,
        start: dateKey(),
        tasks,
        chapters,
        reason: '',
      },
      config,
      'Initial sample schedule. No model was called.',
    ),
    sessions: {},
  }
}

export function demoQuestions(
  state: DemoState,
  chapterId: string,
  round: 1 | 2,
): Question[] {
  const chapter = state.plan.chapters.find(
    (item) => item.id === chapterId,
  )

  if (!chapter) return []

  const examples: Record<
    string,
    {
      prompt: string
      options: string[]
      correct: string
      short: string
      rubric: string[]
      explanation: string
    }
  > = {
    trees: {
      prompt:
        'How many children can a binary-tree node have at most?',
      options: [
        'One',
        'Two',
        'Three',
        'Unlimited',
      ],
      correct: 'Two',
      short:
        'Describe a binary tree using the terms binary, two, left, right, and child.',
      rubric: [
        'binary',
        'two',
        'left',
        'right',
        'child',
      ],
      explanation:
        'A binary-tree node has at most two children, conventionally called left and right.',
    },

    graphs: {
      prompt:
        'Which data structure is conventionally used by breadth-first search?',
      options: [
        'Queue',
        'Stack only',
        'Heap only',
        'Sorted array only',
      ],
      correct: 'Queue',
      short:
        'Explain BFS using the terms queue, breadth, first, level, and visited.',
      rubric: [
        'queue',
        'breadth',
        'first',
        'level',
        'visited',
      ],
      explanation:
        'Breadth-first search uses a queue to explore successive levels and tracks visited vertices.',
    },

    dp: {
      prompt:
        'What does memoization store?',
      options: [
        'Previously computed subproblem results',
        'Only input filenames',
        'Random guesses',
        'Only the final source code',
      ],
      correct:
        'Previously computed subproblem results',
      short:
        'Explain memoization using the terms store, result, subproblem, reuse, and overlapping.',
      rubric: [
        'store',
        'result',
        'subproblem',
        'reuse',
        'overlapping',
      ],
      explanation:
        'Memoization stores subproblem results for reuse when overlapping subproblems recur.',
    },
  }

  const example = examples[chapterId]

  if (!example) return []

  return [
    {
      id: `${chapterId}-${round}-mcq`,
      kind: 'mcq',
      prompt:
        `${round === 2 ? 'Round 2 check: ' : ''}` +
        example.prompt,
      options: example.options,
      correct: example.correct,
      rubric: [],
      explanation: example.explanation,
      sources: chapter.sources,
    },
    {
      id: `${chapterId}-${round}-short`,
      kind: 'short',
      prompt: example.short,
      options: [],
      correct: '',
      rubric: example.rubric,
      explanation: example.explanation,
      sources: chapter.sources,
    },
  ]
}

export function startDemoSession(
  state: DemoState,
  chapterId: string,
): DemoState {
  if (
    state.sessions[chapterId] ||
    !state.plan.chapters.some(
      (chapter) => chapter.id === chapterId,
    )
  ) {
    return state
  }

  return {
    ...state,
    sessions: {
      ...state.sessions,
      [chapterId]: {
        chapterId,
        round: 1,
        status: 'Answering',
        answers: {},
        history: [],
      },
    },
    plan: {
      ...state.plan,
      tasks: state.plan.tasks.map((task) =>
        task.id === `practice-${chapterId}`
          ? { ...task, status: 'In progress' }
          : task,
      ),
    },
  }
}

export function submitDemo(
  state: DemoState,
  chapterId: string,
): DemoState {
  const session = state.sessions[chapterId]

  if (
    !session ||
    session.status !== 'Answering'
  ) {
    return state
  }

  const questions = demoQuestions(
    state,
    chapterId,
    session.round,
  )

  if (
    !questions.length ||
    questions.some(
      (question) =>
        !session.answers[question.id]?.trim(),
    )
  ) {
    return state
  }

  const marked = questions.map((question) => {
    const answer =
      session.answers[question.id].toLowerCase()

    const hits = question.rubric.filter(
      (point) =>
        new RegExp(
          `\\b${point}\\w*\\b`,
          'i',
        ).test(answer),
    )

    const correct =
      question.kind === 'mcq'
        ? session.answers[question.id] ===
          question.correct
        : hits.length /
            question.rubric.length >=
          0.8

    return {
      questionId: question.id,
      correct,
      hits,
      explanation: correct
        ? ''
        : question.explanation,
    }
  })

  const score = percent(
    marked.filter((question) => question.correct)
      .length,
    marked.length,
  )

  const passed = score >= 80
  const ended = passed || session.round === 2

  let tasks: Task[] = state.plan.tasks.map(
    (task) =>
      task.id === `practice-${chapterId}`
        ? {
            ...task,
            status: ended
              ? 'Completed'
              : 'In progress',
          }
        : task,
  )

  if (!passed && session.round === 1) {
    const chapter = state.plan.chapters.find(
      (item) => item.id === chapterId,
    )!

    tasks = [
      ...tasks,
      {
        id: `review-${chapterId}`,
        chapterId,
        title: `Review: ${chapter.title}`,
        kind: 'Review',
        date: dateKey(),
        minutes: 20,
        status: 'Not started',
        concepts: chapter.concepts,
        sources: chapter.sources,
      },
    ]

    const practiceIndex = tasks.findIndex(
      (task) =>
        task.id === `practice-${chapterId}`,
    )

    const [review] = tasks.splice(
      tasks.length - 1,
      1,
    )

    tasks.splice(practiceIndex, 0, review)
  }

  const result = {
    round: session.round,
    score,
    passed,
    answers: { ...session.answers },
    questions: marked,
  }

  return {
    ...state,
    sessions: {
      ...state.sessions,
      [chapterId]: {
        ...session,
        status: ended
          ? 'Ended'
          : 'Review required',
        history: [
          ...session.history,
          result,
        ],
      },
    },
    plan: scheduleDemo(
      { ...state.plan, tasks },
      decodeBrief(state.course.student_brief),
      passed
        ? 'Sample practice passed; remaining tasks rescheduled.'
        : 'Sample practice identified weak concepts; review retained in the schedule.',
    ),
  }
}

export function nextDemoRound(
  state: DemoState,
  chapterId: string,
): DemoState {
  const session = state.sessions[chapterId]

  const reviewed = state.plan.tasks.some(
    (task) =>
      task.id === `review-${chapterId}` &&
      task.status === 'Completed',
  )

  if (
    !session ||
    session.round !== 1 ||
    session.status !== 'Review required' ||
    !reviewed
  ) {
    return state
  }

  return {
    ...state,
    sessions: {
      ...state.sessions,
      [chapterId]: {
        ...session,
        round: 2,
        status: 'Answering',
        answers: {},
      },
    },
  }
}