import { request } from '../../shared/request'
import type { CourseDetail } from '../course/types'

export function createCourse(
  name: string,
  student_brief: string,
) {
  return request<CourseDetail>(
    '/api/courses',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        student_brief,
      }),
    },
  )
}