# ADR-007: Arquitetura de Deployment — Frontend React e Backend API em Produção

## Contexto
O frontend React (SPA) e o backend API (FastAPI) precisam ser acessíveis em produção de forma global, segura e comercialmente viável.
Esta decisão afeta autenticação, HTTPS, CORS, pipeline CI/CD e exposição na internet pública.

## Opções Consideradas

### Opção A: Cloud hosted (Vercel / Render / Railway / Fly.io)
- Acesso público pela internet.
- **Free tier**: Vercel Hobby (gratuito, mas limitado a ~100 GB bandwidth/mês, uso non-commercial ou limits rígidos em produção); Render (free tier com 750 horas/mês, bom para MVP); Railway ($5 crédito mensal no Hobby, uso real); Fly.io (crédito inicial ~$5, pay-as-you-go).
- **Custom domain**: Fácil e automático em todos.
- **Ease of CI/CD**: Excelente (Git push → deploy automático via GitHub Actions ou nativo).
- **Requer auth + HTTPS**: Obrigatório e automático.
- **Implicações de exposição pública**: Dados sensíveis expostos (mitigado com HTTPS, JWT/OAuth, encriptação em repouso e minimização de dados enviados). Risco de ataques DDoS/breach, mas providers oferecem proteção básica + WAF opcional.

### Opção B: LAN server
- Hospedado em máquina dedicada na rede local do cliente.
- **Acessibilidade**: Restrita à LAN (acesso só dentro da rede Wi-Fi do cliente). Sem acesso remoto sem VPN adicional.
- **Autenticação**: Mais simples (JWT local ou até sem auth forte, pois rede confiável).
- **Requisito de máquina dedicada**: Precisa de hardware sempre ligado (ex: NAS ou PC dedicado), o que **aumenta complexidade e custo** para o cliente.

### Opção C: VPN-gated server
- Acesso remoto via VPN (ex: Tailscale/WireGuard).
- **Perfil de segurança**: Alto (dados nunca expostos publicamente; tudo dentro de rede privada mesh).
- **Complexidade de setup VPN**: Média-alta com WireGuard puro (config manual de chaves/portas); baixa-média com Tailscale (app install + login SSO → ~3 min, NAT traversal automático, magicDNS).
- **Capacidade de acesso remoto**: Excelente (acesso global seguro sem exposição pública).

### Opção D: Local Docker only
- Roda só na máquina do desenvolvedor/operator (docker-compose local).
- **Viável para demo**: Ótimo para desenvolvimento e testes rápidos.
- **Limitações para longo prazo/produção**: Não escalável, sem acesso multi-dispositivo, sem CI/CD real, sem HTTPS fácil, sem monitoramento central. **Não é viável para produto comercial**.

## Pesquisa: Formas de servir React + FastAPI

### FastAPI servindo React dist/ como static files (single-process deployment)
- FastAPI (Uvicorn/Gunicorn) monta pasta `/static` ou usa `StaticFiles` custom para SPA (catch-all route para index.html em paths não-API).
- **Prós**:
  - Deploy ultra-simples (um único container/processo).
  - Zero CORS (mesmo origin).
  - Ideal para low-traffic ou MVP.
- **Contras**:
  - Uvicorn não otimiza static files (respostas 4-350ms; pior com slow clients/internet ruim).
  - Memória extra para conexões longas (slow clients bloqueiam workers Python).
  - Não recomendado para produção real (comunidade FastAPI sugere evitar para tráfego externo).

### Nginx + FastAPI split
- Nginx serve React dist/ diretamente (static files rápidos, cache, gzip).
- Proxy reverso: `/api/*` → FastAPI (localhost:8000).
- **Prós**:
  - Melhor performance (Nginx lida com slow clients, buffering, conexões simultâneas >1000 com baixa memória).
  - Segurança (backend escondido, rate limiting, headers security via Nginx).
  - Fácil em Docker (multi-stage ou compose com Nginx + FastAPI).
  - Zero CORS issues.
- **Contras**:
  - Config extra (arquivo nginx.conf simples, templates prontos disponíveis).
  - Dois processos/containers (mas overhead mínimo).

**Recomendação técnica**: Usar Nginx + FastAPI split em produção (Docker Compose ou Dockerfile multi-stage).

