# TRUTH — OPC UA integrado ao NSPi

Status: approved for execution; Task 1 complete and reviewer-approved. Tasks 2–9 await user command.
Data: 2026-10-20. Base observada: `feature/nspi-scan-opcua`, `971ba8d`.

## Narrativa

O NSPi já inclui a porta usual de OPC UA na descoberta de rede, mas seu inventário
industrial e mapeamento dedicados atendem ao Modbus. O operador precisa identificar
servidores OPC UA, conhecer a segurança anunciada e verificar o alcance de leituras
permitidas dentro da mesma experiência de scan.

O operador continua selecionando NSPi e os submodos existentes. Um equipamento que
oferece os dois protocolos pode produzir observações de ambos na mesma varredura.

## Regras de negócio

- U01: preservar os modos atuais. `inventory` permanece o padrão; `read_only_mapping`
  acrescenta navegação e leitura limitadas de OPC UA. Não criar modo ou submodo.
- U02: porta aberta indica candidato. Confirmar OPC UA exige resposta válida do
  protocolo; não inferir vulnerabilidade, fabricante ou versão da porta.
- U03: inventário coleta identidade anunciada, endpoints, políticas de segurança,
  modos de proteção e métodos de autenticação, conservando procedência e limites.
- U04: endpoint anunciado e operação efetivamente permitida são evidências distintas.
  Anunciar acesso anônimo não comprova navegação ou leitura anônima.
- U05: mapeamento percorre uma parte limitada dos objetos e variáveis e verifica as
  leituras permitidas. Registra metadados e resultados; valores de processo e seus
  derivados não podem sair do processo do agente.
- U06: a primeira entrega usa descoberta e, quando permitido, sessão anônima. Exigência
  de credenciais ou de preparação de certificados deve gerar motivo explícito de
  cobertura limitada. Não tentar senhas, adivinhar credenciais ou contornar confiança.
- U07: todas as operações de aplicação são de descoberta, navegação ou leitura.
  Escrita, execução de métodos, alterações de configuração e assinaturas de dados
  ficam indisponíveis. Estabelecer e encerrar a comunicação usa somente o necessário
  para essas operações permitidas.
- U08: alvos permanecem restritos aos dispositivos e serviços descobertos. URLs e
  referências fornecidas por um servidor não autorizam conexões a outros destinos.
- U09: inspeção é sequencial e limitada por requisições, páginas, nós, profundidade,
  tamanho de dados e tempo. Cancelamento e prazo global também interrompem OPC UA.
- U10: Modbus e OPC UA compartilham o orçamento industrial e preservam seus resultados
  independentes. Falha de um serviço não apaga resultados do outro.
- U11: falha, recusa de acesso, incompatibilidade de segurança e limite atingido têm
  estados distintos. Nenhum desses casos equivale a ausência de risco ou scan completo.
- U12: observações e eventuais findings seguem a política de qualidade da evidência
  existente. Configuração anunciada, operação verificada e correlação de versão devem
  preservar significados diferentes; CVE não é confirmada pela identidade anunciada.
  Esta entrega acrescenta observações OPC UA; novos findings e severidades OPC UA
  dependem de regras futuras com contexto e evidência suficientes.
- U13: resultados atravessam o fluxo atual até detalhes do scan e equipamento,
  relatórios e exportações no front, com separação visível por protocolo. O front é
  a interface principal. A TUI mantém compatibilidade com o motor compartilhado;
  melhorias de apresentação nela ficam para uma entrega futura. Scans antigos e
  consumidores existentes de Modbus continuam válidos.
- U14: dados de equipamentos são não confiáveis. Limitar antes de conservar, escapar
  antes de exibir e remover segredos de URLs, certificados e mensagens de diagnóstico.
- U15: validar a feature com testes determinísticos e um servidor de laboratório
  isolado. Diferenciar comprovação no simulador de validação em equipamento real.

## Histórias de usuário

1. Como operador, quero identificar os protocolos industriais presentes ao escolher
   NSPi, sem precisar selecionar um scan separado para OPC UA.
