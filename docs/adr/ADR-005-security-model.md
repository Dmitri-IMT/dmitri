# ADR-005: Modelo de Segurança — Autenticação de Agent, API e Frontend

## Contexto
O sistema possui estas interfaces principais que precisam de autenticação:
- **Agent (dispositivo embarcado)** → Backend API (envio de scans de rede/vulnerabilidades).
- **Frontend React** → Backend API (acesso ao dashboard e gerenciamento).

## Threat Model
**Ativos sensíveis**: 
- Lista de dispositivos na rede local + vulnerabilidades detectadas.
- Credenciais de acesso ao dashboard (usuário final).
- Chaves/tokens do dispositivo (para envio de dados).

**Atores/ameaças principais**
- **Atacantes externos na internet** (principal ameaça em cloud): interceptação MITM, brute-force em API, credential stuffing, XSS/CSRF no frontend, API abuse (DDoS, data exfiltration).
- **Usuários maliciosos na mesma LAN** (se device exposto localmente): sniffing de tráfego não-encriptado, spoofing de device.
- **Acesso físico ao dispositivo** (Pi): extração de chaves/firmware, tampering (debug ports).
- **Ataques no backend cloud**: misconfig (open buckets, weak IAM), supply-chain (dependências vulneráveis), insider threats.

**Prioridades**: Proteger confidencialidade/integridade dos scans (dados sensíveis nunca expostos sem auth), disponibilidade do dashboard, integridade do envio de dados do device.

## Opções de autenticação de agente para backend: API key in header, mutual TLS, HMAC-signed requests — vantagens e desvantagens para um contexto incorporado
**Opções avaliadas**:
- **API Key simples (header)**: fácil implementação, baixo overhead no Pi → mas vulnerável a leakage se a key for exposta.
- **Mutual TLS (mTLS)**: altíssima segurança (certificados mútuos) → complexo para embedded (gerenciamento de certificados e revogação no Pi).
- **HMAC-signed requests**: integridade + autenticação (cada request assinado com secret compartilhado) → leve, previne tampering, ideal para IoT.

**Decisão para MVP**: HMAC com secret único por device (provisionado na manufatura ou admin cloud).  
**Alternativa escalável**: JWT via client credentials (OAuth2 M2M).  
**Trade-offs**: HMAC é o melhor equilíbrio para contexto embedded (leve, seguro, sem necessidade de browser).

## Opções de autenticação para frontend
- **JWT (ideal para cloud)**: escalável, não requer sessão no servidor, perfeito para SPA React e múltiplos dispositivos.  
  **Decisão**: Escolhido como principal para Opção A (cloud). Fluxo: login → JWT access token (short-lived) + refresh token.

- **Session cookies (ideal para LAN)**: mais simples em ambientes controlados, mas exige estado no backend (menos escalável em cloud).  
  **Decisão**: Não escolhido para MVP (cloud), mas viável em cenários LAN puro (não priorizado).

- **No auth (VPN-only)**: rede privada atua como autenticação (Tailscale ACLs + magicDNS).  
  **Decisão**: Aceitável apenas para Opção C (VPN-gated futura), onde a rede mesh privada serve como camada de proteção primária.

## Se cloud-deployed, autenticação de frontend é obrigatória? — documentação dos requisitos mínimos
**Cloud (Opção A - principal)**: Autenticação frontend é **obrigatória**.  
**Requisitos mínimos**:
- JWT Bearer token.
- HTTPS obrigatório.
- Login com email/senha ou OAuth SSO.
- Sem opção de "no auth".

## Se VPN/LAN-only, documentação se a proteção em nível de rede é suficiente
**VPN-gated (Opção C: futura)**: Sim, a proteção de rede é suficiente.  
- Tailscale ACLs + SSO no app atuam como autenticação primária.  
- Auth adicional na API (JWT ou session) é opcional.  
- Rede mesh privada elimina necessidade de auth forte na camada de aplicação.

## CORS: com o que o FastAPI precisa ser configurado em cada cenário de implantação?
**Configuração recomendada no FastAPI**:
- **Cloud (A)**: `allow_origins = ["https://app.seudominio.com"]` (restrito ao domínio do frontend).
- **Local/dev**: incluir `["http://localhost:3000", "http://localhost:5173"]`.
- **VPN (C)**: `allow_origins = ["*.ts.net"]` (magicDNS do Tailscale).

## HTTPS: self-signed cert (LAN), Let's Encrypt (cloud), Cloudflare proxy
Decisão por cenário:

- **Cloud (A)**: Automático via provider (Render/Railway/Vercel) + Let's Encrypt (gratuito, auto-renew).
- **VPN (C)**: Tailscale magicDNS + HTTPS interno (self-signed ou Let's Encrypt no backend local).
- **Local/dev** ou LAN puro: Self-signed com mkcert (para trust local) ou HTTP em testes.

## Armazenamento de tokens no navegador: localStorage vs cookie httpOnly — implicações de segurança de cada um.
Decisão: Refresh token em httpOnly + Secure cookie, access token em memory (React state) ou httpOnly cookie.
Comparação:

- localStorage: fácil de usar, mas vulnerável a XSS (JavaScript consegue ler o token).
- httpOnly cookie: protege contra XSS (não acessível por JS), vulnerável a CSRF (mitigado com SameSite=Strict + CSRF token).

**Melhor prática: httpOnly cookies + HTTPS = padrão de segurança para SPAs.**

## Decisão Final

- MVP/TCC (Cloud A): HMAC/JWT para agent, JWT + httpOnly cookies para frontend, CORS restrito, HTTPS automático.
- Feature futura (C - VPN): Network-level protection via Tailscale (auth opcional na API).
- Privacidade adicional: encriptação em trânsito/repouso, minimização de dados, revogação de tokens/keys.

## Referências

- Frontiers: Threat Modelling in IoT Environments. Disponível em: https://www.frontiersin.org/journals/the-internet-of-things/articles/10.3389/friot.2024.1306465/full. Acesso em: 21 mar. 2026.

- FastAPI Docs: CORS e HTTPS. Disponível em: https://fastapi.tiangolo.com/tutorial/cors/ e https://fastapi.tiangolo.com/deployment/https/. Acesso em: 21 mar. 2026.

- Tailscale Docs: Auth Keys e Security Best Practices. Disponível em: https://tailscale.com/docs/features/access-control/auth-keys e https://tailscale.com/docs/reference/best-practices/security. Acesso em: 21 mar. 2026.

- Zuplo: Top 7 API Authentication Methods Compared. Disponível em: https://zuplo.com/learning-center/top-7-api-authentication-methods-compared. Acesso em: 21 mar. 2026.
