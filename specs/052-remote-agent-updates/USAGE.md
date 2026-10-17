# Uso observado - planejamento

Sessoes separadas iniciadas com modelo/esforco explicitos. Fonte: ultimo evento
`turn.completed` de cada JSONL em `output/remote-agent-update-planning-2026-10-17/`
na raiz do workspace. Cada acumulado de sessao e contado uma unica vez.

| Papel | Modelo / esforco | Entrada total | Entrada em cache | Entrada sem cache (diferenca) | Saida |
|---|---|---:|---:|---:|---:|
| architecture | gpt-6.1-sol / high | 2,234,247 | 2,084,352 | 149,895 | 34,834 |
| design | gpt-6-luna / medium | 224,835 | 174,336 | 50,499 | 3,655 |
| review | gpt-6.1-sol / medium | 320,996 | 256,384 | 64,612 | 2,894 |

Entrada em cache ja faz parte da entrada total. Tokens de raciocinio reportados ja fazem parte
da saida e nao sao somados novamente. Os contadores nao informam custo monetario nem saldo ou
porcentagem restante do plano Codex. Uso da sessao coordenadora indisponivel aqui.

A arquitetura concentrou a investigacao de contratos, privilegios e recuperacao; nao sera
repetida no design. Design e revisao recebem limite de chamadas e leituras agrupadas para reduzir
repeticao. Estes numeros sao registro, nao comprovacao de economia contra outra estrategia.

Documentos e evento final foram salvos mesmo quando o CLI retornou 1 apos aviso do hook local
`legacy_notify` com caminho inexistente. Esse aviso nao representa falha de teste de produto e
nao motivou repeticao do trabalho concluido.

Decomposição em tarefas (2026-10-17): executada na sessão coordenadora, sem novas sessões de
subagentes. Contadores desta sessão não estão disponíveis; não somar às métricas históricas
nem apresentar a seleção futura de modelos como consumo já realizado.
