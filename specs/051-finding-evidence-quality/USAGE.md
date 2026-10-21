# Registro de uso — preparação

Data: 2026-10-10. Apenas a preparação do harness/specs foi despachada.
Não confundir o cálculo ilustrativo do plano com consumo medido.

| Trabalho | Modelo explicitamente selecionado | Esforço | Input/cache/output/reasoning medidos |
|---|---|---|---|
| Adaptação do harness | GPT-6 Luna | medium | Não expostos pela ferramenta de delegação desta sessão |
| Arquitetura/integração | GPT-6.1 Sol | high | Não expostos pela ferramenta de delegação desta sessão |
| Design | GPT-6 Luna | medium | Não expostos pela ferramenta de delegação desta sessão |
| Revisão independente do harness e reavaliação | GPT-6.1 Sol | medium | Não expostos pela ferramenta de delegação desta sessão |
| Correções do harness após rejeição | GPT-6 Luna | medium | Não expostos pela ferramenta de delegação desta sessão |
| Coordenação e arquivos de domínio | Modelo da sessão principal | Herdado do cliente | Não expostos nesta sessão; não se afirma troca do modelo principal |

Foram selecionados modelos reais nos despachos, com `fork_turns="none"`.
Os filhos recebem caminhos e escopo; não receberam a conversa inteira.
Design e revisão receberam follow-ups delimitados, sem reenvio do histórico completo.
Esta ferramenta não forneceu saldo do plano ou telemetria de tokens. Verificar o painel
do cliente para consumo observado; não atribuir variação de outras sessões a este trabalho.

Após iniciar as tasks de produto, registrar deltas de uso quando o mecanismo de execução
permitir. Não somar snapshots acumulados como se fossem chamadas independentes.

## Execução da Entrega A

| Despacho real | Modelo selecionado | Esforço | Telemetria |
|---|---|---|---|
| task01_coder, primeira tentativa | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task01_tester | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task01_reviewer | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task01_fix01_coder, após REJECT 1 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task01_fix01_tester | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task01_reviewer, re-revisão por follow-up | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task02_coder | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task02_tester | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task02_reviewer | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task02_fix01_coder, após REJECT 1 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task01_tester, encerramento administrativo de pending_init | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task02_tester, revalidação por follow-up | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task02_reviewer, re-revisão por follow-up | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task03_coder | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_tester | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_reviewer | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task03_fix01_coder, após REJECT 1 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_tester, revalidação por follow-up | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_reviewer, re-revisão por follow-up | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task03_fix02_coder, após REJECT 2 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_fix02_coder, correção lint por follow-up | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_tester, revalidação após REJECT 2 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task03_reviewer, re-revisão após REJECT 2 | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task03_reviewer, esclarecimento de configuração Ruff | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task04_coder | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| issue_key_arch_decision | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task04_coder, retomada após decisão issue_key | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_tester | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_reviewer | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task04_fix01_coder, após REJECT 1 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_tester, revalidação por follow-up após REJECT 1 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_reviewer, re-revisão por follow-up após REJECT 1 | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task04_fix02_coder, após REJECT 2 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_tester, revalidação após REJECT 2 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_reviewer, re-revisão após REJECT 2 | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task04_fix03_coder, após REJECT 3 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_tester, revalidação após REJECT 3 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_reviewer, re-revisão após REJECT 3 | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |
| task04_tester, correção final de imports I001 | gpt-6-luna | medium | Tokens/quota não expostos pela ferramenta |
| task04_reviewer, confirmação final de Ruff | gpt-6.1-sol | high | Tokens/quota não expostos pela ferramenta |

Despachos usam fork_turns="none" e seleção explícita de modelo/esforço. Perfis .codex são referência; não se afirma execução nativa dos TOMLs. Workers concluídos liberam a concorrência nesta ferramenta; não há ferramenta close disponível.

A ferramenta não expõe seleção de service tier nem saldo dos limites do plano. Não se afirma ativação de Standard, custo medido ou economia percentual real. Modelos/esforços selecionados acima são registros de despacho, não medições de consumo.
