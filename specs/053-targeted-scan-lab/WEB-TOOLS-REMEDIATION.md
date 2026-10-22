# Correção de execução do Nikto e testssl e retomada do laboratório

Data: 2026-10-22. Estado: implementacao e validacao integrada concluidas.

## Objetivo e escopo confirmado

O diagnostico e a correcao focaram por que Nikto e testssl nao conclu?am adequadamente no Dmitri. Implementacao, ensaios diretos e validacao integrada concluidos. Este escopo nao amplia parsers, classificacao ou relatorios.

A seleção automática já está implementada nos modos `nspi` e `extensive`, conforme os serviços e portas descobertos. No ensaio `extensive`, Nikto e testssl foram selecionados e iniciados; o problema observado ocorreu depois da seleção. A implementação em `nspi` não equivale a uma prova runtime já feita nesse modo. A correção deve preservar os dois caminhos, sem redesenhar a seleção ou os modos.

As ferramentas devem continuar úteis à auditoria automatizada: coletar evidências de vulnerabilidades e configurações inseguras para reportar problemas e apoiar possíveis correções. O laboratório demonstra esse uso. Os ajustes devem funcionar em serviços reais, sem depender dos IPs ou conteúdos do laboratório e sem coleta manual na operação normal.

## Limites da correção imediata

Entra no escopo:

- Diagnosticar as chamadas reais, versões, dependências, duração, saída estruturada, códigos de retorno e motivos de interrupção.
- Corrigir parâmetros de execução e dependências de Nikto/testssl conforme causas demonstradas.
- Ajustar somente os limites individuais dessas ferramentas quando a medição justificar; manter limites explícitos e cobertura incompleta visível.
- Complementar diagnósticos sanitizados e limitados nos dois adaptadores usando a saída já capturada pelo executor. Não reformular o executor compartilhado.
- Corrigir pontualmente a leitura do relatório apenas se um defeito demonstrado impedir o processamento de um formato já suportado.
- Testar a correção e conferir que os resultados suportados continuam chegando à persistência e ao relatório existentes.

Fica fora desta correção:

- Alterar seleção automática, modos, ordem geral das ferramentas ou comportamento de ffuf, ssh-audit, enum4linux-ng, FTP, Telnet, Nmap/NSE e Vulners.
- Ampliar parsers, criar novas famílias de findings, validações HTTP adicionais, tratamento de novos IDs/categorias ou regras de severidade.
- Promover genericamente resultados inconclusivos a confirmados, implementar validações específicas de `.env`/Git ou ampliar a interpretação de cabeçalhos.
- Criar contratos de API, telas, mecanismos de consolidação ou reformular relatórios.
- Ignorar falhas ou remover cobertura somente para aprovar a demonstração.

## Evidência de partida

Scan: `8d1fa696-6da0-4289-a959-400fe47fe848`, de 2026-10-21. O JSON exportado está em `scan-results/targeted-lab-2026-10-21.json` na raiz do workspace, fora deste repositório. Preservar esse ensaio sem agregar seus achados aos de outro scan.

| Ferramenta | Estado atual | Resultado observado |
|---|---|---|
| Nikto | 2.6.0, commit e banco fixados; selecionado para HTTP/HTTPS | O ensaio de 2026-10-22 com 250 s nativos expirou nas duas unidades. Chamadas diretas com perfil amplo e 600 s concluíram HTTP em 565 s (5.920 requisições, 13 sinais) e HTTPS em 582 s (5.920 requisições, 14 sinais), sem limite nativo. |
| testssl | Pacote Debian `3.0.8+dfsg-1`; executável `testssl` ou `testssl.sh`; selecionado para TLS | O código 1 do ensaio anterior não foi reproduzido. Chamada direta concluiu em 190 s com código 0 e JSON de 22,7 KB; o ensaio integrado de 2026-10-22 também concluiu com código 0 e persistiu 11 findings TLS. |

Gateway e agente estao fora da faixa de scan. O endpoint antigo do gateway foi excluido. A chamada direta de 600 s completou o perfil amplo nos dois transportes; o scan `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f` passou no verificador, com ambas as unidades Nikto terminando em codigo 0 e evidencias persistidas.

## Nikto: diagnóstico, correção e ganho

Chamada atual em `hardware-agent/src/agent/targeted/web.py`, função `run_nikto`:

