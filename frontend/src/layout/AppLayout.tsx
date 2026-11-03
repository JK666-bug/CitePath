import {
  useEffect,
  useRef,
} from 'react'

import type { ReactNode } from 'react'

import { useLocation } from '../shared/router'
import { useStudy } from '../shared/StudyProvider'
import { Notice } from '../shared/components/UI'

import Sidebar from './Sidebar'
import './layout.css'

export default function AppLayout({
  username,
  onSignOut,
  children,
}: {
  username: string
  onSignOut: () => void
  children: ReactNode
}) {
  const { storageError } = useStudy()
  const { path } = useLocation()

  const main =
    useRef<HTMLElement>(null)

  useEffect(() => {
    main.current?.scrollTo({ top: 0 })

    main.current?.focus({
      preventScroll: true,
    })
  }, [path])

  return (
    <div className="cp-app">
      <a
        href="#main-content"
        className="skip-link"
      >
        Skip to content
      </a>

      <Sidebar
        username={username}
        onSignOut={onSignOut}
      />

      <main
        className="main-content"
        id="main-content"
        tabIndex={-1}
        ref={main}
      >
        {storageError && (
          <Notice tone="error">
            {storageError}
          </Notice>
        )}

        {children}
      </main>
    </div>
  )
}