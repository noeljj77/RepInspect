import AddRepositoryForm from '../components/repository/AddRepositoryForm'
import RepositoryList from '../components/repository/RepositoryList'
import { useCurrentUser } from '../hooks/useAuth'
import { useRepositories } from '../hooks/useRepositories'

export default function DashboardPage() {
  const { data: user } = useCurrentUser()
  const { data: repositories } = useRepositories()
  const count = repositories?.length ?? 0

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Your library</h1>
        <p className="mt-1.5 text-muted">
          {user ? `Welcome, ${user.display_name}. ` : ''}
          {count > 0
            ? `${count} ${count === 1 ? 'repository' : 'repositories'} to explore and prepare with.`
            : 'Add a repository, then explore it and prepare to talk about it.'}
        </p>
      </header>

      <AddRepositoryForm />

      <section aria-labelledby="library-heading" className="mt-10">
        <h2 id="library-heading" className="sr-only">
          Your repositories
        </h2>
        <RepositoryList />
      </section>
    </div>
  )
}
