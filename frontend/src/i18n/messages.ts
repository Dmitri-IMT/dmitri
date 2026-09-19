import type { Language } from './LanguageProvider'

export type MessageKey =
  | 'nav.home'
  | 'nav.scans'
  | 'nav.network'
  | 'nav.devices'
  | 'nav.users'
  | 'nav.settings'
  | 'nav.logout'
  | 'nav.preferences'
  | 'nav.theme'
  | 'nav.language'
  | 'scans.title'
  | 'scans.caption'
  | 'scans.error'
  | 'scans.emptyHeading'
  | 'scans.emptyBody'
  | 'scans.open'
  | 'scans.pages'
  | 'network.title'
  | 'network.caption'
  | 'network.error'
  | 'network.emptyHeading'
  | 'network.emptyBody'
  | 'network.emptyActive'
  | 'network.quiet'
  | 'network.open'
  | 'network.pages'
  | 'home.noScans'
  | 'home.firstScanBody'
  | 'home.error'
  | 'home.retry'
  | 'home.nothingNeedsAttention'
  | 'home.oneNeedsAttention'
  | 'home.manyNeedAttention'
  | 'home.lastScan'
  | 'home.vulnerability'
  | 'home.machine'
  | 'home.severity'
  | 'home.attentionCaption'
  | 'home.attentionPages'
  | 'home.events'
  | 'home.eventsEmpty'
  | 'home.eventsPages'
  | 'home.activity'
  | 'home.activityEmpty'
  | 'home.activityPages'
  | 'common.none'
  | 'common.when'
  | 'common.box'
  | 'common.mode'
  | 'common.status'
  | 'common.duration'
  | 'common.machines'
  | 'common.vulnerabilities'
  | 'common.highestSeverity'
  | 'common.address'
  | 'common.type'
  | 'common.lastSeen'
  | 'common.noName'
  | 'common.notSeenFor'
  | 'common.week'
  | 'common.weeks'
  | 'ai.contextHint'
  | 'ai.showHistory'
  | 'ai.hideHistory'
  | 'ai.question'
  | 'ai.asking'
  | 'ai.ask'
  | 'ai.loadingHistory'
  | 'ai.answer'
  | 'ai.limitations'
  | 'ai.openAssistant'
  | 'ai.assistant'
  | 'ai.askDmitri'
  | 'ai.chooseScan'
  | 'ai.viewScans'
  | 'ai.askContext'
  | 'ai.placeholder'
  | 'ai.thisScan'
  | 'ai.thisHost'
  | 'ai.askAbout'
  | 'ai.askAboutScan'
  | 'ai.viewFinding'
  | 'ai.genericError'
  | 'ai.overview'
  | 'ai.overviewDescription'
  | 'ai.reloadOverview'
  | 'ai.explainScan'
  | 'ai.failedOverview'
  | 'ai.loadFailed'
  | 'ai.notRequestedOverview'
  | 'ai.preparingOverview'
  | 'ai.completedDescription'
  | 'ai.whatToDoFirst'
  | 'ai.whyVulnerabilities'
  | 'ai.recordedVulnerability'
  | 'ai.recommendedAction'
  | 'ai.showDetails'
  | 'ai.showOverview'
  | 'ai.cannotConfirm'
  | 'ai.priorityImmediate'
  | 'ai.priorityHigh'
  | 'ai.priorityMedium'
  | 'ai.priorityLow'
  | 'reports.title'
  | 'reports.description'
  | 'reports.preparing'
  | 'reports.downloadExplained'
  | 'reports.downloadTechnical'
  | 'reports.error'
  | 'reports.previewExplained'
  | 'reports.previewTechnical'
  | 'reports.previewTitle'
  | 'common.cancel'
  | 'common.confirmDownload'
  | 'settings.account'
  | 'settings.email'
  | 'settings.role'
  | 'settings.admin'
  | 'settings.viewer'
  | 'settings.changePassword'
  | 'settings.recordedAbout'
  | 'settings.activityDescription'
  | 'settings.leaveOrganisation'
  | 'settings.leaveDescription'
  | 'settings.deleteAccount'
  | 'settings.deleteAccountQuestion'
  | 'settings.deleteAccountBody'
  | 'settings.passwordChanged'
  | 'devices.subtitle'
  | 'devices.caption'
  | 'devices.error'
  | 'devices.emptyHeading'
  | 'devices.emptyBody'
  | 'devices.emptyNote'
  | 'devices.open'
  | 'users.invite'
  | 'settings.aiUsage'
  | 'settings.aiUsageDescription'
  | 'settings.loadingUsage'
  | 'settings.usageError'
  | 'settings.tryAgain'
  | 'settings.summary'
  | 'settings.requests'
  | 'settings.inputTokens'
  | 'settings.outputTokens'
  | 'settings.totalTokens'
  | 'settings.errors'
  | 'settings.recentRequests'
  | 'settings.operation'
  | 'settings.model'
  | 'settings.status'
  | 'settings.tokens'
  | 'settings.latency'
  | 'settings.noRequests'

