# ADR-005: Modelo de Seguranca v1

> **Status:** Aceito, com duas emendas.
> **(a)** §1 (direcionalidade do canal do agente) **emendado por
> [ADR-011](ADR-011-pi-command-channel.md)** — o canal do agente passa a ser **bidirecional**
> (resultados sobem via `POST /scans`; comandos descem via WSS).
> **(b)** §1 (algoritmo de autenticacao do agente) **emendado em 2026-07-24**: a autenticacao
> agente→API passa de **HMAC-SHA256 simetrico** para **assinatura assimetrica Ed25519**. O
> backend passa a guardar apenas a **chave publica** de cada device; nao existe mais segredo
> recuperavel no servidor, o que **aposenta a [ADR-015](ADR-015-agent-secret-storage-at-rest.md)**
> (armazenamento cifrado do segredo). O envelope de assinatura (string canonica, headers, skew,
> nonce) permanece **identico** — muda apenas o algoritmo e o lado de verificacao. Fundamentacao:
> [`docs/research/device-auth-hmac-vs-asymmetric.md`](../research/device-auth-hmac-vs-asymmetric.md).
> As decisoes de JWT Bearer, CORS e transporte desta ADR permanecem em vigor.

## Contexto

O produto precisa de um modelo de seguranca unico para evitar drift entre arquitetura e implementacao.
Hoje existiam duas fontes com divergencia:

- o ADR apontava HMAC para o agente e JWT com suporte a cookie para o frontend
- o OpenAPI ainda modelava o agente principalmente com `X-API-Key` e aceitava bearer ou session cookie como alternativa nos endpoints atuais

Escopo confirmado para v1:

- um unico device no inicio
- frontend hospedado na cloud
- sem VPN/Tailscale como requisito de v1
- desenvolvimento local pode usar HTTP
- producao deve usar HTTPS

## Decisao

### 1. Agent -> API na v1

> **Emenda 2026-07-24 (algoritmo):** esta secao foi originalmente decidida com **HMAC-SHA256 por
> device**. Ela agora usa **assinatura assimetrica Ed25519 por device**. Motivo: HMAC e simetrico,
> entao o backend precisaria guardar o segredo do device de forma **recuperavel** (foi o que
> originou a ADR-015). Com Ed25519 o backend guarda **apenas a chave publica**; um vazamento do
> banco nao entrega nada forjavel, e a ADR-015 deixa de ser necessaria. Todo o restante desta
> secao — string canonica, headers, skew, nonce, codigos de erro — permanece **inalterado**.
> Fundamentacao: [`docs/research/device-auth-hmac-vs-asymmetric.md`](../research/device-auth-hmac-vs-asymmetric.md).

A autenticacao do agente para a API sera feita por **assinatura Ed25519 por device**
(chave privada no device, chave publica registrada no backend). `X-API-Key` simples nao faz
parte da v1, e nao ha segredo simetrico compartilhado.

Headers obrigatorios em `POST /api/v1/scans`:

- `X-Device-Id`: identificador unico do dispositivo (`agent_id`)
- `X-Timestamp`: timestamp UTC em ISO 8601
- `X-Nonce`: valor unico por request para anti-replay
- `X-Body-SHA256`: hash SHA-256 do corpo bruto da requisicao em hex lowercase
- `X-Signature`: assinatura **Ed25519** da string canonica, em hex lowercase (64 bytes → 128 chars)

String canonica da v1 (inalterada):

```text
METHOD
PATH
X-Device-Id
X-Timestamp
X-Nonce
X-Body-SHA256
```

Regras da v1:

- algoritmo: **Ed25519** (assinatura assimetrica; o backend verifica com a chave publica do device)
- tolerancia de relogio: 5 minutos
- nonce deve ser unico por device dentro da janela de validacao
- `401 Unauthorized`: assinatura ausente, invalida, expirada ou replay detectado
- `403 Forbidden`: device revogado, desconhecido ou sem permissao para envio

Provisionamento e rotacao:

- **cada device gera o proprio par de chaves** (Ed25519) localmente; a chave privada **nunca sai
  do device**
- apenas a **chave publica** e registrada no backend, ligada ao `agent_id`/`org_id` no
  provisionamento — canal de registro precisa de **integridade**, nao de sigilo (chave publica
  nao e segredo)
