import { Link } from 'react-router'

import AnnotatedCode from '../components/landing/AnnotatedCode'
import DemoPlayer from '../components/landing/DemoPlayer'
import QuestionPreview from '../components/landing/QuestionPreview'
import PublicHeader from '../components/layout/PublicHeader'
import { buttonClass } from '../components/ui/button'
import { LogoMark } from '../components/ui/Logo'
import { useCurrentUser } from '../hooks/useAuth'

const steps = [
  {
    title: 'Add a repository',
    body: 'Paste a public GitHub link or upload a ZIP. Files are read and parsed, never run.',
  },
  {
    title: 'Ask about the implementation',
    body: 'Answers cite the files and lines they come from. Anything not backed by the code is marked as a suggestion.',
  },
  {
    title: 'Rehearse the interview',
    body: 'Get a preparation report, questions built from the code, and a mock interview with feedback on each answer.',
  },
]

export default function LandingPage() {
  const { data: user } = useCurrentUser()

  return (
    <div className="min-h-dvh">
      <PublicHeader />

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-14 pb-20 sm:px-6 lg:grid-cols-12 lg:gap-10 lg:pt-24 lg:pb-28">
          <div className="lg:col-span-5">
            <h1 className="text-[clamp(2.6rem,6vw,4.25rem)] leading-[1] font-extrabold tracking-[-0.035em]">
              Understand the code. Own the interview.
            </h1>
            <p className="mt-6 max-w-[34rem] text-lg leading-relaxed text-muted">
              RepInspect reads a repository, maps how it fits together and answers your questions with references to
              the exact files and lines. Then it turns that code into interview practice.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to={user ? '/dashboard' : '/register'}
                className={buttonClass('primary', 'h-11 px-5 text-[15px]')}
              >
                {user ? 'Open dashboard' : 'Create an account'}
              </Link>
              <a href="#how-it-works" className={buttonClass('secondary', 'h-11 px-5 text-[15px]')}>
                See how it works
              </a>
            </div>
          </div>

          <div className="min-w-0 lg:col-span-7">
            <AnnotatedCode />
          </div>
        </section>

        <section id="how-it-works" className="scroll-mt-8 border-y border-line bg-surface/70">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <h2 className="max-w-2xl text-4xl leading-[1.08] font-bold tracking-tight">
              From an unfamiliar repository to a confident explanation
            </h2>
            <div className="mt-12 grid items-start gap-12 lg:grid-cols-12 lg:gap-10">
              <ol className="space-y-9 lg:col-span-4">
                {steps.map((step, index) => (
                  <li key={step.title} className="border-l-2 border-line pl-5">
                    <span className="font-mono text-xs text-faint">Step {index + 1}</span>
                    <h3 className="mt-1 text-xl font-semibold">{step.title}</h3>
                    <p className="mt-2 max-w-sm leading-relaxed text-muted">{step.body}</p>
                  </li>
                ))}
              </ol>
              <div className="min-w-0 lg:col-span-8">
                <DemoPlayer />
              </div>
            </div>
          </div>
        </section>

        <section>
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2">
            <div>
              <h2 className="max-w-md text-4xl leading-[1.08] font-bold tracking-tight">
                Questions come from your code, not a question bank
              </h2>
              <p className="mt-5 max-w-lg text-lg leading-relaxed text-muted">
                Every question links to the source it was written from, explains what the interviewer is looking
                for and includes a suggested answer. Mark each one as you go and see what still needs work.
              </p>
            </div>
            <QuestionPreview />
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-surface/70">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-muted sm:px-6">
          <span className="inline-flex items-center gap-2">
            <LogoMark size={18} />
            RepInspect
          </span>
          <a
            href="https://github.com/noeljj77/RepInspect"
            className="hover:text-ink"
            target="_blank"
            rel="noreferrer"
          >
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
