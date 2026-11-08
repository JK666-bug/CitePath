//统一英文日期和时长，避免不同页面显示不一致。
export function dateKey(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

export function parseDate(value: string) {
  return new Date(`${value.slice(0, 10)}T12:00:00`)
}

export function addDays(
  value: string,
  count: number,
) {
  const date = parseDate(value)
  date.setDate(date.getDate() + count)

  return dateKey(date)
}

export function daysBetween(
  from: string,
  to: string,
) {
  const a = parseDate(from)
  const b = parseDate(to)

  const start = Date.UTC(
    a.getFullYear(),
    a.getMonth(),
    a.getDate(),
  )

  const end = Date.UTC(
    b.getFullYear(),
    b.getMonth(),
    b.getDate(),
  )

  return Math.round((end - start) / 86400000)
}

export function prettyDate(
  value: string,
  full = false,
) {
  if (!value) return 'Not set'

  const date = parseDate(value)

  if (Number.isNaN(date.getTime())) {
    return 'Not set'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(full ? { year: 'numeric' as const } : {}),
  }).format(date)
}

export function duration(minutes: number) {
  const value = Math.max(0, Math.round(minutes))

  if (value < 60) {
    return `${value} min`
  }

  const hours = Math.floor(value / 60)
  const remaining = value % 60

  return `${hours}h${remaining ? ` ${remaining}m` : ''}`
}

export function percent(
  done: number,
  total: number,
) {
  return total
    ? Math.min(100, Math.round((done / total) * 100))
    : 0
}