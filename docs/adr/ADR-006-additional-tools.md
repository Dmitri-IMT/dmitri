---
 
## Contexto
 
O scanner de segurança de rede utiliza o Nmap como ferramenta principal de varredura ativa. Porém é preciso a avaliação de um conjunto de ferramentas adicionais de pentest e enumeração para determinar se alguma delas oferece valor que o Nmap/NSE não cobre, e se é viável executá-las no agente. Este ADR registra essas decisões.
 
O scanner opera **externamente aos hosts-alvo** — ele está posicionado na rede local e sonda outros hosts pela rede. Ele **não** possui acesso shell aos hosts-alvo, não realiza pós-exploração e não conduz operações autenticadas, a menos que credenciais sejam explicitamente fornecidas pelo módulo de configuração.
 
Cada ferramenta considerada aqui deve passar por três critérios:
 
1. **Critério de valor** — Ela produz descobertas que o Nmap/NSE não consegue produzir?
2. **Critério ético/legal** — Pode ser usada de forma responsável em um contexto de varredura autorizada pelo dono da rede? Apresenta riscos inerentes que a tornam inadequada para um scanner de uso geral?
3. **Critério de hardware** — Pode rodar adequadamente em um Raspberry Pi 4 (4 GB RAM, ARM64) dentro das restrições do pipeline de varredura?
 
---
 
## Ferramentas Avaliadas

### 1. LinPEAS / WinPEAS

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Enumeração de escalada local de privilégios — executa *dentro* de um host comprometido após acesso inicial |
| **Critério de valor** | LinPEAS/WinPEAS exigem uma sessão shell no host-alvo. A príncipio este scanner não possui acesso shell a alvos. Seria necessário um Reverse Shell ou garantir esse acesso. |
| **Critério ético/legal** | Se for em uma rede que o operador possui, se os hosts-alvo não forem de sua propriedade ou se nenhuma autorização escrita explícita cobrir atividades de pós-exploração, essa prática é proibida. |
| **Critério de hardware** | N/A — os scripts rodam nos alvos, não no Pi. |
| **Decisão** | **REVALIDAR - Futuro(v3)** |
| **Justificativa** | Fora do escopo atual. Porém pode ser possível melhoria para o futuro. |

---
 
### 2. Ferramentas Automatizadas de Reverse Shell (ex.: payloads MSFvenom, reverse shells com netcat)

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Estabelecer um reverse shell de um alvo de volta à máquina do atacante. |
| **Critério de valor** | Reverse shells exigem execução de código no alvo. Este scanner não realiza exploração atualmente. |
| **Critério ético/legal** | Obter execução remota de código não autorizada é ilegal em praticamente toda jurisdição, independentemente da propriedade da rede. Automatizar isso é a definição de um ciberataque. Seria necessário permissão. |
| **Critério de hardware** | N/A. |
| **Decisão** | **EXCLUIR** |
| **Justificativa** | Completamente fora do escopo e dificuldade de implementação. Reverse Shells normalmente funcionam baseado em fluxos específicos e exigem algum tipo de ação da vítima. Dispositivos de rede normalmente não apresentam essas vulnerabilidades. |

---
 
### 3. enum4linux / enum4linux-ng

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Enumeração SMB/NetBIOS — extrai compartilhamentos, usuários, grupos, informações de SO, políticas de senha e informações de impressora de hosts Windows e servidores Samba via chamadas MSRPC autenticadas ou não autenticadas |
| **Critério de valor** | Os scripts NSE do Nmap (`smb-enum-shares`, `smb-enum-users`, `smb-security-mode`) cobrem sobreposição significativa, mas o enum4linux-ng fornece saída estruturada mais rica e lida melhor com casos extremos em configurações SMB modernas (SMBv3). Em redes mistas Windows/Linux/NAS, preenche lacunas que os scripts NSE deixam. |
| **Critério ético/legal** | A enumeração SMB não autenticada consulta serviços SMB publicamente anunciados — os mesmos dados que clientes Windows trocam durante a navegação normal na rede. É de baixo risco em uma varredura interna autorizada. A enumeração autenticada (usando credenciais) requer uma decisão de política explícita. |
| **Critério de hardware** | O enum4linux-ng é um script Python 3 leve com dependências mínimas (impacket, ldap3). Roda confortavelmente no Pi 4. |
| **Decisão** | **INCLUIR — Futuro (v2)** |
| **Justificativa** | O caso de valor é real, mas restrito. Para a v1, o NSE do Nmap (scripts `smb-*`) é suficiente para detectar exposição SMB. O enum4linux-ng deve ser adicionado na v2 junto com o motor de descobertas estendido, como um scanner direcionado invocado apenas quando as portas 139/445 estiverem confirmadamente abertas. A enumeração autenticada está fora do escopo da v1 e requer seu próprio ADR antes da implementação. |

