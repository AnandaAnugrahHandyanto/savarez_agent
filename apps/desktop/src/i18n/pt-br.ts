import { FIELD_DESCRIPTIONS, FIELD_LABELS } from '@/app/settings/constants'

import type { Translations } from './types'

export const ptBr: Translations = {
  common: {
    save: 'Salvar',
    saving: 'Salvando…',
    cancel: 'Cancelar',
    close: 'Fechar',
    confirm: 'Confirmar',
    delete: 'Excluir',
    refresh: 'Atualizar',
    retry: 'Tentar novamente',
    on: 'Ligado',
    off: 'Desligado'
  },

  boot: {
    ready: 'Hermes Desktop está pronto',
    desktopBootFailedWithMessage: message => `Falha ao iniciar o desktop: ${message}`,
    steps: {
      connectingGateway: 'Conectando ao gateway do desktop',
      loadingSettings: 'Carregando configurações do Hermes',
      loadingSessions: 'Carregando sessões recentes',
      startingDesktopConnection: 'Iniciando conexão do desktop',
      startingHermesDesktop: 'Iniciando Hermes Desktop…'
    },
    errors: {
      backgroundExited: 'O processo em segundo plano do Hermes foi encerrado.',
      backgroundExitedDuringStartup:
        'O processo em segundo plano do Hermes foi encerrado durante a inicialização.',
      backendStopped: 'Backend parado',
      desktopBootFailed: 'Falha ao iniciar o desktop',
      gatewaySignInRequired: 'Login no gateway necessário',
      ipcBridgeUnavailable: 'A ponte IPC do desktop não está disponível.'
    },
    failure: {
      title: 'Hermes não conseguiu iniciar',
      description:
        'O gateway em segundo plano não foi iniciado. Tente uma das opções de recuperação abaixo. Nada aqui exclui seus chats ou configurações.',
      remoteTitle: 'Login no gateway remoto necessário',
      remoteDescription:
        'Sua sessão no gateway remoto expirou. Faça login novamente para reconectar. Nada aqui exclui seus chats ou configurações.',
      retry: 'Tentar novamente',
      repairInstall: 'Reparar instalação',
      useLocalGateway: 'Usar gateway local',
      openLogs: 'Abrir logs',
      repairHint:
        'A reparação reinstala o instalador e pode levar alguns minutos em uma máquina nova.',
      remoteSignInHint:
        'Abre a janela de login do gateway. Use o gateway local para mudar para o backend integrado.',
      hideRecentLogs: 'Ocultar logs recentes',
      showRecentLogs: 'Mostrar logs recentes',
      signedInTitle: 'Conectado',
      signedInMessage: 'Reconectando ao gateway remoto…',
      signInIncompleteTitle: 'Login incompleto',
      signInIncompleteMessage:
        'A janela de login foi fechada antes da autenticação ser concluída.',
      signInFailed: 'Falha no login',
      signInToRemoteGateway: 'Fazer login no gateway remoto',
      signInWithProvider: provider => `Fazer login com ${provider}`,
      identityProvider: 'seu provedor de identidade'
    }
  },

  notifications: {
    region: 'Notificações',
    hide: 'Ocultar',
    show: 'Mostrar',
    more: count => `${count} ${count === 1 ? 'notificação' : 'notificações'} a mais`,
    clearAll: 'Limpar tudo',
    dismiss: 'Dispensar notificação',
    details: 'Detalhes',
    copyDetail: 'Copiar detalhe',
    copyDetailFailed: 'Não foi possível copiar o detalhe da notificação',
    backendOutOfDateTitle: 'Backend desatualizado',
    backendOutOfDateMessage:
      'Seu backend Hermes é mais antigo que esta versão do desktop e pode não funcionar corretamente. Atualize para alinhá-los.',
    updateHermes: 'Atualizar Hermes',
    updateReadyTitle: 'Atualização pronta',
    updateReadyMessage: count =>
      `${count} nova${count === 1 ? '' : 's'} alteração${count === 1 ? '' : 'ões'} disponível.`,
    seeWhatsNew: 'Ver novidades',
    errors: {
      elevenLabsNeedsKey: 'O STT do ElevenLabs precisa de ELEVENLABS_API_KEY.',
      elevenLabsRejectedKey: 'O ElevenLabs rejeitou a chave de API (401).',
      methodNotAllowed:
        'O backend do desktop rejeitou essa requisição (405 Method Not Allowed). Tente reiniciar o Hermes Desktop.',
      microphonePermission: 'A permissão do microfone foi negada.',
      openaiRejectedApiKey: 'A OpenAI rejeitou a chave de API.',
      openaiRejectedApiKeyWithStatus: status =>
        `A OpenAI rejeitou a chave de API (${status} invalid_api_key).`,
      openaiTtsNeedsKey:
        'O TTS da OpenAI precisa de VOICE_TOOLS_OPENAI_KEY ou OPENAI_API_KEY.'
    }
  },

  titlebar: {
    hideSidebar: 'Ocultar barra lateral',
    showSidebar: 'Mostrar barra lateral',
    search: 'Pesquisar',
    searchTitle: 'Pesquisar sessões, visualizações e ações',
    swapSidebarSides: 'Trocar lados da barra lateral',
    swapSidebarSidesTitle: 'Trocar os lados das sessões e do navegador de arquivos',
    hideRightSidebar: 'Ocultar barra lateral direita',
    showRightSidebar: 'Mostrar barra lateral direita',
    muteHaptics: 'Silenciar hápticos',
    unmuteHaptics: 'Ativar hápticos',
    openSettings: 'Abrir configurações'
  },

  language: {
    label: 'Idioma',
    description: 'Escolha o idioma da interface do desktop.',
    saving: 'Salvando idioma…',
    saveError: 'Falha ao atualizar o idioma'
  },

  settings: {
    closeSettings: 'Fechar configurações',
    exportConfig: 'Exportar configuração',
    importConfig: 'Importar configuração',
    resetToDefaults: 'Restaurar padrões',
    resetConfirm: 'Restaurar todas as configurações para os padrões do Hermes?',
    exportFailed: 'Falha na exportação',
    resetFailed: 'Falha ao restaurar',
    nav: {
      gateway: 'Gateway',
      apiKeys: 'Ferramentas e Chaves',
      mcp: 'MCP',
      archivedChats: 'Chats Arquivados',
      about: 'Sobre'
    },
    sections: {
      model: 'Modelo',
      chat: 'Chat',
      appearance: 'Aparência',
      workspace: 'Área de trabalho',
      safety: 'Segurança',
      memory: 'Memória e Contexto',
      voice: 'Voz',
      advanced: 'Avançado'
    },
    searchPlaceholder: {
      about: 'Sobre o Hermes Desktop',
      config: 'Pesquisar configurações...',
      gateway: 'Conexão do gateway...',
      keys: 'Pesquisar chaves de API...',
      mcp: 'Pesquisar servidores MCP...',
      sessions: 'Pesquisar sessões arquivadas...'
    },
    modeOptions: {
      light: { label: 'Claro', description: 'Superfícies claras do desktop' },
      dark: { label: 'Escuro', description: 'Espaço de trabalho sem brilho' },
      system: { label: 'Sistema', description: 'Seguir aparência do sistema' }
    },
    appearance: {
      title: 'Aparência',
      intro:
        'Estas são preferências de exibição apenas do desktop. O modo controla o brilho; o tema controla a paleta de cores e o estilo da superfície do chat.',
      colorMode: 'Modo de Cor',
      colorModeDesc: 'Escolha um modo fixo ou deixe o Hermes seguir a configuração do sistema.',
      toolViewTitle: 'Exibição de Chamadas de Ferramentas',
      toolViewDesc:
        'Produto oculta dados brutos das ferramentas; Técnico mostra entrada/saída completa.',
      product: 'Produto',
      productDesc: 'Atividade de ferramentas amigável com resumos concisos.',
      technical: 'Técnico',
      technicalDesc: 'Incluir argumentos/resultados brutos e detalhes de baixo nível.',
      themeTitle: 'Tema',
      themeDesc: 'Paletas do desktop apenas. O modo selecionado é aplicado por cima.'
    },
    fieldLabels: FIELD_LABELS,
    fieldDescriptions: FIELD_DESCRIPTIONS,
    about: {
      heading: 'Hermes Desktop',
      version: value => `Versão ${value}`,
      versionUnavailable: 'Versão indisponível',
      updates: 'Atualizações',
      checkNow: 'Verificar agora',
      checking: 'Verificando…',
      seeWhatsNew: 'Ver novidades',
      releaseNotes: 'Notas de lançamento',
      onLatest: 'Você está na versão mais recente.',
      installing: 'Uma atualização está sendo instalada.',
      cantUpdate: 'Esta compilação não pode se atualizar de dentro do app.',
      cantReach: 'Não foi possível acessar o servidor de atualização.',
      tapCheck: 'Toque em "Verificar agora" para buscar atualizações.',
      updateReady: count =>
        `Uma nova atualização está pronta (${count} alteração${count === 1 ? '' : 'ões'} incluída${count === 1 ? '' : 's'}).`,
      lastChecked: age => `Última verificação ${age}`,
      justNowSuffix: ' · agora',
      automaticUpdates: 'Atualizações automáticas',
      automaticUpdatesDesc:
        'O Hermes verifica atualizações automaticamente em segundo plano e avisa quando uma estiver pronta.',
      branchCommit: (branch, commit) => `Branch ${branch} · Commit ${commit}`,
      never: 'nunca',
      justNow: 'agora',
      minAgo: count => `${count} min atrás`,
      hoursAgo: count => `${count} horas atrás`,
      daysAgo: count => `${count} dias atrás`
    }
  },

  skills: {
    tabSkills: 'Habilidades',
    tabToolsets: 'Conjuntos de ferramentas',
    all: 'Todas',
    searchSkills: 'Pesquisar habilidades...',
    searchToolsets: 'Pesquisar conjuntos de ferramentas...',
    refresh: 'Atualizar habilidades',
    refreshing: 'Atualizando habilidades',
    loading: 'Carregando capacidades...',
    noSkillsTitle: 'Nenhuma habilidade encontrada',
    noSkillsDesc: 'Tente uma pesquisa mais ampla ou uma categoria diferente.',
    noToolsetsTitle: 'Nenhum conjunto de ferramentas encontrado',
    noToolsetsDesc: 'Tente uma pesquisa mais ampla.',
    noDescription: 'Sem descrição.',
    configured: 'Configurado',
    needsKeys: 'Precisa de chaves',
    toolsetsEnabled: (enabled, total) =>
      `${enabled}/${total} conjuntos de ferramentas habilitados`,
    configureToolset: label => `Configurar ${label}`,
    toggleToolset: label => `Alternar conjunto de ferramentas ${label}`,
    skillsLoadFailed: 'Falha ao carregar habilidades',
    toolsetsRefreshFailed: 'Falha ao atualizar conjuntos de ferramentas',
    skillEnabled: 'Habilidade habilitada',
    skillDisabled: 'Habilidade desabilitada',
    toolsetEnabled: 'Conjunto de ferramentas habilitado',
    toolsetDisabled: 'Conjunto de ferramentas desabilitado',
    appliesToNewSessions: name => `${name} se aplica a novas sessões.`,
    failedToUpdate: name => `Falha ao atualizar ${name}`
  },

  agents: {
    close: 'Fechar agentes',
    title: 'Árvore de spawn',
    subtitle: 'Atividade de subagentes ao vivo para o turno atual.',
    emptyTitle: 'Nenhum subagente ativo',
    emptyDesc: 'Quando um turno delega trabalho, os agentes filhos transmitem seu progresso aqui.',
    running: 'Executando',
    failed: 'Falhou',
    done: 'Concluído',
    streaming: 'Transmitindo',
    files: 'Arquivos',
    moreFiles: count => `+${count} arquivos a mais`,
    delegation: index => `Delegação ${index}`,
    workers: count => `${count} workers`,
    workersActive: count => `${count} ativos`,
    agentsCount: count => `${count} ${count === 1 ? 'agente' : 'agentes'}`,
    activeCount: count => `${count} ativos`,
    failedCount: count => `${count} falharam`,
    toolsCount: count => `${count} ferramentas`,
    filesCount: count => `${count} arquivos`,
    updatedAgo: age => `atualizado ${age}`,
    ageNow: 'agora',
    ageSeconds: seconds => `${seconds}s atrás`,
    ageMinutes: minutes => `${minutes}m atrás`,
    ageHours: hours => `${hours}h atrás`,
    durationSeconds: seconds => `${seconds}s`,
    durationMinutes: (minutes, seconds) => `${minutes}m ${seconds}s`,
    tokensK: k => `${k}k tok`,
    tokens: value => `${value} tok`
  },

  commandCenter: {
    close: 'Fechar centro de comandos',
    searchPlaceholder: 'Pesquisar sessões, visualizações e ações',
    sections: { sessions: 'Sessões', system: 'Sistema', usage: 'Uso' },
    sectionDescriptions: {
      sessions: 'Pesquisar e gerenciar sessões',
      system: 'Status, logs e ações do sistema',
      usage: 'Atividade de tokens, custos e habilidades ao longo do tempo'
    },
    nav: {
      newChat: { title: 'Nova sessão', detail: 'Iniciar uma sessão nova' },
      settings: { title: 'Configurações', detail: 'Configurar o Hermes Desktop' },
      skills: {
        title: 'Habilidades e Ferramentas',
        detail: 'Habilitar habilidades, conjuntos de ferramentas e provedores'
      },
      messaging: {
        title: 'Mensagens',
        detail: 'Configurar Telegram, Slack, Discord e mais'
      },
      artifacts: { title: 'Artefatos', detail: 'Navegar pelas saídas geradas' }
    },
    sectionEntries: {
      sessions: {
        title: 'Painel de sessões',
        detail: 'Pesquisar, fixar e gerenciar sessões'
      },
      system: {
        title: 'Painel do sistema',
        detail: 'Status do gateway, logs, reiniciar/atualizar'
      },
      usage: {
        title: 'Painel de uso',
        detail: 'Atividade de tokens, custos e habilidades'
      }
    },
    providerNavigate: 'Navegar',
    providerSessions: 'Sessões',
    refresh: 'Atualizar',
    refreshing: 'Atualizando...',
    noResults: 'Nenhum resultado correspondente encontrado.',
    pinSession: 'Fixar sessão',
    unpinSession: 'Desafixar sessão',
    exportSession: 'Exportar sessão',
    deleteSession: 'Excluir sessão',
    noSessions: 'Nenhuma sessão ainda.',
    gatewayRunning: 'Gateway de mensagens executando',
    gatewayStopped: 'Gateway de mensagens parado',
    hermesActiveSessions: (version, count) =>
      `Hermes ${version} · Sessões ativas ${count}`,
    restartMessaging: 'Reiniciar mensagens',
    updateHermes: 'Atualizar Hermes',
    actionRunning: 'executando',
    actionDone: 'concluído',
    actionFailed: 'falhou',
    actionStartedWaiting: 'Ação iniciada, aguardando status...',
    loadingStatus: 'Carregando status...',
    recentLogs: 'Logs recentes',
    noLogs: 'Nenhum log carregado ainda.',
    days: count => `${count}d`,
    statSessions: 'Sessões',
    statApiCalls: 'Chamadas de API',
    statTokens: 'Tokens entrada/saída',
    statCost: 'Custo est.',
    actualCost: cost => `real ${cost}`,
    loadingUsage: 'Carregando uso...',
    noUsage: period => `Nenhum uso nos últimos ${period} dias.`,
    retry: 'Tentar novamente',
    dailyTokens: 'Tokens diários',
    input: 'entrada',
    output: 'saída',
    noDailyActivity: 'Nenhuma atividade diária.',
    topModels: 'Principais modelos',
    noModelUsage: 'Nenhum uso de modelos ainda.',
    topSkills: 'Principais habilidades',
    noSkillActivity: 'Nenhuma atividade de habilidades ainda.',
    actions: count => `${count} ações`
  },

  messaging: {
    search: 'Pesquisar mensagens...',
    loading: 'Carregando plataformas de mensagens...',
    loadFailed: 'Falha ao carregar plataformas de mensagens',
    states: {
      connected: 'Conectado',
      connecting: 'Conectando',
      disabled: 'Desabilitado',
      fatal: 'Erro',
      gateway_stopped: 'Gateway de mensagens parado',
      not_configured: 'Precisa de configuração',
      pending_restart: 'Reinício necessário',
      retrying: 'Tentando novamente',
      startup_failed: 'Falha na inicialização'
    },
    unknown: 'Desconhecido',
    hintPendingRestart:
      'Reinicie o gateway pela barra de status para aplicar esta alteração.',
    hintGatewayStopped: 'Inicie o gateway pela barra de status para conectar.',
    credentialsSet: 'Credenciais definidas',
    needsSetup: 'Precisa de configuração',
    gatewayStopped: 'Gateway de mensagens parado',
    getCredentials: 'Obter suas credenciais',
    openSetupGuide: 'Abrir guia de configuração',
    required: 'Obrigatório',
    recommended: 'Recomendado',
    advanced: count => `Avançado (${count})`,
    noTokenNeeded:
      'Esta plataforma não precisa de um token aqui. Use o guia de configuração acima, depois habilite abaixo.',
    enabled: 'Habilitado',
    disabled: 'Desabilitado',
    unsavedChanges: 'Alterações não salvas',
    saving: 'Salvando...',
    saveChanges: 'Salvar alterações',
    saved: 'Salvo',
    replaceValue: 'Substituir valor atual',
    openDocs: 'Abrir documentação',
    clearField: key => `Limpar ${key}`,
    enableAria: name => `Habilitar ${name}`,
    disableAria: name => `Desabilitar ${name}`,
    platformEnabled: name => `${name} habilitado`,
    platformDisabled: name => `${name} desabilitado`,
    restartToApply: 'Reinicie o gateway para que esta alteração tenha efeito.',
    setupSaved: name => `Configuração de ${name} salva`,
    restartToReconnect:
      'Reinicie o gateway para reconectar com as novas credenciais.',
    keyCleared: key => `${key} limpo`,
    setupUpdated: name => `A configuração de ${name} foi atualizada.`,
    failedUpdate: name => `Falha ao atualizar ${name}`,
    failedSave: name => `Falha ao salvar ${name}`,
    failedClear: key => `Falha ao limpar ${key}`,
    fieldCopy: {},
    platformIntro: {}
  },

  profiles: {
    close: 'Fechar perfis',
    nameHint:
      'Letras minúsculas, dígitos, hífens e sublinhados. Deve começar com uma letra ou dígito.',
    title: 'Perfis',
    count: count => `${count} ${count === 1 ? 'perfil' : 'perfis'}`,
    loading: 'Carregando perfis...',
    newProfile: 'Novo perfil',
    noProfiles: 'Nenhum perfil ainda.',
    selectPrompt: 'Selecione um perfil para ver seus detalhes.',
    refresh: 'Atualizar perfis',
    refreshing: 'Atualizando perfis',
    default: 'padrão',
    skills: count => `${count} ${count === 1 ? 'habilidade' : 'habilidades'}`,
    env: 'env',
    defaultBadge: 'Padrão',
    rename: 'Renomear',
    copySetup: 'Copiar configuração',
    copying: 'Copiando...',
    modelLabel: 'Modelo',
    skillsLabel: 'Habilidades',
    notSet: 'Não definido',
    soulDesc:
      'O prompt de sistema e as instruções de persona integradas neste perfil.',
    unsavedChanges: 'Alterações não salvas',
    loadingSoul: 'Carregando SOUL.md...',
    emptySoul: 'SOUL.md vazio — comece a escrever a persona...',
    saving: 'Salvando...',
    saveSoul: 'Salvar SOUL.md',
    deleteTitle: 'Excluir perfil?',
    deleteDescPrefix: 'Isto excluirá ',
    deleteDescMid: ' e removerá seu diretório ',
    deleteDescSuffix: '. Isso não pode ser desfeito.',
    deleting: 'Excluindo...',
    createDesc:
      'Perfis são ambientes Hermes independentes: configuração, habilidades e SOUL.md separados.',
    nameLabel: 'Nome',
    cloneFromDefault: 'Clonar do padrão',
    cloneFromDefaultDesc:
      'Copiar configuração, habilidades e SOUL.md do seu perfil padrão.',
    invalidName: hint => `Nome inválido. ${hint}`,
    nameRequired: 'O nome é obrigatório.',
    creating: 'Criando...',
    createAction: 'Criar perfil',
    renameTitle: 'Renomear perfil',
    renameDescPrefix:
      'Renomear atualiza o diretório do perfil e quaisquer scripts em ',
    renameDescSuffix: '.',
    newNameLabel: 'Novo nome',
    renaming: 'Renomeando...',
    created: 'Perfil criado',
    renamed: 'Perfil renomeado',
    deleted: 'Perfil excluído',
    setupCopied: 'Comando de configuração copiado',
    soulSaved: 'SOUL.md salvo',
    failedLoad: 'Falha ao carregar perfis',
    failedDelete: 'Falha ao excluir perfil',
    failedCopy: 'Falha ao copiar comando de configuração',
    failedLoadSoul: 'Falha ao carregar SOUL.md',
    failedSaveSoul: 'Falha ao salvar SOUL.md',
    failedCreate: 'Falha ao criar perfil',
    failedRename: 'Falha ao renomear perfil'
  },

  cron: {
    close: 'Fechar cron',
    search: 'Pesquisar tarefas agendadas...',
    refresh: 'Atualizar tarefas agendadas',
    refreshing: 'Atualizando tarefas agendadas',
    loading: 'Carregando tarefas agendadas...',
    states: {
      enabled: 'habilitado',
      scheduled: 'agendado',
      running: 'executando',
      paused: 'pausado',
      disabled: 'desabilitado',
      error: 'erro',
      completed: 'concluído'
    },
    deliveryLabels: {
      local: 'Este desktop',
      telegram: 'Telegram',
      discord: 'Discord',
      slack: 'Slack',
      email: 'E-mail'
    },
    scheduleLabels: {
      daily: 'Diário',
      weekdays: 'Dias úteis',
      weekly: 'Semanal',
      monthly: 'Mensal',
      hourly: 'A cada hora',
      'every-15-minutes': 'A cada 15 minutos',
      custom: 'Personalizado'
    },
    scheduleHints: {
      daily: 'Todos os dias às 9:00',
      weekdays: 'De segunda a sexta às 9:00',
      weekly: 'Toda segunda-feira às 9:00',
      monthly: 'No primeiro dia de cada mês às 9:00',
      hourly: 'No início de cada hora',
      'every-15-minutes': 'A cada 15 minutos',
      custom: 'Sintaxe cron ou linguagem natural'
    },
    days: {
      '0': 'Domingo',
      '1': 'Segunda-feira',
      '2': 'Terça-feira',
      '3': 'Quarta-feira',
      '4': 'Quinta-feira',
      '5': 'Sexta-feira',
      '6': 'Sábado',
      '7': 'Domingo'
    },
    dayFallback: value => `dia ${value}`,
    everyDayAt: time => `Todos os dias às ${time}`,
    weekdaysAt: time => `Dias úteis às ${time}`,
    everyDayOfWeekAt: (day, time) => `Toda ${day} às ${time}`,
    monthlyOnDayAt: (dayOfMonth, time) =>
      `Mensalmente no dia ${dayOfMonth} às ${time}`,
    topOfHour: 'No início de cada hora',
    everyHourAt: minute => `A cada hora às :${minute}`,
    active: (enabled, total) => `${enabled}/${total} ativos`,
    newCron: 'Nova tarefa',
    createFirst: 'Criar primeira tarefa',
    emptyDescNew:
      'Agende um prompt para executar em uma expressão cron. O Hermes o executará e entregará os resultados ao destino que você escolher.',
    emptyDescSearch: 'Tente uma pesquisa mais ampla.',
    emptyTitleNew: 'Nenhuma tarefa agendada ainda',
    emptyTitleSearch: 'Nenhuma correspondência',
    last: 'Último:',
    next: 'Próximo:',
    actionsFor: title => `Ações para ${title}`,
    actionsTitle: 'Ações da tarefa agendada',
    resume: 'Retomar cron',
    pause: 'Pausar cron',
    resumeTitle: 'Retomar',
    pauseTitle: 'Pausar',
    triggerNow: 'Executar agora',
    edit: 'Editar cron',
    deleteTitle: 'Excluir tarefa agendada?',
    deleteDescPrefix: 'Isto removerá ',
    deleteDescSuffix:
      ' permanentemente. Ela parará de ser executada imediatamente.',
    deleting: 'Excluindo...',
    resumed: 'Cron retomado',
    paused: 'Cron pausado',
    triggered: 'Cron executado',
    deleted: 'Cron excluído',
    created: 'Cron criado',
    updated: 'Cron atualizado',
    failedLoad: 'Falha ao carregar tarefas agendadas',
    failedUpdate: 'Falha ao atualizar tarefa agendada',
    failedTrigger: 'Falha ao executar tarefa agendada',
    failedDelete: 'Falha ao excluir tarefa agendada',
    failedSave: 'Falha ao salvar tarefa agendada',
    editTitle: 'Editar tarefa agendada',
    createTitle: 'Nova tarefa agendada',
    editDesc:
      'Atualize o agendamento, prompt ou destino de entrega. As alterações se aplicam na próxima execução.',
    createDesc:
      'Agende um prompt para executar automaticamente. Use sintaxe cron ou uma frase natural como "a cada 15 minutos".',
    nameLabel: 'Nome',
    namePlaceholder: 'Briefing matinal',
    promptLabel: 'Prompt',
    promptPlaceholder:
      'Resumir meus threads não lidos do Slack e me enviar os 5 principais...',
    frequencyLabel: 'Frequência',
    deliverLabel: 'Entregar para',
    customScheduleLabel: 'Agendamento personalizado',
    customPlaceholder: '0 9 * * * ou dias úteis às 9h',
    customHint:
      'Expressão cron, ou frases como "a cada hora" ou "dias úteis às 9h".',
    optional: 'Opcional',
    promptScheduleRequired: 'O prompt e o agendamento são obrigatórios.',
    saveChanges: 'Salvar alterações',
    createAction: 'Criar cron'
  },

  artifacts: {
    search: 'Pesquisar artefatos...',
    refresh: 'Atualizar artefatos',
    refreshing: 'Atualizando artefatos',
    indexing: 'Indexando artefatos de sessões recentes',
    tabAll: 'Todos',
    tabImages: 'Imagens',
    tabFiles: 'Arquivos',
    tabLinks: 'Links',
    noArtifactsTitle: 'Nenhum artefato encontrado',
    noArtifactsDesc:
      'Imagens geradas e saídas de arquivos aparecerão aqui conforme as sessões os produzirem.',
    failedLoad: 'Falha ao carregar artefatos',
    openFailed: 'Falha ao abrir',
    itemsImage: 'imagens',
    itemsLink: 'links',
    itemsFile: 'arquivos',
    itemsGeneric: 'itens',
    zero: '0',
    rangeOf: (start, end, total) => `${start}-${end} de ${total}`,
    goToPage: (itemLabel, page) => `Ir para ${itemLabel} página ${page}`,
    colTitleLink: 'Título do link',
    colTitleFile: 'Nome',
    colTitleDefault: 'Título / nome',
    colLocationLink: 'URL',
    colLocationFile: 'Caminho',
    colLocationDefault: 'Localização',
    colSession: 'Sessão',
    kindImage: 'imagem',
    kindFile: 'arquivo',
    kindLink: 'link',
    chat: 'Chat',
    copyUrl: 'Copiar URL',
    copyPath: 'Copiar caminho'
  },

  sidebar: {
    nav: {
      'new-session': 'Nova sessão',
      skills: 'Habilidades e Ferramentas',
      messaging: 'Mensagens',
      artifacts: 'Artefatos'
    },
    searchAria: 'Pesquisar sessões',
    searchPlaceholder: 'Pesquisar sessões…',
    clearSearch: 'Limpar pesquisa',
    noMatch: query => `Nenhuma sessão corresponde a "${query}".`,
    results: 'Resultados',
    pinned: 'Fixadas',
    sessions: 'Sessões',
    groupAriaGrouped: 'Mostrar sessões como lista única',
    groupAriaUngrouped: 'Agrupar sessões por área de trabalho',
    groupTitleGrouped: 'Desagrupar sessões',
    groupTitleUngrouped: 'Agrupar por área de trabalho',
    allPinned:
      'Tudo aqui está fixado. Desafixe um chat para mostrá-lo nos recentes.',
    shiftClickHint:
      'Shift-clique em um chat para fixar · arraste para reordenar',
    noWorkspace: 'Sem área de trabalho',
    newSessionIn: label => `Nova sessão em ${label}`,
    reorderWorkspace: label => `Reordenar área de trabalho ${label}`,
    showMoreIn: (count, label) => `Mostrar ${count} a mais em ${label}`,
    loading: 'Carregando…',
    loadMore: 'Carregar mais',
    loadCount: step => `Carregar ${step} a mais`,
    row: {
      pin: 'Fixar',
      unpin: 'Desafixar',
      copyId: 'Copiar ID',
      export: 'Exportar',
      rename: 'Renomear',
      archive: 'Arquivar',
      copyIdFailed: 'Não foi possível copiar o ID da sessão',
      actionsFor: title => `Ações para ${title}`,
      sessionActions: 'Ações da sessão',
      sessionRunning: 'Sessão em execução',
      needsInput: 'Precisa da sua entrada',
      waitingForAnswer: 'Aguardando sua resposta',
      renamed: 'Renomeado',
      renameFailed: 'Falha ao renomear',
      renameTitle: 'Renomear sessão',
      renameDesc:
        'Dê a este chat um título memorável. Deixe vazio para limpar.',
      untitledPlaceholder: 'Sessão sem título',
      ageNow: 'agora',
      ageDay: 'd',
      ageHour: 'h',
      ageMin: 'm'
    }
  },

  composer: {
    message: 'Mensagem',
    placeholderStarting: 'Iniciando Hermes...',
    placeholderReconnecting: 'Reconectando ao Hermes…',
    placeholderFollowUp: 'Enviar acompanhamento',
    newSessionPlaceholders: [
      'O que vamos construir?',
      'Dê uma tarefa ao Hermes',
      'O que está pensando?',
      'Descreva o que você precisa',
      'O que devemos resolver?',
      'Pergunte qualquer coisa',
      'Comece com um objetivo'
    ],
    followUpPlaceholders: [
      'Enviar acompanhamento',
      'Adicionar mais contexto',
      'Refinar a solicitação',
      'E a seguir?',
      'Continue',
      'Vá além',
      'Ajustar ou continuar'
    ],
    startVoice: 'Iniciar conversa por voz',
    queueMessage: 'Enfileirar mensagem',
    steer: 'Orientar a execução atual (⌘⏎)',
    stop: 'Parar',
    send: 'Enviar',
    speaking: 'Falando',
    transcribing: 'Transcrevendo',
    thinking: 'Pensando',
    muted: 'Silenciado',
    listening: 'Ouvindo',
    muteMic: 'Silenciar microfone',
    unmuteMic: 'Ativar microfone',
    stopListening: 'Parar de ouvir e enviar',
    stopShort: 'Parar',
    endConversation: 'Encerrar conversa por voz',
    endShort: 'Encerrar',
    stopDictation: 'Parar ditado',
    transcribingDictation: 'Transcrevendo ditado',
    voiceDictation: 'Ditado por voz',
    commonCommands: 'Comandos comuns',
    hotkeys: 'Atalhos',
    helpFooter: 'abre o painel completo · backspace dispensa',
    commandDescs: {
      '/help': 'lista completa de comandos + atalhos',
      '/clear': 'iniciar uma nova sessão',
      '/resume': 'retomar uma sessão anterior',
      '/details': 'controlar nível de detalhe da transcrição',
      '/copy': 'copiar seleção ou última mensagem do assistente',
      '/quit': 'sair do hermes'
    },
    hotkeyDescs: {
      '@': 'referenciar arquivos, pastas, urls, git',
      '/': 'paleta de comandos slash',
      '?': 'esta ajuda rápida (delete para dispensar)',
      Enter: 'enviar · Shift+Enter para nova linha',
      'Cmd/Ctrl+K': 'enviar próximo turno enfileirado',
      'Cmd/Ctrl+L': 'redesenhar',
      Esc: 'fechar popover · cancelar execução',
      '↑ / ↓': 'ciclar popover / histórico'
    },
    attachUrlTitle: 'Anexar uma URL',
    attachUrlDesc:
      'O Hermes buscará a página e a incluirá como contexto para este turno.',
    urlPlaceholder: 'https://exemplo.com.br/post',
    urlHintPre: 'Inclua a URL completa, ex. ',
    attach: 'Anexar',
    queued: count => `${count} Enfileirado${count === 1 ? '' : 's'}`,
    attachmentOnly: 'Turno apenas com anexo',
    emptyTurn: 'Turno vazio',
    attachments: count =>
      `${count} anexo${count === 1 ? '' : 's'}`,
    editingInComposer: 'Editando no compositor',
    editQueued: 'Editar turno enfileirado',
    sendQueuedNext: 'Enviar turno enfileirado a seguir',
    sendQueuedNow: 'Enviar turno enfileirado agora',
    deleteQueued: 'Excluir turno enfileirado',
    previewUnavailable: 'Visualização indisponível',
    previewLabel: label => `Visualizar ${label}`,
    couldNotPreview: label => `Não foi possível visualizar ${label}`,
    removeAttachment: label => `Remover ${label}`,
    dictating: 'Ditando',
    preparingAudio: 'Preparando áudio',
    speakingResponse: 'Falando resposta',
    readingAloud: 'Lendo em voz alta',
    themeSuggestions: 'Sugestões de temas do desktop',
    noMatchingThemes: 'Nenhum tema correspondente.',
    themeTryPre: 'Experimente ',
    themeTryPost: '.',
    attachLabel: 'Anexar',
    files: 'Arquivos…',
    folder: 'Pasta…',
    images: 'Imagens…',
    pasteImage: 'Colar imagem',
    url: 'URL…',
    promptSnippets: 'Snippets de prompt…',
    tipPre: 'Dica: digite ',
    tipPost: ' para referenciar arquivos em linha.',
    snippetsTitle: 'Snippets de prompt',
    snippetsDesc:
      'Escolha um prompt inicial para inserir no compositor.',
    snippets: {
      codeReview: {
        label: 'Revisão de código',
        description:
          'Auditar a alteração atual em busca de regressões, casos de borda perdidos e testes faltantes.',
        text: 'Por favor, revise isso em busca de bugs, regressões e testes faltantes.'
      },
      implementationPlan: {
        label: 'Plano de implementação',
        description:
          'Esboçar uma abordagem antes de mexer no código para manter o diff focado.',
        text: 'Por favor, faça um plano de implementação conciso antes de alterar o código.'
      },
      explainThis: {
        label: 'Explicar isso',
        description:
          'Explicar como o código selecionado funciona e linkar para os arquivos-chave.',
        text: 'Por favor, explique como isso funciona e aponte os arquivos-chave.'
      }
    }
  }
}
