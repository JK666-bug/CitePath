//集中定义课程、任务和练习的数据格式。
export type CourseConfig = {
  deadline: string
  weeklyHours: number
  earlyDays: number
  note: string
}

export type Material = {
  id: number
  filename: string
  ingest_status: string
  page_count: number
  usable_page_count: number
}

export type CourseDetail = {
  id: number
  name: string
  student_brief: string
  created_at: string
  documents: Material[]
}

export type Source = {
  document_id: number
  filename: string
  page_number: number
}

export type Task = {
  id: string
  chapterId: string
  title: string
  kind: 'Reading' | 'Practice' | 'Review'
  date: string
  minutes: number
  status:
    | 'Not started'
    | 'In progress'
    | 'Completed'
  sources: Source[]
  concepts: string[]
}

export type Chapter = {
  id: string
  title: string
  concepts: string[]
  sources: Source[]
}

export type StudyPlan = {
  version: number
  start: string
  tasks: Task[]
  chapters: Chapter[]
  reason: string
}

export type Question = {
  id: string
  kind: 'mcq' | 'short'
  prompt: string
  options: string[]
  correct: string
  rubric: string[]
  explanation: string
  sources: Source[]
}

export type QuestionResult = {
  questionId: string
  correct: boolean
  hits: string[]
  explanation: string
}

export type RoundResult = {
  round: 1 | 2
  score: number
  passed: boolean
  answers: Record<string, string>
  questions: QuestionResult[]
}

export type PracticeSession = {
  chapterId: string
  round: 1 | 2
  status:
    | 'Answering'
    | 'Review required'
    | 'Ended'
  answers: Record<string, string>
  history: RoundResult[]
}

export type DemoState = {
  schema: 1
  course: CourseDetail
  plan: StudyPlan
  sessions: Record<string, PracticeSession>
}

export type QAResponse = {
  qa_id: number
  course_name: string
  question?: string
  answer: string
  cited_pages: Source[]
  refused: boolean
}