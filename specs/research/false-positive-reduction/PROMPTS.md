# Prompts — redução de falsos positivos

Estes prompts preparam uma execução futura. Nenhum deles foi executado para implementar a melhoria nesta sessão.
Selecionar modelo/esforço no cliente ou na delegação real; o texto do prompt sozinho não muda isso.

Base: [PLAN.md](PLAN.md). Contexto compacto: [CONTEXT.md](CONTEXT.md).

## 0. Preparação seletiva do harness

Modelo da sessão: GPT-6.1 Sol medium. Cópia/adaptação delimitada: GPT-6 Luna medium.

```text
Prepare o harness para o plano specs/research/false-positive-reduction/PLAN.md.
Leia AGENTS.md e CONTEXT.md nesse diretório. Confira os caminhos atuais:
.claude contém as fontes; .codex pode ter apenas diretórios vazios; não presuma
que .agents/skills, .codex/docs ou os papéis estejam instalados.

Confirme a versão do cliente e a documentação oficial de descoberta de skills
e configuração de agentes. Adapte somente as skills/papéis necessários à
Entrega A. Preserve coder → tester → reviewer, tarefas sequenciais e os gates.
Trate regras “single layer” como históricas: o projeto atual tem várias camadas.
Não altere as regras globais do usuário nem as permissões da máquina.

Mantenha .claude/docs como mapa canônico, referenciando-o nos prompts. Corrija
o layout documentado no AGENTS.md somente para caminhos efetivamente criados.
Evite duplicar toda a base documental. Confira links e recursos das skills.

Use Sol medium na coordenação, Sol high na arquitetura/revisões de evidência
e Luna medium na adaptação mecânica. Se a seleção não estiver disponível,
informe a limitação e forneça os prompts para sessões separadas; não use
outro modelo silenciosamente. Não implemente a melhoria de produto agora.

Entregue um delta curto do harness, caminhos instalados, verificação de
descoberta e como escolher os modelos. Nenhum diretório vazio conta como
skill instalada. Preserve alterações preexistentes e segredos.
```

## 1. Arquitetura e specs da primeira entrega

Modelo: GPT-6.1 Sol high. Usar este prompt após preparar o harness, ou ler diretamente as fontes locais se a instalação das skills ainda não tiver ocorrido.

```text
Planeje a Entrega A da redução de falsos positivos do Dmitri.
Leia AGENTS.md e specs/research/false-positive-reduction/{CONTEXT,PLAN}.md.
Use as versões realmente disponíveis de feature-planning e consult-docs;
se não estiverem descobertas pelo cliente, leia os SKILL.md indicados no
contexto. Revalide as constatações no código; não carregue a base inteira.

Amplie confidence, cobertura, deduplicação e apresentação existentes. Não
crie do zero recursos que o backend e FindingPanel já têm. Rastreie ambos
os caminhos de scan, daemon/CLI/TUI, ingest, leitura, risco, PDF e contexto IA.

Crie o próximo specs/NNN-finding-evidence-quality com TRUTH, ARCHITECTURE,
INTEGRATION e DESIGN. Defina nomes e arquivos exatos; marque arquivos novos.
Inclua mockups simples dos estados da interface e do resumo do PDF, segundo
o design system. Os metadados novos devem ser mínimos e justificados.

Decida o significado de confirmação, observação de configuração, associação
por versão, negativo e inconclusivo. Não use origem nmap_nse como prova
automática, nem substring vuln ou CVE citada como positivo. Defina tratamento
de resultados mistos, fallback textual e histórico sem evidência estruturada.
Defina política de conflito, nulabilidade, migração e rollout backend antes
do agente. Preserve o JSON técnico e as fronteiras de dados da IA.

Mapeie critérios a testes reais, inclusive negativos com CVE e scans parciais.
Referencie código/símbolos observados e registre dúvidas como dúvidas.
Mantenha B/C como roadmap, sem especificar conectores genéricos ou dezenas
de validadores futuros. Não implemente código, não rode scan e não publique.

Ao terminar, entregue os caminhos e as decisões materiais para aprovação,
conforme o gate de feature-planning. Não marque specs aprovadas por conta
própria e não comece a execução.
```

## 2. Orquestrador de implementação

Modelo: GPT-6.1 Sol medium. Preencher `{SPEC_DIR}` com as specs aprovadas. Este é o prompt para usar quando o usuário decidir iniciar a implementação.

