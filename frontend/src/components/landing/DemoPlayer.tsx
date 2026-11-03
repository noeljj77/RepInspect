/** A recording of the real app, with a still for people who ask their system to reduce motion. */
export default function DemoPlayer() {
  return (
    <figure>
      <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-lift">
        <picture>
          <source media="(prefers-reduced-motion: reduce)" srcSet="/how-it-works-still.png" />
          <img
            src="/how-it-works.gif"
            width={800}
            height={546}
            loading="lazy"
            decoding="async"
            alt="Recording of RepInspect: a GitHub link is analyzed, an overview and a chat answer quote the exact lines of code they rely on, and a mock interview answer is graded against the code."
            className="block h-auto w-full"
          />
        </picture>
      </div>
      <figcaption className="mt-3 text-sm text-faint">Recorded in the app with pallets/click, a public repository.</figcaption>
    </figure>
  )
}