type Value = string | ((v: Record<string, string | number>) => string)
type Catalog = Record<MessageKey, Value>

const en: Catalog = {
  'nav.home': 'Home',
  'nav.scans': 'Scans',
  'nav.network': 'Network',
  'nav.devices': 'Devices',
  'nav.users': 'Users',
  'nav.settings': 'Settings',
  'nav.logout': 'Log out',
  'nav.preferences': 'Preferences',
  'nav.theme': 'Theme',
  'nav.language': 'Language',
  'scans.title': 'Scans',
  'scans.caption': 'Scan run log',
  'scans.error': "Couldn't load the scans.",
  'scans.emptyHeading': 'No scans yet',
  'scans.emptyBody':
    'Your first scan finds the machines on your network and what needs fixing.',
  'scans.open': ({ id }) => 'Open scan ' + id,
  'scans.pages': 'Scan pages',
  'network.title': 'Network',
  'network.caption': 'Machines on your network',
  'network.error': "Couldn't load your network.",
  'network.emptyHeading': 'No machines yet',
  'network.emptyBody':
    'Your first scan finds the machines on your network and what needs fixing.',
  'network.emptyActive': 'No machines seen in the last 7 days.',
  'network.quiet': ({ count }) => 'Not seen recently (' + count + ')',
  'network.open': ({ host }) => 'Open ' + host,
  'network.pages': 'Machine pages',
  'home.noScans': 'No scans yet',
  'home.firstScanBody':
    'Your first scan finds the machines on your network and what needs fixing.',
  'home.error': "Couldn't load what needs your attention.",
  'home.retry': 'Try again',
  'home.nothingNeedsAttention': 'Nothing needs your attention',
  'home.oneNeedsAttention': '1 thing needs your attention',
  'home.manyNeedAttention': ({ count }) =>
    count + ' things need your attention',
  'home.lastScan': 'Last scan finished',
  'home.vulnerability': 'Vulnerability',
  'home.machine': 'Machine',
  'home.severity': 'Severity',
  'home.attentionCaption': 'Vulnerabilities needing your attention',
  'home.attentionPages': 'Attention pages',
  'home.events': 'Events',
  'home.eventsEmpty': 'Nothing to report right now.',
  'home.eventsPages': 'Events pages',
  'home.activity': 'Activity',
  'home.activityEmpty': 'Nothing has been recorded yet.',
  'home.activityPages': 'Activity pages',
  'common.none': 'None',
  'common.when': 'When',
  'common.box': 'Box',
  'common.mode': 'Mode',
  'common.status': 'Status',
  'common.duration': 'Duration',
  'common.machines': 'Machines',
  'common.vulnerabilities': 'Vulnerabilities',
  'common.highestSeverity': 'Highest severity',
  'common.address': 'Address',
  'common.type': 'Type',
  'common.lastSeen': 'Last seen',
  'common.noName': 'No name yet',
  'common.notSeenFor': ({ count, unit }) =>
    'Not seen for ' + count + ' ' + unit,
  'common.week': 'week',
  'common.weeks': 'weeks',
  'ai.contextHint':
    'The answer uses only the evidence available in this context.',
  'ai.showHistory': 'Show history',
  'ai.hideHistory': 'Hide history',
  'ai.question': 'Your question',
  'ai.asking': 'Analyzing...',
  'ai.ask': 'Ask',
  'ai.loadingHistory': 'Loading history...',
  'ai.answer': 'Answer',
  'ai.limitations': 'Limitations',
  'ai.openAssistant': 'Open security assistant',
  'ai.assistant': 'AI assistant',
  'ai.askDmitri': 'Ask Dmitri',
  'ai.chooseScan': 'Choose a scan to ask questions about its security data.',
  'ai.viewScans': 'View scans',
  'ai.askContext': 'Ask about this context',
  'ai.placeholder': 'What should I fix first?',
  'ai.thisScan': 'this scan',
  'ai.thisHost': 'this machine',
  'ai.askAbout': ({ label }) => 'Ask about ' + label,
  'ai.askAboutScan': 'Ask about this scan',
  'ai.viewFinding': ({ index }) => 'View finding ' + index,
  'ai.genericError': 'Unable to get an answer right now. Try again.',
  'ai.overview': 'AI overview',
  'ai.overviewDescription': 'Get a plain-language overview of this scan.',
  'ai.reloadOverview': 'Reload overview',
  'ai.explainScan': 'Explain this scan',
  'ai.failedOverview':
    "Couldn't prepare the overview. The scan results are complete without it.",
  'ai.loadFailed': "Couldn't load the overview.",
  'ai.notRequestedOverview': 'Get a plain-language overview of this scan.',
  'ai.preparingOverview': 'Preparing a plain-language overview of this scan.',
  'ai.completedDescription':
    "A plain-language interpretation of this scan's recorded evidence.",
  'ai.whatToDoFirst': 'What to do first',
  'ai.whyVulnerabilities': 'Why these vulnerabilities matter',
  'ai.recordedVulnerability': 'Recorded vulnerability',
  'ai.recommendedAction': 'Recommended action:',
  'ai.showDetails': 'Show assessment details and limitations',
  'ai.showOverview': 'Show AI summary',
  'ai.cannotConfirm': 'What this scan cannot confirm',
  'ai.priorityImmediate': 'Immediate',
  'ai.priorityHigh': 'High priority',
  'ai.priorityMedium': 'Medium priority',
  'ai.priorityLow': 'Low priority',
  'reports.title': 'Scan reports',
  'reports.description': 'Choose which report you want to download.',
  'reports.preparing': 'Preparing report...',
  'reports.downloadExplained': 'Download explained report',
  'reports.downloadTechnical': 'Download technical report',
  'reports.error': "Couldn't prepare the report. Try again.",
  'reports.previewExplained': 'Explained report preview',
  'reports.previewTechnical': 'Technical report preview',
  'reports.previewTitle': 'PDF report preview',
  'common.cancel': 'Cancel',
  'common.confirmDownload': 'Confirm download',
  'settings.account': 'Your account',
  'settings.email': 'Email',
  'settings.role': 'Role',
  'settings.admin': 'Admin',
  'settings.viewer': 'Viewer',
  'settings.changePassword': 'Change password',
  'settings.recordedAbout': "What's recorded about me?",
  'settings.activityDescription':
    "Everyone in your organization can see when you last signed in, and a log of changes to the organization: scans, machines that join the network, invitations, role changes, and members joining or leaving. We don't record what you viewed.",
  'settings.leaveOrganisation': 'Leave this organisation',
  'settings.leaveDescription':
    "Your account is deleted and you lose access to this organisation's scans, network and vulnerabilities straight away. This can't be undone — an admin would have to invite you again.",
  'settings.deleteAccount': 'Delete my account',
  'settings.deleteAccountQuestion': 'Delete your account?',
  'settings.deleteAccountBody':
    "Your account is deleted and you lose access straight away. This can't be undone.",
  'settings.passwordChanged': 'Password changed.',
  'devices.subtitle': 'The Dmitri boxes reporting to this organisation.',
  'devices.caption': 'Dmitri boxes',
  'devices.error': "Couldn't load your devices.",
  'devices.emptyHeading': 'No box connected yet',
  'devices.emptyBody':
    'Your installer connects the box on site; it appears here once it comes online.',
  'devices.emptyNote':
    'Contact whoever installed Dmitri if you were expecting one.',
  'devices.open': ({ name }) => 'Open ' + name,
  'users.invite': 'Invite a user',
  'settings.aiUsage': 'AI usage',
  'settings.aiUsageDescription':
    'Organization-wide provider usage. Prompts and model responses are not stored here.',
  'settings.loadingUsage': 'Loading usage…',
  'settings.usageError': 'Usage data could not be loaded.',
  'settings.tryAgain': 'Try again',
  'settings.summary': 'Summary',
  'settings.requests': 'Requests',
  'settings.inputTokens': 'Input tokens',
  'settings.outputTokens': 'Output tokens',
  'settings.totalTokens': 'Total tokens',
  'settings.errors': 'Errors',
  'settings.recentRequests': 'Recent AI provider requests',
  'settings.operation': 'Operation',
  'settings.model': 'Model',
  'settings.status': 'Status',
  'settings.tokens': 'Tokens',
  'settings.latency': 'Latency',
  'settings.noRequests': 'No AI requests recorded yet.',
}

