# TRUTH — Qualidade da evidência dos achados

Status: proposta aguardando aprovação. Entrega A. Data: 2026-10-10.

## Narrativa

O usuário precisa saber se um alerta vem de uma versão associada a uma falha conhecida,
de uma configuração observada ou de uma verificação específica. Um resultado negativo,
uma referência textual e uma tentativa inconclusiva não podem aparecer como prova de
vulnerabilidade. A primeira entrega corrige a interpretação dos resultados e conserva
a origem da evidência até a interface, o relatório e as explicações automatizadas.

## Regras de negócio

1. Gravidade e força da evidência são informações distintas. Um alerta grave pode depender de validação.
2. Existência de uma falha em um catálogo não confirma sua presença no equipamento.
3. Uma verificação positiva confirma somente a condição que foi testada e o alcance que sua evidência demonstra.
4. Uma configuração diretamente observada deve ser descrita como configuração observada; não como exploração comprovada de uma falha conhecida.
5. Resultado negativo se aplica à verificação realizada. Não comprova segurança do equipamento inteiro.
6. Resultado inconclusivo, erro ou ausência de informação não prova nem descarta a falha.
7. A mera presença de um identificador de falha em texto ou referência não constitui resultado positivo.
8. Resultados diferentes na mesma resposta são analisados individualmente; um resultado negativo não apaga um positivo independente.
9. Evidências repetidas não aumentam a confiança por contagem. Fontes contraditórias conservam sua procedência e seguem uma regra explícita de qualidade, alcance e atualidade.
10. Dados antigos continuam legíveis. Evidência que nunca foi registrada não pode ser reconstruída como confirmação.
11. A nova classificação conserva evidências necessárias para revisão e não modifica o significado do resultado original.
12. Verificações incompletas não encerram automaticamente problemas anteriormente encontrados fora do alcance efetivamente verificado.
13. Interface, relatório e explicações automatizadas usam o mesmo significado para a evidência. A explicação não pode elevar a certeza do dado fornecido.
14. Contagens distinguem registros de achados de falhas demonstradas e informam o escopo da contagem.
15. A atualização mantém a leitura de resultados anteriores e permite atualizar os componentes em ordem compatível.

## Histórias de usuário

- Como responsável pela rede, quero entender por que um alerta foi gerado e o que ainda precisa ser validado.
- Como administrador, quero revisar as evidências de um alerta sem confundir um aviso de catálogo com uma falha demonstrada no alvo.
- Como usuário do relatório, quero encontrar a mesma classificação que aparece na interface e saber os limites da conclusão.

## Critérios de aceitação

| ID | Cenário | Dado | Quando | Então |
|---|---|---|---|---|
| A01 | Negativo com referência | Uma verificação negativa que cita uma falha conhecida | O resultado é interpretado | A citação não gera achado positivo e não comprova segurança geral. |
| A02 | Menção textual | Um texto contém um identificador de falha, sem resultado positivo verificável | O texto é processado | Não surge um achado confirmado; a incerteza não é escondida. |
| A03 | Resultado misto | A mesma resposta contém verificações positivas e negativas independentes | Cada resultado é processado | Os positivos legítimos permanecem e os negativos não são transformados em positivos. |
| A04 | Correlação de versão | Uma versão foi associada a uma falha de catálogo | O achado é armazenado ou enriquecido | Continua descrito como associação pendente de validação no alvo. |
| A05 | Configuração observada | O equipamento respondeu demonstrando uma configuração | O achado é apresentado | O usuário lê qual configuração foi observada, sem afirmação de exploração comprovada. |
| A06 | Verificação específica | Um teste suportado retornou evidência positiva suficiente | O achado é apresentado | O método e a condição demonstrada ficam explícitos; não se amplia o alcance da conclusão. |
| A07 | Inconclusivo | A verificação falha, termina por tempo ou responde de forma desconhecida | O resultado é consolidado | Não vira confirmação nem ausência de risco. |
| A08 | Repetições | A mesma associação aparece em mais de uma fonte | As fontes são consolidadas | A repetição não promove a confiança; a procedência é preservada. |
| A09 | Contradição | Evidências distintas sobre a mesma condição | A consolidação ocorre em ordens diferentes | O resultado segue a política definida e não depende da ordem incidental. |
| A10 | Legado | Um resultado anterior não contém a nova procedência | Ele é ingerido ou consultado | Continua válido e mostra o limite da informação, sem confirmação inventada. |
| A11 | Verificação parcial | Há um problema anterior e verificações incompletas | O inventário é reconciliado | O problema não é encerrado por ausência de observação fora do alcance verificado. |
| A12 | Consistência | O mesmo achado aparece na interface e nos relatórios | O usuário consulta cada apresentação | Método, confiança e limites são semanticamente equivalentes. |
| A13 | Resumo | Há achados de métodos e estados distintos | O resumo é calculado | Contagens têm escopo explícito, não confundem registros com comprovações e não usam apenas uma página para um total global. |
| A14 | Explicação automatizada | O achado é correlacionado ou sua evidência está incompleta | Uma explicação é gerada | A resposta respeita o limite do dado e não declara falha confirmada ou alvo seguro. |
| A15 | Compatibilidade | Há componentes atualizados e resultados anteriores | A atualização ocorre na ordem definida | Resultados antigos seguem aceitos; componentes antigos não recebem dados que não podem interpretar. |
| A16 | Controles positivos | Exemplos com falhas/configurações realmente demonstradas | O parser corrigido é avaliado | A redução de alertas indevidos não elimina os controles positivos legítimos. |

## Fora do escopo desta entrega

- Criar novos testes ativos de vulnerabilidade ou ampliar a varredura da rede.
- Determinar automaticamente todas as condições de aplicabilidade de um catálogo de falhas.
- Coletar credenciais, consultar pacotes autenticados ou validar backports instalados.
- Criar decisões manuais de falso positivo e seu fluxo de aprovação.
- Atribuir percentuais de confiabilidade sem conjunto de referência validado.
- Reclassificar todo o histórico por inferência ou alterar sua evidência original.

## Documentos relacionados

- `ARCHITECTURE.md`: decisões técnicas e tabela de arquivos.
- `INTEGRATION.md`: contrato, consumidores e compatibilidade.
- `DESIGN.md`: rótulos, estados e apresentação.
