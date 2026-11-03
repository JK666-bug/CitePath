import type { CourseConfig } from '../course/types'

export function encodeBrief(
  config: CourseConfig,
) {
  return JSON.stringify({
    schema: 'citepath-course-v1',
    ...config,
  })
}

export function decodeBrief(
  text: string,
): CourseConfig {
  try {
    const value: unknown = JSON.parse(text)

    if (
      value &&
      typeof value === 'object' &&
      'schema' in value &&
      value.schema === 'citepath-course-v1'
    ) {
      const item = value as Record<string, unknown>

      if (
        typeof item.deadline === 'string' &&
        /^\d{4}-\d{2}-\d{2}$/.test(item.deadline) &&
        typeof item.weeklyHours === 'number' &&
        item.weeklyHours > 0 &&
        typeof item.earlyDays === 'number' &&
        item.earlyDays >= 0 &&
        typeof item.note === 'string'
      ) {
        return {
          deadline: item.deadline,
          weeklyHours: item.weeklyHours,
          earlyDays: item.earlyDays,
          note: item.note,
        }
      }
    }
  } catch {
    // Legacy courses contain a plain study note.
  }

  return {
    deadline: '',
    weeklyHours: 0,
    earlyDays: 0,
    note: text,
  }
}