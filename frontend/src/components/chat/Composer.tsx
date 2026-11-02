import { ArrowUp } from 'lucide-react'
import { useId, useState, type FormEvent, type KeyboardEvent } from 'react'

import { buttonClass } from '../ui/button'

const MAX_LENGTH = 2000

interface Props {
  onAsk: (question: string) => void
  /** True while a question is being sent or answered. */
  busy: boolean
  placeholder?: string
  autoFocus?: boolean
}

export default function Composer({ onAsk, busy, placeholder, autoFocus }: Props) {
  const [question, setQuestion] = useState('')
  const id = useId()
  const trimmed = question.trim()

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (!trimmed || busy) return
    onAsk(trimmed)
    setQuestion('')
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter starts a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-line bg-surface p-2 focus-within:border-faint">
      <label htmlFor={id} className="sr-only">
        Your question
      </label>
      <textarea
        id={id}
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={onKeyDown}
        rows={2}
        maxLength={MAX_LENGTH}
        autoFocus={autoFocus}
        placeholder={placeholder ?? 'Ask about this repository'}
        className="block w-full resize-none bg-transparent px-2 py-1.5 text-[15px] leading-relaxed placeholder:text-faint focus:outline-none focus-visible:outline-none"
      />
      <div className="flex items-center justify-between gap-3 px-2 pt-1">
        <span className="text-xs text-faint">Enter to send, Shift+Enter for a new line</span>
        <button type="submit" disabled={!trimmed || busy} className={buttonClass('primary', 'h-8 px-3')}>
          <ArrowUp size={15} aria-hidden="true" />
          Ask
        </button>
      </div>
    </form>
  )
}