```text
nikto -h <url> -nointeractive -nolookup -nocheck -nocookies
  -Tuning 2345789acf -timeout 5 -maxtime 700s -Pause 0.05
  -Format json -output <relatorio>
```

Limite externo: 800 s. `-nocheck` desativa consulta de atualização, não os testes HTTP.

**Causa confirmada:** o limite `-maxtime` por host terminava antes do perfil amplo concluir; o limite externo original de 220 s também podia matar o processo antes da finalização. O `-Pause` aplica uma espera literal por requisição, então passou de 0,2 s a 0,05 s. Perfil `2345789acf` mantido. As chamadas reais com `-maxtime 600s` terminaram após 5.920 requisições em 565 s HTTP e 582 s HTTPS; o código usa 700 s internos e 800 s externos para margem.

No scan integrado final, HTTP e HTTPS completaram sem timeout e persistiram sinais reconhecidos. Esses sinais permanecem inconclusivos pela politica atual.

**Ganho:** Nikto conclui verificações úteis e entrega resultados ao parser existente. Quando não concluir, o estado e o motivo permanecem claros.

## testssl: diagnóstico, correção e ganho

Chamada atual em `hardware-agent/src/agent/targeted/tls.py`, função `run_testssl`:

```text
testssl --warnings batch --color 0 --connect-timeout 5 --openssl-timeout 5
  --protocols --server-defaults --header --vulnerable
  --jsonfile-pretty <relatorio> <ip>:<porta>
```

Limite externo: 300 s. Os cinco segundos limitam conexões/operações específicas, não o conjunto inteiro. Algumas verificações de `--vulnerable` têm esperas próprias.

**Observado:** o código 1 do ensaio inicial não foi reproduzido com a mesma versão e chamada. A reprodução direta completou em 190 s, código 0, JSON de 22,7 KB; o ensaio integrado de 2026-10-22 completou em código 0 e persistiu 11 achados TLS. O aviso de engine/GOST aparece em `scanProblem` com severidade WARN e não explica, por si só, a falha anterior.

Plano:

1. O adaptador agora extrai linhas de erro/aviso/fatal/problema/falha/timeout do diagnóstico já capturado, stdout, stderr e `scanProblem` estruturado. Sanitiza e limita a 512 caracteres e exclui cabeçalhos HTTP.
2. A versão/caminho do OpenSSL e as dependências foram conferidos; não houve incompatibilidade demonstrada que justificasse troca de pacote ou provisionamento.
3. A chamada combinada real foi validada; o limite existente de 300 s foi suficiente para os ensaios concluídos.
4. Manter o código de saída e `scanProblem` visíveis. A causa exata do antigo código 1 permanece desconhecida porque não se reproduziu.

**Ganho:** conclusão funcional com evidência TLS útil e cobertura correta. Manter achados suportados de resultados parciais com suas lacunas. Não ignorar código 1, trocar globalmente `--warnings batch` por `off` ou suprimir avisos como substituto do diagnóstico. Avaliar `NO_ENGINE` somente se houver incompatibilidade demonstrada. Códigos de pontuação documentados entre 50–200 continuam distintos de erros operacionais.

O alvo já fornece TLS legado, RSA 1024, SHA-1 e certificado fictício autoassinado. Não é necessário enfraquecê-lo mais para investigar a falha.

## Limitações registradas, sem ampliação de escopo

| Constatação | Tratamento |
|---|---|
| O parser Nikto marca resultados aceitos como `inconclusive`, com `targeted:nikto-unsupported` | Preservar a política. Execução concluída não significa confirmação automática de vulnerabilidade. |
| A categoria `1` não é selecionada e resultados exclusivos dela não recebem severidade no parser | Registrar a limitação ao comparar perfis; não ampliar a política nesta correção. |
| O banco fixado tem testes para `/.env` (`007226`) e `/.git/HEAD` (`006609`), compatíveis com fixtures existentes | Usar como testemunhas para verificar execução e coleta, sem criar regras específicas do laboratório. |
| `/.git/config` requer `[core]` e `[branch]` no teste `006807`; o fixture só contém `[core]` | Completar o fixture na retomada do laboratório, depois da correção de execução. |
| Plugins, IDs e cabeçalhos podem ter limitações de classificação no parser atual | Registrar as lacunas encontradas; ampliação de classificação fica em trabalho separado. |

