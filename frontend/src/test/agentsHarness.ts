import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { defaultAgent, defaultCommand } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type CommandDetail = components['schemas']['CommandDetail']
type ErrorResponse = components['schemas']['ErrorResponse']

export const baseURL = 'http://localhost:8000/api/v1'

export function agentDetail(agent: AgentDetail) {
  server.use(
    http.get(`${baseURL}/agents`, () => HttpResponse.json({ data: [agent] })),
    http.get(`${baseURL}/agents/:agentId`, () => HttpResponse.json(agent)),
  )
}

export function noAgents() {
  server.use(
    http.get(`${baseURL}/agents`, () => HttpResponse.json({ data: [] })),
  )
}

export function agentsFail() {
  server.use(
    http.get(
      `${baseURL}/agents`,
      () => new HttpResponse(null, { status: 500 }),
    ),
  )
}

export function commandStatuses(statuses: CommandDetail['status'][]) {
  let index = 0
  server.use(
    http.get(`${baseURL}/commands/:commandId`, () => {
      const status = statuses[Math.min(index, statuses.length - 1)]
      index += 1
      return HttpResponse.json({
        ...defaultCommand,
        status,
        completed_at: status === 'done' ? new Date().toISOString() : null,
      })
    }),
  )
}

export function commandRefused(status: number, code: string) {
  const response = {
    error: { code, message: code, details: {} },
  } satisfies ErrorResponse
  server.use(
    http.post(`${baseURL}/agents/:agentId/commands`, () =>
      HttpResponse.json(response, { status }),
    ),
  )
}

export function withActiveCommand(
  command: CommandDetail = defaultCommand,
  agent: AgentDetail = defaultAgent,
) {
  agentDetail({ ...agent, active_command_id: command.command_id })
  server.use(
    http.get(`${baseURL}/commands/:commandId`, () =>
      HttpResponse.json(command),
    ),
  )
}
