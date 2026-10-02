# ADR-010: Política de Contingência de Varredura (parar vs. continuar em erros)

## Contexto

Varreduras longas (extensive / max / subnets grandes) travavam, congelavam ou perdiam todos os
resultados. A causa raiz não era um bug único, mas a **ausência de uma política de contingência**
no pipeline de varredura: nenhum timeout de subprocesso, qualquer falha de uma unidade abortava a
varredura inteira, e uma falha tardia descartava tudo o que já havia sido descoberto.

O ADR-004 define os **estágios** do pipeline (descoberta → portas → serviços → vulnerabilidades),
mas não define o que acontece quando um estágio **falha**. Este ADR registra essa decisão: como
classificar cada falha e quando parar a varredura versus degradar de forma controlada preservando
o trabalho já realizado.

Auditoria completa e proposta: `docs/implementation/SCAN-PIPELINE-RESILIENCE.md`.
Especificação de implementação: `specs/010-scan-pipeline-resilience/`.

## Decisão

### 1. Taxonomia de erros

Toda falha é classificada como exatamente uma destas categorias (subclasses de um `ScanError` base):

| Categoria | Significado | Exemplos |
|-----------|-------------|----------|
| **Fatal** | A varredura não pode prosseguir de forma útil | binário nmap ausente, argumentos inválidos, permissão negada, workspace não gravável |
| **Unit** | Um único item de trabalho falhou; os demais não são afetados | um lote/host: exit não-zero, XML malformado, script NSE falhou |
| **Transient** | Provável sucesso em nova tentativa | falha temporária de resolução, blip de rede |
| **Cancelled** | O usuário pediu para parar | abortar (Ctrl+X) |
| **BudgetExceeded** | Um limite de tempo foi atingido | timeout por passo, deadline da varredura |
| **CircuitBreaker** | Taxa de falha de unidades acima do limite (ambiente quebrado) | >50% dos lotes/hosts falhando |

`CircuitBreakerError` é subclasse de `BudgetExceeded` (mesma decisão "parar e manter parcial"), mas
distinta para que o `terminated_by` seja `"error"` ("varredura interrompida cedo") em vez de
`"timeout"`. A `NmapExecutionError` única e genérica é **removida** e substituída por esta taxonomia.

Detecção de **Transient**: levantada apenas quando o stderr do nmap casa com uma lista explícita de
marcadores conhecidos (ex.: falha temporária de resolução, conexão reiniciada); demais falhas
não-zero viram **Unit** (sem retry). Um **timeout nunca faz retry**.

### 2. Tabela de decisão parar / continuar

| Situação | Decisão | O que é preservado |
|----------|---------|--------------------|
| Fatal **antes** de qualquer dado | **PARAR** imediatamente | Nada; erro claro ao usuário |
| Fatal **depois** da descoberta | **PARAR**, emitir parcial | Hosts/portas coletados, `partial_result=True` |
| Fatal **na gravação do resultado** | **PARAR**, sem emitir parcial | Nenhum JSON; o canal de preservação falhou, embora o payload possa permanecer em memória |
| Transient em uma unidade | **RETRY uma vez**; persistindo, rebaixa para falha de unidade | — |
| Unit em um único lote/host | **CONTINUAR** com as demais unidades; registrar a falha | Todas as unidades bem-sucedidas |
| Taxa de falha de unidades acima do limite (circuit breaker) | **PARAR** (ambiente quebrado) | Tudo que teve sucesso, `partial_result=True` |
| Descoberta retorna 0 hosts | **CONTINUAR** (não é erro) — pula estágios seguintes, finaliza vazio | Resultado vazio mas válido |
| Cancelled (Ctrl+X) | **PARAR** de lançar trabalho, **matar subprocessos em execução**, finalizar parcial | Tudo até o cancelamento, `interrupted_stage` definido |
| BudgetExceeded | Tratar como cancelamento: parar, manter parcial | Parcial, `partial_result=True`, `interrupted_stage` definido |

**Princípio guia:** parar apenas quando continuar é inútil (fatal), destrutivo (ambiente
quebrado), solicitado pelo usuário, ou um orçamento de recurso foi atingido. Caso contrário,
degradar de forma controlada e **sempre preservar o trabalho parcial**, exceto quando o próprio
canal de gravação falhar.

