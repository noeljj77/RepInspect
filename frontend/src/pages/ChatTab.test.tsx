import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { chat, CHAT_ID, question, REPO_ID, reply, repositoryDetail, searchIndex } from '../test/fixtures'
import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`
const chatUrl = `/repositories/${REPO_ID}/chat`

function open(url: string, extra: ApiRoutes = {}) {
  const fetchMock = mockApi({
    'GET /api/auth/me': { body: ada },
    [`GET ${base}`]: { body: repositoryDetail() },
    [`GET ${base}/index`]: { body: searchIndex() },
    [`GET ${base}/chats`]: { body: [] },
    ...extra,
  })
  return { fetchMock, ...renderRoute(url) }
}

const posted = (fetchMock: ReturnType<typeof open>['fetchMock'], url: string) =>
  fetchMock.mock.calls.filter(([input, init]) => String(input) === url && init?.method === 'POST')

describe('Chat tab: the search index', () => {
  it('appears in the repository tabs', async () => {
    open(`/repositories/${REPO_ID}`)

    const tabs = await screen.findByRole('navigation', { name: 'Repository sections' })
    expect(within(tabs).getByRole('link', { name: 'Chat' })).toHaveAttribute('href', chatUrl)
  })

  it('shows progress while the index is being built', async () => {
    open(chatUrl, {
      [`GET ${base}/index`]: { body: searchIndex({ status: 'building', chunks_embedded: 512 }) },
    })

    expect(await screen.findByRole('heading', { name: 'Preparing chat' })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Indexing progress' })).toHaveAttribute('aria-valuenow', '512')
    expect(screen.getByRole('status')).toHaveTextContent('512 of 1,966 parts indexed')
  })

  it('offers to build an index for older imports', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(chatUrl, {
      [`GET ${base}/index`]: { body: searchIndex({ status: 'missing', chunk_count: 0, chunks_embedded: 0 }) },
      [`POST ${base}/index`]: { status: 202, body: searchIndex({ status: 'pending', chunk_count: 0, chunks_embedded: 0 }) },
    })

    await user.click(await screen.findByRole('button', { name: 'Build the search index' }))

    expect(posted(fetchMock, `${base}/index`)).toHaveLength(1)
    expect(await screen.findByRole('heading', { name: 'Preparing chat' })).toBeInTheDocument()
  })

  it('explains a failure and offers no retry when there is nothing to search', async () => {
    open(chatUrl, {
      [`GET ${base}/index`]: {
        body: searchIndex({
          status: 'failed',
          error_code: 'nothing_to_index',
          error_message: 'This repository has no files that can be searched.',
        }),
      },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('no files that can be searched')
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })
})

describe('Chat tab: asking', () => {
  it('starts a conversation from a suggested question and shows the answer', async () => {
    const user = userEvent.setup()
    const started = chat([question('How does the application start?'), reply()])
    const { fetchMock, router } = open(chatUrl, {
      [`POST ${base}/chats`]: { status: 201, body: started },
      [`GET ${base}/chats/${CHAT_ID}`]: { body: started },
    })

    await user.click(await screen.findByRole('button', { name: 'How does the application start?' }))

    await waitFor(() => expect(router.state.location.search).toBe(`?chat=${CHAT_ID}`))
    const [, init] = posted(fetchMock, `${base}/chats`)[0]
    expect(JSON.parse(String(init?.body))).toEqual({ question: 'How does the application start?' })
    expect(await screen.findByRole('heading', { level: 3, name: 'How does the application start?' })).toBeInTheDocument()
  })

  it('sends with Enter and adds a new line with Shift+Enter', async () => {
    const user = userEvent.setup()
    const { fetchMock } = open(chatUrl, {
      [`POST ${base}/chats`]: { status: 201, body: chat() },
      [`GET ${base}/chats/${CHAT_ID}`]: { body: chat() },
    })

    const box = await screen.findByRole('textbox', { name: 'Your question' })
    await user.type(box, 'Where is{Shift>}{Enter}{/Shift}login?')
    expect(box).toHaveValue('Where is\nlogin?')
    expect(posted(fetchMock, `${base}/chats`)).toHaveLength(0)

    await user.keyboard('{Enter}')

    expect(posted(fetchMock, `${base}/chats`)).toHaveLength(1)
  })

  it("shows the server's reason when a question cannot be asked", async () => {
    const user = userEvent.setup()
    open(chatUrl, {
      [`POST ${base}/chats`]: { status: 429, body: { detail: "You have reached today's limit of 40 AI requests." } },
    })

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), 'Hi?{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent("today's limit")
  })
})

describe('Chat tab: answers', () => {
  function openChat(messages = [question(), reply()], extra: ApiRoutes = {}) {
    return open(`${chatUrl}?chat=${CHAT_ID}`, {
      [`GET ${base}/chats`]: { body: [chat(messages)] },
      [`GET ${base}/chats/${CHAT_ID}`]: { body: chat(messages) },
      ...extra,
    })
  }

  it('links each citation marker to the exact lines and lists the sources', async () => {
    openChat()

    const markers = await screen.findAllByRole('link', { name: 'Source 1: src/flask/app.py:5–6' })
    expect(markers).toHaveLength(2)
    expect(markers[0]).toHaveAttribute('href', `/repositories/${REPO_ID}/files?path=src%2Fflask%2Fapp.py&line=5`)
    expect(screen.getByRole('link', { name: /\[1\]\s*src\/flask\/app\.py:5–6/ })).toHaveTextContent('class Flask:')
  })

  it('renders code names and bullet points, never raw HTML', async () => {
    openChat([question(), reply({ content: 'Uses `create_app` [1].\n\n- First point\n- <img src=x onerror=alert(1)>' })])

    expect(await screen.findByText('create_app', { selector: 'code' })).toBeInTheDocument()
    const items = screen.getAllByRole('listitem').map((item) => item.textContent)
    expect(items).toContain('First point')
    expect(items).toContain('<img src=x onerror=alert(1)>')
    expect(document.querySelector('img')).toBeNull()
  })

  it('shows what was searched and how each part was found', async () => {
    openChat()

    const searched = await screen.findByText('Searched 2 parts of the code')
    const details = searched.closest('details') as HTMLElement
    expect(details).toHaveTextContent('src/flask/app.py:5–6')
    expect(details).toHaveTextContent('found by similar meaning, named in the question')
    expect(details).toHaveTextContent('found by same words')
  })

  it('marks answers the code does not contain', async () => {
    openChat([
      question(),
      reply({ content: 'No database is used in the searched code.' }, { answerable: false, citations: [] }),
    ])

    expect(await screen.findByText('Not found in the code that was searched')).toBeInTheDocument()
  })

  it('warns when nothing in an answer could be confirmed', async () => {
    openChat([question(), reply({ content: 'It probably uses Redis.' }, { citations: [], removed_citations: 2 })])

    expect(await screen.findByText(/No part of this answer could be confirmed/)).toBeInTheDocument()
    expect(screen.getByText(/2 references that could not be confirmed in the code were removed/)).toBeInTheDocument()
  })

  it('shows that an answer is being written and waits before the next question', async () => {
    openChat([question(), reply({ status: 'pending', content: '', details: null })])

    expect(await screen.findByText('Searching the code and writing an answer…')).toHaveAttribute('role', 'status')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })

  it('lets a failed answer be tried again', async () => {
    const user = userEvent.setup()
    const failed = reply({ status: 'failed', content: '', details: null, error_message: 'The AI service is busy.' })
    const { fetchMock } = openChat([question(), failed], {
      [`POST ${base}/chats/${CHAT_ID}/messages/a1/retry`]: { status: 202, body: chat() },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('The AI service is busy.')
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(posted(fetchMock, `${base}/chats/${CHAT_ID}/messages/a1/retry`)).toHaveLength(1)
    expect(await screen.findByRole('link', { name: /\[1\]/ })).toBeInTheDocument()
  })

  it('sends follow-up questions to the same conversation', async () => {
    const user = userEvent.setup()
    const followUp = chat([question(), reply(), question('And the tests?', { id: 'q2' }), reply({ id: 'a2' })])
    const { fetchMock } = openChat(undefined, {
      [`POST ${base}/chats/${CHAT_ID}/messages`]: { status: 202, body: followUp },
    })

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), 'And the tests?{Enter}')

    expect(posted(fetchMock, `${base}/chats/${CHAT_ID}/messages`)).toHaveLength(1)
    expect(await screen.findByRole('heading', { level: 3, name: 'And the tests?' })).toBeInTheDocument()
  })

  it('lists conversations and deletes one after confirming', async () => {
    const user = userEvent.setup()
    const { fetchMock, router } = openChat(undefined, {
      [`DELETE ${base}/chats/${CHAT_ID}`]: { status: 204 },
    })

    const list = await screen.findByRole('navigation', { name: 'Conversations' })
    expect(await within(list).findByRole('link', { name: /How is the app started\?/ })).toHaveAttribute(
      'aria-current',
      'page',
    )

    await user.click(await screen.findByRole('button', { name: 'Delete conversation' }))
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Delete this conversation' }))

    await waitFor(() => expect(router.state.location.search).toBe(''))
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true)
  })
})
