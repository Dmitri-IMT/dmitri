# Plano de desenvolvimento — redução de falsos positivos

Status: proposta de execução, sem implementação iniciada. Data: 2026-10-10.
Base verificada: [CONTEXT.md](CONTEXT.md). Prompts: [PROMPTS.md](PROMPTS.md).
Estes documentos são planejamento prévio; não equivalem a specs aprovadas ou a um `TASKS.md` em execução.

## Estratégia

Corrigir primeiro a interpretação da evidência, propagar a procedência e melhorar sua apresentação. Depois validar identidade/aplicabilidade e adicionar confirmações selecionadas. Acesso autenticado e revisão manual ficam na terceira entrega.

Ampliar `confidence`, cobertura, deduplicação, contexto de IA e relatórios existentes. Não criar outro motor de scan, outro banco de CVEs nem um classificador por LLM.

O resultado negativo de um teste se aplica àquela verificação e ao seu alcance; não prova que o equipamento inteiro esteja seguro. Uma resposta inconclusiva preserva a incerteza. Configuração observada e CVE confirmada são categorias diferentes.

## Modelos e papéis

| Papel | Modelo/esforço | Escopo |
|---|---|---|
| Orquestrador | `gpt-6.1-sol`, `medium` | Ordenar tarefas, despachar papéis, manter estado e consumo. Não implementar código. |
| Arquiteto | `gpt-6.1-sol`, `high` | Política de evidência, contratos, compatibilidade, reconciliação, aplicabilidade e acesso autenticado. |
| Coder | `gpt-6-luna`, `medium` | Implementação delimitada pela task e pelos contratos aprovados. |
| Tester | `gpt-6-luna`, `medium`, contexto separado | Casos adversos e regressões contra os critérios; não repetir literalmente a implementação. |
| Reviewer | `gpt-6.1-sol`, `medium` ou `high` | `high` nas regras do parser, contrato, reconciliação, aplicabilidade e autenticação; `medium` em apresentação e integração mecânica. |
| Sincronização documental | `gpt-6-luna`, `medium` | Atualização por diff ao fim de cada entrega; decisões novas voltam ao arquiteto. |

`medium` é o padrão da coordenação porque a arquitetura fica registrada em arquivos. A economia real de esforço precisa ser medida: não há uma porcentagem fixa garantida ao mudar `high` para `medium`.

Usar velocidade Standard. Selecionar os modelos no cliente/configuração real, ou passar modelo/esforço explicitamente no mecanismo de delegação. Escrever o nome no prompt não troca o modelo. Se o ambiente não permitir trocar modelos de subagentes, executar os papéis em sessões separadas com os mesmos arquivos de passagem. Não substituir Luna silenciosamente por Sol.

## Preparação do harness — antes da implementação

1. Revalidar branch, HEAD, alterações locais, instruções e descoberta de skills. Não trocar branch nem descartar trabalho do usuário automaticamente.
2. Adaptar apenas o necessário de `.claude` para o Codex: `consult-docs`, `feature-planning`, `create-tasks`, `feature-orchestrator`, `tdd`, `frontend-conventions`, `frontend-design-system`, `openapi-contract-sync` e `docs-sync`, mais seus recursos realmente referenciados.
3. Publicar as skills no local reconhecido pelo cliente; a documentação atual indica `.agents/skills`. Usar `.codex/agents` para papéis somente após conferir o formato suportado pela versão instalada. Corrigir o `AGENTS.md` para o layout efetivamente escolhido.
4. Manter `.claude/docs` como mapa canônico inicialmente. Evitar uma cópia completa em `.codex/docs` que exigiria dupla manutenção. Skill carregada sob demanda não precisa ser colada integralmente em todo prompt.
5. Converter chamadas Claude (`Task`, `subagent_type`, modelos Claude e hooks próprios) para ferramentas realmente disponíveis. Preservar coder → tester → reviewer, tarefas sequenciais e critérios de conclusão. Não converter permissões em aprovações automáticas.
6. Registrar as adaptações e verificar nomes, links relativos, recursos e descoberta no cliente. Os diretórios vazios atuais não comprovam que uma skill esteja instalada.