---
 
### 4. Hydra / Medusa (Força Bruta de Credenciais)

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Força bruta automatizada de credenciais e password spraying contra serviços de rede (SSH, FTP, HTTP Basic, SMB, RDP, etc.) |
| **Critério de valor** | Força bruta é um *ataque ativo*, não enumeração passiva. Um scanner de segurança de rede que automaticamente força credenciais em hosts descobertos causaria interrupções de serviço (bloqueios de conta, quedas de serviço), geraria enorme ruído de log e provavelmente violaria os termos de autorização mesmo ao varrer uma rede que o operador possui. |
| **Critério ético/legal** | Ataques automatizados de credenciais contra sistemas que o operador não controla totalmente (ex.: estações de trabalho de funcionários, dispositivos IoT, dispositivos de convidados na rede) são ilegais pela CFAA e equivalentes. Mesmo em infraestrutura totalmente própria, força bruta automatizada sem cobertura explícita de escopo por escrito é considerada acesso não autorizado. Bloqueios de conta constituem impacto de negação de serviço. |
| **Critério de hardware** | Ambas as ferramentas rodam em ARM64 Pi 4 |
| **Decisão** | **MODIFICAR ESCOPO — Futuro(v2)** |
| **Justificativa** | Força bruta de credenciais pode causar problemas na rede se usarmos wordlists completas. Podemos modificar para usar somente usuários e senhas conhecidas, como 'admin/admin', assim asseguramos um número baixo de tentativas mas garantimos que senhas fáceis não vão estar dentro da rede. |
 
 ---
 
### 5. CrackMapExec / NetExec

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Ferramenta de pós-exploração e movimento lateral em toda a rede — enumera SMB/RDP/LDAP/WMI em muitos hosts simultaneamente, pode executar comandos, extrair credenciais, fazer password spraying |
| **Critério de valor** | Na melhor das hipóteses, os recursos de enumeração SMB passiva se sobrepõem ao enum4linux-ng. O restante do conjunto de recursos da ferramenta (execução de comandos, extração de credenciais, pass-the-hash, movimento lateral) é pós-exploração pura. |
| **Critério ético/legal** | O CrackMapExec/NetExec é projetado principalmente para movimento lateral pós-exploração. Implantá-lo como componente de varredura automatizado — mesmo apenas seus módulos de enumeração — introduz risco significativo: gera logs de eventos de Segurança do Windows consistentes com um comprometimento, pode disparar respostas de EDR/AV nos hosts-alvo e poderia ser facilmente mal utilizado se o Pi for acessado por um terceiro não autorizado. |
| **Critério de hardware** | O NetExec é baseado em Python e roda em ARM64, mas seu modelo de conexões concorrentes é intensivo em memória em escala. |
| **Decisão** | **EXCLUIR** |
| **Justificativa** | O valor marginal de enumeração SMB que oferece além dos scripts NSE e do enum4linux-ng não justifica o risco ético, legal e operacional. A ferramenta é desenvolvida para operações ofensivas e é inadequada em um scanner automatizado sempre ativo. |
  
---
 
