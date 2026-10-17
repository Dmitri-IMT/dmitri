# Atualização do agente pela interface web

Status: proposta com tarefas detalhadas a pedido do usuário; implementação aguarda seu comando.

## Narrativa

O administrador precisa atualizar o software dos dispositivos Dmitri pelo navegador, sem abrir
terminal nem informar senha do sistema operacional em cada atualização. A interface deve informar
o que está instalado, qual versão está disponível e o resultado real da atualização.

Uma publicação do agente é diferente de um commit no projeto. Cada publicação instalável deve
ter identidade e versão únicas, procedência verificável e notas de mudança. Dispositivos antigos
podem precisar de uma preparação inicial assistida antes de receber esse recurso remotamente.

## Regras de negócio

- A atualização é manual por padrão: um administrador da organização escolhe atualizar um
  dispositivo compatível e conectado. Apenas verificar disponibilidade não autoriza instalação.
- Visualizadores podem consultar versões e estado; não podem solicitar atualização.
- A solicitação seleciona uma publicação aprovada. Não aceita comandos, arquivos ou endereços
  arbitrários fornecidos pelo navegador.
- Uma atualização não pode interromper scans, envio de resultados ou finalização pendente. Uma
  varredura não pode começar durante a atualização. Isso também vale para operações locais.
- Não enfileirar atualização para execução surpresa quando um dispositivo offline voltar.
- Só uma atualização pode executar por dispositivo. Repetições da mesma solicitação não devem
  produzir instalações repetidas; uma intenção antiga não pode atualizar novamente após reconexão.
- O instalador deve continuar capaz de finalizar ou recuperar a operação mesmo se o processo do
  agente for substituído ou reiniciado. Estado e identidade da operação devem sobreviver a falhas.
- Preservar identidade, credenciais, organização, configuração e resultados do dispositivo.
- Verificar autenticidade, integridade, compatibilidade e versão da publicação antes de instalar.
  Publicações anteriores devem estar disponíveis para recuperação controlada.
- Pedido aceito, pacote instalado e agente saudável são fatos diferentes. A interface deve mostrar
  progresso e evidências de conclusão sem tratar desconexão esperada como sucesso ou falha definitiva.
- Uma falha local deve acionar a recuperação prevista e registrar o resultado. Perda de acesso ao
  backend, isoladamente, não prova que o software instalado está defeituoso.
- Registrar quem pediu a atualização, versões anterior/desejada/observada, horários e resultado.
  Mensagens ao usuário devem explicar o próximo passo e não expor segredos.
- Dispositivos sem suporte informam a preparação inicial necessária. A interface não deve sugerir
  que um agente antigo adquire a capacidade de atualização apenas por receber um comando novo.

## Histórias de usuário

1. Como administrador, quero comparar a versão instalada e a disponível e ler as mudanças antes
   de atualizar um dispositivo.
2. Como administrador, quero atualizar com um botão e acompanhar o resultado, preservando scans
   e dados existentes.
3. Como operador, quero entender se a atualização está em andamento, aguardando confirmação,
   falhou ou foi recuperada para uma versão anterior.
4. Como responsável pela instalação, quero preparar um dispositivo uma vez para permitir futuras
   atualizações pelo navegador.

## Critérios de aceitação

| ID | Cenário | Dado / quando | Resultado observável |
|---|---|---|---|
| U01 | Versão e procedência | Um dispositivo já reportou sua versão | A última versão observada e sua atualidade continuam visíveis mesmo offline; ausência não vira valor inventado. |
| U02 | Publicação disponível | Há uma publicação compatível aprovada | Interface diferencia instalado, disponível, atualizado e verificação indisponível; mostra notas da publicação. |
| U03 | Permissões | Um visualizador ou usuário de outra organização tenta atualizar | A operação é recusada sem alterar o dispositivo; apenas administrador da organização pode solicitar. |
| U04 | Confirmação manual | Administrador confirma uma versão disponível | Uma operação identificável é registrada; aceitação não aparece como conclusão. |
| U05 | Scan em andamento | Scan, upload ou finalização está ativo | Atualização é recusada sem cancelar o scan nem modificar o agente. |
| U06 | Corrida local/remota | Scan e atualização disputam o dispositivo | Apenas a operação compatível com a exclusão mútua inicia; o resultado é explícito em todos os caminhos locais e remotos. |
| U07 | Offline ou legado | O dispositivo está offline, revogado ou sem suporte | A instalação não é enfileirada; a interface explica reconexão, restauração ou preparação inicial, conforme o caso. |
| U08 | Repetição e reconexão | Uma solicitação se repete ou uma conexão é substituída | Não ocorre instalação duplicada nem aceitação de resultado de sessão/dispositivo incorreto. |
| U09 | Publicação inválida | Autenticidade, integridade, compatibilidade ou versão não confere | O pacote não é instalado; o motivo aparece sem revelar segredos. |
| U10 | Reinício previsto | O pacote é instalado e o agente reinicia | Estado durável permite retomar acompanhamento; a versão observada corresponde à publicação solicitada antes de declarar sucesso. |
| U11 | Falha e recuperação | Instalação ou verificação local falha | O dispositivo tenta a recuperação definida, preserva dados e informa falha, recuperação concluída ou intervenção necessária. |
| U12 | Rede ou energia interrompida | Ocorre interrupção durante atualização | Ao recuperar, o estado é reconciliado sem sucesso falso, replay de instalação ou perda silenciosa da operação. |
| U13 | Backend indisponível | Agente atualizado está saudável localmente, mas sem backend | A confirmação remota fica pendente; desconexão isolada não é interpretada como defeito comprovado da instalação. |
| U14 | Histórico e privacidade | Uma atualização termina ou falha | Histórico registra solicitante, versões, horários e resultado; não registra chaves, senhas ou conteúdo sensível de configuração. |
| U15 | Experiência localizada | Usuário acessa os idiomas existentes e usa teclado/leitor de tela | Estados, confirmação e erros são localizados e acessíveis; falhas usam o tratamento de erros do produto. |
| U16 | Preparação e distribuição | Há um dispositivo legado ou falta distribuição de publicações | Pré-requisitos e responsabilidade pela infraestrutura são explícitos; a feature não é declarada operacional antes da preparação real. |

## Fora do escopo desta entrega

- Atualizações do sistema operacional, firmware, backend ou frontend pelo dispositivo.
- Executar comandos remotos genéricos, enviar pacotes arbitrários ou atualizar a partir de um checkout.
- Atualizações automáticas sem confirmação, campanhas em massa e agendamento por organização.
- Alterar ferramentas ou intensidade do scan, iniciar ou cancelar scans para viabilizar atualização.
- Inventar percentuais de progresso, prazos de recuperação ou limites de confiabilidade sem evidência.
- Implementação ou provisionamento de produção nesta fase de planejamento.

## Documentos relacionados

- Decisões e caminhos: `ARCHITECTURE.md`.
- Contratos entre camadas: `INTEGRATION.md`.
- Experiência web: `DESIGN.md`.
- Execução e modelos: `PLAN.md` e `PROMPTS.md`.
- Ledger de desenvolvimento, dependências e critérios por tarefa: `TASKS.md`.