Esta preparação é trabalho do harness, separado dos commits da melhoria. O usuário está pedindo planejamento agora; os prompts abaixo preparam a execução futura.

## Specs e decisões antes de codificar

Criar `specs/NNN-finding-evidence-quality/`, calculando NNN pela numeração existente no momento da execução. No checkout inspecionado, o próximo número seria 051; não fixá-lo em caso de novos specs.

- `TRUTH.md`: regras e casos verificáveis de cada entrega, sem detalhes de implementação.
- `ARCHITECTURE.md`: política de evidência, tabela de arquivos existentes/novos e expectativas de teste.
- `INTEGRATION.md`: agente → ingest → persistência → leitura → web/PDF/IA, compatibilidade e ordem de implantação.
- `DESIGN.md`: rótulos e estados da interface/relatório, com mockups legíveis.
- `TASKS.md`: gerado após aprovação das specs, com a forma canônica do harness.
- `PROGRESS.md`: decisões, impedimentos, rejeições e resultados resumidos por tarefa.
- `USAGE.md`: chamadas e consumo medido, incluindo os agentes filhos.

Decisões obrigatórias: significado preciso de `confirmed`; como distinguir observação/configuração de teste de CVE; campos aditivos e nulabilidade; tratamento dos negativos/inconclusivos; procedência por observação; compatibilidade de dados antigos; prioridade de evidências conflitantes e contagens públicas.

Preservar os valores existentes de confiança, salvo uma decisão explícita com migração. Nomes novos para método/estado/motivo são propostas a definir no contrato, não campos que já existem. Não substituir o `evidence_basis` usado pela IA sem rastrear seus consumidores.

Backend precisa aceitar os campos novos antes de o agente enviá-los, pois os modelos atuais proíbem campos extras. Payload legado continua válido. Histórico sem prova suficiente não deve ganhar confirmação por inferência. Migração histórica deve afetar somente registros identificáveis e manter justificativa.

## Tasks de implementação

Cada task inclui implementação, testes relevantes e revisão. Configuração, fixtures, tipos gerados e documentação pequena ficam com a tarefa consumidora. O arquiteto confirma a tabela final de arquivos antes do coder. Caminhos sugeridos para módulos novos precisam ser marcados como novos nas specs.

### 1. Parser NSE e corpus inicial de regressão

**Base:** `normalize/findings.py`; `hardware-agent/tests/test_findings.py`.
Interpretar estados explícitos; impedir positivos por substring negativa ou mera menção de CVE. Distinguir múltiplas tabelas no mesmo script e o fallback textual. Proteger os extratores específicos existentes.

**Aceite:** negativo com CVE, inconclusivo, menção em referência e tabela mista não viram confirmação indevida; positivos legítimos continuam detectados. Criar fixtures pequenas e rotuladas que alimentem também a comparação final.
**Dependências:** specs aprovadas. **Review:** Sol high.

### 2. Contrato, política e persistência da procedência

**Base:** `contracts/openapi/openapi.yaml`; schemas de ingest/read; `models/persistence.py`; `services/persistence.py`, `scan_evidence.py`, `risk.py`; Alembic.
Definir os metadados mínimos de método/estado/motivo e sua relação com a confiança existente. Persistir e expor; aceitar payloads antigos; atualizar snapshots somente pelo critério aprovado. Reutilizar os pontos atuais de enriquecimento.

**Aceite:** round-trip de ingest/read; contrato e exemplos consistentes; migração verificável quando necessária; NVD/Vulners não promovem correlação para confirmação. Testes de ingest, contrato e risco.
**Dependências:** #1. **Review:** Sol high.

### 3. Agente como produtor da evidência estruturada

**Base:** `normalize/contracts.py`, `normalize/findings.py`; scanner, targeted adapters e consumidores efetivamente encontrados.
Emitir os novos metadados conforme o contrato e a evidência disponível, incluindo configuração observada e resultados de testes específicos. Rastrear CLI, daemon, pipeline e TUI; parâmetros novos também chegam a `ScanRunner` e `ScanProgressScreen`.

