# Wireframes do Frontend

## Objetivo

Definir a estrutura das telas React antes da implementacao. Este documento cobre:

- layout e navegacao
- requisitos de dados por pagina
- sistema de cores de severidade
- wireframes em ASCII das 5 telas principais

O foco e clareza, nao fidelidade visual.

## Decisoes globais

### Estrutura de navegacao

Decisao: usar `AppShell` com sidebar persistente + top bar simples.

Motivos:

- a aplicacao tem 5 telas analiticas com navegacao frequente entre listas e detalhes
- sidebar facilita trocar entre Dashboard, Scans e Devices sem perder contexto
- deixa breadcrumbs e acoes secundarias na top bar, sem competir com a navegacao principal

### Rotas principais

- `/login` - fora do AppShell
- `/dashboard`
- `/scans`
- `/scans/:scanId`
- `/devices`
- `/devices/:deviceId`

### Escopo responsivo

Decisao: desktop-only no MVP.

Motivos:

- trata-se de uma ferramenta operacional de seguranca de rede, usada principalmente em notebook/desktop
- tabelas densas, historico de scans e detalhes de portas/servicos perdem legibilidade em mobile
- reduz custo de design e implementacao nesta sprint

Suporte minimo previsto:

- largura alvo: 1440px
- largura minima suportada no MVP: 1280px
- abaixo disso: comportamento nao garantido

### Sistema de cores de severidade

| Severidade | Cor | Uso |
| --- | --- | --- |
| Critical | `#DC2626` | badge, numero agregado, highlight de risco maximo |
| High | `#F97316` | badge e contadores de risco alto |
| Medium | `#EAB308` | badge e estados de atencao |
| Low | `#22C55E` | badge e itens de baixo risco |
| Informational | `#3B82F6` | estados informativos, metadados, notas e extensao futura |

Observacao:

- o contrato atual de findings usa `low`, `medium`, `high` e `critical`
- `informational` entra como token visual do sistema, nao como severidade obrigatoria do backend neste momento

### Componentes compartilhados

- `Sidebar`
- `TopBar`
- `PageHeader`
- `MetricCard`
- `DataTable`
- `SeverityBadge`
- `EmptyState`
- `LoadingSkeleton`
- `Breadcrumbs`

## Mapeamento de paginas para API

| Pagina | Endpoint(s) | Dados consumidos |
| --- | --- | --- |
| Dashboard | `GET /api/v1/scans`, `GET /api/v1/findings` | cards de severidade, lista dos 5 scans mais recentes, ultimo scan |
| Scan List | `GET /api/v1/scans` | tabela paginada e filtros de scans |
| Scan Detail | `GET /api/v1/scans/{id}` | metadados do scan, dispositivos, portas, servicos, findings |
| Device Inventory | `GET /api/v1/devices` | inventario de hosts conhecidos |
| Device Detail | `GET /api/v1/devices/{id}` | metadados do host, historico de scans, portas e findings consolidados |

## Layout base do AppShell

```text
+----------------------------------------------------------------------------------+
| Sidebar                    | TopBar: Breadcrumbs | Search | User | Theme Toggle |
|---------------------------|------------------------------------------------------|
| Dashboard                 | Page Header + Actions                                 |
| Scans                     |------------------------------------------------------|
| Devices                   |                                                      |
|                           | Main content area                                    |
|                           |                                                      |
|                           |                                                      |
+----------------------------------------------------------------------------------+
```

Regras:

- sidebar fixa a esquerda
- top bar horizontal apenas com contexto, busca global opcional e menu do usuario
- conteudo principal com margem generosa e largura maxima de leitura

## Pagina 1 - Dashboard

### Objetivo

Dar visao rapida do estado atual do ambiente: distribuicao de severidades, scans recentes e ultimo horario de coleta.

### Conteudo

- 4 cards principais de severidade: Critical, High, Medium, Low
- card secundario com `Last scan`
- lista dos 5 scans mais recentes
- atalhos rapidos para `Scans` e `Devices`

### Requisitos de dados

- `GET /api/v1/findings`
  - o frontend agrega contagens por severidade
- `GET /api/v1/scans?per_page=5&sort_by=timestamp&sort_order=desc`
  - fornece scans recentes e timestamp do ultimo scan

Observacao:

- se o volume de findings crescer, sera recomendavel criar um endpoint agregado de dashboard no futuro
- para o MVP, o contrato atual permite montar a tela com os endpoints ja definidos

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Dashboard                                                   Last scan: 2026-03-25 |
|----------------------------------------------------------------------------------|
| [Critical: 12] [High: 28] [Medium: 44] [Low: 91] [Devices: 38]                  |
|----------------------------------------------------------------------------------|
| Quick actions                 | Recent scans                                      |
|------------------------------|---------------------------------------------------|
| [Go to Scan List]            | 2026-03-25 09:15   Full   Completed   14 hosts    |
| [Go to Device Inventory]     | 2026-03-24 09:10   Quick  Completed   14 hosts    |
|                              | 2026-03-23 09:08   Full   Completed   13 hosts    |
|                              | 2026-03-22 09:11   Quick  Failed      0 hosts     |
|                              | 2026-03-21 09:12   Full   Completed   15 hosts    |
+----------------------------------------------------------------------------------+
```

### Comportamento

- click em card de severidade leva para `Findings` filtrado no futuro ou `Scans` com foco em risco
- click em item da lista recente leva para detalhe do scan

## Pagina 2 - Scan List

### Objetivo

Listar todos os scans executados com filtros e ordenacao.

### Conteudo

- cabecalho com filtros
- tabela de scans
- paginacao

### Requisitos de dados

- `GET /api/v1/scans?page=1&per_page=20&status=completed&sort_by=timestamp&sort_order=desc`

### Colunas da tabela

- Data/Hora
- Scan ID
- Subnet
- Mode
- Status
- Host count
- Finding count
- Highest severity
- Acao `View details`

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Scan List                                                    [Refresh] [Filters] |
|----------------------------------------------------------------------------------|
| Status [All v]  Sort by [timestamp v]  Order [desc v]  Search [______________]  |
|----------------------------------------------------------------------------------|
| Date/Time         | Subnet         | Mode  | Status    | Hosts | Findings | Go  |
|-------------------|----------------|-------|-----------|-------|----------|-----|
| 2026-03-25 09:15  | 192.168.1.0/24 | Full  | Completed | 14    | 09       | >   |
| 2026-03-24 09:10  | 192.168.1.0/24 | Quick | Completed | 14    | 03       | >   |
| 2026-03-22 09:11  | 192.168.1.0/24 | Quick | Failed    | 00    | 00       | >   |
| ...                                                                            |
|----------------------------------------------------------------------------------|
| < Prev                              Page 1 of 8                              Next |
+----------------------------------------------------------------------------------+
```

### Comportamento

- linha clicavel abre `Scan Detail`
- badges de status devem ser compactas e consistentes
- ordenacao deve ser server-driven

## Pagina 3 - Scan Detail

### Objetivo

Mostrar um scan completo com metadados, hosts encontrados, portas/servicos e findings.

### Conteudo

- cabecalho do scan
- resumo numerico
- lista de hosts no scan
- painel detalhado do host selecionado
- lista de findings do scan

### Requisitos de dados

- `GET /api/v1/scans/{id}`

### Estrutura visual

- topo: scan metadata
- meio: split view com lista de hosts na esquerda e detalhe do host na direita
- base: findings agregados do scan

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Scan Detail > b9a2de1d...                                      [Back to list]    |
|----------------------------------------------------------------------------------|
| Timestamp: 2026-03-25 09:15 | Subnet: 192.168.1.0/24 | Mode: Full | Status: OK  |
| Hosts: 14 | Findings: 9 | Highest severity: High                                 |
|----------------------------------------------------------------------------------|
| Hosts in this scan            | Host detail                                       |
|------------------------------|---------------------------------------------------|
| > 192.168.1.10  lab-camera   | Hostname: lab-camera                              |
|   192.168.1.40  office-nas   | IP: 192.168.1.10                                  |
|   192.168.1.55  printer-01   | Vendor: Raspberry Pi Trading Ltd                  |
|   ...                        |                                                   |
|                              | Open ports                                         |
|                              | Port | Proto | State | Service | Version          |
|                              | 22   | tcp   | open  | ssh     | OpenSSH 7.2p2    |
|                              | 80   | tcp   | open  | http    | lighttpd 1.4.59  |
|----------------------------------------------------------------------------------|
| Findings in this scan                                                           |
| [High] Outdated SSH service exposed                                             |
| [Medium] SMB signing disabled                                                   |
+----------------------------------------------------------------------------------+
```

### Comportamento

- selecionar host na lista lateral atualiza o painel direito
- findings devem exibir badge de severidade, titulo e evidencia curta
- um estado vazio deve existir para scans sem findings

## Pagina 4 - Device Inventory

### Objetivo

Mostrar todos os hosts conhecidos pelo sistema.

### Conteudo

- tabela de inventario
- busca por hostname/IP/MAC/vendor
- ordenacao por `last_seen_at`, hostname, vendor e IP

### Requisitos de dados

- `GET /api/v1/devices?page=1&per_page=20&sort_by=last_seen_at&sort_order=desc`

### Colunas da tabela

- IP
- Hostname
- MAC
- Vendor
- Last seen
- Open port count
- Highest severity
- Acao `View detail`

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Device Inventory                                               [Refresh] [Add?]  |
|----------------------------------------------------------------------------------|
| Search [hostname / IP / MAC / vendor___________________________]                 |
| Sort by [last_seen_at v]  Order [desc v]                                         |
|----------------------------------------------------------------------------------|
| IP           | Hostname     | MAC               | Vendor   | Last seen | Go     |
|--------------|--------------|-------------------|----------|-----------|--------|
| 192.168.1.10 | lab-camera   | B8:27:EB:44:55:66 | RPi      | 09:15     | >      |
| 192.168.1.40 | office-nas   | 00:1C:B3:AA:BB:CC | Synology | 09:15     | >      |
| ...                                                                            |
|----------------------------------------------------------------------------------|
| < Prev                              Page 1 of 3                              Next |
+----------------------------------------------------------------------------------+
```

