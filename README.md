# Dmitri

Monorepo do Trabalho de Conclusão de Curso (Engenharia de Computação) que irá entregar um dispositivo embarcado capaz de conectar-se a uma rede local, executar varreduras com o Nmap e, em fases posteriores, disponibilizar relatórios via backend e frontend web.

**Nome do projeto (agente / TUI):** **Dmitri** — interface em terminal e pipeline de varredura no Raspberry Pi.

https://mauabr-my.sharepoint.com/:w:/r/personal/22_00085-2_maua_br/Documents/ATIVIDADE%201%20-%20TCC%20-%202026.docx?d=w0581bf6338ae4395a2070a5a633a5023&csf=1&web=1&e=VTZq7k

# Integrantes

- Giuliano Rodrigues Tumoli // 21.00036-0
- Guilherme Thomasi Ronca // 22.00522-6
- Joao Vitor Marques Ferrenha Cerqueira // 22.00085-2
- Matheus Santos Feitosa // 20.00628-4
- Rafael Maciel Bertani // 21.00634-2

## Escopo e premissas (TCC)

- **Duração:** 8 meses (entrega alinhada ao TCC).
- **Implantação atual (v1):** varreduras no **laboratório de NSPi** da universidade — não se assume uso campus-wide ou redes arbitrárias sem decisão explícita.
- **Usuários:** até **10** operadores/visualizadores em cenário típico.
- **Carga:** **1–2 varreduras por dia** em operação normal (evitar dimensionar como produção 24/7 ou alto throughput sem necessidade).
- **Evolução:** versões futuras (**v2/v3**) podem **ampliar o escopo operacional** (mais locais, usuários ou frequência).

## Foco atual do desenvolvimento

Por ora o grupo está construindo **apenas o agente embarcado com TUI** (**Dmitri**): varreduras, normalização de resultados e uso pelo operador no próprio dispositivo.

- **Em escopo agora:** `hardware-agent`, interface Textual (`dmitri`), contratos JSON compartilhados e CI relacionado ao agente.
- **Fora de escopo por enquanto:** **backend** (FastAPI), **frontend** web e implantação cloud descritos na arquitetura-alvo. Esses componentes permanecem planejados; integração virá em uma fase posterior.

## Ambiente de implantação: laboratório NSPi

O foco operacional atual é implantar o **Dmitri** no **NSPi** — laboratório de robótica industrial da universidade (rede do laboratório, não campus inteiro). O cenário orienta prioridades de rede e visibilidade dos equipamentos locais.

Equipamentos e sistemas típicos no ambiente (referência para contexto da rede):

| Fabricante / papel | Observações |
| ------------------ | ----------- |
| **CLP Schneider** | Unix; Modbus |
| **Outro CLP** | Windows Embedded 2013 |
| **Balluf** | IO, IO-Link, EtherCAT |
| **Beckhoff** | EtherCAT, OPC UA |
| **CLP Altus** | — |
| **Raspberry Pi** | Agente Dmitri (escaneia a partir da conectividade disponível) |

**Conectividade:** os CLPs costumam estar em **Ethernet**; o Raspberry Pi acessa a rede do laboratório via **Wi‑Fi**.

## Componentes do sistema

Visão completa do sistema; **itens 2–4 não estão em desenvolvimento ativo** enquanto o foco for apenas o **Dmitri** (TUI + agente).

1. **Hardware Agent (Raspberry Pi 4 + Python + Nmap + Dmitri)**: Varreduras rápidas ou completas, normalização segundo os schemas compartilhados e uso pelo operador via TUI; **envio ao backend** via REST/HTTPS fica para uma **fase posterior**.
2. **Backend API (FastAPI + PostgreSQL)**: Receberá e validará os resultados, armazenará em PostgreSQL e fornecerá endpoints para consulta pelos clientes *(planeado)*.
3. **Banco de Dados (PostgreSQL)**: Fonte única para histórico de scans, dispositivos, portas, findings e telemetria de agentes *(planeado)*.
4. **Frontend web (React + Vite + TypeScript)**: Interface em navegador para acompanhar status, resultados e recomendações; consome a API via OpenAPI *(planeado)*.
5. **Contratos Compartilhados**: JSON Schemas, OpenAPI e exemplos que asseguram alinhamento entre todos os componentes.
6. **Infraestrutura & CI**: Docker, docker-compose, templates de variáveis de ambiente e pipelines de validação contínua.

## Estrutura do Monorepo

```
docs/                  Documentação inicial; docs/adr/ — decisões de arquitetura (ADRs)
contracts/             Schemas JSON, OpenAPI e exemplos de payloads
hardware-agent/        Pacote Python do agente embarcado + TUI Dmitri (foco atual)
backend/               Esqueleto FastAPI + Dockerfile + layout de camadas
frontend/              SPA React + Vite + TypeScript (ADR-008; diretório a provisionar)
infra/                 docker-compose, env.example, instruções de infraestrutura
.github/workflows/     Pipeline CI para checar schemas e compilar fontes
LICENSE, README.md, .gitignore
```

