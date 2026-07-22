import { http, HttpResponse } from 'msw'

const baseURL = 'http://localhost:8000/api/v1'

export const validLoginResponse = {
  access_token: 'test-access-token',
  token_type: 'bearer',
  expires_in: 3600,
}

export const handlers = [
  http.post(`${baseURL}/auth/login`, () =>
    HttpResponse.json(validLoginResponse),
  ),
  http.post(`${baseURL}/auth/refresh`, () =>
    HttpResponse.json(validLoginResponse),
  ),
  http.get(`${baseURL}/hosts`, () => HttpResponse.json([])),
]