```text
Implemente a Entrega A aprovada em {SPEC_DIR}, com delegação explícita.
Siga AGENTS.md e as specs aprovadas. Use create-tasks e feature-orchestrator
realmente disponíveis, conferindo suas instruções. A aprovação informada
vale para esta entrega; confirme que os arquivos correspondem à versão
aprovada. Futuras entregas B/C continuam fora desta execução.

Você é o orquestrador GPT-6.1 Sol medium. Mantenha TASKS.md, PROGRESS.md e
USAGE.md; não escreva código de produto nem se aprove como reviewer.
Gere apenas tarefas da entrega aprovada na forma canônica do harness,
absorvendo config, fixtures e wrappers na task que os consome.

Desenvolvedor: gpt-6-luna medium. Tester: gpt-6-luna medium em contexto
separado. Reviewer: gpt-6.1-sol high para parser, contrato, procedência e
reconciliação; medium para UI/PDF quando a política já estiver fechada.
Arquiteto adicional: gpt-6.1-sol high somente para decisão não resolvida.

Despache uma task por vez: coder → tester → reviewer. Passe id, caminhos,
critérios, arquivos permitidos e decisões relevantes, sem herdar a conversa
inteira. Se esta sessão expuser spawn_agent, use fork_turns="none" e passe
model/reasoning_effort explicitamente. Caso contrário, use a configuração
verificada do cliente ou os prompts separados; não finja uma troca de modelo.

Só marque COMPLETED após [APPROVE], com evidência dos critérios e gates.
Rejeição gera coder novo, preservando o diff e fornecendo feedback preciso.
Segunda rejeição pelo mesmo motivo pede análise arquitetural curta; quarta
rejeição segue o bloqueio estrutural e o gate humano da skill.

Registre consumo por chamada ou por deltas de acumulados quando disponível.
Nunca some o mesmo acumulado várias vezes. Consumo indisponível fica marcado
como tal. Faça o piloto nas primeiras duas tasks e atualize a estimativa.
Resuma erros de gates sem colar logs completos; conserve os arquivos de log.

Mantenha mudanças reversíveis e escopo delimitado. Respeite o pedido para
não iniciar scans reais. Não faça deploy no Pi, commit/push ou PR como parte
desta execução, pois são etapas próprias posteriores. Não altere segredos.

Ao fechar a entrega, delegue docs-sync a Luna medium, execute os gates por
meio dos papéis apropriados e reporte critérios, limitações e consumo real.
```

## 3. Despacho do coder

Modelo: GPT-6 Luna medium. Orquestrador preenche os campos a partir de `TASKS.md` e da tabela de arquivos aprovada.

```text
Papel: coder. Implemente somente Task {N} de {SPEC_DIR}/TASKS.md.
Leia AGENTS.md, a seção da task e os trechos de ARCHITECTURE/INTEGRATION/DESIGN
citados nela. Comece pelos arquivos permitidos: {ARQUIVOS}. Critérios:
{CRITERIOS}. Decisões já aprovadas: {DECISOES}. Use {SKILLS_RELEVANTES}.

Localize símbolos com rg e confira cada dependência no código. Reutilize
contratos, normalizadores e componentes existentes. Campo/módulo não
encontrado não pode ser tratado como existente. Não amplie a task para
resolver detalhes arquiteturais não aprovados; reporte o ponto concreto.

Preserve alterações de outras pessoas. Não formate o repositório inteiro,
não adicione comentários/docstrings e não altere segredos ou dependências
sem necessidade demonstrada. Tipos OpenAPI são gerados, não editados à mão.
Considere todos os consumidores listados na integração, inclusive TUI.

Implemente o comportamento completo desta task. Não marque COMPLETED nem
se dê [APPROVE]. Não inicie scan, não faça deploy/commit/push.
Retorne arquivos alterados, decisões aplicadas, critérios entregues e
limitações objetivas, preferencialmente em até 400 palavras. Não cole o diff.
```

## 4. Tester independente

Modelo: GPT-6 Luna medium, sessão/contexto diferente do coder.

```text
Papel: tester de {CAMADA}. Task {N} em {SPEC_DIR}/TASKS.md.
Leia AGENTS.md, critérios da task e diff dos arquivos {ARQUIVOS}.
Use o agente/skill de teste da camada realmente disponível.

Escreva testes que verifiquem o comportamento externo dos critérios e
falhariam com o erro descrito. Reutilize fixtures e padrões próximos.
Inclua limites, respostas negativas, inconclusivas, conflitantes e legado
quando aplicáveis. Não espelhe a implementação como resultado esperado.
Não altere a lógica de produto para fazer os testes passarem.

Use dados offline mínimos e resultados rotulados independentemente. Não
rode scans reais. Testes backend usam dmitri_test e a preparação documentada;
nunca reutilize dmitri_sim. Não declare verde se coleta/ambiente falhar.

Rode a seleção pertinente para validar os testes, respeitando os gates da
camada. Salve detalhes em {LOG_PATH}. Retorne os testes entregues, quais
critérios cobrem, comandos/exit codes e falhas pertinentes; sem log completo.
O reviewer decide [APPROVE]/[REJECT].
```

