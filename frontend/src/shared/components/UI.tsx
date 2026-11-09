import {
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'

import type { ReactNode } from 'react'

import {
  FileText,
  LoaderCircle,
  X,
} from 'lucide-react'

import type { Material, Source } from '../../pages/course/types'
import { numberMaterials } from '../../pages/course/materials'
import { Link } from '../router'

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && (
          <p className="eyebrow">{eyebrow}</p>
        )}

        <h1>{title}</h1>

        {subtitle && (
          <p className="muted">{subtitle}</p>
        )}
      </div>

      {actions && (
        <div className="actions">
          {actions}
        </div>
      )}
    </header>
  )
}

export function Notice({
  children,
  tone = 'info',
}: {
  children: ReactNode
  tone?: 'info' | 'error' | 'success'
}) {
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  )
}

export function DemoNotice() {
  return (
    <Notice>
      <strong>Interface demo.</strong>{' '}
      Sample materials and questions are fixed.
      No PDF analysis, AI generation, or model
      grading is performed. Changes are stored
      only in this browser.
    </Notice>
  )
}

export function Loading({
  text = 'Loading your study space…',
}: {
  text?: string
}) {
  return (
    <div
      className="loading-state"
      role="status"
    >
      <LoaderCircle
        className="spin"
        size={20}
      />

      {text}
    </div>
  )
}

export function Empty({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) {
  return (
    <section className="empty-state">
      <FileText
        size={28}
        strokeWidth={1.3}
      />

      <h2>{title}</h2>

      {children && (
        <div className="muted">
          {children}
        </div>
      )}
    </section>
  )
}

export function Modal({
  open,
  title,
  onClose,
  children,
  closeable = true,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  closeable?: boolean
}) {
  const ref =
    useRef<HTMLDialogElement>(null)

  const heading = useId()

  useEffect(() => {
    if (open && !ref.current?.open) {
      ref.current?.showModal()
    }

    if (!open && ref.current?.open) {
      ref.current.close()
    }
  }, [open])

  return (
    <dialog
      className="cp-modal"
      ref={ref}
      aria-labelledby={heading}
      onCancel={(event) => {
        event.preventDefault()

        if (closeable) {
          onClose()
        }
      }}
      onClick={(event) => {
        if (
          closeable &&
          event.target === event.currentTarget
        ) {
          onClose()
        }
      }}
    >
      <div className="modal-content">
        <header>
          <h2 id={heading}>{title}</h2>

          {closeable && (
            <button
              type="button"
              className="icon-button"
              aria-label="Close dialog"
              onClick={onClose}
            >
              <X size={18} />
            </button>
          )}
        </header>

        {open && children}
      </div>
    </dialog>
  )
}

export function Sources({
  sources,
  materials,
}: {
  sources: Source[]
  materials: readonly Material[]
}) {
  const [selected, setSelected] =
    useState<Source | null>(null)

  // 编号来自课程的完整资料列表，与当前回答引用了几份资料无关。
  const documentNumbers = new Map(
    numberMaterials(materials).map((material) => [
      material.id,
      material.displayNumber,
    ]),
  )

  function sourceLabel(source: Source): string {
    const number = documentNumbers.get(source.document_id)
    return number === undefined
      ? `${source.filename} (unavailable)`
      : `Doc ${number}`
  }

  return (
    <>
      <div className="source-list">
        {sources.map((source) => (
          <button
            type="button"
            className="source-chip"
            title={source.filename}
            key={
              `${source.document_id}-` +
              source.page_number
            }
            onClick={() =>
              setSelected(source)
            }
          >
            <FileText size={12} />
            {sourceLabel(source)}
            {' · '}
            p. {source.page_number}
          </button>
        ))}
      </div>

      <Modal
        open={Boolean(selected)}
        title="Source reference"
        onClose={() => setSelected(null)}
      >
        {selected && (
          <div className="stack">
            <strong>
              {selected.filename}
            </strong>

            <p>
              {sourceLabel(selected)}
              {' · '}
              PDF page {selected.page_number}
            </p>

            <p className="muted">
              This reference identifies the
              source page. The current backend
              does not provide a PDF viewer or
              file download endpoint.
            </p>
          </div>
        )}
      </Modal>
    </>
  )
}

export function PlanningUnavailable() {
  return (
    <Empty title="Your study plan is not available yet">
      <p>
        Course materials can be saved now.
        The planning service has not been
        connected in the current backend.
      </p>

      <div className="actions centered">
        <Link
          className="button secondary"
          href="/courses/demo/plan"
        >
          Explore the interface demo
        </Link>
      </div>
    </Empty>
  )
}
