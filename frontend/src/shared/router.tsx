//负责页面切换和浏览器前进、后退
import { useSyncExternalStore } from 'react'
import type { AnchorHTMLAttributes } from 'react'

const eventName = 'citepath:navigate'

function subscribe(listener: () => void) {
  window.addEventListener('popstate', listener)
  window.addEventListener(eventName, listener)

  return () => {
    window.removeEventListener('popstate', listener)
    window.removeEventListener(eventName, listener)
  }
}

export function navigate(
  to: string,
  replace = false,
) {
  const url = new URL(to, window.location.href)

  if (url.origin !== window.location.origin) {
    window.location.assign(url.href)
    return
  }

  const changedPage =
    url.pathname !== window.location.pathname

  window.history[
    replace ? 'replaceState' : 'pushState'
  ]({}, '', url.href)

  window.dispatchEvent(new Event(eventName))

  if (changedPage) {
    window.scrollTo({
      top: 0,
      behavior: 'instant',
    })
  }
}

export function useLocation() {
  const value = useSyncExternalStore(
    subscribe,
    () => location.pathname + location.search,
  )

  const [path, query = ''] = value.split('?')

  return {
    path: path.replace(/\/+$/, '') || '/',
    search: new URLSearchParams(query),
  }
}

export function Link({
  href = '/',
  onClick,
  children,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      {...props}
      href={href}
      onClick={(event) => {
        onClick?.(event)

        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey ||
          props.target ||
          props.download
        ) {
          return
        }

        const url = new URL(href, location.href)

        if (
          url.origin !== location.origin ||
          url.hash
        ) {
          return
        }

        event.preventDefault()
        navigate(href)
      }}
    >
      {children}
    </a>
  )
}