**Aceite:** ambos os caminhos de scan produzem o mesmo significado; arquivo JSON e ingest preservam a procedência; sem afirmações de confirmação fundadas apenas em origem genérica. Testes do contrato e caminhos afetados.
**Dependências:** #2. **Review:** Sol high.

### 4. Reconciliação de evidências e conflito

**Base:** deduplicação no agente; `services/persistence.py`, `inventory.py`, `risk.py`, `enrichment.py`.
Consolidar observações da mesma falha sem aumentar confiança pela quantidade de repetições. Tratar conflito por qualidade, alcance e atualidade. Reavaliar `_max_confidence` conforme a política; preservar cobertura incompleta.

**Aceite:** duplicatas não elevam confirmação; ordem das entradas não muda resultado; negativos/inconclusivos não encerram achados fora do seu alcance; enriquecimento tardio não apaga evidência mais forte. Testes de reconciliação/risco.
**Dependências:** #2, #3. **Review:** Sol high.

### 5. Interface: confiança, método e contagens

**Base:** `FindingPanel.tsx`, telas/tabelas de scan e host, traduções em `frontend/src/i18n/messages/` e tipos gerados.
Explicar separadamente severidade, método e confirmação. Reutilizar os cards e o design system. Contagens por estado devem respeitar filtros e paginação; o escopo agregado pertence à API, não a uma soma improvisada da página atual.

**Aceite:** versão associada, configuração observada, teste específico e histórico sem informação têm rótulos compreensíveis e consistentes com a API. Testes de componentes e integração da tela.
**Dependências:** #4. **Review:** Sol medium, com contrato previamente aprovado.

### 6. Relatório explicado, JSON, IA e fechamento da primeira entrega

**Base:** `reports.py`, `report_education.py`, `report_education_pdf.py`, `report_education_copy.py`; `services/ai/context.py`, `groq.py`.
Usar a política compartilhada para tabelas, explicações e resumo visual. Preservar o relatório técnico JSON e a prévia. O PDF e a IA não podem elevar a certeza do dado. Validar visualmente os PDFs alterados com a skill PDF durante esta implementação.

**Aceite:** contagens, rótulos e limites iguais nos consumidores; JSON continua preservando a evidência; linguagem não transforma suspeita em falha comprovada. Testes de relatórios/IA; comparação inicial do corpus; docs-sync e gates da entrega.
**Dependências:** #4, #5. **Review:** Sol medium; high se houver mudança da política.

### 7. Identidade de produto e versão

**Base:** modelos de serviço/CPE, parsing Nmap e avaliação de identidade já existentes.
Analisar precisão de fabricante/produto/versão, conflitos e identificação incompleta antes de associar falhas. Não atribuir versão ou produto apenas pela porta, nome de host ou fabricante do MAC.

**Aceite:** identidade insuficiente é explicitada; identificações incompatíveis não são combinadas como se confirmassem um produto. Testes de fingerprints e casos de conflito.
**Dependências:** #3, #4. **Review:** Sol high.

### 8. Aplicabilidade das CVEs

**Base:** `services/nvd.py`, `enrichment.py` e clientes/cache existentes.
Avaliar condições estruturadas de produto, intervalo de versões e plataforma, preservando AND/OR/negações quando suportados. Definir o subconjunto suportado; condições não suportadas ou faltantes são desconhecidas, sem tentativa genérica de ordenar versões de fornecedores diferentes.

**Aceite:** incompatibilidade demonstrável descarta a associação; desconhecido não confirma nem descarta. Fonte/data e justificativa ficam registradas. Testes offline com dados representativos; atualizar consumidores ao mudar o contrato.
**Dependências:** #7. **Review:** Sol high.

### 9. Confirmações específicas selecionadas

**Base:** scripts NSE configurados, scanner/stages, targeted adapters, deadlines e cobertura.
Escolher uma lista pequena baseada nos serviços realmente suportados. Registrar resultado, alcance, versão da regra e timeout. Manter limites OT; testes com risco operacional não entram automaticamente no modo Standard.