## 5. Reviewer

Modelo: Sol high para lógica de evidência/contrato; Sol medium para apresentação com semântica aprovada.

```text
Papel: reviewer de {CAMADA}. Avalie Task {N} em {SPEC_DIR}/TASKS.md.
Leia AGENTS.md, critérios, decisões relevantes e o diff delimitado em
{ARQUIVOS}. Use a definição real do reviewer dessa camada.

Confira semântica da evidência, regressões, compatibilidade, cobertura dos
testes e integração com todos os consumidores. Não aceite certeza fundada
apenas em nome do script, existência de CVE ou quantidade de fontes repetidas.
Verifique que desconhecido/erro não virou confirmação ou segurança.

Rode os gates exigidos no escopo da task; gates completos na entrega ou
quando houver risco concreto. Contrato alterado exige fidelidade e geração
dos tipos. Backend exige preparação de dmitri_test. Não esconda falhas
preexistentes; registre separadamente as comprovadas. Não rode scan real.

Não corrija código de produto. Retorne primeiro [APPROVE] ou [REJECT], depois
critério, arquivo:linha e evidência/ação necessária. Cite comando e exit code.
Sem prescrições genéricas de refatoração ou abstrações adicionais.
Prefira retorno curto e específico; detalhes ficam em {LOG_PATH}.
```

## 6. Correção após rejeição

Modelo: GPT-6 Luna medium, coder novo.

```text
Corrija Task {N} em {SPEC_DIR}/TASKS.md. Você é um coder novo.
O diff existente deve ser preservado exceto onde a correção exigir mudança.
Leia AGENTS.md, a task e a decisão arquitetural citada. Rejeição:
{FEEDBACK_INTEGRAL_RELEVANTE}.

Resolva somente os critérios rejeitados nos arquivos {ARQUIVOS} e mantenha
os positivos legítimos. Não enfraqueça testes nem elimine achados válidos
apenas para reduzir a contagem. Não reinicie a arquitetura já aprovada.
Se o feedback exigir mudar contrato/política, explique a decisão ausente
para o orquestrador antes de adotar um comportamento novo.
Retorne o delta e os critérios corrigidos para nova revisão. Sem autoaprovação.
```

## 7. Documentação e encerramento da entrega

Modelo: Luna medium; revisão das conclusões pelo Sol.

```text
Sincronize documentação da Entrega {A/B/C} em {SPEC_DIR} conforme docs-sync.
Use apenas o diff delimitado e os resultados aprovados do PROGRESS.md.
Atualize o mapa canônico existente, docs humanos afetados, referências de
contrato e decisões aceitas. Não duplique .claude/docs em outro diretório.
Não descreva melhorias planejadas como implementadas.

Documente origem/confiança/limitações, compatibilidade e ordem de atualização,
gates e métricas efetivamente executados. USAGE.md deve separar estimativa
de consumo observado; valores indisponíveis permanecem desconhecidos.

Não altere lógica de produto, não rode novo scan nem publique. Retorne os
caminhos atualizados e qualquer divergência que dependa de decisão arquitetural.
```

## Complementos por task

Adicionar somente o bloco da task selecionada ao despacho do coder/tester. Não colar os doze blocos em cada chamada. Revalidar arquivos finais nas specs aprovadas.

### Task 1 — parser

```text
Corrija os extratores genéricos em normalize/findings.py. Separe explicitamente
negativo, provável, positivo e desconhecido. Não deixe o fallback textual
reintroduzir uma CVE descartada por resposta negativa estruturada. Trate
múltiplos resultados por script, sem um negativo global apagar positivos de
outra verificação. Preserve extratores específicos. Entregue os casos de
regressão em test_findings.py com evidências pequenas e positivas de controle.
```

### Task 2 — backend e contrato

```text
Implemente os metadados de procedência aprovados no contrato, ingest,
persistência e leitura. Reutilize confidence e scan_evidence existentes.
Inclua legado, migração quando necessária e snapshots de risco. Lembre que
extra=forbid requer backend atualizado antes do agente. Não confirme CVE
apenas porque NVD/KEV/EPSS conhece ou prioriza a falha. Não invente campos.
```

