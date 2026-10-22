# JSON do Raspberry e opção Baixar relatório explicado

Data: 2026-10-22. Estado: levantamento do código atual; mudanças de integração com Groq adiadas pelo usuário.

## Caminho específico do download no frontend

1. Em `frontend/src/pages/scans/ScanReports.tsx`, a opção **Baixar relatório explicado** chama `openPreview('explained')`, que solicita `downloadScanReport()`.
2. `frontend/src/api/scans.ts` acessa `GET /api/v1/scans/{scan_id}/reports/explained/download`, no idioma selecionado.
3. `backend/src/api/routers/scans.py`, em `download_scan_report()`, chama `read_scan_report()` e renderiza o PDF.
4. `backend/src/api/services/reports.py`, em `build_scan_report()`, lê o detalhe persistido do scan e o resumo de risco. Consulta também a análise de IA existente no idioma solicitado.
5. Se essa análise estiver concluída, o PDF incorpora seu resumo, ações e explicações disponíveis. Sem análise concluída, o backend usa conteúdo educativo determinístico. O download não dispara por si só uma análise completa no Groq.
6. O frontend mostra uma prévia; a confirmação baixa o PDF já recebido.

O PDF contém registros de todos os achados pelo caminho educativo do backend. Isso não significa que todos tenham sido enviados ao Groq ou recebido uma explicação individual gerada por IA. O PDF é montado pelo backend; não é um arquivo PDF retornado diretamente pelo provedor.

## JSON do Raspberry e contexto do Groq hoje

| Etapa | O que o código faz |
|---|---|
| Agente no Raspberry | Normaliza achados reconhecidos pelos parsers/políticas, com IP/porta, origem, ferramenta/script, descrição, recomendação, evidência, referências e observações estruturadas. Envia também cobertura. Não transforma toda saída bruta em finding. |
| Contrato do agente | `FindingPayload` e observações têm limites de tamanho/quantidade; há `evidence_truncated`. O payload do scan contém `coverage`. |
| Backend | Persiste os registros e fornece o detalhe do scan. O detalhe completo e o contexto de IA são objetos distintos. |
| Seleção para IA | `AI_MAX_FINDINGS` tem padrão 10 e intervalo 1–15. O worker repassa esse limite a `build_scan_ai_context()`, que seleciona `risk.top_findings`. |
| Contexto por achado | `AIFindingContext` inclui referências `finding_N`/`machine_N`, CVE, severidade, confiança, método/base/estado da evidência, truncamento e métricas de risco. Não inclui descrição, recomendação, evidência textual, observações estruturadas, ferramenta, IP ou porta como campos desse objeto. Os mapas privados para identidade/exibição não equivalem ao JSON completo enviado pelo Raspberry. |
| Agregados | O contexto contém contagens do scan, resumo de evidências, completude e quantidade de verificações incompletas; esses agregados não substituem os achados individuais omitidos. |
| Blocos Groq | `run_bounded_analysis()` divide o conjunto previamente selecionado em blocos de cinco por padrão e sintetiza respostas validadas. Não percorre automaticamente todos os achados persistidos. Suas contagens de cobertura referem-se ao conjunto selecionado. |
| Download explicado | Usa os registros completos para o conteúdo educativo e acrescenta a análise de IA já disponível. Não envia automaticamente o scan completo ao Groq ao clicar em baixar. |

Código conferido: `hardware-agent/src/agent/normalize/{contracts,findings}.py`, `hardware-agent/src/agent/scanner/stages.py`, `backend/src/api/core/config.py`, `backend/src/api/services/worker.py`, `backend/src/api/services/ai/{context,jobs,analyzer,groq}.py`, `backend/src/api/services/{reports,report_education,report_education_pdf}.py` e as rotas/frontend acima.

## Efeito das correções Nikto/testssl

As correções estão no hardware-agent e terão efeito no Raspberry quando essa versão for instalada: Nikto usa pausa de 0,05 s, teto nativo de 700 s e timeout externo de 800 s; testssl ganhou diagnósticos sanitizados e limitados em falhas. Achados aceitos entram no JSON do scan, sujeitos aos limites do contrato. A evidência Nikto continua inconclusiva pela política atual; correlação Vulners por versão/CPE não confirma exploração ou aplicabilidade.

O ensaio anterior validou cinco alvos com agente em contêiner e persistiu 90 achados. Não validou execução física no Raspberry, o novo alvo MySQL ou a análise de todos esses achados pelo Groq.

## Trabalho posterior: explicação completa na opção de download

O usuário decidiu revisar Groq depois. Este registro não altera código, limites, prompts, schemas ou comportamento do download.

Na revisão futura:

1. Rastrear os achados do JSON do Raspberry até o backend, o contexto serializado para Groq, a análise armazenada e o PDF obtido pela opção **Baixar relatório explicado**.
2. Definir como disponibilizar todos os achados e evidências aceitos à IA, incluindo endpoint, ferramenta, descrição, recomendação e limitações, considerando limites de tokens/requisições e tratamento de dados.
3. Rever seleção, schemas, blocos e síntese em conjunto. Aumentar somente `AI_MAX_FINDINGS` não acrescenta os campos de evidência ausentes.
4. Registrar analisados, omitidos e falhos em relação ao total persistido; não equiparar processamento dos blocos selecionados à análise integral.
5. Definir explicitamente a preparação/espera da análise no fluxo do relatório. Hoje o download lê a análise disponível e pode produzir PDF sem IA concluída.
6. Validar a opção real do frontend com os achados de cada alvo, preservando evidências inconclusivas, correlações e truncamentos. Não afirmar que 90 achados persistidos significam 90 achados enviados ao Groq.

## Relação com o laboratório planejado

O novo desenho terá somente seis alvos em Docker numa VM Linux em bridge/macvlan, escaneados pelo Raspberry físico: Web/HTTPS, SSH, FTP, SMB, Telnet e MySQL 5.7.30 com CVEs conhecidas. Esse desenho permanece planejado. A revisão da IA é uma etapa posterior e independente da produção dos achados pelo agente.