**Aceite:** apenas resposta específica promove um achado; erro/timeout preserva incerteza; orçamento e cancelamento funcionam. Testes com respostas simuladas; nenhum scan real iniciado pelo assistente sem pedido próprio do usuário.
**Dependências:** #8. **Review:** Sol high.

### 10. Verificação autenticada de patches e backports

**Base:** arquitetura de provisionamento/autorização existente; fornecedor/SO escolhido nas specs.
Entrega própria: coleta opcional, com escopo limitado, armazenamento de credenciais adequado, privilégio mínimo e consulta de pacote/firmware suportado. Começar por uma família de sistema operacional; documentar as restantes como não suportadas.

**Aceite:** patch verificável permite descartar a CVE com justificativa; coleta indisponível continua desconhecida; segredo não aparece em payload, relatório, log ou IA. Testes de falha de autenticação, coletor e mapeamento de advisories.
**Dependências:** #8 e aprovação do desenho de acesso. **Review:** Sol high.

### 11. Revisão manual auditável

**Base:** routers de findings, autorização por organização, persistência e componentes existentes.
Separar decisão manual da evidência automática. Definir escopo equipamento/serviço/CVE/versão, autor, motivo, data, reversão e condição de reavaliação. Não usar IP isolado como identidade durável.

**Aceite:** isolamento de organização, permissões, histórico e reabertura após mudança verificável; decisão não altera dados brutos do scan. Testes de API, permissão e interface.
**Dependências:** #4, #5; após primeira entrega aprovada. **Review:** Sol high.

### 12. Avaliação comparativa de qualidade

**Base:** corpus criado nas tasks anteriores e testes/ferramentas de avaliação já disponíveis, a localizar.
Reproduzir versões antes/depois sobre casos rotulados independentemente e medir TP, FP, FN, precisão e cobertura. Acrescentar taxa FP somente se houver negativos de referência suficientes. Reportar separadamente não avaliáveis e inconclusivos; divisão por método de detecção.

**Aceite:** relatório reproduzível com versões, dataset, denominadores, limitações e resultados; reduzir alertas sozinho não é sucesso. Fixtures de desenvolvimento e conjunto independente de avaliação devem ser distintos. Docs-sync e gates finais por camada alterada.
**Dependências:** tasks da entrega sob avaliação; baseline desde #1. **Review:** Sol high para a validade das métricas.

## Entregas e ordem

```text
Preparação → specs aprovadas → 1 → 2 → 3 → 4 → 5 → 6
                                      └────→ 7 → 8 → 9
                                                 └→ 10
                                  4 + 5 ──────────→ 11
Corpus de 1 → comparação em 6 → avaliação 12 por entrega
```

- Entrega A: #1–#6; correção concreta e comunicação da evidência.
- Entrega B: #7–#9; identidade, aplicabilidade e testes selecionados.
- Entrega C: #10–#11; acesso autenticado e decisão manual.
- #12 acompanha as entregas com escopo correspondente, sem bloquear A pelo trabalho futuro de B/C.

Gerar `TASKS.md` apenas para a entrega aprovada. Manter o restante como roadmap, conforme `create-tasks`; não declarar futuro concluído e não construir implementações provisórias para descartá-las depois.

## Eficiência e estimativa

Não há leitura do saldo do plano nesta sessão. Limites incluídos dependem de contexto, modelo, raciocínio, ferramentas e cache; preços de API não calculam quantas tasks cabem na assinatura. Consultar o painel de uso e, no CLI, `/status`.

Referência oficial de créditos Standard por 1 milhão de tokens:

| Modelo | Entrada | Entrada em cache | Saída |
|---|---:|---:|---:|
| GPT-6.1 Sol | 50 | 2,5 | 250 |
| GPT-6 Luna | 2,5 | 0,25 | 12,5 |

Exemplo hipotético da entrega A: 150 mil tokens de entrada acumulados e 30 mil de saída, com 20% de cada categoria em Sol e 80% em Luna; sem desconto de cache.