### 6. testssl.sh

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Auditoria abrangente de configuração SSL/TLS — conjuntos de cifras, versões de protocolo, validade de certificados, vulnerabilidades conhecidas (BEAST, POODLE, Heartbleed, DROWN, ROBOT, LUCKY13, etc.), HSTS, transparência de certificados |
| **Critério de valor** | Os scripts NSE `ssl-*` do Nmap (ssl-enum-ciphers, ssl-heartbleed, ssl-dh-params) cobrem as verificações mais críticas, mas o testssl.sh fornece auditoria TLS substancialmente mais profunda e confiável, melhor suporte a TLS 1.3 moderno, classificação de cifras mais abrangente e saída estruturada mais rica. Para um scanner direcionado a uma rede moderna com serviços HTTPS, isso representa um sinal de valor real. |
| **Critério ético/legal** | A inspeção de handshake TLS é uma técnica de observação passiva — ela completa o handshake TLS para ler a configuração do servidor, mas não o explora. Isso é equivalente ao que qualquer cliente HTTPS faz. Nenhum dado é exfiltrado. Nenhuma interrupção de serviço ocorre. |
| **Critério de hardware** | O testssl.sh é um script bash sem dependências pesadas de runtime (requer bash, openssl e ferramentas Unix padrão, todas presentes no Raspberry Pi OS). O uso de memória e CPU é baixo por host. Em escala de rede, deve ter sua taxa limitada para evitar sobrecarregar o Pi. |
| **Decisão** | **INCLUIR — Futuro (v2)** |
| **Justificativa** | Configuração incorreta de TLS é uma das descobertas mais comuns e de maior valor em varreduras de redes internas. O testssl.sh roda no hardware do Pi, é juridicamente inequívoco e preenche uma lacuna genuína na cobertura NSE do Nmap. Deve ser adicionado na v2 como um scanner direcionado invocado apenas quando portas TLS (443, 8443, 993, 995, 465, etc.) estiverem confirmadamente abertas, com descobertas normalizadas no motor de descobertas. |

---

### 6.1 Nikto e ffuf/gobuster

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Análise web direcionada após detecção de HTTP/HTTPS: Nikto para checks conhecidos e ffuf/gobuster para enumeração e classificação de conteúdo encontrado. |
| **Critério de valor** | Complementam o Nmap/NSE em superfícies web, registrando caminhos encontrados e classificando exposição de arquivos/diretórios sensíveis, painéis administrativos e misconfigurações comuns de servidor web. |
| **Critério ético/legal** | Adequados apenas em redes autorizadas, com escopo condicionado a serviços web detectados, timeouts e wordlists pequenas/controladas. Não devem executar autenticação, exploração ou extração de dados. |
| **Critério de hardware** | Leves quando executados com baixa concorrência e por alvo selecionado; adequados ao Raspberry Pi dentro dos limites de timeout do pipeline. |
| **Decisão** | **INCLUIR — Futuro (v2)** |
| **Justificativa** | A implementação deve invocar essas ferramentas somente depois que o Nmap confirmar portas/serviços web abertos. Ausência de binário ou wordlist deve causar skip não fatal, preservando o fluxo principal de scan. |

---
 
### 7. OpenVAS

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Scanner de vulnerabilidades completo baseado em feed — executa mais de 100.000 Testes de Vulnerabilidade de Rede (NVTs/VTs) contra hosts-alvo, cobrindo CVEs conhecidos, configurações incorretas de serviços e verificações autenticadas de software instalado. É o componente scanner da Greenbone Community Edition (GCE), que inclui também um daemon de gerenciamento (gvmd), interface web (GSA) e banco de dados Redis. |
| **Critério de valor** | O OpenVAS oferece uma profundidade de verificação de CVE muito superior à do Nmap NSE, com feed atualizado diariamente e correlação com CVSS. Para um scanner de vulnerabilidades dedicado, é a referência da indústria no ecossistema open source. No entanto, o NSE do Nmap — especialmente com o script vulners — cobre os casos de uso mais relevantes do projeto sem a sobrecarga arquitetural do OpenVAS. |
| **Critério ético/legal** | O OpenVAS é uma ferramenta legítima e amplamente utilizada para gestão de vulnerabilidades em redes autorizadas. Suporta varreduras não autenticadas (externas) e autenticadas (com credenciais SSH/SMB). As varreduras autenticadas exigem credenciais explícitas fornecidas pelo operador e são fora do escopo da v1. |
| **Critério de hardware** | A GCE é uma pilha de múltiplos serviços — openvas-scanner, gvmd, ospd-openvas, notus-scanner, Redis, PostgreSQL e um servidor web — que na prática exige no mínimo 4 GB de RAM só para a sincronização do feed funcionar sem OOM. Testes documentados no Pi 4 mostram que varreduras com configurações padrão travam ou matam processos por falta de recursos; mesmo com configurações reduzidas (3 hosts / 5 NVTs simultâneos), uma varredura de rede /24 pode levar vários dias. O Pi 4 com 4 GB de RAM está no limite absoluto de viabilidade, com a RAM praticamente toda consumida pela stack GCE, sem sobra para o agente Python, o pipeline de varredura e os outros módulos do projeto. |
| **Decisão** | **EXCLUIR** |
| **Justificativa** | A barreira de hardware é intransponível no contexto deste projeto. O OpenVAS não é uma ferramenta que se encaixa no modelo de agente leve rodando no Pi ao lado dos outros módulos. A cobertura de CVEs que ele oferece a mais em relação ao Nmap NSE + vulners NSE não justifica substituir toda a arquitetura do agente por uma stack de serviços pesada. Se o projeto evoluir para um appliance dedicado exclusivamente ao OpenVAS, isso requer um novo ADR e revisão da arquitetura. |
  
