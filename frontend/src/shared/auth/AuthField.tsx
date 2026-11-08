//输入框、密码显隐
import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

type AuthFieldProps = {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'password'
  placeholder?: string
  hint?: string
  error?: string
  autoComplete?: string
  disabled?: boolean
}

export default function AuthField({
  id,
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  hint,
  error,
  autoComplete,
  disabled = false,
}: AuthFieldProps) {
  const [visible, setVisible] = useState(false)
  const isPassword = type === 'password'

  const description = [
    hint ? `${id}-hint` : '',
    error ? `${id}-error` : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="auth-field">
      <label htmlFor={id}>{label}</label>

      <div className="auth-input-wrap">
        <input
          id={id}
          name={id}
          className="auth-input"
          type={isPassword && visible ? 'text' : type}
          value={value}
          onChange={(event) => {
            onChange(event.target.value)
          }}
          placeholder={placeholder}
          autoComplete={autoComplete}
          autoCapitalize="none"
          spellCheck={false}
          disabled={disabled}
          required
          aria-invalid={Boolean(error)}
          aria-describedby={description || undefined}
        />

        {isPassword ? (
          <button
            className="auth-password-toggle"
            type="button"
            onClick={() => {
              setVisible((current) => !current)
            }}
            disabled={disabled}
            aria-label={
              `${visible ? 'Hide' : 'Show'} ` +
              label.toLowerCase()
            }
            aria-pressed={visible}
          >
            {visible ? (
              <EyeOff
                size={18}
                strokeWidth={1.6}
                aria-hidden="true"
              />
            ) : (
              <Eye
                size={18}
                strokeWidth={1.6}
                aria-hidden="true"
              />
            )}
          </button>
        ) : null}
      </div>

      {hint ? (
        <p
          className="auth-field-hint"
          id={`${id}-hint`}
        >
          {hint}
        </p>
      ) : null}

      {error ? (
        <p
          className="auth-field-error"
          id={`${id}-error`}
          role="alert"
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}