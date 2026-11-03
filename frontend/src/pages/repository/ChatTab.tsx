import { MessageSquarePlus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { ChatMessage } from '../../api/chat'
import Composer from '../../components/chat/Composer'
import IndexPanel from '../../components/chat/IndexPanel'
import Turn from '../../components/chat/Turn'
import { buttonClass } from '../../components/ui/button'
import { useAsk, useChat, useChats, useDeleteChat, useRetryAnswer, useSearchIndex, useStartChat } from '../../hooks/useChat'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'
import { cn } from '../../lib/cn'
import { formatRelativeTime } from '../../lib/format'
import LoadingLine from '../../components/ui/LoadingLine'

const SUGGESTIONS = [
  'How does the application start?',
  'What are the main parts of the code and how do they connect?',
  'How is data stored and loaded?',
  'How are errors handled?',
]

function ConversationList({ repositoryId, selected }: { repositoryId: string; selected: string | null }) {
  const { data: chats } = useChats(repositoryId)

  return (
    <nav aria-label="Conversations" className="space-y-3">
      <Link to="?" className={buttonClass('secondary', 'h-9 w-full justify-start')}>
        <MessageSquarePlus size={15} aria-hidden="true" />
        New conversation
      </Link>
      {chats && chats.length > 0 && (
        <ul className="max-h-60 space-y-0.5 overflow-y-auto lg:max-h-[calc(100dvh-14rem)]">
          {chats.map((chat) => (
            <li key={chat.id}>
              <Link
                to={`?chat=${chat.id}`}
                aria-current={chat.id === selected ? 'page' : undefined}
                className={cn(
                  'block rounded-md border-l-2 px-2.5 py-1.5 text-sm',
                  chat.id === selected
                    ? 'border-mark bg-raised/60 text-ink'
                    : 'border-transparent text-muted hover:bg-raised/40 hover:text-ink',
                )}
              >
                <span className="line-clamp-2">{chat.title}</span>
                <span className="mt-0.5 block text-xs text-faint">{formatRelativeTime(chat.updated_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </nav>
  )
}

function NewConversation({ repositoryId, onStarted }: { repositoryId: string; onStarted: (id: string) => void }) {
  const start = useStartChat(repositoryId)
  const ask = (question: string) => start.mutate(question, { onSuccess: (chat) => onStarted(chat.id) })

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold">Ask about this repository</h2>
      <p className="mt-1.5 text-muted">
        Each question searches the code for the most relevant functions, classes and documents, and the answer
        quotes the lines it relies on. If the code does not say, the answer says so.
      </p>

      <ul aria-label="Suggested questions" className="mt-5 flex flex-wrap gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <li key={suggestion}>
            <button
              type="button"
              onClick={() => ask(suggestion)}
              disabled={start.isPending}
              className="rounded-full border border-line px-3 py-1.5 text-sm text-muted hover:border-faint hover:text-ink disabled:opacity-50"
            >
              {suggestion}
            </button>
          </li>
        ))}
      </ul>

      <div className="mt-5">
        <Composer onAsk={ask} busy={start.isPending} autoFocus />
      </div>
      {start.isError && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {start.error.message}
        </p>
      )}
    </div>
  )
}

/** Questions paired with the answer that follows each. */
function turns(messages: ChatMessage[]): Array<[ChatMessage, ChatMessage | undefined]> {
  const pairs: Array<[ChatMessage, ChatMessage | undefined]> = []
  messages.forEach((message, index) => {
    if (message.role === 'user') {
      const next = messages[index + 1]
      pairs.push([message, next?.role === 'assistant' ? next : undefined])
    }
  })
  return pairs
}

function DeleteButton({ onDelete, busy }: { onDelete: () => void; busy: boolean }) {
  const [confirming, setConfirming] = useState(false)
  if (!confirming) {
    return (
      <button type="button" onClick={() => setConfirming(true)} className={buttonClass('ghost', 'h-8 px-2 text-xs')}>
        <Trash2 size={13} aria-hidden="true" />
        Delete conversation
      </button>
    )
  }
  return (
    <span className="flex items-center gap-1 text-xs">
      <button type="button" onClick={onDelete} disabled={busy} className={buttonClass('ghost', 'h-8 px-2 text-xs text-danger hover:text-danger')}>
        Delete this conversation
      </button>
      <button type="button" onClick={() => setConfirming(false)} className={buttonClass('ghost', 'h-8 px-2 text-xs')}>
        Keep it
      </button>
    </span>
  )
}

function Conversation({ repositoryId, chatId, onDeleted }: { repositoryId: string; chatId: string; onDeleted: () => void }) {
  const { data: chat, isPending, isError } = useChat(repositoryId, chatId)
  const ask = useAsk(repositoryId, chatId)
  const retry = useRetryAnswer(repositoryId, chatId)
  const remove = useDeleteChat(repositoryId)
  const turnsRef = useRef<HTMLDivElement>(null)
  const count = chat?.messages.length ?? 0

  useEffect(() => {
    // Bring the newest question into view when one is added (or a long conversation opens).
    if (count <= 2) return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    turnsRef.current?.lastElementChild?.scrollIntoView?.({ block: 'start', behavior: reduced ? 'auto' : 'smooth' })
  }, [count])

  if (isPending) {
    return (
      <LoadingLine>
        Loading the conversation…
      </LoadingLine>
    )
  }
  if (isError) {
    return (
      <div role="alert" className="text-sm">
        <p className="text-danger">This conversation could not be opened. It may have been deleted.</p>
        <Link to="?" className="mt-2 inline-block text-mark-text hover:underline">
          Start a new conversation
        </Link>
      </div>
    )
  }

  const pairs = turns(chat.messages)
  const waiting = chat.messages.some((message) => message.status === 'pending')
  const lastAnswerId = chat.messages.at(-1)?.id
  const actionError = ask.error ?? retry.error ?? remove.error

  return (
    <div className="max-w-3xl">
      <header className="mb-5 flex items-start justify-between gap-4 border-b border-line pb-3">
        <h2 className="sr-only">{chat.title}</h2>
        <p className="text-sm text-muted">
          {pairs.length} {pairs.length === 1 ? 'question' : 'questions'}, started {formatRelativeTime(chat.created_at)}
        </p>
        <DeleteButton onDelete={() => remove.mutate(chatId, { onSuccess: onDeleted })} busy={remove.isPending} />
      </header>

      <div ref={turnsRef}>
        {pairs.map(([question, answer]) => (
          <Turn
            key={question.id}
            repositoryId={repositoryId}
            question={question}
            answer={answer}
            canRetry={answer?.id === lastAnswerId}
            onRetry={(id) => retry.mutate(id)}
            retrying={retry.isPending}
          />
        ))}
      </div>

      <div className="sticky bottom-0 bg-canvas pt-3 pb-4">
        <Composer
          onAsk={(question) => ask.mutate(question)}
          busy={waiting || ask.isPending}
          placeholder="Ask a follow-up question"
        />
        {actionError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {actionError.message}
          </p>
        )}
      </div>
    </div>
  )
}

export default function ChatTab() {
  const { repository } = useRepositoryContext()
  const { data: index, isPending, isError } = useSearchIndex(repository.id)
  const [params, setParams] = useSearchParams()
  const chatId = params.get('chat')

  if (isPending) {
    return (
      <LoadingLine>
        Checking whether chat is ready…
      </LoadingLine>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        Chat could not be loaded. Try refreshing the page.
      </p>
    )
  }
  if (index.status !== 'ready') return <IndexPanel repositoryId={repository.id} index={index} />

  return (
    <div className="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
      <div className="lg:sticky lg:top-4 lg:self-start">
        <ConversationList repositoryId={repository.id} selected={chatId} />
        {index.truncated && (
          <p className="mt-4 text-xs text-muted">
            This repository is large, so only its {index.chunk_count.toLocaleString('en')} most important parts
            were indexed.
          </p>
        )}
      </div>
      <div className="min-w-0">
        {chatId ? (
          <Conversation
            key={chatId}
            repositoryId={repository.id}
            chatId={chatId}
            onDeleted={() => setParams({})}
          />
        ) : (
          <NewConversation repositoryId={repository.id} onStarted={(id) => setParams({ chat: id })} />
        )}
      </div>
    </div>
  )
}