---
 
### 8. Vuls

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Scanner de vulnerabilidades agentless escrito em Go — conecta-se a hosts Linux/FreeBSD via SSH, enumera os pacotes instalados, e cruza essa lista com múltiplos bancos de dados de CVEs (NVD, JVN, OVAL, RHSA, Changelog). Não executa varredura de portas; pressupõe acesso SSH aos hosts-alvo. |
| **Critério de valor** | Reprovado para este caso de uso. O Vuls é projetado para gerenciamento de vulnerabilidades em servidores que o operador controla e nos quais tem acesso SSH autorizado, tipicamente a própria infraestrutura (servidores de aplicação, VMs, containers). Ele não é um scanner de rede externo: não descobre hosts, não varre portas e não funciona em hosts para os quais o operador não possui credenciais SSH. O scanner deste projeto opera externamente à rede e descobre dispositivos arbitrários (IoT, workstations, dispositivos de terceiros) para os quais não há e não deve haver credenciais SSH disponíveis.Porém, pode ser uma melhoria futura. |
| **Critério ético/legal** | Neutro em si mesmo, mas problemático no contexto. Conectar-se via SSH a hosts de terceiros presentes na rede (dispositivos de convidados, equipamentos de funcionários) sem autorização explícita constitui acesso não autorizado, mesmo em uma rede própria. |
| **Critério de hardware** | O Vuls é um binário Go leve, sem dependências pesadas. Rodaria sem problemas no Pi 4. |
| **Decisão** | **REVALIDAR - Futuro(v3)** |
| **Justificativa** | O Vuls é excelente para inventário e gestão de vulnerabilidades em infraestrutura própria e gerenciada, mas este projeto é um scanner de rede externo que opera sem credenciais nos hosts descobertos. Porém, no futuro seria possível revalidar escopo, para que possamos fazer leituras mais personalizadas das redes dos clientes. |
  
---
 
### 9. vulners NSE

| Atributo | Avaliação |
|----------|-----------|
| **Propósito** | Script NSE de terceiro (não incluído no Nmap por padrão) que, após a detecção de versão (`-sV`), envia o CPE (Common Platform Enumeration) de cada serviço identificado para a API pública do Vulners.com e retorna a lista de CVEs conhecidos com pontuação CVSS correspondente. Complementa o script `--script vuln` nativo do Nmap, que cobre ~150 vulnerabilidades com verificações ativas, com uma correlação passiva de CVE baseada em banco de dados atualizado continuamente. |
| **Critério de valor** | Preenche diretamente a lacuna mais importante do Nmap NSE puro: o script `vuln` nativo verifica um conjunto fixo de vulnerabilidades conhecidas; o vulners NSE mapeia a versão de qualquer serviço identificado contra toda a base de dados do Vulners (250+ GB de CVEs, advisories e exploits). O resultado é uma cobertura de CVE muito mais ampla sem nenhuma sonda ativa adicional — apenas uma consulta à API com nome do software e versão. Suporta filtro por `mincvss` para controle de ruído de falsos positivos de baixa severidade. |
| **Critério ético/legal** | O script é passivo: não tenta explorar nenhuma vulnerabilidade, não envia dados além do nome e versão do software (CPE) para a API externa. A única consideração é a privacidade: os nomes e versões de software dos hosts internos trafegam para servidores do Vulners.com. Em redes com política de não exfiltração de dados de inventário, isso deve ser documentado. Para ambientes com restrição de saída de internet, o script simplesmente não retorna resultados — não causa erro ou falha na varredura. |
| **Critério de hardware** | É um script Lua executado pelo Nmap, sem overhead adicional além da latência de rede para a chamada de API. Sem impacto mensurável no Pi. |
| **Decisão** | **INCLUIR** |
| **Justificativa** | O vulners NSE se integra diretamente ao pipeline de varredura existente (Nmap + NSE), não requer nova infraestrutura, não adiciona dependências pesadas, e expande drasticamente a cobertura de CVE sem qualquer sonda ativa adicional. Deve ser incluído no módulo de varredura de portas e detecção de serviços e suas saídas integradas ao motor de descobertas como fonte primária de correlação de CVE. O filtro `mincvss` deve ser configurável via IMPL-01 (padrão sugerido: 5.0 para reduzir ruído). |
  
