import type { ClaimCheck, Grade, Verdict } from '../../api/mock'
import { cn } from '../../lib/cn'
import { CitationLink, FindingList } from '../ai/Findings'

const VERDICTS: Record<Verdict, { label: string; rule: string; tone: string }> = {
  supported: { label: 'The code agrees', rule: 'border-l-2 border-mark', tone: 'text-mark-text' },
  contradicted: { label: 'The code says otherwise', rule: 'border-l-2 border-danger', tone: 'text-danger' },
  not_found: { label: 'Not in the code that was searched', rule: 'border-l-2 border-line', tone: 'text-muted' },
  unverified: { label: 'Could not be checked', rule: 'border-l-2 border-dashed border-hint/70', tone: 'text-hint' },
}

/** A score out of 4, as a row of marks and a word. */
export function ScoreBadge({ score, label }: { score: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm" aria-label={`Score ${score} of 4: ${label}`}>
      <span aria-hidden="true" className="flex gap-0.5">
        {[1, 2, 3, 4].map((n) => (
          <span key={n} className={cn('h-2.5 w-4 rounded-sm', n <= score ? (score >= 3 ? 'bg-ok' : 'bg-mark') : 'bg-raised')} />
        ))}
      </span>
      <span className={cn('font-medium', score >= 3 ? 'text-ok' : score >= 2 ? 'text-mark-text' : 'text-danger')}>{label}</span>
    </span>
  )
}

export function ClaimList({ repositoryId, claims }: { repositoryId: string; claims: ClaimCheck[] }) {
  if (claims.length === 0) return null
  return (
    <ul className="space-y-3">
      {claims.map((claim, index) => {
        const style = VERDICTS[claim.verdict]
        return (
          <li key={index} className={cn('pl-3', style.rule)}>
            <p className="text-sm">
              <span className="text-muted">You said: </span>
              {claim.claim}
            </p>
            <p className={cn('mt-0.5 text-xs', style.tone)}>{style.label}</p>
            {claim.citations.length > 0 && (
              <div className="mt-1.5 space-y-1.5">
                {claim.citations.map((citation, i) => (
                  <CitationLink key={i} repositoryId={repositoryId} citation={citation} />
                ))}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function List({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  if (items.length === 0) return null
  return (
    <div>
      <h5 className={cn('text-xs', tone)}>{title}</h5>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm marker:text-faint">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export default function GradeView({ repositoryId, grade }: { repositoryId: string; grade: Grade }) {
  return (
    <div className="space-y-4 rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center gap-3">
        <ScoreBadge score={grade.score} label={grade.label} />
      </div>
      <p className="leading-relaxed">{grade.summary}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <List title="What went well" items={grade.strengths} tone="text-ok" />
        <List title="What was missing" items={grade.gaps} tone="text-mark-text" />
      </div>
      {grade.claims.length > 0 && (
        <div>
          <h5 className="mb-2 text-xs text-muted">Your statements, checked against the code</h5>
          <ClaimList repositoryId={repositoryId} claims={grade.claims} />
        </div>
      )}
      {grade.missed_points.length > 0 && (
        <div>
          <h5 className="mb-2 text-xs text-muted">Points a strong answer would also cover</h5>
          <FindingList repositoryId={repositoryId} findings={grade.missed_points} />
        </div>
      )}
    </div>
  )
}