## Avaliação do backend deployment
- **Backend roda no Pi?** Não.  
  O dispositivo (Pi) roda apenas o scanner que envia dados via HTTPS para a API central.  
  Backend API (FastAPI + DB) roda em servidor separado na nuvem (escalável, multi-tenant, atualizações fáceis, analytics central).

## Tabela Comparativa

| Critério                        | A (Cloud)                          | B (LAN)                          | C (VPN-gated)                    | D (Local Docker)                |
|---------------------------------|------------------------------------|----------------------------------|----------------------------------|---------------------------------|
| **Preço aproximado (inicial)**  | R$0–R$100/mês (free tier → pago)   | Baixo (hardware cliente)         | Médio (server + VPN coord)       | Zero                            |
| **Complexidade de implementação**| Baixa (providers gerenciam)        | Média (setup no hardware)        | Média-Alta (Tailscale simplifica)| Baixa                           |
| **Complexidade para o cliente** | Baixa (plug-and-play, link)        | Alta (acesso só LAN)             | Média (instalar app + login)     | Alta (só dev)                   |
| **Segurança do tráfego**        | Média-Alta (HTTPS + auth forte)    | Alta (local)                     | Alta (privada)                   | Alta (local)                    |
| **Prós**                        | - Acesso global<br>- CI/CD fácil<br>- HTTPS auto<br>- Escalável | - Privacidade máxima<br>- Sem custo nuvem | - Alta privacidade<br>- Acesso remoto seguro<br>- Tailscale (torna **quase** plug-and-play) | - Rápido para dev/teste<br>- Sem custo |
| **Contras**                     | - Acesso público pela internet (mitigado por HTTPS obrigatório, TLS 1.3, autenticação JWT/OAuth2, rate limiting e proteções do provider como WAF/DDoS básico)<br>- Custos escalam | - Sem acesso remoto<br>- Dependente rede cliente | - Maior tempo e complexidade de implementação<br> - Demanda setup extra do cliente<br>- Dificuldade para cliente comum | - Não acessível remotamente<br>- Não escalável<br>- Demo only |

## Matriz de Decisão

| Critério              | A (Cloud) | B (LAN) | C (VPN) | D (Local) |
|-----------------------|-----------|---------|---------|-----------|
| **Segurança**         | ★★★★☆     | ★★★★★   | ★★★★★   | ★★★★★     |
| **Acessibilidade**    | ★★★★★     | ★★☆☆☆   | ★★★★☆   | ★☆☆☆☆     |
| **Complexidade**      | ★★☆☆☆     | ★★★☆☆   | ★★★★☆   | ★☆☆☆☆     |
| **Custo Infra**       | ★★★★☆     | ★★★★★   | ★★★☆☆   | ★★★★★     |
| **Viabilidade Demo/Comercial** | ★★★★★ | ★★☆☆☆   | ★★★☆☆   | ★☆☆☆☆     |
| **Total**                       | **20★**    | **17★**  | **19★**  | **13★**    |

## Decisão
**Escolhida: Opção A: Cloud hosted** (prioridade: Render ou Railway por suporte Docker/FastAPI, custo previsível e bom free tier inicial).  
- Deploy: Docker + Nginx (React static) + proxy FastAPI.
- HTTPS/auth: Automático e obrigatório.
- Backend: Na nuvem (não no Pi).

## Justificativa

A **Opção A: Cloud hosted** foi escolhida por:

- Acesso global sem configuração extra (essencial para produto comercial e usabilidade).
- Libera CPU/memória do dispositivo (apenas scanner + envio leve de dados).
- Atualizações automáticas de backend e frontend (correções de bugs/segurança instantâneas para todos os clientes).
- Experiência plug-and-play (dashboard acessível de qualquer lugar via browser).
- Facilita CI/CD, auto-scaling, logs e monitoramento centralizados.
- Privacidade aceitável (HTTPS + encriptação + minimização de dados; opção C premium para casos ultra-privados).

## Motivo da não escolha da opção C como padrão & Alternativa documentada

A **Opção C (VPN-gated com Tailscale ou similar)** não foi escolhida como arquitetura principal de produção pelos seguintes motivos:

