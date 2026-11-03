import { Download, FileText, Printer } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { downloadText, fileSafe, printAsPdf } from '../../lib/exportReport'

/** "Export" menu for a report: a Markdown file, or the print dialog for saving as PDF. */
export default function ExportMenu({
  title,
  getMarkdown,
}: {
  /** Used for the file name and the PDF title. */
  title: string
  getMarkdown: () => string
}) {
  const menu = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    // A <details> menu stays open until its summary is clicked again; close it on outside clicks too.
    function close(event: PointerEvent) {
      if (menu.current?.open && !menu.current.contains(event.target as Node)) menu.current.open = false
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  const choose = (action: () => void) => () => {
    if (menu.current) menu.current.open = false
    action()
  }
  const item = 'flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-raised/60'

  return (
    <details ref={menu} className="no-print relative">
      <summary className="inline-flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-md border border-line px-2.5 text-xs text-muted transition-colors hover:border-faint hover:text-ink [&::-webkit-details-marker]:hidden">
        <Download size={13} aria-hidden="true" />
        Export
      </summary>
      <div className="absolute right-0 z-20 mt-1.5 w-52 rounded-lg border border-line bg-surface p-1.5 shadow-pop">
        <button
          type="button"
          className={item}
          onClick={choose(() => downloadText(`${fileSafe(title)}.md`, getMarkdown()))}
        >
          <FileText size={14} aria-hidden="true" />
          Download as Markdown
        </button>
        <button type="button" className={item} onClick={choose(() => printAsPdf(title))}>
          <Printer size={14} aria-hidden="true" />
          Save as PDF
        </button>
      </div>
    </details>
  )
}