const pt: Catalog = {
  ...en,
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
  'common.none': 'Nenhuma',
  'common.when': 'Quando',
  'common.box': 'Agente',
  'common.mode': 'Modo',
  'common.duration': 'Duração',
  'common.machines': 'Equipamentos',
  'common.vulnerabilities': 'Vulnerabilidades',
  'common.highestSeverity': 'Maior gravidade',
  'common.address': 'Endereço',
  'common.type': 'Tipo',
  'common.lastSeen': 'Visto por último',
  'common.noName': 'Sem nome',
  'common.notSeenFor': ({ count, unit }) =>
    'Não visto há ' + count + ' ' + unit,
  'common.week': 'semana',
  'common.weeks': 'semanas',
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
  'settings.changePassword': 'Alterar senha',
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
  'settings.passwordChanged': 'Senha alterada.',
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
}

const ru: Catalog = {
  ...en,
  'nav.home': 'Главная',
  'nav.scans': 'Сканирования',
  'nav.network': 'Сеть',
  'nav.devices': 'Устройства',
  'nav.users': 'Пользователи',
  'nav.settings': 'Настройки',
  'nav.logout': 'Выйти',
  'nav.preferences': 'Настройки',
  'nav.theme': 'Тема',
  'nav.language': 'Язык',
  'scans.title': 'Сканирования',
  'scans.caption': 'Журнал сканирований',
  'scans.error': 'Не удалось загрузить сканирования.',
  'scans.emptyHeading': 'Сканирований пока нет',
  'scans.emptyBody':
    'Первое сканирование обнаружит устройства сети и проблемы, требующие исправления.',
  'scans.open': ({ id }) => 'Открыть сканирование ' + id,
  'scans.pages': 'Страницы сканирований',
  'network.title': 'Сеть',
  'network.caption': 'Устройства вашей сети',
  'network.error': 'Не удалось загрузить сеть.',
  'network.emptyHeading': 'Устройств пока нет',
  'network.emptyBody':
    'Первое сканирование обнаружит устройства сети и проблемы, требующие исправления.',
  'network.emptyActive': 'Устройств не было видно последние 7 дней.',
  'network.quiet': ({ count }) => 'Недавно не обнаружены (' + count + ')',
  'network.open': ({ host }) => 'Открыть ' + host,
  'network.pages': 'Страницы устройств',
  'home.noScans': 'Сканирований пока нет',
  'home.firstScanBody':
    'Первое сканирование обнаружит устройства сети и проблемы, требующие исправления.',
  'home.error': 'Не удалось загрузить сведения, требующие внимания.',
  'home.retry': 'Повторить',
  'home.nothingNeedsAttention': 'Ничего не требует внимания',
  'home.oneNeedsAttention': '1 пункт требует внимания',
  'home.manyNeedAttention': ({ count }) => count + ' пунктов требуют внимания',
  'home.lastScan': 'Последнее сканирование завершено',
  'home.vulnerability': 'Уязвимость',
  'home.machine': 'Устройство',
  'home.severity': 'Критичность',
  'home.attentionCaption': 'Уязвимости, требующие внимания',
  'home.attentionPages': 'Страницы внимания',
  'home.events': 'События',
  'home.eventsEmpty': 'Сейчас нечего сообщить.',
  'home.eventsPages': 'Страницы событий',
  'home.activity': 'Активность',
  'home.activityEmpty': 'Активность ещё не зарегистрирована.',
  'home.activityPages': 'Страницы активности',
  'common.none': 'Нет',
  'common.when': 'Когда',
  'common.box': 'Агент',
  'common.mode': 'Режим',
  'common.duration': 'Длительность',
  'common.machines': 'Устройства',
  'common.vulnerabilities': 'Уязвимости',
  'common.highestSeverity': 'Максимальная критичность',
  'common.address': 'Адрес',
  'common.type': 'Тип',
  'common.lastSeen': 'Последняя активность',
  'common.noName': 'Без имени',
  'common.notSeenFor': ({ count, unit }) => 'Не видно ' + count + ' ' + unit,
  'common.week': 'неделю',
  'common.weeks': 'недель',
  'ai.contextHint':
    'Ответ использует только доступные сведения из этого контекста.',
  'ai.showHistory': 'Показать историю',
  'ai.hideHistory': 'Скрыть историю',
  'ai.question': 'Ваш вопрос',
  'ai.asking': 'Анализирую...',
  'ai.ask': 'Спросить',
  'ai.loadingHistory': 'Загрузка истории...',
  'ai.answer': 'Ответ',
  'ai.limitations': 'Ограничения',
  'ai.openAssistant': 'Открыть помощника по безопасности',
  'ai.assistant': 'ИИ-помощник',
  'ai.askDmitri': 'Спросите Дмитри',
  'ai.chooseScan':
    'Выберите сканирование, чтобы задать вопросы о данных безопасности.',
  'ai.viewScans': 'Открыть сканирования',
  'ai.askContext': 'Спросить об этом контексте',
  'ai.placeholder': 'Что исправить в первую очередь?',
  'ai.thisScan': 'это сканирование',
  'ai.thisHost': 'это устройство',
  'ai.askAbout': ({ label }) => 'Спросить об объекте: ' + label,
  'ai.askAboutScan': 'Спросить об этом сканировании',
  'ai.viewFinding': ({ index }) => 'Открыть находку ' + index,
  'ai.genericError': 'Не удалось получить ответ. Попробуйте снова.',
  'ai.overview': 'Обзор ИИ',
  'ai.overviewDescription': 'Получите обзор этого сканирования простым языком.',
  'ai.reloadOverview': 'Обновить обзор',
  'ai.explainScan': 'Объяснить это сканирование',
  'ai.failedOverview':
    'Не удалось подготовить обзор. Результаты сканирования доступны.',
  'ai.loadFailed': 'Не удалось загрузить обзор.',
  'ai.notRequestedOverview':
    'Получите обзор этого сканирования простым языком.',
  'ai.preparingOverview': 'Готовим обзор этого сканирования.',
  'ai.completedDescription':
    'Простое объяснение данных, зарегистрированных в этом сканировании.',
  'ai.whatToDoFirst': 'Что исправить в первую очередь',
  'ai.whyVulnerabilities': 'Почему важны эти уязвимости',
  'ai.recordedVulnerability': 'Зафиксированная уязвимость',
  'ai.recommendedAction': 'Рекомендуемое действие:',
  'ai.showDetails': 'Показать детали оценки и ограничения',
  'ai.showOverview': 'Показать сводку ИИ',
  'ai.cannotConfirm': 'Что нельзя подтвердить этим сканированием',
  'ai.priorityImmediate': 'Немедленно',
  'ai.priorityHigh': 'Высокий приоритет',
  'ai.priorityMedium': 'Средний приоритет',
  'ai.priorityLow': 'Низкий приоритет',
  'reports.title': 'Отчеты сканирования',
  'reports.description': 'Выберите отчет для скачивания.',
  'reports.preparing': 'Подготовка отчета...',
  'reports.downloadExplained': 'Скачать пояснительный отчет',
  'reports.downloadTechnical': 'Скачать технический отчет',
  'reports.error': 'Не удалось подготовить отчет. Попробуйте снова.',
  'reports.previewExplained': 'Предварительный просмотр пояснительного отчета',
  'reports.previewTechnical': 'Предварительный просмотр технического отчета',
  'reports.previewTitle': 'Предварительный просмотр PDF-отчета',
  'common.cancel': 'Отмена',
  'common.confirmDownload': 'Подтвердить скачивание',
  'settings.account': 'Ваша учетная запись',
  'settings.email': 'Электронная почта',
  'settings.role': 'Роль',
  'settings.admin': 'Администратор',
  'settings.viewer': 'Наблюдатель',
  'settings.changePassword': 'Изменить пароль',
  'settings.recordedAbout': 'Что записывается обо мне?',
  'settings.activityDescription':
    'Все участники организации видят время последнего входа и журнал изменений: сканирования, подключение устройств, приглашения, изменение ролей и вступление или выход участников. Просмотренные вами данные не записываются.',
  'settings.leaveOrganisation': 'Покинуть организацию',
  'settings.leaveDescription':
    'Ваша учетная запись будет удалена, и вы сразу потеряете доступ к сканированиям, сети и уязвимостям этой организации. Это нельзя отменить — администратору придется пригласить вас снова.',
  'settings.deleteAccount': 'Удалить учетную запись',
  'settings.deleteAccountQuestion': 'Удалить учетную запись?',
  'settings.deleteAccountBody':
    'Ваша учетная запись будет удалена, и доступ будет потерян. Это нельзя отменить.',
  'settings.passwordChanged': 'Пароль изменен.',
  'devices.subtitle':
    'Устройства Dmitri, отправляющие данные в эту организацию.',
  'devices.caption': 'Устройства Dmitri',
  'devices.error': 'Не удалось загрузить устройства.',
  'devices.emptyHeading': 'Подключенных устройств пока нет',
  'devices.emptyBody':
    'Установщик подключает устройство на месте; оно появится здесь после выхода в сеть.',
  'devices.emptyNote':
    'Свяжитесь с установщиком Dmitri, если ожидали увидеть устройство.',
  'devices.open': ({ name }) => 'Открыть ' + name,
  'users.invite': 'Пригласить пользователя',
  'settings.aiUsage': 'Использование ИИ',
  'settings.aiUsageDescription':
    'Использование провайдера во всей организации. Промпты и ответы модели здесь не хранятся.',
  'settings.loadingUsage': 'Загрузка данных…',
  'settings.usageError': 'Не удалось загрузить данные об использовании.',
  'settings.tryAgain': 'Повторить',
  'settings.summary': 'Сводка',
  'settings.requests': 'Запросы',
  'settings.inputTokens': 'Входные токены',
  'settings.outputTokens': 'Выходные токены',
  'settings.totalTokens': 'Всего токенов',
  'settings.errors': 'Ошибки',
  'settings.recentRequests': 'Последние запросы к провайдеру ИИ',
  'settings.operation': 'Операция',
  'settings.model': 'Модель',
  'settings.status': 'Статус',
  'settings.tokens': 'Токены',
  'settings.latency': 'Задержка',
  'settings.noRequests': 'Запросов к ИИ пока нет.',
}

const catalog: Record<Language, Catalog> = { en, 'pt-BR': pt, ru }

export function getMessage(
  language: Language,
  key: MessageKey,
  variables: Record<string, string | number> = {},
) {
  const value = catalog[language][key]
  return typeof value === 'function' ? value(variables) : value
}