## Etapas e critérios

R1-R7 concluidas. O scan unico passou no verificador estrito e foi exportado em `../../scan-results/targeted-lab-2026-10-22.json`.

| Etapa | Trabalho | Arquivos prováveis | Critério |
|---|---|---|---|
| R1 — Diagnóstico | Reproduzir chamadas, identificar causas, medir duração e dependências; complementar diagnóstico | Adaptadores e testes | Concluído: limite Nikto insuficiente medido; testssl code 1 não reproduzido e diagnóstico ampliado. |
| R2 - Nikto | Preservar perfil amplo e limites medidos | `targeted/web.py`, `agent/config.py` | Concluido: HTTP/HTTPS integrados completaram com limites 700/800 s; evidencia persistida. |
| R3 — testssl | Manter chamada e JSON; explicar falhas com diagnósticos sanitizados | `targeted/tls.py` e testes | Concluído funcionalmente: chamada direta e integrada concluíram e resultados TLS foram persistidos. |
| R4 — Regressão focada | Preservar seleção, políticas e outras ferramentas | Testes web/TLS/selection | Concluído: 177 testes passaram e Ruff passou nos arquivos alterados. |
| R5 - Validacao funcional | Confirmar persistencia dos resultados suportados | Scan integrado e relatorio | Concluido: 5 hosts, 90 achados; verificador PASS e evidencias targeted persistidas. |
| R6 — Retomar laboratório | Completar fixtures e verificador do escopo | Fixtures, API subnet guard, CLI, runbook | Implementado: FTP anônimo validado, rede `/29` isolada, API aceita sub-rede contida no `/28` reportado; verificador não aceita o scan diagnóstico com timeout Nikto. |
| R7 - Apresentacao | Validar scan unico e exportar resultado | Runbook e JSON | Concluido: `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f`, PASS; JSON em `../../scan-results/targeted-lab-2026-10-22.json`. |

Parametros Nikto baseados em chamadas HTTP/HTTPS reais. Sem atualizacao de versao, ampliacao de parser/politica ou mudanca da selecao automatica. Validacao integrada concluida.

## Auditoria e resultado esperado

O fluxo específico de **Baixar relatório explicado**, o conteúdo do JSON do Raspberry e os limites atuais do contexto Groq estão em [SCAN-JSON-AND-AI.md](./SCAN-JSON-AND-AI.md). A revisão da IA fica para trabalho posterior; persistir achados não comprova que todos foram enviados ao provedor.

A correção deve restabelecer a coleta automática de evidência de segurança útil no relatório existente para apoiar possíveis correções. Executável iniciado, conexão aceita ou código zero isolado não bastam. Relatório parcial não é cobertura completa. Correlação de versão não prova exploração; a política inconclusiva atual do Nikto continua aplicável.

Avaliar cobertura pertinente, achados suportados, evidência por serviço/IP/porta, confiança e orientação de correção que o produto já fornece. Registrar limitações encontradas sem converter esta correção em reformulação das ferramentas ou do relatório. Depois de validar ambas as ferramentas, continuar o laboratório simulado.

## Fontes

Consultadas em 2026-10-22. Conferir opções contra a versão fixada antes de implementar.

- [Nikto — opções e categorias](https://github.com/sullo/nikto/wiki/Annotated-Option-List).
- [Nikto — plugins e relatórios](https://github.com/sullo/nikto/wiki/Selecting-Plugins).
- [Nikto — banco exato instalado](https://raw.githubusercontent.com/sullo/nikto/69681e2e4213c15b85a90c53b2169ecb2a88fb01/program/databases/db_tests).
- [Nikto — implementação fixada](https://raw.githubusercontent.com/sullo/nikto/69681e2e4213c15b85a90c53b2169ecb2a88fb01/program/plugins/nikto_core.plugin).
- [testssl 3.0.8 — parâmetros e códigos de saída](https://raw.githubusercontent.com/testssl/testssl.sh/v3.0.8/doc/testssl.1.md).
- [testssl 3.0.8 — implementação e aviso de engine](https://raw.githubusercontent.com/testssl/testssl.sh/v3.0.8/testssl.sh).
- Código local: `hardware-agent/src/agent/targeted/{selection,executor,web,tls}.py`, `hardware-agent/src/agent/config.py`, imagem do agente e fixtures web.
