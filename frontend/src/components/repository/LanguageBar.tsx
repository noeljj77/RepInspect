// Distinct but calm colours on the dark surface. The legend always repeats the
// name and percentage, so colour is never the only way to read the chart.
const COLORS = ['#f2c14e', '#93a4f5', '#7fd1a4', '#ef8a8a', '#6fc3d6', '#c9a0e6']
const OTHER_COLOR = '#636c84'
const MAX_NAMED = COLORS.length

interface Slice {
  name: string
  percent: number
  color: string
}

function toSlices(bytesByLanguage: Record<string, number>): Slice[] {
  const entries = Object.entries(bytesByLanguage)
    .filter(([, bytes]) => bytes > 0)
    .sort((a, b) => b[1] - a[1])
  const total = entries.reduce((sum, [, bytes]) => sum + bytes, 0)
  if (total === 0) return []

  const named = entries.slice(0, MAX_NAMED).map(([name, bytes], index) => ({
    name,
    percent: (bytes / total) * 100,
    color: COLORS[index],
  }))
  const otherBytes = entries.slice(MAX_NAMED).reduce((sum, [, bytes]) => sum + bytes, 0)
  return otherBytes > 0
    ? [...named, { name: 'Other', percent: (otherBytes / total) * 100, color: OTHER_COLOR }]
    : named
}

const formatPercent = (value: number) => (value < 0.1 ? '<0.1%' : `${value.toFixed(1)}%`)

export default function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const slices = toSlices(languages)
  if (slices.length === 0) return null

  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-line" role="img" aria-label={`Languages: ${slices.map((s) => `${s.name} ${formatPercent(s.percent)}`).join(', ')}`}>
        {slices.map((slice) => (
          <div key={slice.name} style={{ width: `${slice.percent}%`, backgroundColor: slice.color }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {slices.map((slice) => (
          <li key={slice.name} className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ backgroundColor: slice.color }} aria-hidden="true" />
            <span>{slice.name}</span>
            <span className="text-muted">{formatPercent(slice.percent)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