- rotacao ocorre gerando novo par no device e substituindo a chave publica registrada;
  nao ha segredo a transmitir nem a invalidar de forma confidencial
- a chave privada deve ser armazenada no dispositivo fora do codigo-fonte e fora de artefatos
  versionados (mesma exigencia de antes, agora sobre a chave privada)

> **Emenda (ADR-011):** a v1 assumia o agente como *one-way push* (apenas `POST /api/v1/scans`).
> O escopo Control passou a exigir um canal **backend -> Pi**, tornando o canal do agente
> **bidirecional**: resultados sobem por `POST /api/v1/scans` e comandos descem por WSS
> `…/agents/{agent_id}/commands`. **As mesmas regras de assinatura desta secao** se aplicam ao
> upgrade do WebSocket (string canonica e headers analogos, com hash de corpo vazio). Detalhe em
> [ADR-011](ADR-011-pi-command-channel.md).

### 2. Frontend -> API na v1

Os endpoints atuais do frontend usarao **JWT Bearer** no header `Authorization`.

Decisao de v1:

- endpoints de leitura e operacao ja documentados no OpenAPI usam apenas `Authorization: Bearer <token>`
- session-cookie-only auth nao faz parte da v1
- refresh token em cookie `httpOnly` pode existir apenas quando os endpoints de login/refresh forem adicionados
- esse cookie de refresh nao substitui o Bearer token nos endpoints atuais de negocio

Flags previstas para cookie de refresh quando o fluxo de auth for implementado:

- producao: `HttpOnly`, `Secure`, `SameSite=Lax` ou mais restritivo
- desenvolvimento local HTTP: excecao documentada para `Secure=false`
- se houver mutacoes autenticadas por cookie no futuro, CSRF devera ser tratado explicitamente

### 3. CORS e transporte na v1

CORS da v1 fica fechado para dois cenarios:

- desenvolvimento: `http://localhost:5173`
- producao: `https://app.vscanner.example.com`

Regras da v1:

- sem wildcard em `allow_origins`
- sem referencia normativa a VPN/Tailscale na v1
- producao: HTTPS obrigatorio
- desenvolvimento local: HTTP permitido apenas em ambiente local

### 4. VPN/Tailscale ficam fora da v1

VPN/Tailscale podem aparecer como evolucao futura, mas nao sao requisito, pre-condicao nem atalho de autenticacao da v1.

## Consequencias

- o OpenAPI deve modelar **assinatura Ed25519** no agente (scheme `AgentSignatureAuth`), nao `X-API-Key` nem HMAC
- os endpoints atuais do frontend devem exigir apenas JWT Bearer
- a documentacao de cookie fica restrita ao fluxo futuro de refresh/login, nao como alternativa generica de auth para os endpoints atuais
- CORS e `servers` do OpenAPI devem deixar explicito: HTTPS em producao, HTTP apenas local

## Evolucao planejada (v2+)

Itens que podem ser adicionados depois, sem reabrir a decisao da v1:

- endpoints dedicados de login, refresh e logout
- refresh token em cookie `httpOnly` com contrato OpenAPI proprio
- mTLS para agente (avaliado e descartado para a v1: o edge da Railway termina o TLS, entao um
  client cert nao chega ao processo FastAPI — ver research note)
- rotacao automatica de chave do device e onboarding mais forte

## Resumo executivo da v1

- **Agent -> API**: assinatura **Ed25519** por device (backend guarda so a chave publica; sem segredo recuperavel)
- **Frontend -> API**: JWT Bearer nos endpoints atuais
- **Cookie de refresh**: somente fluxo futuro de auth, nao como auth alternativa do contrato atual
- **CORS**: apenas localhost dev + dominio web de producao
- **Transporte**: HTTPS em producao, HTTP apenas local

## Referencias

- FastAPI Docs: CORS e HTTPS.
- OWASP REST Security Cheat Sheet.
- OWASP Session Management Cheat Sheet.
- RFC 8032: EdDSA / Ed25519 (assinatura assimetrica do agente).
- RFC 2104: HMAC (algoritmo original, substituido pela emenda de 2026-07-24).