- Tudo Sol: `0,15 × 50 + 0,03 × 250 = 15 créditos`.
- Divisão: Sol `0,03 × 50 + 0,006 × 250 = 3`; Luna `0,12 × 2,5 + 0,024 × 12,5 = 0,6`; total `3,6`.
- Diferença nesse cenário: 76%. Não é medição nem previsão de porcentagem do limite incluído. Retrabalho, raciocínio e contextos podem alterar os volumes. Com 30% de reserva: 195 mil de entrada e 39 mil de saída.

Fonte: [OpenAI — Pricing](https://learn.chatgpt.com/docs/pricing), consultada em 2026-10-10. Confirmar taxas na execução. Os volumes são hipótese de planejamento, não teto técnico. A reserva não substitui conclusão dos critérios.

### Regras operacionais de economia

1. Começar por duas tasks piloto (#1 e #2); medir consumo e rejeições antes de projetar B/C.
2. Um coder por vez. Aproximadamente três despachos especializados por task; seis tasks de A significam 18 despachos, além de arquitetura e documentação. Contar também consumo do orquestrador.
3. Usar contexto novo nos filhos, sem herdar a conversa inteira. Passar caminhos, id da task, critérios e delta relevante. Ao usar a ferramenta desta sessão, `fork_turns="none"` com modelo/esforço explícitos; disponibilidade deve ser conferida.
4. Meta de despacho: até 500–800 tokens; retorno até 300–600, exceto bloqueio real. São orientações de concisão, não limites que autorizem omitir evidências.
5. Ler trechos por símbolo com `rg`; abrir no máximo os documentos da camada necessários. Não carregar scans completos, histórico de chat, todos os ADRs ou todas as skills em cada agente.
6. Salvar logs de gates em arquivos; devolver comando, exit code e falhas pertinentes. Não colar a suíte inteira no contexto.
7. Rodar testes focais por task; gates completos nas entregas ou diante de risco concreto. Falha anterior comprovada deve ser registrada, sem esconder uma suíte vermelha.
8. Não recriar contratos/types/helpers. `npm.cmd run gen:types` gera os tipos, sem edição manual do resultado.
9. Registrar pequenos deltas em PROGRESS; docs-sync uma vez por entrega. Não regenerar specs inteiras a cada ajuste.
10. Após primeira rejeição, usar coder novo com feedback preciso; após segunda pelo mesmo motivo, revisar a decisão arquitetural antes de repetir. Preservar o gate estrutural formal da quarta rejeição do harness.

Medir `input`, cache, saída e raciocínio quando a ferramenta expuser. Registrar valores por chamada ou deltas entre acumulados: somar acumulados repetidamente gera contagem falsa. Quando não houver telemetria, marcar “não disponível”; registrar também variação do painel, sem atribuí-la exclusivamente à task se houver outras sessões ativas.

## Gates e documentação

- Agente: pytest e Ruff focais, depois gate completo da camada alterada.
- Backend: preparar `dmitri_test` conforme `database.ps1`/`database.sh`; nunca apontar para o banco de desenvolvimento. Registrar indisponibilidade em vez de declarar suíte verde. Ruff sem formatador global.
- Frontend: `npm.cmd run lint`, `format:check`, `typecheck`, `test`, `build`, conforme os scripts atuais. Verificação de contrato e tipos sempre que o schema mudar.
- PDF: testes semânticos e renderização das páginas afetadas; JSON técnico precisa continuar compatível.
- Registrar arquivos, decisões, critérios atendidos, gates, limitações e consumo. Sem comentários/docstrings novos em código, conforme as instruções do projeto.
- Publicação, deploy no Pi e scan real são ações distintas de implementar. Preservar o pedido atual para o usuário iniciar seus scans.

Referências oficiais dos modelos: [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). Descoberta de skills: [Build skills](https://learn.chatgpt.com/docs/build-skills). Papéis e conversões devem refletir a versão do cliente disponível, não uma configuração presumida.
