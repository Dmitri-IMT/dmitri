---
 
## Contexto
 
O projeto demanda um frontend web para que os dados do scanner possam ser lidos e analizados remotamente. Stakeholders usaram o UI para ver os resultados dos scans automatizados, o report operacional, quais dispostivos estão na rede e sua classificação de risco, etc. O frontend se comunica exclusivamente com o backend FastAPI via um contrato OpenAPI
 
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

### Roteamento: React Router v6

**Decisão:** Usar React Router v6 para roteamento no lado do cliente.

**Alternativas consideradas:**
- TanStack Router — mais recente, totalmente type-safe, mas com comunidade menor e menos documentação no momento
- Wouter — roteador minimalista de 1,5kb, adequado para ferramentas com 2–3 telas; insuficiente para a quantidade de telas deste projeto
- Sem roteador (troca de telas via useState) — quebra o histórico do navegador, sem URLs compartilháveis, difícil de manter cache.

**Justificativa:** A aplicação possui no mínimo 5 telas distintas: dashboard, lista de scans, detalhe do scan, inventário de dispositivos, detalhe do dispositivo e login. As rotas aninhadas do React Router v6 permitem que um único componente de layout `AppShell` (sidebar/navbar persistente) envolva todas as rotas autenticadas, com cada rota filha renderizando seu conteúdo dentro dele. A rota `/login` fica fora do shell. Isso corresponde à UX pretendida: sem recarregamentos completos de página, a URL reflete a tela atual, o botão voltar/avançar do navegador funciona corretamente e os links são compartilháveis.

O React Router v6 é o padrão da indústria. Documentação e suporte da comunidade são extensos.

---

### Busca de Dados: TanStack Query v5

**Decisão:** Usar TanStack Query para todo o gerenciamento de estado do servidor.

**Alternativas consideradas:**
- SWR — leve, excelente para casos de uso de polling somente leitura
- `fetch` puro com `useState`/`useEffect` — viável, mas gera 10+ linhas de código repetitivo por requisição, sem cache, sem deduplicação, sem atualização em segundo plano

**Justificativa:** O caso de uso principal, exibir resultados de scans automáticos a cada 24 horas, é focado em leitura e atendido tanto pelo TanStack Query quanto pelo SWR. Ambos suportam polling via `refetchInterval`/`refreshInterval` com sintaxe e comportamento equivalentes.

O fator decisivo é o gerenciamento de dispositivos. O frontend precisa suportar o registro e a configuração de dispositivos na rede. Isso introduz mutações onde o cache de múltiplos recursos fica desatualizado simultaneamente: um novo dispositivo afeta a lista de dispositivos, o contador de resumo do dashboard e potencialmente as associações com o histórico de scans. O `useMutation` do TanStack Query com invalidação de cache via `onSuccess` lida com isso de forma declarativa e colocada junto à definição da mutação. O SWR exige chamadas manuais de `mutate()` espalhadas pelos componentes.

---

### Biblioteca de Componentes de UI: shadcn/ui

**Decisão:** Usar shadcn/ui como biblioteca de componentes principal.

**Alternativas consideradas:**
- Chakra UI — conjunto extenso de componentes, mas com estética padrão arredondada, pastel e genérica de SaaS; adaptar suas opiniões de design exige mais esforço do que possuir os componentes diretamente
- Mantine — componentes de exibição de dados sólidos, bom suporte a TypeScript, mas entregue como dependência de pacote

**Justificativa:** shadcn/ui não é uma dependência, é uma coleção de componentes copiados diretamente para o projeto em `/src/components/ui/`. Cada componente é de propriedade do projeto, legível e modificável sem precisar contornar as opiniões de uma biblioteca. Mas no final, o fator principal foi o design da biblioteca, o grupo achou o melhor estéticamente. 

---

### Biblioteca de Gráficos: Recharts

**Decisão:** Usar Recharts para todas as visualizações de dados.

**Alternativas consideradas:**
- Nivo — estética padrão superior, mas bundle maior, menos flexível para layouts customizados, lacunas na documentação
- Chart.js — maduro e de alta performance em grandes conjuntos de dados, mas a API imperativa baseada em canvas é estranha ao modelo declarativo do React; os objetos de configuração são verbosos

**Justificativa:** O Recharts expõe uma API JSX totalmente declarativa que se integra naturalmente ao modelo de componentes do React. Os gráficos são compostos como árvores JSX, o que significa que participam do mesmo fluxo de dados e estado que o restante da aplicação. Os tipos de gráficos necessários, distribuição de severidade (pizza/donut), achados ao longo do tempo (barra/linha), são bem suportados com implementação direta. O Recharts é responsivo por padrão e ativamente mantido.

---

## Estrutura de Pastas
```
/src
  /api          ← um arquivo por recurso de API (scans.ts, devices.ts, findings.ts)
  /components   ← componentes de UI reutilizáveis
    /ui         ← cópias dos componentes shadcn/ui ficam aqui
  /pages        ← um arquivo por rota (Dashboard.tsx, ScanList.tsx, etc.)
  /hooks        ← hooks React customizados (useScans, useDevices, etc.)
  /types        ← interfaces TypeScript geradas a partir da especificação OpenAPI
```

---

## Padrão de Cliente de API

Uma instância centralizada do Axios reside em `/src/api/client.ts`. Ela é configurada uma única vez com a URL base (lida de uma variável de ambiente do Vite) e quaisquer headers de autenticação. Todas as funções de endpoint importam essa instância — nenhum componente chama `fetch` ou `axios` diretamente.
```typescript
// /src/api/client.ts
import axios from 'axios';

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

// /src/api/scans.ts
import { client } from './client';
import { ScanResult } from '../types';

export const getScans = (): Promise =>
  client.get('/scans').then(r => r.data);
```

Quando a URL do backend ou o token de autenticação muda, apenas um arquivo é alterado. Nenhum componente é tocado.

---

## Consequências

- O TypeScript adiciona uma etapa de compilação e requer definições de tipos. O benefício é a aplicação em tempo de compilação do contrato OpenAPI.
- Os componentes shadcn/ui devem ser adicionados individualmente via CLI (`npx shadcn-ui@latest add button`). Eles não são importados em massa. Isso é intencional — apenas os componentes realmente utilizados estão presentes no código.
- O TanStack Query requer envolver a aplicação em um `QueryClientProvider`. Isso representa ~5 linhas de configuração em `main.tsx`.
- O React Router v6 requer envolver a aplicação em um `BrowserRouter` e definir uma árvore de rotas. Isso é feito uma única vez em `main.tsx` ou em um arquivo dedicado `routes.tsx`.

---

## Referências

- [Documentação do Vite](https://vitejs.dev)
- [Documentação do React Router v6](https://reactrouter.com)
- [Documentação do TanStack Query v5](https://tanstack.com/query/latest)
- [Documentação do shadcn/ui](https://ui.shadcn.com)
- [Documentação do Recharts](https://recharts.org)
- [openapi-typescript](https://github.com/openapi-ts/openapi-typescript)