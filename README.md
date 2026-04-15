# Vulnerability Scanner Device

Monorepo do Trabalho de Conclusão de Curso (Engenharia de Computação) que irá entregar um dispositivo embarcado capaz de conectar-se a uma rede local, executar varreduras com o Nmap e disponibilizar relatários abrangentes através de um backend e de um frontend web.

# Integrantes

- Giuliano Rodrigues Tumoli // 21.00036-0
- Guilherme Thomasi Ronca // 22.00522-6
- Joao Vitor Marques Ferrenha Cerqueira // 22.00085-2
- Matheus Santos Feitosa // 20.00628-4
- Rafael Maciel Bertani // 21.00634-2

## Componentes do sistema

1. **Hardware Agent (Raspberry Pi 4 + Python + Nmap)**: Executará varreduras rápidas ou completas, normalizará os resultados segundo os schemas compartilhados e enviará os relatários ao backend via REST/HTTPS.
2. **Backend API (FastAPI + PostgreSQL)**: Receberá e validará os resultados, armazenará em PostgreSQL e fornecerá endpoints para consulta pelos clientes.
3. **Banco de Dados (PostgreSQL)**: Fonte única para histórico de scans, dispositivos, portas, findings e telemetria de agentes.
4. **Frontend web (React + Vite + TypeScript)**: Interface em navegador para acompanhar status, resultados e recomendações; consome a API via OpenAPI.
5. **Contratos Compartilhados**: JSON Schemas, OpenAPI e exemplos que asseguram alinhamento entre todos os componentes.
6. **Infraestrutura & CI**: Docker, docker-compose, templates de variáveis de ambiente e pipelines de validação contínua.

## Estrutura do Monorepo

```
docs/                  Documentação inicial; docs/adr/ — decisões de arquitetura (ADRs)
contracts/             Schemas JSON, OpenAPI e exemplos de payloads
hardware-agent/        Pacote Python para o agente embarcado (placeholders)
backend/               Esqueleto FastAPI + Dockerfile + layout de camadas
frontend/              SPA React + Vite + TypeScript (ADR-008; diretório a provisionar)
infra/                 docker-compose, env.example, instruções de infraestrutura
.github/workflows/     Pipeline CI para checar schemas e compilar fontes
LICENSE, README.md, .gitignore
```

## Fluxo de alto nível

1. O agente de hardware agenda e executa scans (quick/full) usando o Nmap na sub-rede configurada.
2. Os resultados são normalizados em JSON conforme `contracts/schemas/scan_result.schema.json`.
3. O backend recebe os payloads, persiste no PostgreSQL e prepara dados agregados.
4. O frontend web consome os endpoints documentados em `docs/api.md` para exibir históricos, alertas e recomendações.

## Versões do projeto (roadmap)

As versões **v1**, **v2** e **v3** descrevem fases da **capacidade de varredura** no agente (ferramentas e profundidade), conforme [ADR-002](docs/adr/ADR-002-scanning-tools-selection.md) e [ADR-006](docs/adr/ADR-006-additional-tools.md). Não confundir com versionamento semver do repositório nem, isoladamente, com caminhos de API como `/api/v1/...`.


| Versão | Foco                  | Conteúdo (resumo)                                                                                                                                                                                                                 |
| ------ | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **v1** | Scanner principal     | Nmap + NSE + script **vulners** (CVE via API passiva). Escopo fixo: observação passiva, sem ferramentas ativas extras.                                                                                                            |
| **v2** | Scanner estendido     | Inclui **enum4linux-ng** (SMB), **testssl.sh** (TLS), **Nikto** e **sqlmap** em avaliação; verificações de credenciais **limitadas** (ex.: tentativas controladas). Ferramentas condicionais conforme portas/serviços detectados. |
| **v3** | Solução personalizada | Cenários com credenciais corporativas, possível **Vuls** para inventário de patches em infraestrutura gerenciada, revalidação de ferramentas mais invasivas (ex.: LinPEAS/WinPEAS) **somente com autorização explícita**.         |


**Segurança e API:** o (HMAC no agente, JWT no frontend, CORS, HTTPS) documenta a primeira entrega de autenticação; evoluções (login/refresh, mTLS, etc.) aparecem como **v2+** naquele ADR, em eixo separado do roadmap de ferramentas acima.

**Dados:** políticas como retenção no banco podem referir-se à primeira entrega no sentido operacional.

## Estado Atual

- Estrutura de diretórios, arquivos placeholder e documentação inicial concluídos.
- Sem qualquer lógica de negócio implementada (scans, validações, rotas, persistência ou UI).
- Ferramentas de desenvolvimento, testes automatizados e integrações externas serão definidas nas próximas fases.

