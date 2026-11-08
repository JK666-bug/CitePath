//请求及错误处理
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const messages: Record<string, string> = {
  'Incorrect username or password':
    'Incorrect username or password.',

  'This username is already taken':
    'This username is already taken. Please choose another.',

  'Username must be 2 to 32 characters':
    'Your username must contain 2–32 characters.',

  'Username cannot contain spaces':
    'Your username cannot contain spaces.',

  'Password must be 6 to 72 characters':
    'Your password must contain 6–72 characters.',

  'Sign in first':
    'Your session has expired. Please sign in again.',

  'Enter a course name':
    'Please enter a course name.',

  'Write your goals and dates':
    'Please enter your goals and study dates.',

  'Course not found':
    'This course could not be found.',

  'Material not found':
    'This material could not be found.',

  'Upload a PDF file':
    'Please choose a PDF file.',

  'The PDF is empty':
    'This PDF is empty.',

  'This PDF could not be read':
    'This PDF could not be read. Please choose another file.',

  'This PDF has no pages':
    'This PDF has no readable pages.',

  'Write a question':
    'Please enter a question.',

  'Question is too long':
    'Your question must contain at most 2,000 characters.',

  'This course has no material to cite':
    'Upload a readable PDF before asking a question.',

  'Could not answer':
    'Unable to answer this question. Please try again.',
}

function errorMessage(
  payload: unknown,
  status: number,
): string {
  const detail =
    payload &&
    typeof payload === 'object' &&
    'detail' in payload
      ? payload.detail
      : undefined

  if (typeof detail === 'string' && messages[detail]) {
    return messages[detail]
  }

  if (status === 401) {
    return 'Please sign in to continue.'
  }

  if (status === 404) {
    return 'The requested item could not be found.'
  }

  if (status === 422) {
    return 'Please check your details and try again.'
  }

  if (status >= 500) {
    return 'The service is temporarily unavailable. Please try again later.'
  }

  return 'The request could not be completed. Please try again.'
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response

  try {
    response = await fetch(path, {
      ...options,
      credentials: 'include',
    })
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === 'AbortError'
    ) {
      throw error
    }

    throw new ApiError(
      0,
      'Unable to connect to the server. Please try again.',
    )
  }

  const payload: unknown = await response
    .json()
    .catch(() => null)

  if (!response.ok) {
    const authenticationRequest = [
      '/api/me',
      '/api/login',
      '/api/register',
    ].includes(path)

    if (
      response.status === 401 &&
      !authenticationRequest
    ) {
      window.dispatchEvent(
        new Event('citepath:session-expired'),
      )
    }

    throw new ApiError(
      response.status,
      errorMessage(payload, response.status),
    )
  }

  return payload as T
}

export function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'Something went wrong. Please try again.'
}