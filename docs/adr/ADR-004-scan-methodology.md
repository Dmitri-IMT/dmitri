## Contexto

O sistema visa realizar **varreduras de vulnerabilidades ponta a ponta** em redes locais usando um dispositivo embutido.

Para alcançar isso, é necessário definir o que uma "varredura" representa no sistema, incluindo:

- Entradas (alvos, escopo, configuração)
- Estágios de processamento (pipeline)
- Saídas (descobertas estruturadas)
- Como vulnerabilidades são identificadas e correlacionadas


---
## Definição de uma Varredura

Uma **varredura** é definida como um processo estruturado que:

1. Recebe um alvo (um IP, lista de hosts ou subnet)
2. Executa múltiplos estágios de varredura
3. Correlaciona dados coletados
4. Produz um conjunto de **descobertas**

---

## Estágios do Pipeline de Varredura

O fluxo de trabalho de varredura é dividido em estágios modulares:

### 1. Descoberta de Hosts

Objetivo:
Identificar dispositivos ativos na rede.

Técnicas:
- ICMP (ping sweep)
- Requisições ARP
- Nmap (`-sn`)

Saída:
Lista de hosts ativos (IPs)

---

### 2. Enumeração de Portas

Objetivo:
Identificar portas expostas (superfície de ataque).

Técnicas:
- Varredura TCP SYN (`-sS`)
- Varredura rápida (`-F`)
- Varredura completa (`-p-`)

Tradeoffs:

| Modo        | Velocidade | Cobertura | Caso de Uso |
|------------|-----------|-----------|-------------|
| -F         | Alta      | Baixa     | Varredura rápida |
| -p-        | Baixa     | Completa  | Varredura profunda |
| Customizado| Média     | Média     | Varredura direcionada |

Saída:
Lista de portas abertas por host

---

### 3. Detecção de Serviços e Versão

Objetivo:
Identificar serviços em execução nas portas abertas.

Técnicas:
- Nmap `-sV`
- Banner grabbing

Tradeoffs:

| Modo              | Precisão  | Velocidade |
|-------------------|-----------|-----------|
| --version-light   | Média     | Rápida    |
| -sV (padrão)      | Alta      | Média     |
| --version-all     | Muito Alta| Lenta     |

Saída:
- Nome do serviço
- Produto
- Versão (se disponível)

---

### 4. Identificação de Vulnerabilidades

Objetivo:
Mapear serviços detectados para vulnerabilidades conhecidas.

Técnicas:

- Scripts NSE do Nmap (`-sC`, `--script vuln`)
- Busca de CVE (bancos de dados externos)
- Correlação de fingerprint de serviço

Exemplos:
- MySQL → verificar CVEs
- SMB → verificar exploits conhecidos
- HTTP → executar Nikto

Saída:
Lista de vulnerabilidades por serviço

---

## Modos de Varredura Nmap e Tradeoffs

| Modo | Descrição | Caso de Uso |
|------|-----------|-------------|
| -T4 | Execução mais rápida | Varredura padrão |
| -F | Apenas portas principais | Varredura rápida |
| -p- | Todas as portas | Varredura profunda |
| -sV | Detecção de serviços | Obrigatório para mapeamento de vuln |
| -sC | Scripts padrão | Enumeração básica |
| -A | Varredura agressiva | Alto detalhe, alto custo |

Decisão:
- Use **-T4 + -F** para varreduras iniciais
- Use **-sV** para detecção de serviços
- Use **NSE seletivamente**, não `-A`, para reduzir uso de recursos

---

## Correlação de Dados de Vulnerabilidades

Vulnerabilidades não são diretamente descobertas em todos os casos. Elas são derivadas por:

### 1. Análise de Saída NSE

Extrair:

ID da CVE
Descrição
Severidade (se disponível)

### 2. Correlação de CVE

Processo:

Identificar serviço + versão
Consultar bancos de dados de vulnerabilidades (recurso futuro)

Fontes:

NVD (National Vulnerability Database)
CVE
API Vulners

### 3. Mapeamento Heurístico

Exemplos de correlações heurísticas:

- SMB aberto + sem autenticação → Potencial misconfigurção
- HTTP + versão desatualizada → Provável vulnerabilidade

---

## Estratégia de Agendamento de Varreduras

Dois modos principais são definidos:

### 1. Varredura sob Demanda
- Acionada manualmente
- Usada para testes ou investigação

### 2. Varredura Periódica
- Execução agendada (ex: diariamente)
- Detecta novos dispositivos e vulnerabilidades

---

## Escopo da Varredura

Alvos suportados:

- Host único (ex: 192.168.1.10)
- Múltiplos hosts
- Subnet (ex: 192.168.1.0/24)

---

## Definição de uma Descoberta

Uma descoberta representa um problema relevante para segurança identificado durante a varredura.

```json
{
  "host": "192.168.15.10",
  "hostname": "",
  "port": 3306,
  "protocol": "tcp",
  "service": "mysql",
  "product": "MySQL",
  "version": "8.x",
  "vulnerability": {
    "cve_id": "CVE-XXXX-XXXX",
    "name": "Exemplo de vulnerabilidade",
    "description": "Descrição do problema",
    "severity": "high",
    "cvss_score": 8.5
  },
  "source": "nmap_nse",
  "timestamp": "2026-03-31T18:00:00Z"
}
```

## Decisão

### O sistema implementará um pipeline de varredura de múltiplos estágios composto por:

- Descoberta de hosts
- Enumeração de portas
- Detecção de serviços
- Correlação de vulnerabilidades

Cada estágio alimenta o próximo e progressivamente enriquece o conjunto de dados.

## Justificativa

