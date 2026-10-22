import type { Catalog } from './catalog.types'

const SEVERITY: Record<string, string> = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Média',
  low: 'Baixa',
}

const SEVERITY_LOWER: Record<string, string> = {
  critical: 'crítica',
  high: 'alta',
  medium: 'média',
  low: 'baixa',
}

export const catalog: Catalog = {
  'nav.home': 'Início',
  'nav.scans': 'Varreduras',
  'nav.network': 'Rede',
  'nav.devices': 'Dispositivos',
  'nav.users': 'Usuários',
  'nav.settings': 'Configurações',
  'nav.logout': 'Sair',
  'nav.preferences': 'Preferências',
  'nav.theme': 'Tema',
  'nav.language': 'Idioma',
  'scans.title': 'Varreduras',
  'scans.caption': 'Histórico de varreduras',
  'scans.error': 'Não foi possível carregar as varreduras.',
  'scans.emptyHeading': 'Nenhuma varredura ainda',
  'scans.emptyBody':
    'Sua primeira varredura encontra os equipamentos da rede e o que precisa ser corrigido.',
  'scans.open': ({ id }) => 'Abrir varredura ' + id,
  'scans.pages': 'Páginas de varreduras',
  'scans.running': 'Esta varredura ainda está em andamento.',
  'scans.liveProgress':
    'O progresso é atualizado automaticamente enquanto a varredura acontece.',
  'scans.partialWarningTitle': 'Atenção: scan parcial',
  'scans.partialWarningToggle': 'Mostrar detalhes do scan parcial',
  'scans.partialResults': 'Algumas verificações não foram concluídas.',
  'scans.targetedChecks': 'Verificações direcionadas',
  'scans.targetedToolCoverage': 'Cobertura por ferramenta',
  'scans.targetedFindingsTitle': ({ count }) =>
    'Achados das ferramentas por serviço: ' + count,
  'scans.targetedFindingsToggle':
    'Alternar achados das ferramentas por serviço',
  'scans.exposureTableGuidance':
    'Expanda uma linha para ver as evidências e vulnerabilidades relacionadas ao serviço.',
  'scans.exposureTableCaption': 'Serviços alcançáveis neste scan',
  'scans.exposureTableHostCaption': 'Serviços alcançáveis neste equipamento',
  'scans.exposureEndpoint': 'Endereço e porta',
  'scans.exposureObservedService': 'Serviço identificado',
  'scans.exposureRole': 'Função do serviço',
  'scans.exposureAttention': 'Atenção',
  'scans.exposureWhyItMatters': 'Por que isso importa',
  'scans.exposureRelatedVulnerabilities': 'Vulnerabilidades relacionadas',
  'scans.exposureOpenVulnerability': 'Abrir vulnerabilidade',
  'scans.exposureRowDetails': ({ service, endpoint }) =>
    'Mostrar detalhes de ' + service + ' em ' + endpoint,
  'scans.exposureRoleAdministration': 'Administração',
  'scans.exposureRoleDataStore': 'Armazenamento de dados',
  'scans.exposureRoleFileSharing': 'Compartilhamento de arquivos',
  'scans.exposureRoleRemoteAccess': 'Acesso remoto',
  'scans.exposureRoleProxy': 'Proxy',
  'scans.exposureRoleApi': 'API',
  'scans.exposureRoleDeviceControl': 'Controle de dispositivos',
  'scans.exposureRoleDiscovery': 'Descoberta',
  'scans.exposureRoleMedia': 'Mídia',
  'scans.exposureRoleGeneralService': 'Serviço geral',
  'scans.exposureRoleUnknown': 'Desconhecida',
  'scans.exposureConfidenceLow': 'Baixa',
  'scans.exposureConfidenceMedium': 'Média',
  'scans.exposureConfidenceHigh': 'Alta',
  'scans.targetedFindingsDescription':
    'Achados de verificações específicas, agrupados por gravidade. A ferramenta que reportou cada item aparece abaixo do título.',
  'scans.targetedFindingsCaption': ({ severity }) =>
    'Achados de ferramentas direcionadas com gravidade ' +
    severity +
    ' neste scan',
  'scans.targetedSeverityGroupToggle': ({ severity }) =>
    'Alternar achados direcionados de gravidade ' +
    String(severity).toLowerCase(),
  'scans.targetedToolLabel': 'Ferramenta',
  'scans.noTargetedFindings':
    'Nenhum achado foi registrado pelas ferramentas direcionadas. Isso não confirma que todas as verificações planejadas foram executadas.',
  'scans.coveragePlanned': 'Planejadas',
  'scans.coverageCompletedLabel': 'Concluídas',
  'scans.coverageFailed': 'Falharam',
  'scans.coverageTimedOut': 'Expiraram',
  'scans.coverageSkipped': 'Ignoradas',
  'scans.coverageGaps': 'Motivo da cobertura incompleta',
  'scans.gapReasonToolUnavailable': 'ferramenta não instalada ou indisponível',
  'scans.gapReasonDependencyUnavailable': 'dependência necessária indisponível',
  'scans.gapReasonIncompatibleTool': 'ferramenta incompatível com o alvo',
  'scans.gapReasonWordlistUnavailable':
    'lista de palavras necessária indisponível',
  'scans.gapReasonPolicyUnavailable': 'política necessária indisponível',
  'scans.gapReasonPlanLimit': 'limite do plano de scan atingido',
  'scans.gapReasonStageBudget': 'tempo reservado para a etapa esgotado',
  'scans.gapReasonOutputLimit': 'limite de saída da ferramenta atingido',
  'scans.gapReasonIssueLimit': 'limite de problemas atingido',
  'scans.gapReasonValidationLimit': 'limite de validações atingido',
  'scans.gapReasonBaselineUnavailable': 'dados de referência indisponíveis',
  'scans.gapReasonMalformedReport': 'ferramenta retornou um relatório inválido',
  'scans.gapReasonWrongTarget':
    'resultado da ferramenta não corresponde ao alvo',
  'scans.gapReasonSpawnError': 'não foi possível iniciar a ferramenta',
  'scans.gapReasonExecutionError': 'falha durante a execução da ferramenta',
  'scans.gapReasonUnitTimeout': 'verificação excedeu o tempo limite',
  'network.title': 'Rede',
  'network.caption': 'Equipamentos da sua rede',
  'network.error': 'Não foi possível carregar sua rede.',
  'network.emptyHeading': 'Nenhum equipamento ainda',
  'network.emptyBody':
    'Sua primeira varredura encontra os equipamentos da rede e o que precisa ser corrigido.',
  'network.emptyActive': 'Nenhum equipamento visto nos últimos 7 dias.',
  'network.quiet': ({ count }) => 'Não vistos recentemente (' + count + ')',
  'network.open': ({ host }) => 'Abrir ' + host,
  'network.pages': 'Páginas de equipamentos',
  'home.noScans': 'Nenhuma varredura ainda',
  'home.firstScanBody':
    'Sua primeira varredura encontra os equipamentos da rede e o que precisa ser corrigido.',
  'home.error': 'Não foi possível carregar o que precisa de atenção.',
  'home.retry': 'Tentar novamente',
  'home.nothingNeedsAttention': 'Nada precisa de sua atenção',
  'home.oneNeedsAttention': '1 item precisa de sua atenção',
  'home.manyNeedAttention': ({ count }) =>
    count + ' itens precisam de sua atenção',
  'home.lastScan': 'Última varredura concluída',
  'home.vulnerability': 'Vulnerabilidade',
  'home.machine': 'Equipamento',
  'home.severity': 'Gravidade',
  'home.attentionCaption': 'Vulnerabilidades que precisam de atenção',
  'home.attentionPages': 'Páginas de atenção',
  'home.events': 'Eventos',
  'home.eventsEmpty': 'Nada para informar no momento.',
  'home.eventsPages': 'Páginas de eventos',
  'home.activity': 'Atividade',
  'home.activityEmpty': 'Nenhuma atividade registrada ainda.',
  'home.activityPages': 'Páginas de atividade',
  'home.latestScanOverview': 'Resumo da última varredura',
  'home.noOverviewYet':
    'Ainda não há uma explicação em linguagem simples para esta varredura.',
  'home.viewAndExplainScan': 'Ver e explicar esta varredura',
  'home.preparingOverview':
    'A explicação está sendo preparada. Você pode acompanhar o progresso na página da varredura.',
  'home.openResults': 'Abrir resultados',
  'home.viewMoreDetails': 'Ver mais detalhes',
  'common.none': 'Nenhuma',
  'common.when': 'Quando',
  'common.box': 'Agente',
  'common.mode': 'Modo',
  'common.status': 'Status',
  'common.duration': 'Duração',
  'common.machines': 'Equipamentos',
  'common.vulnerabilities': 'Vulnerabilidades',
  'common.highestSeverity': 'Maior gravidade',
  'common.network': 'Rede',
  'common.attackSurface': 'Superfície de ataque',
  'common.unavailable': 'Indisponível',
  'common.attackSurfaceUnavailable':
    'Indisponível — este scan é anterior à análise de superfície de ataque.',
  'common.rerunForData': 'Execute o scan novamente para gerar esses dados.',
  'common.reachableServices': ({ count }) =>
    count + (count === 1 ? ' serviço alcançável' : ' serviços alcançáveis'),
  'common.needsReview': ({ count }) =>
    count + (count === 1 ? ' precisa de revisão' : ' precisam de revisão'),
  'common.noReachableServices':
    'Nenhum serviço alcançável foi encontrado neste scan.',
  'common.noVulnerabilitiesAcceptedEvidence':
    'Nenhuma vulnerabilidade confirmada nas evidências aceitas.',
  'common.noVulnerabilitiesInScan':
    'Nenhuma vulnerabilidade confirmada foi encontrada neste scan.',
  'common.address': 'Endereço',
  'common.type': 'Tipo',
  'common.lastSeen': 'Visto por último',
  'common.noName': 'Sem nome',
  'common.notSeenFor': ({ count, unit }) =>
    'Não visto há ' + count + ' ' + unit,
  'common.week': 'semana',
  'common.weeks': 'semanas',
  'common.machinesSeen': 'Equipamentos encontrados',
  'common.industrialServices': 'Servi\u00e7os industriais',
  'common.servicesRunning': 'Portas observadas neste equipamento',
  'common.scanHistory': 'Hist\u00f3rico de varreduras',
  'common.machine': 'Equipamento',
  'common.vulnerability': 'Vulnerabilidade',
  'common.port': 'Porta',
  'common.cve': 'CVE',
  'common.vendor': 'Fabricante',
  'common.services': 'Servi\u00e7os',
  'common.mac': 'MAC',
  'common.evidence': 'Evid\u00eancias',
  'common.mappingSource': 'Fonte do mapeamento',
  'common.unit': ({ id }) => 'Unidade ' + id,
  'common.addressSpace': 'Espa\u00e7o de endere\u00e7os',
  'common.range': 'Faixa',
  'common.result': 'Resultado',
  'common.noServices': 'Nenhuma porta foi registrada neste equipamento.',
  'common.noIndustrialServices':
    'Nenhum servi\u00e7o industrial foi detectado neste equipamento.',
  'common.noAddressRanges': 'Nenhuma faixa de endere\u00e7os foi mapeada.',
  'common.back': 'Voltar',
  'common.previousPage': 'Página anterior',
  'common.nextPage': 'Próxima página',
  'common.pageNumber': ({ page }) => 'Página ' + page,
  'common.severity': ({ severity }) => SEVERITY[severity],
  'common.severityLabel': 'Gravidade',
  'common.showFindingDetails': ({ title }) => 'Mostrar detalhes de ' + title,
  'common.riskScore': 'Pontuação de risco',
  'common.riskScoreNotCalculated': 'Não calculada',
  'common.riskScoreValue': ({ score }) => score + ' de 100',
  'common.confidence': 'Confiança',
  'evidence.confidenceLabel': 'Confiança da evidência',
  'evidence.methodLabel': 'Método de detecção',
  'evidence.statusLabel': 'Estado da evidência',
  'evidence.method.version_correlation': 'Associação de versão',
  'evidence.method.configuration_observation': 'Configuração observada',
  'evidence.method.specific_check': 'Verificação específica',
  'evidence.method.textual_reference': 'Apenas referência textual',
  'evidence.method.unknown': 'Desconhecido',
  'evidence.status.supported': 'Sustentada para o método registrado',
  'evidence.status.supportedVersionCorrelation':
    'Sustentada para a associação de versão',
  'evidence.status.inconclusive': 'Inconclusivo',
  'evidence.status.conflicting': 'Evidências conflitantes',
  'evidence.status.unknown': 'Desconhecido',
  'evidence.confidence.tentative': 'Preliminar',
  'evidence.confidence.probable': 'Provável',
  'evidence.confidence.confirmed': 'Confirmada',
  'evidence.confidence.unknown': 'Não informada',
  'evidence.confidence.notReported': 'Não informada',
  'evidence.explanation.correlation':
    'Uma versão está associada a uma vulnerabilidade conhecida. A presença dela neste equipamento ainda precisa ser validada.',
  'evidence.explanation.configuration':
    'Esta configuração foi observada. Isso não demonstra a exploração de uma vulnerabilidade conhecida.',
  'evidence.explanation.specificCheck':
    'A verificação encontrou a condição indicada no endpoint registrado. Isso não descreve o equipamento inteiro.',
  'evidence.explanation.textReference':
    'Uma referência a vulnerabilidade apareceu no texto, mas nenhum resultado positivo verificável foi registrado.',
  'evidence.explanation.inconclusive':
    'A verificação não chegou a um resultado conclusivo. Isso não confirma nem descarta a vulnerabilidade.',
  'evidence.explanation.conflicting':
    'As verificações registradas divergem. Revise cada origem e resultado; isso não confirma nem descarta a vulnerabilidade.',
  'evidence.explanation.legacy':
    'Este registro é anterior ao detalhamento da evidência. Os dados disponíveis não mostram como o alerta foi produzido nem validam a vulnerabilidade.',
  'evidence.explanation.unknown':
    'As evidências disponíveis não identificam como o alerta foi produzido nem validam a vulnerabilidade.',
  'evidence.summaryTitle': 'Resumo da evidência',
  'evidence.records': 'Registros de vulnerabilidade',
  'evidence.demonstrated': 'Condições demonstradas',
  'evidence.conflictingRecords': 'Registros conflitantes',
  'evidence.scope': 'Escopo',
  'evidence.scope.scan': 'Scan',
  'evidence.scope.filtered_findings': 'Vulnerabilidades filtradas',
  'evidence.countNote':
    'As contagens são registros de vulnerabilidade, não falhas comprovadas.',
  'evidence.observationsTitle': 'Verificações sem registro de vulnerabilidade',
  'evidence.recordedTitle': 'Evidência registrada',
  'evidence.condition': 'Condição verificada',
  'evidence.endpoint': 'Endpoint',
  'evidence.modbusUnit': 'ID da unidade Modbus',
  'evidence.provenance': 'Origem e regra',
  'evidence.result.positive': 'Resultado positivo',
  'evidence.result.negative':
    'Esta verificação não encontrou a condição indicada',
  'evidence.result.inconclusive': 'Resultado inconclusivo',
  'evidence.truncated':
    'Alguns registros de evidência foram omitidos porque o limite de exibição foi atingido.',
  'common.exploitabilityIndex': 'Índice de explorabilidade',
  'common.whatItIs': 'O que é',
  'common.whatToDo': 'O que fazer',
  'common.references': 'Referências',
  'common.seenOn': 'Observado em',
  'common.cvss': 'CVSS',
  'common.vulnerabilitiesInScanTitle': ({ count }) =>
    'Vulnerabilidades: ' + count,
  'common.vulnerabilitiesInScanToggle': 'Alternar vulnerabilidades do scan',
  'common.severityGroupTitle': ({ severity, count }) =>
    SEVERITY[severity] +
    ': ' +
    count +
    (count === 1 ? ' vulnerabilidade' : ' vulnerabilidades'),
  'common.severityGroupToggle': ({ severity }) =>
    'Alternar vulnerabilidades de gravidade ' + SEVERITY_LOWER[severity],
  'common.severityGroupCaption': ({ severity }) =>
    'Vulnerabilidades de gravidade ' + SEVERITY_LOWER[severity] + ' neste scan',
  'common.findingsLoadError':
    'N\u00e3o foi poss\u00edvel carregar as vulnerabilidades deste equipamento.',
  'common.noVulnerabilities': 'Nenhuma vulnerabilidade neste equipamento.',
  'common.vulnerabilitiesOnMachine': 'Vulnerabilidades neste equipamento',
  'common.machineNotFound': 'Esse equipamento n\u00e3o existe.',
  'common.machineLoadError':
    'N\u00e3o foi poss\u00edvel carregar este equipamento.',
  'common.lastSeenInline': 'visto por \u00faltimo',
  'common.notSeenForInline': ({ count, unit }) =>
    'n\u00e3o visto por ' + count + ' ' + unit,
  'common.firstSeen': 'Visto pela primeira vez',
  'common.openPorts': ({ count }) =>
    `${count} porta${count === 1 ? '' : 's'} aberta${count === 1 ? '' : 's'}`,
  'common.noOpenPorts': 'nenhuma porta aberta',
  'common.service': 'Servi\u00e7o',
  'common.protocol': 'Protocolo',
  'common.version': 'Vers\u00e3o',
  'common.scanHistoryCaption': 'Varreduras em que este equipamento apareceu',
  'common.openScan': ({ id }) => 'Abrir varredura ' + id,
  'ai.explainMachine': 'Explicar com IA',
  'ai.explainMachineLoading': 'Analisando...',
  'ai.explainFinding': 'Explicar com IA',
  'ai.explainFindingLoading': 'Explicando...',
  'ai.findingExplanation': 'Explica\u00e7\u00e3o da IA',
  'ai.defaultFindingQuestion':
    'Explique esta vulnerabilidade em linguagem simples e diga o que devo fazer.',
  'ai.defaultMachineQuestion':
    'Explique o estado de seguran\u00e7a deste equipamento e o que devo priorizar.',
  'ai.contextHint':
    'A resposta usa somente as evidências disponíveis neste contexto.',
  'ai.showHistory': 'Mostrar histórico',
  'ai.hideHistory': 'Ocultar histórico',
  'ai.question': 'Sua pergunta',
  'ai.asking': 'Analisando...',
  'ai.ask': 'Perguntar',
  'ai.loadingHistory': 'Carregando histórico...',
  'ai.answer': 'Resposta',
  'ai.limitations': 'Limitações',
  'ai.openAssistant': 'Abrir assistente de segurança',
  'ai.assistant': 'Assistente IA',
  'ai.askDmitri': 'Pergunte ao Dmitri',
  'ai.chooseScan':
    'Selecione uma varredura para fazer perguntas sobre os dados de segurança.',
  'ai.viewScans': 'Ver varreduras',
  'ai.askContext': 'Pergunte sobre este contexto',
  'ai.placeholder': 'O que devo corrigir primeiro?',
  'ai.thisScan': 'esta varredura',
  'ai.thisHost': 'este equipamento',
  'ai.askAbout': ({ label }) => 'Pergunte sobre ' + label,
  'ai.askAboutScan': 'Pergunte sobre esta varredura',
  'ai.viewFinding': ({ index }) => 'Ver achado ' + index,
  'ai.genericError':
    'Não foi possível obter uma resposta agora. Tente novamente.',
  'ai.overview': 'Resumo da IA',
  'ai.overviewDescription':
    'Obtenha um resumo desta varredura em linguagem simples.',
  'ai.reloadOverview': 'Recarregar resumo',
  'ai.explainScan': 'Explicar esta varredura',
  'ai.failedOverview':
    'Não foi possível preparar o resumo. Os resultados da varredura continuam disponíveis.',
  'ai.loadFailed': 'Não foi possível carregar o resumo.',
  'ai.notRequestedOverview':
    'Obtenha um resumo desta varredura em linguagem simples.',
  'ai.unavailableOverview':
    'O resumo por IA está desativado para esta varredura. Os resultados continuam disponíveis.',
  'ai.preparingOverview':
    'Preparando um resumo desta varredura em linguagem simples.',
  'ai.completedDescription':
    'Interpretação em linguagem simples das evidências registradas nesta varredura.',
  'ai.whatToDoFirst': 'O que fazer primeiro',
  'ai.whyVulnerabilities': 'Por que estas vulnerabilidades importam',
  'ai.recordedVulnerability': 'Vulnerabilidade registrada',
  'ai.recommendedAction': 'Ação recomendada:',
  'ai.showDetails': 'Mostrar detalhes da avaliação e limitações',
  'ai.showOverview': 'Mostrar resumo da IA',
  'ai.cannotConfirm': 'O que esta varredura não pode confirmar',
  'ai.priorityImmediate': 'Imediata',
  'ai.priorityHigh': 'Alta prioridade',
  'ai.priorityMedium': 'Prioridade média',
  'ai.priorityLow': 'Baixa prioridade',
  'reports.title': 'Relatórios da varredura',
  'reports.description': 'Escolha qual relatório deseja baixar.',
  'reports.preparing': 'Preparando relatório...',
  'reports.downloadExplained': 'Baixar relatório explicado',
  'reports.downloadTechnical': 'Baixar relatório técnico',
  'reports.error': 'Não foi possível preparar o relatório. Tente novamente.',
  'reports.previewExplained': 'Prévia do relatório explicado',
  'reports.previewTechnical': 'Prévia do relatório técnico',
  'reports.previewTitle': 'Prévia do relatório PDF',
  'common.cancel': 'Cancelar',
  'common.confirmDownload': 'Confirmar download',
  'settings.account': 'Sua conta',
  'settings.email': 'E-mail',
  'settings.role': 'Função',
  'settings.admin': 'Administrador',
  'settings.viewer': 'Visualizador',
  'settings.changePassword': 'Alterar senha', // pragma: allowlist secret
  'settings.recordedAbout': 'O que é registrado sobre mim?',
  'settings.activityDescription':
    'Todos na sua organização podem ver quando você entrou pela última vez e um registro das alterações na organização: varreduras, equipamentos que entram na rede, convites, mudanças de função e entradas ou saídas de membros. Não registramos o que você visualizou.',
  'settings.leaveOrganisation': 'Sair desta organização',
  'settings.leaveDescription':
    'Sua conta será excluída e você perderá imediatamente o acesso às varreduras, à rede e às vulnerabilidades desta organização. Isso não pode ser desfeito — um administrador terá que convidar você novamente.',
  'settings.deleteAccount': 'Excluir minha conta',
  'settings.deleteAccountQuestion': 'Excluir sua conta?',
  'settings.deleteAccountBody':
    'Sua conta será excluída e você perderá o acesso imediatamente. Isso não pode ser desfeito.',
  'settings.passwordChanged': 'Senha alterada.', // pragma: allowlist secret
  'deletion.deleteScan': 'Excluir varredura',
  'deletion.deleteScanHeading': 'Excluir esta varredura',
  'deletion.deleteScanQuestion': 'Excluir esta varredura?',
  'deletion.deleteScanBody':
    'Os resultados, vulnerabilidades, análise de IA e conversa são excluídos. Isso não pode ser desfeito.',
  'deletion.deleteScanError':
    'Não foi possível excluir esta varredura. Tente novamente.',
  'deletion.scanRunningError': 'Pare a varredura antes de excluí-la.',
  'deletion.scanDeleted': 'Varredura excluída.',
  'deletion.deleteMachine': 'Excluir máquina',
  'deletion.deleteMachineHeading': 'Excluir esta máquina',
  'deletion.deleteMachineQuestion': ({ name }) => 'Excluir ' + name + '?',
  'deletion.deleteMachineBody':
    'A máquina e suas vulnerabilidades são excluídas. As varreduras antigas continuam, mas não a listam mais. Se uma varredura futura a encontrar, ela volta como uma nova máquina. Isso não pode ser desfeito.',
  'deletion.deleteMachineError':
    'Não foi possível excluir esta máquina. Tente novamente.',
  'deletion.machineDeleted': ({ name }) => name + ' foi excluída.',
  'deletion.deleting': 'Excluindo…',
  'deletion.deleteData': 'Excluir dados',
  'deletion.deleteAllScans': 'Excluir todas as varreduras',
  'deletion.deleteAllScansQuestion': 'Excluir todas as varreduras?',
  'deletion.deleteAllScansBody':
    'Todas as varreduras concluídas e seus dados são excluídos. Varreduras em andamento são ignoradas. Máquinas vistas só nessas varreduras também são excluídas. Isso não pode ser desfeito.',
  'deletion.deleteAllScansError':
    'Não foi possível excluir as varreduras. Tente novamente.',
  'deletion.scansDeleted': ({ count }) =>
    'Varreduras excluídas: ' + count + '.',
  'deletion.scansSkipped': ({ count }) =>
    'Varreduras em andamento ignoradas: ' + count + '.',
  'deletion.deleteAllMachines': 'Excluir todas as máquinas',
  'deletion.deleteAllMachinesQuestion': 'Excluir todas as máquinas?',
  'deletion.deleteAllMachinesBody':
    'Todas as máquinas e suas vulnerabilidades são excluídas. As varreduras continuam. A próxima varredura monta a lista de novo. Isso não pode ser desfeito.',
  'deletion.deleteAllMachinesError':
    'Não foi possível excluir as máquinas. Tente novamente.',
  'deletion.machinesDeleted': ({ count }) =>
    'Máquinas excluídas: ' + count + '.',
  'devices.subtitle': 'As caixas Dmitri que reportam para esta organização.',
  'devices.caption': 'Caixas Dmitri',
  'devices.error': 'Não foi possível carregar seus dispositivos.',
  'devices.emptyHeading': 'Nenhuma caixa conectada ainda',
  'devices.emptyBody':
    'O instalador conecta a caixa no local; ela aparecerá aqui quando ficar online.',
  'devices.emptyNote':
    'Fale com quem instalou o Dmitri se esperava ver uma caixa aqui.',
  'devices.open': ({ name }) => 'Abrir ' + name,
  'users.invite': 'Convidar usuário',
  'settings.aiUsage': 'Uso da IA',
  'settings.aiUsageDescription':
    'Uso do provedor em toda a organização. Prompts e respostas do modelo não são armazenados aqui.',
  'settings.loadingUsage': 'Carregando uso…',
  'settings.usageError': 'Não foi possível carregar os dados de uso.',
  'settings.tryAgain': 'Tentar novamente',
  'settings.summary': 'Resumo',
  'settings.requests': 'Solicitações',
  'settings.inputTokens': 'Tokens de entrada',
  'settings.outputTokens': 'Tokens de saída',
  'settings.totalTokens': 'Tokens totais',
  'settings.errors': 'Erros',
  'settings.recentRequests': 'Solicitações recentes ao provedor de IA',
  'settings.operation': 'Operação',
  'settings.model': 'Modelo',
  'settings.status': 'Status',
  'settings.tokens': 'Tokens',
  'settings.latency': 'Latência',
  'settings.noRequests': 'Nenhuma solicitação de IA registrada ainda.',
  'settings.usagePages': 'Páginas de uso de IA',
  'scans.failedEvidence':
    'Observações registradas antes da falha da varredura:',
  'scans.checkCoverage': 'Cobertura das verificações',
  'scans.coverageUnavailable':
    'A cobertura das verificações não foi registrada para esta varredura.',
  'scans.coverageCompleted': ({ completed, total }) =>
    `${completed} de ${total} verificações concluídas`,
  'scans.coverageUnlistedOmissions': ({ count }) =>
    `${count} verificações omitidas adicionais não estão listadas individualmente.`,
  'scans.coverageObservationEvidence': 'Evidência:',
  'scans.coveragePorts': 'Verificação de portas',
  'scans.coverageDeepInspection': 'Inspeção detalhada',
  'scans.coverageOtInspection': 'Inspeção OT',
  'scans.coverageTargetedAssessment': 'Avaliação direcionada',
  'scans.coverageOutcomeCompleted': 'concluída',
  'scans.coverageOutcomePartial': 'parcial',
  'scans.coverageOutcomeFailed': 'falhou',
  'scans.coverageOutcomeTimedOut': 'tempo esgotado',
  'scans.coverageOutcomeSkipped': 'não executada',
  'scans.openPorts': 'Portas abertas',
  'scans.filteredPorts': 'Portas filtradas',
  'scans.stage.discovery': 'Procurando dispositivos',
  'scans.stage.ports': 'Verificando portas',
  'scans.stage.deep_inspection': 'Inspecionando dispositivos',
  'scans.stage.ot_inspection': 'Inspecionando serviços industriais',
  'scans.stage.targeted_assessment': 'Executando verificações direcionadas',
  'scans.stage.normalization': 'Preparando resultados',
  'scans.stage.uploading': 'Enviando resultados',
  'scans.currentPort': 'Observada na última varredura',
  'scans.historicalPort': 'Observação anterior',
  'scans.unknownPort': 'Não verificada na última varredura',
  'home.detected': 'Observado',
  'ai.evidenceLimit':
    'Correspondências de CVE e registros da NVD não confirmam que uma vulnerabilidade afeta os equipamentos verificados. Confirme o software e a versão afetados.',
  'ai.partialLimit': 'Algumas verificações desta varredura não terminaram.',
  'ai.unknownLimit':
    'Esta varredura não informa se todas as verificações terminaram.',
  'updates.title': 'Atualização do agente',
  'updates.status': 'Status',
  'updates.updateTo': ({ version }) => `Atualizar para ${version}`,
  'updates.whatsNew': ({ version }) => `Novidades da versão ${version}`,
  'updates.technicalDetails': 'Detalhes técnicos',
  'updates.installedVersion': 'Versão instalada',
  'updates.installedPackageVersion': 'Versão instalada do pacote',
  'updates.availableVersion': 'Versão disponível',
  'updates.availablePackageVersion': 'Versão disponível do pacote',
  'updates.versionObservedAt': 'Versão observada em',
  'updates.packageVersion': 'Versão observada do pacote',
  'updates.observedVersion': 'Versão observada',
  'updates.catalogueCheckedAt': 'Catálogo verificado em',
  'updates.unknownValue': 'Desconhecida',
  'updates.availability.available': 'Atualização disponível',
  'updates.availability.upToDate': 'Atualizado',
  'updates.availability.unknown': 'Versão instalada desconhecida',
  'updates.availability.unavailable': 'Catálogo indisponível',
  'updates.readiness.ready': 'Pronto para atualizar',
  'updates.readiness.offline': 'Offline',
  'updates.readiness.revoked': 'Revogado',
  'updates.readiness.bootstrap':
    'É necessária preparação assistida antes de atualizações remotas',
  'updates.readiness.busy': 'Dispositivo ocupado',
  'updates.readiness.unknown': 'Preparação desconhecida',
  'updates.updateDevice': 'Atualizar dispositivo',
  'updates.refreshStatus': 'Atualizar status',
  'updates.refreshing': 'Atualizando…',
  'updates.readFailed':
    'Não foi possível carregar a disponibilidade. Atualize o status para tentar novamente.',
  'updates.operationReadFailed':
    'NÃ£o foi possÃ­vel atualizar o status remoto desta operaÃ§Ã£o.',
  'updates.historyFailed':
    'Não foi possível carregar o histórico de atualizações.',
  'updates.refreshFailed':
    'Não foi possível atualizar o status. Tente novamente.',
  'updates.requestFailed':
    'Não foi possível concluir a solicitação. O status salvo da operação não foi alterado.',
  'updates.revokedReadOnly':
    'Este dispositivo revogado é somente leitura e não pode ser atualizado.',
  'updates.offlineNotQueued':
    'Este dispositivo está offline. A atualização não será enfileirada.',
  'updates.history': 'Histórico de atualizações',
  'updates.noHistory': 'Ainda não há histórico de atualizações.',
  'updates.localOutcome': 'Resultado local',
  'updates.outcome.pending': 'Pendente',
  'updates.outcome.succeeded': 'Instalado e saudável localmente',
  'updates.outcome.failed': 'Falhou',
  'updates.outcome.rolled_back': 'Versão anterior restaurada',
  'updates.outcome.needs_intervention': 'É necessária intervenção assistida',
  'updates.phase.requested': 'Solicitação aceita',
  'updates.phase.preparing': 'Preparando',
  'updates.phase.installing': 'Instalando',
  'updates.phase.verifying': 'Verificando',
  'updates.phase.awaitingConfirmation': 'Aguardando confirmação',
  'updates.phase.recovering': 'Recuperando',
  'updates.phase.succeeded': 'Confirmada',
  'updates.phase.failed': 'Falhou',
  'updates.phase.expired': 'Expirada',
  'updates.phase.rolledBack': 'Versão anterior restaurada',
  'updates.phase.intervention': 'É necessária intervenção assistida',
  'updates.awaitingRemoteConfirmation':
    'A instalação local foi concluída. Aguardando confirmação remota.',
  'updates.interventionNextStep':
    'Entre em contato com a pessoa responsável pela manutenção do dispositivo.',
  'updates.requestedBy': 'Solicitada por',
  'updates.requestedAt': ({ date }) => `Solicitada em: ${date}`,
  'updates.localCompletedAt': ({ date }) => `Conclusão local: ${date}`,
  'updates.confirmedAt': ({ date }) => `Confirmação remota: ${date}`,
  'updates.lastContactAt': ({ date }) =>
    `Último contato do dispositivo: ${date}`,
  'updates.contactUnknown': 'O contato do dispositivo não foi informado.',
  'updates.confirmTitle': 'Atualizar este dispositivo?',
  'updates.confirmDescription': ({ device, version }) =>
    `Atualizar “${device}” para a versão ${version}?`,
  'updates.confirmAccessible': ({ version }) =>
    `Confirmar atualização para a versão ${version}`,
  'updates.back': 'Voltar',
  'updates.submitting': 'Solicitando atualização…',
  'updates.loading': 'Carregando…',
  'updates.error.deviceBusy':
    'O dispositivo está ocupado. Atualize o status antes de tentar novamente.',
  'updates.error.sessionReplaced':
    'A conexão do dispositivo mudou. Atualize o status para reconciliar a operação.',
  'updates.error.requestExpired':
    'A solicitação expirou antes de ser aceita pelo dispositivo.',
  'updates.error.releaseNotAllowed':
    'Esta publicação não está mais disponível para o dispositivo.',
  'updates.error.versionConflict':
    'A versão instalada mudou. Atualize o status antes de solicitar uma atualização.',
  'updates.error.metadataUntrusted':
    'Não foi possível verificar os metadados da publicação.',
  'updates.error.metadataExpired':
    'Os metadados da publicação expiraram antes da instalação.',
  'updates.error.artifactMismatch':
    'O pacote não corresponde à publicação verificada.',
  'updates.error.unsupportedPlatform':
    'A plataforma deste dispositivo não é compatível com a publicação.',
  'updates.error.prerequisiteMissing':
    'É necessária preparação assistida antes de atualizar este dispositivo remotamente.',
  'updates.error.insufficientResources':
    'O dispositivo não tinha recursos suficientes para continuar.',
  'updates.error.packageManagerBusy':
    'O gerenciador de pacotes está ocupado. Atualize o status antes de tentar novamente.',
  'updates.error.authorizationExpired':
    'A autorização expirou antes da instalação.',
  'updates.error.installFailed':
    'A instalação falhou. Consulte o status observado da operação.',
  'updates.error.localHealthFailed':
    'A verificação local de saúde falhou após a instalação.',
  'updates.error.recoveryFailed':
    'Não foi possível confirmar a recuperação. É necessária intervenção assistida.',
  'updates.error.stateCorrupt':
    'Não foi possível ler o estado da atualização com segurança. É necessária intervenção assistida.',
}
