//获取课程列表，供课程页和导航共用
import { request } from '../../shared/request'

export type CourseSummary = {
  id: number
  name: string
  student_brief: string
  created_at: string
  document_count: number
}

type CoursesResponse = {
  courses: CourseSummary[]
}

export async function getCourses(): Promise<CourseSummary[]> {
  const result = await request<CoursesResponse>('/api/courses')
  return result.courses
}