import { useId, type InputHTMLAttributes } from 'react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
}

export default function TextField({ label, hint, id, ...inputProps }: TextFieldProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const hintId = `${inputId}-hint`

  return (
    <div>
      <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <input
        id={inputId}
        aria-describedby={hint ? hintId : undefined}
        className="h-10 w-full rounded-md border border-line bg-canvas px-3 text-[15px] placeholder:text-faint hover:border-faint focus:border-mark focus:outline-none focus-visible:outline-none focus:ring-1 focus:ring-mark"
        {...inputProps}
      />
      {hint && (
        <p id={hintId} className="mt-1.5 text-sm text-muted">
          {hint}
        </p>
      )}
    </div>
  )
}