### 3. Mecanismos exigidos

- Timeout de subprocesso por invocação; ao expirar, mata o processo e reporta
  `terminated_by="timeout"`.
- Isolamento por unidade nos estágios de portas e inspeção profunda.
- Retry único para falhas transitórias; circuit breaker por taxa de falha de unidades.
- Cancelamento real: checagem do evento de cancelamento dentro dos laços e término dos
  subprocessos nmap em execução.
- Finalização de resultado parcial (`partial_result=True`, `interrupted_stage`) acessível pelos
  caminhos de cancelamento, timeout e fatal pós-descoberta.

No estágio de portas, a unidade usada pelo circuit breaker é sempre o **host**, mesmo quando o
Nmap executa vários hosts no mesmo lote. Se qualquer host for pulado e o pipeline ainda conseguir
terminar, o resultado final usa `partial_result=True` com `terminated_by="completed"`; não há
`interrupted_stage`, pois nenhum estágio foi interrompido. Limites internos do Nmap podem encerrar
um script ou host antes do timeout do subprocesso, preservando as evidências das demais unidades.

Os estados terminais já previstos no schema (`TerminatedBy` inclui `"timeout"` e `"user_cancel"`)
e os campos `partial_result` / `interrupted_stage` já aceitos por `build_metadata` são reutilizados
— nenhum estado terminal novo é inventado.

### 4. Knobs de configuração

Três campos escalares são adicionados a `AgentSettings` (encadeados pela regra de integração do
CLAUDE.md através de `ScanRunner` **e** `ScanProgressScreen`):

| Knob | Propósito | Default sugerido |
|------|-----------|------------------|
| `scan_deadline_s` | orçamento global de tempo | 0 = ilimitado |
| `unit_failure_threshold` | razão do circuit breaker | 0.5 |
| `transient_retries` | retries por unidade | 1 |

O **timeout de subprocesso** não é um escalar de `AgentSettings`: é resolvido por
`subprocess_timeout_for(scan_mode, stage)` (tabela **modo × estágio** em `config.py`, ao lado de
`min_cvss_for_mode`), passado como parâmetro por chamada. Os valores são **lenientes** — uma rede de
proteção contra travamentos, não um SLA de duração — e variam por modo (quick … max) e estágio
(descoberta / portas / inspeção profunda). A descoberta é uma única chamada `-sn` sobre toda a
subnet, então escala com o tamanho da subnet (muitos hosts), não com o modo.

## Justificativa

- Uma taxonomia explícita permite que cada local de chamada decida parar ou continuar com base na
  tabela de decisão, em vez de tratar toda falha como fatal.
- Preservar resultados parciais respeita o tempo do operador em varreduras longas e torna
  cancelamento/timeout outcomes de primeira classe, não perdas silenciosas.
- Reutilizar estados terminais e campos de metadata já existentes evita criar um novo estado
  terminal. A cobertura por unidade usa um campo opcional no payload, compatível com agentes
  anteriores, e um campo persistido na API.

## Consequências

- Varreduras longas não travam mais indefinidamente; um passo parado é limitado por timeout.
- Uma única unidade ruim não desperdiça a varredura inteira.
- Resultados parciais ficam visíveis e salváveis, claramente marcados como "Partial".
- O backend aceita payloads `partial_result=True`. Eles são persistidos como scans parciais e não
  fecham achados ausentes na reconciliação do inventário. A cobertura por estágio e unidade,
  quando enviada, fica disponível no detalhe do scan. Consulte
  `docs/implementation/SCAN-EVIDENCE-CORRECTIONS-2026-09-24.md`.

## Relacionado

- ADR-004 (metodologia de varredura) — este ADR estende o tratamento de falhas dos estágios lá
  definidos.
- `docs/implementation/SCAN-PIPELINE-RESILIENCE.md` — auditoria completa (modos de falha F1–F8).
- `specs/010-scan-pipeline-resilience/` — TRUTH / ARCHITECTURE / DESIGN da implementação.
- GitHub issue #81.