### Task 3 — produtor no agente

```text
Emita o contrato aprovado no agente para cada tipo de evidência suportado.
Rastreie normalização, adapters e consumidores CLI/daemon/TUI. Preserve o
JSON emitido. Parâmetro novo exige todos os call sites, inclusive ScanRunner
e ScanProgressScreen. Método conhecido não equivale a resultado positivo;
não promova automaticamente todos os findings de nmap_nse.
```

### Task 4 — reconciliação

```text
Aplique a política aprovada à deduplicação, upsert_finding, enriquecimento,
inventário e risco. Repetição não eleva certeza. Teste permutações da ordem,
fontes de qualidades diferentes, enriquecimento tardio e scans parciais.
Negativo vale somente no alcance previsto na política. Evite outro helper
de identidade quando o projeto já possui finding_dedupe_key.
```

### Task 5 — interface

```text
Atualize FindingPanel e consumidores previstos no DESIGN. Reutilize cards,
tabelas, tokens e traduções existentes. Exiba separadamente severidade,
confiança e método, com estado legado compreensível. Tipos vêm de gen:types.
Não some apenas uma página de resultados para apresentar total global.
Inclua acessibilidade e estados vazios/inconclusivos nos testes de tela.
```

### Task 6 — relatório e IA

```text
Reutilize report_education, copy e renderização do PDF. Faça resumo, contagens,
registro e contexto IA seguirem a mesma política da API. Preserve download
JSON técnico e prévia. Não use IA para inferir a certeza. Teste semântica,
renderize páginas afetadas via skill PDF e confira legibilidade. Registre
comparação inicial do corpus e sincronize docs no fechamento da Entrega A.
```

### Task 7 — identidade

```text
Inspecione fingerprints, CPEs, fabricante/produto/versão e conflitos no fluxo
existente. Aplique somente a política aprovada para evidência insuficiente.
Porta, hostname e OUI de MAC não identificam sozinhos software e versão.
Teste sinais contraditórios e identificação parcial sem criar outra camada
de descoberta. Registre por que a identificação foi aceita ou limitada.
```

### Task 8 — aplicabilidade

```text
Amplie o parser/clientes NVD existentes para o subconjunto aprovado de
condições de aplicabilidade. Preserve a lógica AND/OR e limites inclusivos/
exclusivos. Ausência de plataforma/configuração significa desconhecido.
Não use comparação genérica de strings ou uma única regra de versão para
todos os fornecedores. Valide offline e registre fonte/data/justificativa.
```

### Task 9 — teste específico

```text
Implemente só as verificações selecionadas na arquitetura, reutilizando NSE/
targeted, timeout, deadline e cobertura existentes. Confirmação exige resposta
positiva específica. Registre alcance e inconclusivos; mantenha cancelamento.
Preserve restrições OT e modos de scan aprovados. Testes usam respostas
simuladas; não execute a rede real para validar esta task.
```

### Task 10 — autenticado/backports

```text
Implemente apenas a família de SO/firmware e o desenho de acesso aprovados.
Separe credenciais de evidências públicas, relatórios e contexto IA. Colete
versão completa/patch por operação limitada e mapeie advisories do fornecedor.
Falha de login ou produto não suportado resulta em desconhecido, nunca limpo.
Testes cobrem segredo, escopo de acesso, backport e correção comprovada.
```

### Task 11 — decisão manual

```text
Implemente decisão auditável com autorização por organização e isolamento de
tenant. Preserve evidência automática e JSON original. Vincule à identidade
durável e condições definidas; não apenas IP. Teste autor/motivo/reversão,
usuário sem permissão, organização diferente e reavaliação após mudança.
```

### Task 12 — comparação

```text
Compare versões antes/depois usando o corpus rotulado e um conjunto separado
de avaliação. Registre TP, FP, FN, denominadores, precisão, cobertura e
inconclusivos por método. Só calcule taxa FP com negativos conhecidos.
Não chame menor número de alertas de melhoria sem conferir os falsos negativos.
O scan pessoal não é ground truth. Documente reprodução e limitações.
```

## Registro mínimo de uso e passagem

Formato para uma linha por chamada no `USAGE.md` futuro:

```text
task | papel | modelo | esforço | input | cached input | output | reasoning
     | origem da medição | rejeições | gate/exit | observação
```

Quando a métrica for acumulada, registrar início/fim e calcular o delta; tokens de raciocínio podem já estar incluídos na saída. Conferir a definição da ferramenta antes de somar. O prompt de passagem referencia o arquivo de progresso, em vez de colar todo o histórico.