- **Complexidade adicional para o cliente final**: Embora Tailscale simplifique drasticamente o setup (instalação de app mobile/PC + login via SSO Google/Apple/Microsoft + aprovação automática via auth key pré-gerado), ainda exige ~2-5 minutos de configuração manual.
- **Dependência de coordenação externa**: Mesmo com Tailscale (SaaS confiável), há uma camada central de gerenciamento (coord server). Para máxima privacidade/on-premise, seria necessário Headscale (self-hosted), o que aumenta complexidade de manutenção e custo operacional, fora do escopo do MVP.
- **Não essencial para o core do produto**: O foco principal é acessibilidade global, escalabilidade e facilidade. A nuvem atende isso perfeitamente, com privacidade gerenciável via encriptação, tokens e minimização de dados.

## Alternativa documentada como feature futura premium 
A Opção C poderá ser considerada uma **extensão premium de alta privacidade** (ex: plano pago adicional para clientes específicos ou upgrade enterprise), direcionada a nichos específicos:

- Usuários residenciais com alta preocupação de privacidade que rejeitam qualquer dado na nuvem pública.
- **Trade-offs**:
  - **Vantagens**: Privacidade máxima (dados nunca expostos publicamente), acesso remoto seguro, zero dependência de nuvem para o tráfego principal.
  - **Desvantagens**: Fracção maior que cloud, dependência de app Tailscale, custo extra para coordenação (free até ~100 devices; paid para escala).

## Implicações
- **Auth/HTTPS**: JWT/OAuth + HTTPS obrigatório.
- **CORS**: Configurado no backend (ou zero com Nginx same-origin).
- **CI/CD**: GitHub Actions + deploy nativo.
- **Limitações**: Exposição pública (mitigada com boas práticas security).
- **Backend topology**: Nuvem separada do dispositivo.

## Referências

BRATSLAVSKY, P. FastAPI vs Flask 2025: Performance, Speed & When to Choose. Disponível em: https://strapi.io/blog/fastapi-vs-flask-python-framework-comparison. Acesso em: 21 mar. 2026.

FASTAPI; RAMIREZ, S. FastAPI Documentation: Deployment. Disponível em: https://fastapi.tiangolo.com/deployment/. Acesso em: 21 mar. 2026.

FASTAPI; RAMIREZ, S. Static Files. Disponível em: https://fastapi.tiangolo.com/tutorial/static-files/. Acesso em: 21 mar. 2026.

ONEUPTIME. How to Deploy FastAPI to Production: Gunicorn, Docker, Nginx, SSL. Disponível em: https://oneuptime.com/blog/post/2026-02-02-fastapi-production-deployment/view. Acesso em: 21 mar. 2026.

RAILWAY. Pricing. Disponível em: https://railway.com/pricing. Acesso em: 21 mar. 2026.

RENDER. Pricing. Disponível em: https://render.com/pricing. Acesso em: 21 mar. 2026.

TAILSCALE. Pricing: Compare Free Personal Plan & Business Tiers. Disponível em: https://tailscale.com/pricing. Acesso em: 21 mar. 2026.

TAILSCALE. Free Pricing Plans and Discounts. Disponível em: https://tailscale.com/docs/reference/free-plans-discounts. Acesso em: 21 mar. 2026.

VERCEL. Pricing: Hobby, Pro, and Enterprise Plans. Disponível em: https://vercel.com/pricing. Acesso em: 21 mar. 2026.

OMNIWOT. Cloud-Based vs On-Premise IoT Platforms: Pros & Cons Explained. Disponível em: https://omniwot.com/iot-platofrm-in-2025/cloud-based-vs-on-premise-iot-platforms-pros-cons-explained/3741. Acesso em: 21 mar. 2026.

WEBBYLAB. On-Premise Vs Cloud IoT: Choosing Best for Your Business. Disponível em: https://webbylab.com/blog/on-premise-vs-cloud-iot. Acesso em: 21 mar. 2026.

VERY TECHNOLOGY. Enterprise IoT: On-Prem & Hybrid vs. Cloud. Disponível em: https://www.verytechnology.com/insights/enterprise-iot-on-prem-hybrid-vs-cloud. Acesso em: 21 mar. 2026.