2. Como analista, quero conhecer o que o servidor anuncia e o que a sessão consegue
   ler, para interpretar findings sem concluir além da evidência disponível.
3. Como responsável pela rede, quero limites mensuráveis, cancelamento e ausência de
   escrita comprovados pelos testes.
4. Como operador, quero consultar cobertura e resultados no mesmo histórico e
   relatórios já usados para Modbus.

## Critérios de aceitação

| ID | Dado | Quando | Então |
|---|---|---|---|
| A01 | NSPi sem submodo explícito | O scan começa | Executa inventário; não navega nem lê valores de processo. |
| A02 | Serviço na porta usual sem resposta OPC UA válida | É inspecionado | Permanece candidato/inconclusivo, sem confirmação ou finding por porta aberta. |
| A03 | Servidor com endpoints válidos | Inventário termina | Conserva metadados limitados, políticas e autenticação anunciadas com origem. |
| A04 | Endpoint anuncia anônimo, mas recusa sessão ou leitura | Mapeamento é solicitado | Registra a recusa e não afirma leitura anônima confirmada. |
| A05 | Servidor permite sessão e leitura anônimas | Mapeamento é solicitado | Registra nós e atributos permitidos dentro dos limites; valores brutos não aparecem nas saídas. |
| A06 | Servidor exige autenticação ou certificados indisponíveis | A inspeção ocorre | Inventário aproveitável permanece e o mapeamento mostra o requisito não atendido. |
| A07 | Serviço permite métodos, escrita e subscriptions | O scan executa | Nenhuma dessas operações é enviada; testes do tráfego verificam a fronteira. |
| A08 | Endpoint ou referência aponta para outro destino | É recebido | Nenhuma conexão fora do alvo descoberto; a restrição aparece como cobertura. |
| A09 | Grafo cíclico, muitas páginas ou resposta excessiva | Navegação ocorre | Para no limite definido, preserva resultados e informa truncamento. |
| A10 | Cancelamento, timeout ou prazo global | OPC UA está ativo | Encerra comunicação no limite e mantém resultados parciais conforme a semântica existente. |
| A11 | Mesmo host oferece Modbus e OPC UA | NSPi termina ou fica parcial | Conserva ambos, com contadores, cobertura e evidências independentes. |
| A12 | Há somente anúncio de segurança ou identidade | Findings são avaliados | Nenhuma leitura ou CVE recebe confirmação sem os fatos exigidos pela regra. |
| A13 | Scan antigo ou agente que só envia Modbus | Backend e front recebem os dados | Dados continuam legíveis; OPC UA ausente não vira resultado negativo. |
| A14 | Texto com markup, URI com segredo ou valor de processo | JSON, logs, web, TUI e relatórios são produzidos | Saídas respeitam limites, escape e exclusão de segredos/valores. |
| A15 | Mesmos alvos no CLI, TUI e comando remoto | NSPi é executado | Todos usam o mesmo coletor, submodo e limites. |
| A16 | Servidor controlado permite/recusa operações | Harness executa a matriz | Evidência rastreável cobre sucesso, restrições, falhas e regressão Modbus. |

## Fora do escopo desta entrega

- Novo modo de scan, exploração, testes de escrita e o submodo `active_validation`.
- Gerenciamento de credenciais, distribuição de certificados de cliente e trust stores
  por organização; essas capacidades exigem desenho próprio.
- OPC Classic/DA, PubSub, histórico, subscriptions, testes de carga e coleta contínua.
- Expansão das verificações de EtherNet/IP ou revisão geral do pipeline.
- Apresentação detalhada de OPC UA e melhorias visuais da TUI; manter somente a
  compatibilidade necessária para o scan e os consumidores existentes funcionarem.
- Merge, publicação de release ou deploy no Raspberry como efeito do planejamento.

## Documentos relacionados

- Arquitetura e contrato: `ARCHITECTURE.md`, `INTEGRATION.md`.
- Experiência de resultados: `DESIGN.md`.
- Sequência proposta e distribuição de modelos: `PLAN.md`.
- Contextualização de agentes e harness de execução: `PROMPTS.md`.