### Comportamento

- linha clicavel abre `Device Detail`
- badges de severidade devem aparecer na coluna de risco quando houver findings associados

## Pagina 5 - Device Detail

### Objetivo

Concentrar a visao historica de um host especifico: metadados, timeline de scans e tudo que ja foi visto em portas/servicos/findings.

### Conteudo

- cabecalho do host
- cards de resumo
- tabela/lista de portas atuais
- timeline de scans
- findings consolidados do dispositivo

### Requisitos de dados

- `GET /api/v1/devices/{id}`

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Device Detail > lab-camera                                     [Back to devices] |
|----------------------------------------------------------------------------------|
| IP: 192.168.1.10 | MAC: B8:27:EB:44:55:66 | Vendor: Raspberry Pi Trading Ltd     |
| First seen: 2026-03-10 | Last seen: 2026-03-25 | Highest severity: High            |
|----------------------------------------------------------------------------------|
| [Open ports: 2] [Scans seen: 6] [Findings: 3]                                    |
|----------------------------------------------------------------------------------|
| Current ports                  | Scan history timeline                            |
|-------------------------------|--------------------------------------------------|
| 22/tcp  open  ssh            | 2026-03-25  Full   High     2 open ports         |
| 80/tcp  open  http           | 2026-03-24  Quick  Medium   2 open ports         |
|                               | 2026-03-20  Full   High     3 open ports         |
|----------------------------------------------------------------------------------|
| Findings for this device                                                        |
| [High] Outdated SSH service exposed                                             |
| Evidence: Banner from 192.168.1.10...                                           |
+----------------------------------------------------------------------------------+
```

### Comportamento

- timeline deve ser vertical em telas futuras com mais espaco; no MVP pode ser tabela simples
- findings devem permanecer visiveis abaixo da timeline para leitura sequencial

## Especificacao de UX por pagina

| Pagina | Header | Acao principal | Estado vazio |
| --- | --- | --- | --- |
| Dashboard | titulo + ultimo scan | ir para lista de scans | mensagem de nenhum scan recebido |
| Scan List | filtros + refresh | abrir detalhe do scan | tabela vazia com CTA para aguardar ingestao |
| Scan Detail | breadcrumb + voltar | trocar host selecionado | mensagem de scan sem findings |
| Device Inventory | busca + sort | abrir detalhe do dispositivo | nenhum host conhecido ainda |
| Device Detail | breadcrumb + voltar | revisar timeline e findings | dispositivo sem findings historicos |

## Regras de consistencia

- `SeverityBadge` deve usar sempre as mesmas cores e hierarquia visual
- toda tabela deve ter loading skeleton, empty state e erro de carregamento
- links para detalhe devem ser consistentes: linha inteira clicavel + icone `>`
- timestamps em formato local do usuario
- IDs longos devem ser truncados visualmente, com tooltip para valor completo

## Itens que dependem de backend

- contagem agregada de severidades no Dashboard pode ficar custosa sem endpoint dedicado
- `highest_severity` deve ser entregue pelo backend para evitar recomputo repetido no cliente
- historico completo do dispositivo depende do backend consolidar findings e scans por host
