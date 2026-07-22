# ADR-009: Stack de Banco de Dados

> **Status:** Aceito — **revisado em 2026-07-15 (DMI-79):** a decisão *sync-everywhere*
> (2026-07-14, adotada no rebuild do app shell do backend — [DMI-56](https://linear.app/dmitri-imt/issue/DMI-56/backend-app-shell-rebuild))
> **supersede as linhas de driver `asyncpg` e `psycopg2`** deste ADR. O backend usa
> **SQLAlchemy `Session` síncrono sobre psycopg3** (`psycopg[binary]>=3.1.12`), sem asyncpg.
> Ver a seção *Driver: psycopg3 (síncrono)* abaixo. As demais decisões (Supabase, SQLModel,
> Alembic, modos de conexão, fila no Postgres) permanecem como originalmente registradas.

## Decisão
 
### Engine de banco de dados
 
**PostgreSQL via Supabase (cloud).** Versão do PostgreSQL: conforme provisionado pelo Supabase (atualmente 15.x — verificar no dashboard no momento da configuração).
 
O banco não roda no Pi. Backend API e Background Worker (cloud) conectam remotamente ao Supabase via internet.

---
 
### ORM: SQLModel 0.0.21

#### ORM: Ponte entre código Python e banco de dados relacional
 
**Decisão: SQLModel.**
 
SQLModel é construído sobre SQLAlchemy 2.x + Pydantic v2. Um único modelo de classe serve simultaneamente como tabela do banco e schema de resposta da API, eliminando o drift entre modelos de banco e schemas OpenAPI.
 
**Alternativas avaliadas e rejeitadas:**
 
| ORM | Motivo de rejeição |
|-----|-------------------|
| SQLAlchemy 2.x puro | Requer modelos separados dos schemas Pydantic; aumenta superfície de drift com a OpenAPI spec |
| Tortoise ORM | Async-first, mas sem integração nativa com Pydantic e ecossistema menor; não justifica troca |
 
**Versão pinada:** `sqlmodel==0.0.21`
 
---
 
### Driver: psycopg3 (síncrono)

> **Supersede (2026-07-15, DMI-79):** a decisão original deste ADR era `asyncpg` como driver
> assíncrono de produção, com `psycopg2` mantido apenas para o Alembic. A decisão
> *sync-everywhere* (2026-07-14, [DMI-56](https://linear.app/dmitri-imt/issue/DMI-56/backend-app-shell-rebuild))
> substituiu ambos por **psycopg3 síncrono**. O texto original é preservado abaixo apenas como
> registro histórico.

**Decisão (vigente): psycopg3 (`psycopg[binary]`) com SQLAlchemy `Session` síncrono.**

O app shell rebuild adotou acesso a banco **totalmente síncrono**: um único estilo de sessão
(`Session` do SQLAlchemy) para API, worker, Alembic e scripts, eliminando a divisão async/sync e o
par de drivers. As connection strings são normalizadas para o dialeto `postgresql+psycopg://`.
Sob o padrão de escrita do sistema (um POST em bulk por scan, sem queries de alta frequência no
caminho crítico), o custo de não usar um driver async é desprezível, e a simplicidade operacional
de um único driver compensa.

**Versões pinadas:** `psycopg[binary]>=3.1.12`, `sqlalchemy>=2.0.29`

---

<details>
<summary>Decisão original (superada em 2026-07-15) — asyncpg</summary>

**Decisão: asyncpg** para acesso em produção via FastAPI.

FastAPI é um framework async. Usar um driver síncrono (psycopg2) bloquearia o event loop durante queries, eliminando o benefício de concorrência do FastAPI. `asyncpg` é o driver assíncrono de referência para PostgreSQL em Python.

**Versões pinadas:** `asyncpg==0.29.0`, `sqlalchemy[asyncio]==2.0.x`

psycopg2 pode ser mantido como dependência de desenvolvimento exclusivamente para suporte ao Alembic (ver seção de migrações).

</details>

---
 
### Migrações: Alembic 1.13
 
**Decisão: Alembic.**
 
Alembic é o tooling de migração padrão do ecossistema SQLAlchemy/SQLModel. O `env.py` deve importar os modelos SQLModel para que o `autogenerate` detecte alterações de schema corretamente.
 
**Versão pinada:** `alembic==1.13.x`
 
Migrações nunca devem rodar via pooler (porta 6543) — o PgBouncer em transaction mode não suporta o protocolo de sessão necessário para DDL.
 
---
 
### Fila de processamento no PostgreSQL

**Decisão: usar uma fila no próprio PostgreSQL** (tabela de jobs) para o processamento assíncrono, no lugar de um message broker dedicado.

**Padrão sugerido:** tabela `jobs` + seleção concorrente com `SELECT ... FOR UPDATE SKIP LOCKED`.

**Motivos:**
- Menos serviços para operar (remove RabbitMQ).
- Mantém o processamento assíncrono sem alterar o fluxo do agente.

**Riscos / tradeoffs:**
- A fila passa a compartilhar recursos com o banco principal.
- Picos de jobs podem impactar queries de leitura se não houver limites.

---

### Analytics e busca no PostgreSQL

**Decisão: usar recursos nativos do PostgreSQL** para análises e busca, evitando serviços externos.

**Capacidades previstas (alto nível):**
- **Materialized views** para métricas de dashboard (ex.: scans por dia, findings por severidade).
- **Full-text search** (TSVector + GIN) para pesquisa de findings e serviços.

**Motivos:**
- Centraliza dados e queries em um único lugar.
- Reduz complexidade de infraestrutura para o time.

---

### Postura de hosting e sizing inicial

**Decisão: Railway com free tier durante testes.** Upgrade quando o volume justificar ou quando houver necessidade de ambiente sempre ativo.

**Sizing inicial (baixo volume):**
- 1 vCPU / 1 GB RAM para o serviço de backend (API + worker).
- 1 worker de API e 1 worker de fila.
- Pools pequenos de conexão (API 5–10, worker 2–5).

---

### Modo de conexão ao Supabase
 
O Supabase expõe dois endpoints de conexão com propósitos distintos:
 
| Contexto | Endpoint | Porta | Motivo |
|----------|----------|-------|--------|
| Backend API / Worker em produção (cloud) | Pooler (PgBouncer, transaction mode) | 6543 | Múltiplas conexões simultâneas; workers do backend |
| Alembic / migrations | Conexão direta | 5432 | DDL requer modo sessão; PgBouncer transaction mode não suporta |
| Scripts de manutenção | Conexão direta | 5432 | Mesma razão que migrations |
 
**SSL:** obrigatório. Adicionar `?sslmode=require` à connection string em todos os contextos.
 
 
**Latência backend cloud → Supabase:** esperada entre 10–80 ms por query dependendo da região. Aceitável para o endpoint de ingestão de scan, que é um único POST em bulk por scan concluído — não há queries de alta frequência no caminho crítico do agente.
 
**Configurações recomendadas no SQLAlchemy:**
- `pool_pre_ping=True` — detecta conexões mortas antes de usar
- `connect_args={"timeout": 10}` — evita travamentos em falhas de rede
- `pool_size` e `max_overflow` dimensionados conforme número de workers do Uvicorn no backend cloud
 
**Região do Supabase:** selecionar a região AWS mais próxima geograficamente da localização física do Pi e da equipe. Documentar a região escolhida no guia `SUPABASE-CONNECTION.md` após provisionamento.
 
---
 
### Gestão de segredos
 
- A connection string é armazenada exclusivamente como variável de ambiente `DATABASE_URL` no ambiente onde o FastAPI roda (backend cloud em produção, container em desenvolvimento).
- **Nunca** hardcodar credentials no código-fonte.
- O arquivo `.env` local deve estar no `.gitignore`. O repositório não deve conter credentials de nenhum ambiente.
- Docker Compose de desenvolvimento usa uma variável `DATABASE_URL` separada apontando para instância PostgreSQL local (via `docker-compose.yml`) ou Supabase de staging — nunca para produção.
 
 
## Dados persistidos e padrões de acesso
 
### Entidades
 
| Entidade | Propósito |
|----------|-----------|
| `scans` | Metadados de cada execução de scan: timestamps, status, subnet alvo, duração |
| `devices` | Hosts descobertos ao longo do tempo; registro canônico por endereço MAC/IP |
| `ports` | Portas abertas por host por scan; protocolo, estado |
| `services` | Serviço detectado por porta: nome, versão, banner |
| `findings` | Vulnerabilidades com severidade, título, descrição, remediação, fonte |
 
### Padrões de leitura (frontend)
 
1. Lista paginada de scans — filtrada por status e intervalo de datas
2. Detalhe de scan — um scan → todos os hosts → todas as portas/serviços/findings
3. Inventário de devices — todos os hosts conhecidos, última vez visto, contagem de findings
4. Detalhe de device — um host → histórico de scans em que apareceu → findings ao longo do tempo
5. Lista de findings — filtrada por severidade, scan ou device
 
### Padrão de escrita (agente)
 
- Um único `POST /scans` em bulk por scan concluído — payload contém todos os hosts, portas, serviços e findings do scan.
- **Idempotência:** `INSERT ... ON CONFLICT DO NOTHING` usando `scan_id` como discriminador. Reenvios do mesmo scan não criam duplicatas.
 
### Retenção de dados
 
Retenção indefinida em v1. Sem política de expiração ou arquivamento. Decisão explícita — revisitar em v2 se o volume exceder limites de plano.
 
---
 
## Estimativa de volume e limites de plano
 
### Estimativa
 
| Parâmetro | Valor |
|-----------|-------|
| Subnet alvo | /24 (até 254 hosts) |
| Frequência | 1 scans/dia |
 
### Plano Supabase
 
| Limite | Free | Pro ($25/mês) |
|--------|------|---------------|
| Storage | 500 MB | 8 GB |
| Egress | 5 GB/mês | 250 GB/mês |
| Pausa por inatividade | Sim (7 dias) | Não |
| Backups diários | Não | Sim |
 
**Decisão de plano inicial:** iniciar no Free tier durante desenvolvimento e sprints iniciais.
 
**Critério de upgrade para Pro:**
- Storage estimado (~900 MB) ultrapassa o Free tier em ~3–4 meses de uso contínuo → upgrade obrigatório antes do marco de 3 meses.
- Ambiente de staging/demo não pode tolerar pausa automática → upgrade necessário antes de DEMO-01.
- Backups diários requeridos para apresentação final.
 
**Ação:** planejar upgrade para Pro antes do Sprint 5 (May 5).
 
---
 
## Consequências
 
### Positivas
 
- SQLModel elimina duplicação entre modelos de banco e schemas Pydantic, reduzindo drift com a OpenAPI spec (A-03).
- psycopg3 síncrono unifica o acesso a banco (API, worker, Alembic, scripts) em um único driver e estilo de sessão, reduzindo a superfície operacional. O padrão de escrita em bulk do agente não exige concorrência async.
- Supabase cloud remove a carga operacional de banco do Pi, preservando recursos para scans.
- PgBouncer (pooler) protege o banco de picos de conexão do agente.
 
### Negativas / riscos
 
- Latência de rede adiciona 10–80 ms por query — aceitável para o padrão de bulk write do agente, mas deve ser monitorado.
- Dependência de conectividade externa: se o Pi perder acesso à internet, dados não são persistidos. Mitigação: fila local no Pi (fora de escopo para v1).
- Free tier pausa após 7 dias de inatividade — impacto em desenvolvimento; mitigado por upgrade antes de DEMO-01.
- O volume estimado (~900 MB) ultrapassa o Free tier — upgrade para Pro é um custo previsto e documentado.
 