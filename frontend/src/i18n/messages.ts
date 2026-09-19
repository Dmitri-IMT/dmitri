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
  'ai.contextHint': 'The answer uses only the evidence available in this context.',
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
  'ai.contextHint': 'A resposta usa somente as evidências disponíveis neste contexto.',
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
  'ai.chooseScan': 'Selecione uma varredura para fazer perguntas sobre os dados de segurança.',
  'ai.viewScans': 'Ver varreduras',
  'ai.askContext': 'Pergunte sobre este contexto',
  'ai.placeholder': 'O que devo corrigir primeiro?',
  'ai.thisScan': 'esta varredura',
  'ai.thisHost': 'este equipamento',
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
  'ai.contextHint': 'Ответ использует только доступные сведения из этого контекста.',
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
  'ai.chooseScan': 'Выберите сканирование, чтобы задать вопросы о данных безопасности.',
  'ai.viewScans': 'Открыть сканирования',
  'ai.askContext': 'Спросить об этом контексте',
  'ai.placeholder': 'Что исправить в первую очередь?',
  'ai.thisScan': 'это сканирование',
  'ai.thisHost': 'это устройство',
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
