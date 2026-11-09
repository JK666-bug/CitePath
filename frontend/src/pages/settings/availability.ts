export type StudyAvailability = readonly number[]

export const DEFAULT_AVAILABILITY: StudyAvailability = [
  480, 480, 480, 480, 480, 480, 480,
]
export const MAX_DAILY_MINUTES = 24 * 60

function storageKey(userId: number) {
  return `citepath-study-availability-v1-${userId}`
}

function isStudyAvailability(value: unknown): value is StudyAvailability {
  return Array.isArray(value) && value.length === 7 &&
    value.every((minutes) =>
      Number.isInteger(minutes) &&
      minutes >= 0 &&
      minutes <= MAX_DAILY_MINUTES,
    )
}

export function loadBrowserStudyAvailability(
  userId: number,
): StudyAvailability | null {
  try {
    const saved = localStorage.getItem(storageKey(userId))
    const value: unknown = saved === null ? null : JSON.parse(saved)

    return isStudyAvailability(value) ? value : null
  } catch {
    return null
  }
}

export function minutesOnDate(value: StudyAvailability, day: Date) {
  // JavaScript 的 getDay() 从周日开始计数，设置数组从周一开始。
  return value[(day.getDay() + 6) % 7]
}
