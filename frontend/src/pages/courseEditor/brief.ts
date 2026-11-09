import { dateKey, parseDate } from '../../shared/format.ts'
import type { CourseConfig } from '../course/types'

export function encodeBrief(config: CourseConfig): string {
  return JSON.stringify({
    deadline: config.deadline,
    earlyDays: config.earlyDays,
    note: config.note,
  })
}

export function decodeBrief(text: string): CourseConfig {
  const legacy = { deadline: '', earlyDays: 0, note: text }

  try {
    const item: unknown = JSON.parse(text)

    // 通过课程日期字段识别设置，也能读取已经保存过的课程。
    if (
      item === null ||
      typeof item !== 'object' ||
      (!('deadline' in item) && !('earlyDays' in item))
    ) {
      return legacy
    }

    const config = item as Record<string, unknown>
    const rawDate = config.deadline
    const deadline =
      typeof rawDate === 'string' &&
      /^\d{4}-\d{2}-\d{2}$/.test(rawDate) &&
      dateKey(parseDate(rawDate)) === rawDate
        ? rawDate
        : ''

    return {
      deadline,
      earlyDays:
        typeof config.earlyDays === 'number' &&
        Number.isInteger(config.earlyDays) &&
        config.earlyDays >= 0
          ? config.earlyDays
          : 0,
      note: typeof config.note === 'string' ? config.note : '',
    }
  } catch {
    // 最早保存的课程可能只包含一段纯文本备注。
    return legacy
  }
}
