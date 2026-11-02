import { FileCode2, Lightbulb } from 'lucide-react'

import { cn } from '../../lib/cn'

// Each line is a list of [text, tone] segments. A tiny hand-written
// highlighter is enough for a fixed example and avoids a syntax library.
type Tone = 'plain' | 'kw' | 'str' | 'dec'
type Line = { n: number; parts: Array<[string, Tone]> }

const toneClass: Record<Tone, string> = {
  plain: 'text-ink',
  kw: 'text-muted',
  str: 'text-[#a8d5b5]',
  dec: 'text-faint',
}

const lines: Line[] = [
  { n: 12, parts: [['@router.post(', 'dec'], ['"/login"', 'str'], [')', 'dec']] },
  { n: 13, parts: [['def ', 'kw'], ['login(form: LoginForm, db: Session = Depends(get_db)):', 'plain']] },
  { n: 14, parts: [['    user = users.get_by_email(db, form.email)', 'plain']] },
  {
    n: 15,
    parts: [
      ['    if not ', 'kw'],
      ['user ', 'plain'],
      ['or not ', 'kw'],
      ['verify_password(form.password, user.password_hash):', 'plain'],
    ],
  },
  {
    n: 16,
    parts: [['        raise ', 'kw'], ['HTTPException(401, ', 'plain'], ['"Invalid email or password"', 'str'], [')', 'plain']],
  },
  { n: 17, parts: [['    token = create_access_token(user.id)', 'plain']] },
  { n: 18, parts: [['    return ', 'kw'], ['auth_response(token)', 'plain']] },
]

const highlighted = new Set([14, 15, 16])

function Citation({ children }: { children: string }) {
  return (
    <span className="mx-0.5 inline-block rounded bg-mark/15 px-1.5 py-px font-mono text-[12px] text-mark">
      {children}
    </span>
  )
}

/** Static illustration of a cited answer, used in the landing page hero. */
export default function AnnotatedCode() {
  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-surface shadow-[0_24px_60px_-30px_rgba(0,0,0,0.6)]">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5 text-sm text-muted">
        <FileCode2 size={15} strokeWidth={1.75} aria-hidden="true" />
        <span className="font-mono text-[13px]">api/auth.py</span>
      </div>

      <pre className="overflow-x-auto py-3 font-mono text-[13px] leading-6" aria-label="Example source file">
        {lines.map((line) => (
          <div
            key={line.n}
            className={cn(
              'flex min-w-max border-l-2 pr-4',
              highlighted.has(line.n) ? 'border-mark bg-mark/[0.12]' : 'border-transparent',
            )}
          >
            <span className="w-11 shrink-0 select-none pr-3 text-right text-faint">{line.n}</span>
            <code>
              {line.parts.map(([text, tone], i) => (
                <span key={i} className={toneClass[tone]}>
                  {text}
                </span>
              ))}
            </code>
          </div>
        ))}
      </pre>

      <figcaption className="space-y-4 border-t border-line bg-raised/50 px-5 py-5 text-[15px] leading-relaxed">
        <p className="font-medium">How does login check the password?</p>
        <p className="text-ink/85">
          <code className="font-mono text-[13px]">login</code> looks the user up by email, then compares the
          submitted password with the stored hash using{' '}
          <code className="font-mono text-[13px]">verify_password</code>
          <Citation>api/auth.py:14–15</Citation>. Both failures return the same 401 message, so the endpoint
          doesn't reveal which emails are registered
          <Citation>api/auth.py:16</Citation>.
        </p>
        <p className="flex gap-2.5 rounded-md border border-dashed border-hint/40 px-3 py-2.5 text-sm text-hint">
          <Lightbulb size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            <span className="font-medium">Suggestion, not from the code:</span> this route has no rate limit, so
            repeated password guesses aren't slowed down.
          </span>
        </p>
      </figcaption>
    </figure>
  )
}
