export async function readJson(response: Response) {
  const payload = await response.json().catch(() => ({}))
  if (response.status === 401) {
    window.location.assign('/')
    throw new Error('Sign in first')
  }
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : 'Request failed'
    throw new Error(detail)
  }
  return payload
}
