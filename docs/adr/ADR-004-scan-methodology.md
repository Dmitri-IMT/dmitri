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