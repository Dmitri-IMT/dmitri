## Decisão
 
### Engine de banco de dados
 
**PostgreSQL via Supabase (cloud).** Versão do PostgreSQL: conforme provisionado pelo Supabase (atualmente 15.x — verificar no dashboard no momento da configuração).
 
O banco não roda no Pi. O FastAPI conecta remotamente ao Supabase via internet.

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
 
### Driver assíncrono: asyncpg

#### 
 
**Decisão: asyncpg** para acesso em produção via FastAPI.
 
FastAPI é um framework async. Usar um driver síncrono (psycopg2) bloquearia o event loop durante queries, eliminando o benefício de concorrência do FastAPI. `asyncpg` é o driver assíncrono de referência para PostgreSQL em Python.
 
**Versões pinadas:** `asyncpg==0.29.0`, `sqlalchemy[asyncio]==2.0.x`
 
psycopg2 pode ser mantido como dependência de desenvolvimento exclusivamente para suporte ao Alembic (ver seção de migrações).
 
---
 
### Migrações: Alembic 1.13
 
**Decisão: Alembic.**
 
Alembic é o tooling de migração padrão do ecossistema SQLAlchemy/SQLModel. O `env.py` deve importar os modelos SQLModel para que o `autogenerate` detecte alterações de schema corretamente.
 
**Versão pinada:** `alembic==1.13.x`
 
Migrações nunca devem rodar via pooler (porta 6543) — o PgBouncer em transaction mode não suporta o protocolo de sessão necessário para DDL.
 
---
 
### Modo de conexão ao Supabase
 
O Supabase expõe dois endpoints de conexão com propósitos distintos:
 
| Contexto | Endpoint | Porta | Motivo |
|----------|----------|-------|--------|
| FastAPI em produção (Pi) | Pooler (PgBouncer, transaction mode) | 6543 | Múltiplas conexões simultâneas; o Pi pode ter vários workers |
| Alembic / migrations | Conexão direta | 5432 | DDL requer modo sessão; PgBouncer transaction mode não suporta |
| Scripts de manutenção | Conexão direta | 5432 | Mesma razão que migrations |
 
**SSL:** obrigatório. Adicionar `?sslmode=require` à connection string em todos os contextos.
 
 
**Latência Pi → Supabase:** esperada entre 10–80 ms por query dependendo da região. Aceitável para o endpoint de ingestão de scan, que é um único POST em bulk por scan concluído — não há queries de alta frequência no caminho crítico do agente.
 
**Configurações recomendadas no SQLAlchemy:**
- `pool_pre_ping=True` — detecta conexões mortas antes de usar
- `connect_args={"timeout": 10}` — evita travamentos em falhas de rede
- `pool_size` e `max_overflow` dimensionados conforme número de workers do Uvicorn no Pi
 
**Região do Supabase:** selecionar a região AWS mais próxima geograficamente da localização física do Pi e da equipe. Documentar a região escolhida no guia `SUPABASE-CONNECTION.md` após provisionamento.
 
---
 
### Gestão de segredos
 
- A connection string é armazenada exclusivamente como variável de ambiente `DATABASE_URL` no ambiente onde o FastAPI roda (Pi em produção, container em desenvolvimento).
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
- asyncpg mantém o FastAPI não-bloqueante sob carga concorrente.
- Supabase cloud remove a carga operacional de banco do Pi, preservando recursos para scans.
- PgBouncer (pooler) protege o banco de picos de conexão do agente.
 
### Negativas / riscos
 
- Latência de rede adiciona 10–80 ms por query — aceitável para o padrão de bulk write do agente, mas deve ser monitorado.
- Dependência de conectividade externa: se o Pi perder acesso à internet, dados não são persistidos. Mitigação: fila local no Pi (fora de escopo para v1).
- Free tier pausa após 7 dias de inatividade — impacto em desenvolvimento; mitigado por upgrade antes de DEMO-01.
- O volume estimado (~900 MB) ultrapassa o Free tier — upgrade para Pro é um custo previsto e documentado.
 