Esta abordagem baseada em pipeline:

- Garante modularidade e escalabilidade
- Reduz processamento desnecessário
- Permite varredura direcionada (apenas varrer o que importa)
- Se alinha com fluxos de trabalho padrão da indústria de varredura de vulnerabilidades

## Consequências

- Uso eficiente de recursos de dispositivos embutidos
- Clara separação de responsabilidades por módulo
- Fácil integração com sistemas de backend e relatórios
- Permite expansão futura (varredura web, nuvem, banco de dados)

## Pipeline de Varredura

```
[ ENTRADA ]
   |
   |  (IP / Subnet)
   v
+----------------------+
|  Descoberta de Hosts |
| (Ping / ARP / Nmap)  |
+----------------------+
           |
           v
+----------------------+
| Enumeração de Portas |
| (Varredura Rápida /  |
|  Completa)           |
+----------------------+
           |
           v
+----------------------+
| Detecção de Serviços |
| (Nmap -sV)           |
+----------------------+
           |
           v
+----------------------+
| Identificação de     |
| Vulnerabilidades     |
| (NSE / CVE / Tools)  |
+----------------------+
           |
           v
+----------------------+
| Geração de           |
| Descobertas          |
| (JSON Estruturado)   |
+----------------------+
           |
           v
        [ SAÍDA ]
```

---

## Emenda — Timing do estágio de portas do modo NSPi (DMI-50, 2026-07-05)

**Contexto.** O modo NSPi executava o estágio de portas em duas passagens `-T2` (varredura ampla
top-1000 `-sV -O`, depois as portas OT específicas), mas herdou o orçamento de 600 s do modo Quick
(que usa `-T4`). O tempo mínimo de uma passagem `-T2` top-1000 (`max_parallelism=1` + atraso de
0,4 s → ~400 s por host só na fase SYN) excede 600 s, então o estágio nunca concluía: todo lote
batia em `BudgetExceeded`, os hosts eram pulados e o circuit breaker abortava o estágio (0 portas).
Evidência: comentário Stage 1 em DMI-50 e teste de campo `docs/tests/nspi-september/results.md`
(2026-07-03: descoberta achou 9 dispositivos, estágio de portas produziu 0).

**Decisão.** A **passagem 1** (varredura ampla top-1000, `-sV -O`) passa a rodar em **`-T4`**; a
**passagem 2** (portas OT específicas — 502, 4840, 44818, 445, 139, 3389, 5985) permanece em
**`-T2`**. O orçamento (`TIMEOUTS["ports"]["nspi"] = 600.0`) e o tamanho de lote (8) **não mudam**, e
nenhum outro modo (Quick/Standard/Extensive/MAX) é afetado.

**Justificativa de segurança de PLC.** A passagem 1 em `-T4` varre o top-1000 de **todos** os hosts,
PLCs inclusos, na velocidade padrão — não é o caso de "a passagem 1 evitar os PLCs". Isso é aceito
porque o modo **Quick já executa exatamente essa** varredura `-T4` top-1000 `-sV -O` contra esses
mesmos PLCs, e o fez na rede NSPi real em 2026-07-03 sem dano relatado; a passagem 1 do NSPi não é
mais agressiva que o scan que o piloto já roda ali. A validação de DMI-50 é **apenas em dev** (sem
reteste de campo; o piloto continua no Quick). A polidez `-T2` é mantida na passagem 2, onde os
serviços OT de fato respondem. Alternativas que preservavam `-T2` em tudo — aumentar o orçamento /
reduzir o lote (scans de ~20–45 min) ou reduzir o escopo a um conjunto de portas conhecidas — foram
consideradas e rejeitadas em favor de um scan rápido e completo.

**Consequência.** Substitui a nota "Timing & flags = `-T2 -n`" em
`specs/004-nspi-scan-mode/contracts/nspi-constants.md`, que agora vale só para a passagem 2.
Especificação da correção: `specs/011-nspi-port-stage-fix/`. As correções auxiliares de DMI-50
(feedback de progresso por tempo decorrido no estágio de portas, cancelamento responsivo com guarda
antes de novo subprocesso, e retenção de logs que preserva a última execução parcial/falha) seguem a
política de contingência do **ADR-010** e não alteram esta metodologia.

## Emenda — Limites internos do NSPi (2026-09-08)

**Contexto.** Mesmo em `-T4`, a passagem ampla ainda acumulava detecção de versão e de sistema
operacional para até oito hosts no mesmo processo. Um único alvo lento podia consumir o limite do
processo e fazer o estágio descartar o lote inteiro.

**Decisão.** A passagem 1 do NSPi fica restrita à enumeração top-1000
(`-Pn -T4 -n --host-timeout 300s`), sem `-sV` e sem `-O`. A passagem 2 mantém a enumeração gentil
das portas OT com `-T2 -sV` e recebe o mesmo limite de 300 s por host. Detecção de versão, scripts
NSE e detecção de SO são consolidados na inspeção profunda, executada individualmente por host,
com `--script-timeout 60s`, `--host-timeout 300s` e `-O`. Assim, o JSON continua recebendo a melhor
evidência disponível de sistema operacional sem prender a passagem ampla.

O timeout do subprocesso NSPi é 600 s nos estágios de portas e de inspeção profunda e permanece a
última barreira. Um host omitido pelo Nmap após `--host-timeout` é registrado como pulado, mas suas
evidências obtidas por outra passagem são preservadas. O circuit breaker do estágio de portas usa
a razão entre hosts pulados e hosts totais, não a razão entre lotes. Esta emenda substitui, para o
comportamento vigente, a decisão anterior de manter `-sV -O` na passagem 1.