## Fluxo de alto nível

1. O operador inicia o **Dmitri** (TUI), confirma a sub-rede e escolhe a categoria e o **modo de varredura** (ver tabela abaixo).
2. O agente executa o pipeline Nmap (descoberta de hosts → portas → inspeção profunda com NSE, conforme o modo) e normaliza a saída.
3. Os resultados são gravados em JSON conforme o contrato de ingest (`ScanIngestRequest`) em `contracts/openapi/openapi.yaml` (localmente no Pi).

### Modos de varredura (TUI)

O modo é escolhido na interface; o valor `scan_mode` no payload segue o enum `ScanMode` em `contracts/openapi/openapi.yaml`.

| Modo (UI) | `scan_mode` | Escopo (resumo) |
| --------- | ----------- | ---------------- |
| **Quick** | `quick` | Varredura rápida nas portas padrão do Nmap (top 1000); script `vulners` |
| **Standard** | `standard` | Varredura padrão com scripts NSE no estágio de descoberta |
| **Extensive** | `extensive` | Análise de segurança nas top 10 000 portas; `vulners.mincvss = 3.0` |
| **MAX** | `max` | Todas as portas (`-p-`), mesmo conjunto NSE que Extensive; `vulners.mincvss = 1.0` (auditoria completa; ~45 min+) |
| **NSPi** | `nspi` | Fluxo dedicado ao laboratório NSPi (categoria própria no TUI) |

O modo legado **`full`** (all-ports via variável de ambiente / caminho headless) está **sendo removido**; **MAX** é o sucessor no TUI, com `-p-` e scripts completos — acompanhar [#57](https://github.com/Dmitri-IMT/vulnerability-scanner-device/issues/57) e [#70](https://github.com/Dmitri-IMT/vulnerability-scanner-device/issues/70).

**Visão alvo (quando backend e frontend estiverem em uso):**

4. O backend recebe os payloads, persiste no PostgreSQL e prepara dados agregados.
5. O frontend web consome os endpoints documentados em `docs/api.md` para exibir históricos, alertas e recomendações.

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

- **Prioridade:** TUI **Dmitri** e pipeline de varredura no `hardware-agent` (Nmap, normalização, testes e CI do agente).
- **Em curso:** modo **MAX** e remoção do modo legado **`full`** — [#57](https://github.com/Dmitri-IMT/vulnerability-scanner-device/issues/57), [#70](https://github.com/Dmitri-IMT/vulnerability-scanner-device/issues/70).
- **Não prioritário neste momento:** implementação do backend, frontend e ingestão remota — permanecem planejados conforme contratos em `contracts/` e [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).
- **Implantação-alvo:** laboratório **NSPi** (ver secção acima).

**Documentação de referência**

| Tópico | Onde |
| ------ | ---- |
| Arquitetura de sistema | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Pipeline NSE / modos | [docs/implementation/NSE-VULNERABILITY-PIPELINE.md](docs/implementation/NSE-VULNERABILITY-PIPELINE.md) |
| Agente + TUI (setup) | [hardware-agent/README.md](hardware-agent/README.md), [docs/DEV-SETUP.md](docs/DEV-SETUP.md) |

## Setup

Run the automated installer from the repo root:

```bash
./install.sh
```

Or follow the manual guide:

→ [docs/DEV-SETUP.md](docs/DEV-SETUP.md)

### Local database (backend tests)

`install.sh` is the one-time bootstrap: it installs everything and brings up the local
Supabase stack, but it **drops and recreates** `dmitri_test` on every run. For day-to-day
work use `database.sh` instead — it is idempotent and never deletes volumes, so the local
database survives:

```bash
./database.sh          # start Docker + Supabase, ensure dmitri_test exists, tidy images
./database.sh --test   # ...and run the backend suite against it
```

It also recovers from the state where the Supabase CLI still believes the stack is running
after a container has exited, which otherwise makes `supabase start` refuse to run.

| Flag | Effect |
| ---- | ------ |
| `--test` | run the backend suite after setup |
| `--no-clean` | skip the Docker image cleanup |
| `--deep-clean` | also remove unused Supabase images — note `supabase start` re-pulls its whole image set, so these come back |

To run the suite yourself:

```bash
cd backend
DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest
```

The database name must be exactly `dmitri_test` — `conftest.py` aborts otherwise. Alembic is
the sole schema owner (`conftest.py` migrates to head itself), so never point
`supabase db reset|push|migration` at this schema. Without `DATABASE_URL_TEST` the DB-backed
tests skip rather than fail, so a bare `uv run pytest` stays green — it just proves much less.

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md)
