import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { viewerProfile } from '@/test/mswHandlers'
import McpConnectionsPanel from './McpConnectionsPanel'

const baseURL = 'http://localhost:8000/api/v1'
const connection = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  client_name: 'Local Claude Code',
  created_at: '2026-10-22T12:00:00Z',
  expires_at: '2026-11-21T12:00:00Z',
  last_used_at: null,
}

function enableMcp() {
  server.use(
    http.get(`${baseURL}/mcp/info`, () =>
      HttpResponse.json({
        enabled: true,
        url: 'https://api.example.test/mcp',
      }),
    ),
    http.get(`${baseURL}/mcp/connections`, () =>
      HttpResponse.json({ data: [] }),
    ),
  )
}

afterEach(() => vi.restoreAllMocks())

describe('MCP connections', () => {
  it('shows the MCP guide and copies commands for the configured server', async () => {
    enableMcp()
    const user = userEvent.setup()
    const writeText = vi.spyOn(navigator.clipboard, 'writeText')
    renderWithProviders(<McpConnectionsPanel />)

    expect(await screen.findByRole('heading', { name: 'MCP' })).toBeVisible()
    expect(
      await screen.findByText(
        'Acme Corp · Read-only access to your organization',
      ),
    ).toBeVisible()
    await user.click(
      screen.getByRole('button', { name: 'Copy add-server command' }),
    )
    expect(writeText).toHaveBeenLastCalledWith(
      'codex mcp add dmitri --url https://api.example.test/mcp',
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Command copied.',
    )
    await user.click(
      screen.getByRole('button', { name: 'Copy sign-in command' }),
    )
    expect(writeText).toHaveBeenLastCalledWith('codex mcp login dmitri')

    await user.click(screen.getByRole('tab', { name: 'Claude Code' }))
    expect(
      screen.getByRole('tabpanel', { name: 'Claude Code' }),
    ).toHaveTextContent(
      'Open Claude Code, run /mcp, select Dmitri, then choose Authenticate.',
    )
    expect(
      screen.queryByRole('button', { name: 'Copy sign-in command' }),
    ).toBeNull()
    await user.click(
      screen.getByRole('button', { name: 'Copy add-server command' }),
    )
    expect(writeText).toHaveBeenLastCalledWith(
      'claude mcp add --transport http --scope user dmitri https://api.example.test/mcp',
    )
    expect(screen.getByText('Copy a prompt into Claude Code.')).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Codex' }))
    expect(
      screen.getByRole('button', { name: 'Copy sign-in command' }),
    ).toBeVisible()
  })

  it.each([
    ['Summarize my latest NSPi scan.', 'cite the scan'],
    ['Which machines expose Modbus?', 'evidence or coverage gaps'],
    [
      'Show findings and their evidence.',
      'supporting evidence and links back to Dmitri',
    ],
  ])('copies the complete prompt for %s', async (label, evidence) => {
    enableMcp()
    const user = userEvent.setup()
    const writeText = vi.spyOn(navigator.clipboard, 'writeText')
    renderWithProviders(<McpConnectionsPanel />)
    await user.click(
      await screen.findByRole('button', { name: `Copy prompt: ${label}` }),
    )
    expect(writeText).toHaveBeenLastCalledWith(
      expect.stringContaining('Use the Dmitri MCP'),
    )
    expect(writeText).toHaveBeenLastCalledWith(
      expect.stringContaining(evidence),
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Prompt copied.',
    )
  })

  it('reports a clipboard failure only in a toast', async () => {
    enableMcp()
    const user = userEvent.setup()
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(
      new Error('Denied'),
    )
    renderWithProviders(<McpConnectionsPanel />)
    await user.click(
      await screen.findByRole('button', { name: 'Copy add-server command' }),
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Could not copy. Select the text and copy it manually.',
    )
    expect(screen.getByTestId('mcp-connections')).not.toHaveTextContent(
      'Could not copy.',
    )
    expect(screen.getByText(/codex mcp add dmitri/)).toBeVisible()
  })

  it('explains uploaded data, read permissions, and model-provider access for viewers', async () => {
    enableMcp()
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )
    renderWithProviders(<McpConnectionsPanel />)
    expect(
      await screen.findByText(/Your NSPi does not need to be online/),
    ).toBeVisible()
    await userEvent.click(
      screen.getByRole('button', { name: 'What can the assistant access?' }),
    )
    expect(
      screen.getByText('Access follows your current organization membership.'),
    ).toBeVisible()
    expect(
      screen.getByText(
        'Read only. It cannot start scans, control devices, or change data.',
      ),
    ).toBeVisible()
    expect(
      screen.getByText(
        'Requested results go to your assistant and its configured model provider.',
      ),
    ).toBeVisible()
  })

  it('hides setup and does not load connections when MCP is disabled', async () => {
    const infoRequest = vi.fn(() =>
      HttpResponse.json({ enabled: false, url: null }),
    )
    const connectionsRequest = vi.fn(() => HttpResponse.json({ data: [] }))
    server.use(
      http.get(`${baseURL}/mcp/info`, infoRequest),
      http.get(`${baseURL}/mcp/connections`, connectionsRequest),
    )
    renderWithProviders(<McpConnectionsPanel />)
    await waitFor(() => expect(infoRequest).toHaveBeenCalledOnce())
    expect(screen.queryByTestId('mcp-connections')).toBeNull()
    expect(connectionsRequest).not.toHaveBeenCalled()
  })

  it('reports a server-info failure through a toast without a fake setup URL', async () => {
    server.use(
      http.get(
        `${baseURL}/mcp/info`,
        () => new HttpResponse(null, { status: 503 }),
      ),
    )
    renderWithProviders(<McpConnectionsPanel />)
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "Couldn't load assistant connections.",
    )
    expect(screen.queryByTestId('mcp-connections')).toBeNull()
  })

  it('lists and disconnects a client, then shows the empty state', async () => {
    enableMcp()
    let connected = true
    const deleted: string[] = []
    server.use(
      http.get(`${baseURL}/mcp/connections`, () =>
        HttpResponse.json({ data: connected ? [connection] : [] }),
      ),
      http.delete(`${baseURL}/mcp/connections/:id`, ({ params }) => {
        deleted.push(String(params.id))
        connected = false
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithProviders(<McpConnectionsPanel />)
    const user = userEvent.setup()
    await user.click(
      await screen.findByRole('button', {
        name: 'Disconnect Local Claude Code',
      }),
    )
    expect(await screen.findByText('No assistants connected.')).toBeVisible()
    expect(deleted).toEqual([connection.id])
    expect(screen.queryByText('Local Claude Code')).not.toBeInTheDocument()
  })

  it('shows request errors only through a toast and allows retry', async () => {
    enableMcp()
    server.use(
      http.get(
        `${baseURL}/mcp/connections`,
        () => new HttpResponse(null, { status: 503 }),
      ),
    )
    renderWithProviders(<McpConnectionsPanel />)
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "Couldn't load assistant connections.",
    )
    expect(screen.getByTestId('mcp-connections')).not.toHaveTextContent(
      "Couldn't load assistant connections",
    )
    server.use(
      http.get(`${baseURL}/mcp/connections`, () =>
        HttpResponse.json({ data: [] }),
      ),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() =>
      expect(screen.getByText('No assistants connected.')).toBeVisible(),
    )
  })

  it('keeps the connection when disconnect fails and reports the error in a toast', async () => {
    enableMcp()
    server.use(
      http.get(`${baseURL}/mcp/connections`, () =>
        HttpResponse.json({ data: [connection] }),
      ),
      http.delete(
        `${baseURL}/mcp/connections/:id`,
        () => new HttpResponse(null, { status: 503 }),
      ),
    )
    renderWithProviders(<McpConnectionsPanel />)
    await userEvent.click(
      await screen.findByRole('button', {
        name: 'Disconnect Local Claude Code',
      }),
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "Couldn't disconnect that assistant.",
    )
    expect(screen.getByText('Local Claude Code')).toBeVisible()
    expect(screen.getByTestId('mcp-connections')).not.toHaveTextContent(
      "Couldn't disconnect that assistant.",
    )
  })
})