---

### Distinção Passivo vs. Ativo
 
As ferramentas incluídas neste projeto (descoberta Nmap, varredura de portas, detecção de serviços NSE e as adições da v2 — Nikto, ffuf/gobuster, enum4linux-ng e testssl.sh) devem permanecer no espectro de enumeração autorizada e de baixo impacto: elas leem informações que os serviços anunciam publicamente ou fazem requisições controladas contra serviços já detectados. Elas não se autenticam, não executam código nos alvos e não tentam explorar vulnerabilidades.
 
Ferramentas que cruzam para o território de ataque ativo — força bruta de credenciais, execução de código, reverse shells, movimento lateral — estão **categoricamente fora do escopo da v1**, porque:
 
- Causam dano mensurável (bloqueios de conta, interrupções de serviço, alertas de AV).
- Exigem autorização de teste de penetração documentada e assinada para ser legal.
- São incompatíveis com o propósito declarado do sistema (descoberta e relatório de descobertas).
 
### Sensibilidade dos Dados
 
Os resultados de varredura podem conter informações sensíveis (portas abertas, banners de serviço, assuntos de certificados TLS, nomes de compartilhamentos SMB). O backend deve impor controles de acesso apropriados. As descobertas não devem ser transmitidas por canais não criptografados.
 
### Divulgação Responsável
 
Se o scanner descobrir uma vulnerabilidade crítica em um host que o operador não possui (ex.: dispositivo de convidado, laptop de um prestador de serviços), o operador é responsável pelo tratamento adequado. A documentação do sistema (DOC-01) deve incluir orientações sobre obrigações de divulgação responsável.
 
---

 ## Consequências
 
- **O escopo da v1 está fixo**: Apenas Nmap + NSE. Nenhuma ferramenta ativa adicional.
- **Nova proposta de futuro** pode referenciar Nikto, ffuf/gobuster, enum4linux-ng e testssl.sh como fontes futuras de dados, mas não deve depender deles para a entrega da v1.
- **Qualquer adição de ferramenta na v2 ou v3 requer seu próprio card de implementação** no backlog e deve estar em conformidade com a arquitetura do pipeline de varredura (A-04) e o contrato de API (A-03).
- **As ferramentas "EXCLUIR" não devem ser adicionadas ao projeto sob nenhuma circunstância** sem um novo ADR, uma revisão legal e aprovação explícita do instrutor/stakeholder.
- **Vamos fazer uma diferenciação entre versões de projeto**: a v1 vai ser o scanner principal, v2 um scanner mais potente com scripts de penetração basicos somente para verificação, v3 uma solução mais personalizada com possibilidade de rodar scripts avançados usando credenciais da empresa.
 
---

## Referências
 
- [Documentação Nmap NSE](https://nmap.org/nsedoc/)
- [enum4linux-ng GitHub](https://github.com/cddmp/enum4linux-ng)
- [testssl.sh GitHub](https://github.com/drwetter/testssl.sh)
- [Nikto GitHub](https://github.com/sullo/nikto)
- [ffuf GitHub](https://github.com/ffuf/ffuf)
- [OpenVAS / Greenbone Community Edition — Documentação](https://greenbone.github.io/docs/latest/)
- [Vuls GitHub](https://github.com/future-architect/vuls)
- [vulners NSE — Documentação oficial Nmap](https://nmap.org/nsedoc/scripts/vulners.html)
- [nmap-vulners GitHub](https://github.com/vulnersCom/nmap-vulners)
- OWASP Testing Guide — Testes de Infraestrutura de Rede
