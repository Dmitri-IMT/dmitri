# ADR-008: Stack do Frontend

> **Status:** Aceito (2026-03-22) — **revisado em 2026-07-10 (DMI-54):** React Router atualizado
> para **v7 (modo library)**; seção de **auth client** adicionada; racional do TanStack Query e
> inventário de telas atualizados para o escopo Control ([`FRONTEND.md`](../roadmap/FRONTEND.md),
> [`AUTH.md`](../roadmap/AUTH.md)); geração de tipos via openapi-typescript promovida a decisão.
> As decisões de Vite, TypeScript e shadcn/ui permanecem como originalmente registradas.
> **Recharts** permanece a escolha caso uma visualização seja posteriormente incluída, mas não é
> parte do MVP Home nem do scaffold inicial, conforme [`ui/SCREENS.md`](../ui/SCREENS.md).
>
> **Revisão 2026-07-13:** o `AppShell` foi estreitado de *"sidebar/navbar"* para **top bar, sem
> sidebar**. Fundamentos visuais compartilhados (shell, viewport, componentes, regras de
> consistência) passam a ser propriedade de [`ui/SCREENS.md`](../ui/SCREENS.md#foundations) —
> **essa é a fonte da verdade da UI**; este ADR possui a *stack*, não o desenho das telas.

---

## Contexto

O projeto demanda um frontend web — SPA em **React 19 + TypeScript** — que se comunica
exclusivamente com o backend FastAPI via o contrato OpenAPI
([`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml)).

A plataforma tem dois papéis ([`AUTH.md`](../roadmap/AUTH.md)):

- **Org admin** — operador não-técnico: faz login, convida usuários, gerencia papéis, vê os
  agents (Pis) online/offline, dispara scans ("Scan now") e lê os resultados.
- **Viewer** — somente leitura: Home, scans, hosts e agents; não vê as ações de mutação nem
  Users & invites.

A modelagem das telas é **admin-first**. A primeira fatia de implementação é login → Home com
dados reais; as demais superfícies admin e de leitura seguem os fluxos em
[`ui/FLOWS.md`](../ui/FLOWS.md) e o roadmap em [`FRONTEND.md`](../roadmap/FRONTEND.md).

**Inventário de telas** (inventário apenas — fluxos em [`docs/ui/FLOWS.md`](../ui/FLOWS.md);
layouts, estados e copy em [`docs/ui/SCREENS.md`](../ui/SCREENS.md)): login · aceite de convite (definir senha) ·
esqueci/reset de senha · troca forçada de senha · gestão de usuários/convites · Home ·
lista/detalhe de scans · inventário/detalhe de hosts · agents (online/offline + "Scan now") ·
painel LLM explainer (posterior, ver [`AI.md`](../roadmap/AI.md)).

---

## Decisões

### Ferramente de Build: Vite

**Decisão:** Usar Vite como a ferramenta de build e servidor dev.

**Alternativas consideradas:**
- Create React App (CRA) — oficialmente deprecado desde 2023, não é mais mantido e por isso pode introduzir bugs e vulnerabilidades
- Webpack — viável mas requere configuração extensa de código, sem beneficios aparentes em comparação ao Vite.
- Next.js — framework de React FullStack; não é necessário pois backend já vai ser feito com FastAPI, desenvolver pensando em Next vai além do escopo do projeto.

**Justificativa:** Vite é o padrão atual da comunidade e da documentação oficial do React para novos projetos. O servidor de desenvolvimento inicia em milissegundos, contra 30–60 segundos com CRA/Webpack. O HMR (Hot Module Replacement) é quase instantâneo. Nenhuma configuração relevante é necessária para um projeto React + TypeScript.

---

### Linguagem: TypeScript

**Decisão:** Usar TypeScript no frontend.

**Alternativas consideradas:**
- JavaScript

**Justificativa:** O FastAPI consegue gerar uma especificação OpenAPI automaticamente e ferramentas como o openapi-typescript conseguem consumir essa especificação e gerar interfaces TypeScript diretamente, o que significa que o sistema de tipos do frontend fica sincronizado com o contrato do backend no momento da geração.

Sem TypeScript, essa garantia de contrato desaparece completamente. Uma renomeação de campo no backend vira um bug em tempo de execução, descoberto apenas ao testar a interface manualmente. Com TypeScript, isso se torna um erro em tempo de compilação, detectado imediatamente em todos os arquivos que referenciam aquele campo.

---

### Geração de Tipos: openapi-typescript

**Decisão:** Gerar as interfaces TypeScript a partir de
[`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) com **openapi-typescript**,
via script (`npm run gen:types`), com o resultado versionado em `/src/types`.

**Alternativas consideradas:**
- Tipos escritos à mão — drift garantido em relação ao contrato; exatamente o problema que a decisão de TypeScript acima pretende eliminar.
- orval / openapi-generator — geram clientes HTTP inteiros além dos tipos; mais maquinário do que o necessário, já que o client Axios central (abaixo) cumpre esse papel.

**Justificativa:** é o mecanismo que materializa a garantia de contrato da decisão de TypeScript:
uma mudança de campo no backend vira erro de compilação em todos os pontos de uso. O resultado
versionado torna o drift visível em diff de PR quando o contrato muda.

---

### Roteamento: React Router v7 (modo library)

**Decisão:** Usar React Router **v7 em modo library/declarativo** (pacote `react-router`) para roteamento no lado do cliente.

**Alternativas consideradas:**
- React Router v6 — a decisão original (2026-03); em modo manutenção desde o lançamento da v7 (nov/2024). Escolher v6 num scaffold greenfield em 2026 assume uma migração conhecida no dia um, sem contrapartida.
- React Router v7 em **modo framework** — herança do Remix: file routing, loaders/actions, SSR via plugin próprio do Vite. **Explicitamente não adotado:** é maquinário além do necessário para uma SPA pura atrás do FastAPI, e loaders competiriam com o TanStack Query pela posse do data-fetching.
- TanStack Router — totalmente type-safe e com boa integração com TanStack Query, mas comunidade e documentação menores; re-abriria uma decisão já assentada sem dor concreta que a justifique.
- Wouter — roteador minimalista de 1,5kb, adequado para ferramentas com 2–3 telas; insuficiente para a quantidade de telas deste projeto.
- Sem roteador (troca de telas via useState) — quebra o histórico do navegador, sem URLs compartilháveis, difícil de manter cache.

**Justificativa:** o modo library da v7 preserva a API e o modelo mental da v6 — a justificativa
original sobrevive intacta, só muda a major e o pacote. A aplicação possui ~10 telas (ver
inventário no Contexto). As rotas aninhadas permitem que um único componente de layout `AppShell`
(**top bar persistente — sem sidebar**, ver [`ui/SCREENS.md`](../ui/SCREENS.md#app-shell)) envolva
todas as rotas autenticadas, com cada rota filha renderizando
seu conteúdo dentro dele. As telas públicas de auth (`/login`, aceite de convite, esqueci/reset de
senha) ficam fora do shell. Isso corresponde à UX pretendida: sem recarregamentos completos de
página, a URL reflete a tela atual, o botão voltar/avançar do navegador funciona corretamente e os
links são compartilháveis.

---

### Busca de Dados: TanStack Query v5

**Decisão:** Usar TanStack Query para todo o gerenciamento de estado do servidor.

**Alternativas consideradas:**
- SWR — leve, excelente para casos de uso de polling somente leitura
- `fetch` puro com `useState`/`useEffect` — viável, mas gera 10+ linhas de código repetitivo por requisição, sem cache, sem deduplicação, sem atualização em segundo plano

**Justificativa:** No lado de leitura — dashboards, listas de scans/hosts e polling — TanStack
Query e SWR são equivalentes (`refetchInterval`/`refreshInterval`). O fator decisivo são as
**mutações com invalidação de múltiplos caches**, que existem em dois fluxos reais do escopo de
setembro:

1. **Admin** — convidar usuário, alterar papel → invalida a lista de usuários e os convites
   pendentes.
2. **"Scan now"** ([`FRONTEND.md`](../roadmap/FRONTEND.md), ADR-011) — `useMutation` com
   `POST /agents/{agent_id}/commands` → poll de `GET /commands/{command_id}` com
   `refetchInterval` enquanto o status é pendente (`queued → delivered → running → uploading`) →
   ao chegar em `done`, invalidar `['scans']`, `['agents']` e `['findings']`. Erros do contrato
   tratados na mutação: **503** `device_offline` e **409** `device_busy` (copy ainda aberta em
   `ui/FLOWS.md`).

O `useMutation` do TanStack Query com invalidação de cache via `onSuccess` lida com isso de forma
declarativa e colocada junto à definição da mutação. O SWR exige chamadas manuais de `mutate()`
espalhadas pelos componentes.

> **Nota (revisão 2026-07):** a justificativa original citava o registro/configuração de
> dispositivos como fator decisivo. Esse fluxo saiu do admin UI de setembro — o provisionamento do
> Pi é do instalador/vendor ([`AUTH.md`](../roadmap/AUTH.md)). A decisão permanece válida pelas
> mutações acima; se a configuração de dispositivos voltar ao escopo, ela reforça (não altera) esta
> escolha.

---

### Auth Client

**Decisão:** access token **em memória** + refresh via **cookie httpOnly** (fixado pelo
contrato); **interceptors** no client Axios central; **guards de rota** e gating por papel.

O contrato já fixa o transporte: `POST /auth/login` retorna o access JWT no corpo e o refresh
token em `Set-Cookie` httpOnly, rotacionado a cada `POST /auth/refresh`. A **política** (TTLs,
rotação, matriz de permissões) pertence a [`AUTH.md`](../roadmap/AUTH.md) /
[`ADR-005`](ADR-005-security-model.md); esta seção fixa apenas a mecânica do cliente. Valores de
política citados abaixo refletem AUTH.md em 2026-07.

**Armazenamento do access token — alternativas consideradas:**

| Opção | Sobrevive ao reload | Exposição a XSS | Veredito |
| --- | --- | --- | --- |
| Memória (module scope) | não | não persiste; janela limitada ao TTL do access | **Adotado** |
| localStorage | sim | legível por qualquer script injetado | Rejeitado |
| Cookie httpOnly também para o access | sim | não legível por script | Rejeitado — exigiria proteção CSRF em toda rota da API; o padrão do contrato é Bearer |

A perda no reload não é um problema: o boot da aplicação restaura a sessão silenciosamente via
refresh (passo 5 abaixo).

**Ciclo de vida da sessão:**

1. **Login** → access JWT em memória + refresh cookie (janela de re-login de **7 dias** — AUTH.md).
2. **Requisições** → interceptor de request anexa `Authorization: Bearer <access>`.
3. **Access expira** → resposta 401 → interceptor de response executa **um único**
   `POST /auth/refresh` (*single-flight*: 401s concorrentes aguardam a mesma promise) e repete a
   requisição original uma vez.
4. **Refresh falha** (expirado/revogado) → limpar estado em memória e redirecionar para `/login`.
5. **Boot/reload** → tentar `POST /auth/refresh` antes de renderizar rotas protegidas; sucesso
   restaura a sessão, falha cai em `/login`.
6. **Logout** → `POST /auth/logout` (revoga o refresh server-side e limpa o cookie) → `/login`.

**Postura CSRF:** o único ponto autenticado por cookie é o refresh. `withCredentials` fica
restrito a `/auth/login`, `/auth/refresh` e `/auth/logout`; todas as demais chamadas usam Bearer
(imune a CSRF). Flags do cookie (`HttpOnly`, `Secure`, `SameSite`) são responsabilidade do backend
(ADR-005 / AUTH.md).

**Troca forçada de senha (rotação a cada 3 meses — AUTH.md):** o contrato retorna **403** no login
quando a senha expirou → o frontend redireciona para a tela de troca obrigatória e bloqueia o resto
do app até concluir.

> ⚠️ **Ponto de contrato a resolver antes de implementar esta tela:** `POST /auth/change-password`
> exige Bearer, mas o login com senha expirada retorna 403 **sem emitir token** — enquanto AUTH.md
> diz que "login may succeed only to reach change-password flow". O contrato precisa ou de um token
> limitado no 403, ou de login bem-sucedido com escopo restrito. Registrar a resolução em AUTH.md +
> contrato.

**Papéis e guards:** o papel (`admin`/`viewer` — AUTH.md) vem de **`GET /users/me`**, não de
claims decodificadas do JWT. O access token carrega apenas identidade de sessão; o
`SessionProvider` (spec 020) é o único leitor do papel e nada no SPA decodifica o token — um payload
com `role: admin` não altera o que a UI renderiza (B11-C16). Uma rota de layout protegida envolve o
`AppShell` (não autenticado → `/login`); rotas de admin e ações de mutação (ex.: botão "Scan now",
visível só para `admin`) têm gating por papel no cliente — como UX apenas: a autorização real é
sempre do backend.

---

### Biblioteca de Componentes de UI: shadcn/ui

**Decisão:** Usar shadcn/ui como biblioteca de componentes principal, sobre **Tailwind CSS v4**
(dependência de estilo requerida pelo shadcn/ui).

**Alternativas consideradas:**
- Chakra UI — conjunto extenso de componentes, mas com estética padrão arredondada, pastel e genérica de SaaS; adaptar suas opiniões de design exige mais esforço do que possuir os componentes diretamente
- Mantine — componentes de exibição de dados sólidos, bom suporte a TypeScript, mas entregue como dependência de pacote

**Justificativa:** shadcn/ui não é uma dependência, é uma coleção de componentes copiados diretamente para o projeto em `/src/components/ui/`. Cada componente é de propriedade do projeto, legível e modificável sem precisar contornar as opiniões de uma biblioteca. Mas no final, o fator principal foi o design da biblioteca, o grupo achou o melhor estéticamente.

---

### Biblioteca de Gráficos: Recharts (quando necessário)

**Decisão:** Se uma visualização de dados entrar no escopo, usar Recharts. Não instalar nem criar
gráficos para o MVP atual: a tela principal é a **Home**, uma revisão de julgamento em linguagem simples,
não um dashboard de métricas.

**Alternativas consideradas:**
- Nivo — estética padrão superior, mas bundle maior, menos flexível para layouts customizados, lacunas na documentação
- Chart.js — maduro e de alta performance em grandes conjuntos de dados, mas a API imperativa baseada em canvas é estranha ao modelo declarativo do React; os objetos de configuração são verbosos

**Justificativa:** O Recharts expõe uma API JSX declarativa que se integra naturalmente ao modelo
de componentes do React. Se uma necessidade futura justificar gráficos, a decisão evita reabrir a
escolha de biblioteca. Ela não é autorização para introduzir donut, série temporal ou cards de
métrica que o produto deliberadamente retirou do MVP.

---

## Estrutura de Pastas
```
/src
  /api          ← client.ts + um arquivo por recurso de API
                  (auth.ts, users.ts, invites.ts, scans.ts, hosts.ts, agents.ts, findings.ts)
  /components   ← componentes de UI reutilizáveis
    /ui         ← cópias dos componentes shadcn/ui ficam aqui
  /pages        ← um arquivo por rota (Home.tsx, ScanList.tsx, Agents.tsx, etc.)
  /hooks        ← hooks React customizados (useScans, useHosts, useCommandPolling, etc.)
  /types        ← interfaces TypeScript geradas a partir da especificação OpenAPI
```

---

## Padrão de Cliente de API

Uma instância centralizada do Axios reside em `/src/api/client.ts`. Ela é configurada uma única
vez com a URL base (lida de uma variável de ambiente do Vite) e com os **interceptors de auth**
(seção *Auth Client* acima). Todas as funções de endpoint importam essa instância — nenhum
componente chama `fetch` ou `axios` diretamente.
```typescript
// /src/api/client.ts
import axios from 'axios';

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

// /src/api/scans.ts
import { client } from './client';
import { ScanResult } from '../types';

export const getScans = (): Promise<ScanResult[]> =>
  client.get('/scans').then(r => r.data);
```

Quando a URL do backend ou a mecânica de auth muda, apenas um arquivo é alterado. Nenhum componente é tocado.

---

## Consequências

- O TypeScript adiciona uma etapa de compilação e requer definições de tipos. O benefício é a aplicação em tempo de compilação do contrato OpenAPI.
- Os tipos gerados exigem rodar `gen:types` quando o contrato muda; o resultado versionado torna o drift visível em PR.
- Os componentes shadcn/ui devem ser adicionados individualmente via CLI (`npx shadcn@latest add button`). Eles não são importados em massa. Isso é intencional — apenas os componentes realmente utilizados estão presentes no código.
- O interceptor de refresh *single-flight* concentra complexidade real em `client.ts` — é o preço de manter tokens fora do localStorage.
- O TanStack Query requer envolver a aplicação em um `QueryClientProvider`. Isso representa ~5 linhas de configuração em `main.tsx`.
- O React Router v7 (modo library) requer envolver a aplicação em um `BrowserRouter` e definir uma árvore de rotas. Isso é feito uma única vez em `main.tsx` ou em um arquivo dedicado `routes.tsx`.

---

## Referências

- [Documentação do Vite](https://vitejs.dev)
- [Documentação do React Router v7](https://reactrouter.com)
- [Documentação do TanStack Query v5](https://tanstack.com/query/latest)
- [Documentação do shadcn/ui](https://ui.shadcn.com)
- [Documentação do Tailwind CSS](https://tailwindcss.com)
- [Documentação do Recharts](https://recharts.org)
- [openapi-typescript](https://github.com/openapi-ts/openapi-typescript)
- [`AUTH.md`](../roadmap/AUTH.md) · [`FRONTEND.md`](../roadmap/FRONTEND.md) · [`ADR-005`](ADR-005-security-model.md) · [`ADR-011`](ADR-011-pi-command-channel.md)
