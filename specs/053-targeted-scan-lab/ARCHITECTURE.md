# ARCHITECTURE — Laboratório local para um scan direcionado

## System context

Ampliar o simulador local existente, que já executa daemon real, backend, banco e alvo Samba. O caminho do ensaio é: comando local → `ScanRunner` → descoberta Nmap → seleção em `targeted/selection.py` → execução serial em `targeted/stage.py` → normalização → upload assinado → backend local. O modo `extensive` habilita a etapa direcionada e procura as portas padrão do laboratório; `quick` e `standard` não a habilitam. O modo `nspi` tem inspeções industriais adicionais, portanto não é o perfil principal deste ensaio.

Não alterar o código de seleção nem chamar as ferramentas diretamente para produzir a prova de aceitação. Smoke checks diretos podem diagnosticar o alvo antes do scan; a aprovação depende do resultado do fluxo completo.

## Objetivo da demonstração e estratégia de cobertura

Este laboratório é orientado a uma demonstração de alto rendimento: um único scan deve mostrar o máximo de resultados úteis que o fluxo atual do Dmitri consegue produzir para os serviços presentes. A meta é diversidade de achados verificáveis por serviço, não só fazer cada executável iniciar. Não ampliar adaptadores, parsers ou políticas de produção para fabricar cobertura dentro deste trabalho; se o fluxo atual não representar um sinal, registrar a lacuna para uma decisão separada.

Antes de congelar cada alvo, revisar os seletores, adaptadores, parsers e políticas correspondentes e criar uma matriz de planejamento com: ferramenta, endpoint selecionado, condição do alvo, evidência nativa esperada, finding/identificador aceito e severidade ou categoria quando disponível. Essa revisão orienta os fixtures e evita escolher uma condição que a ferramenta relate, mas que o Dmitri descarte. A matriz distingue:

- **Obrigatório**: ao menos um achado suportado por ferramenta, conforme os critérios de aceitação.
- **Adicional planejado**: outros sinais suportados e independentes que aumentam a demonstração, sem duplicar o mesmo problema com nomes diferentes.
- **Lacuna conhecida**: sinal que uma ferramenta pode observar, mas que o parser/política atual não persiste como finding; documentar sem apresentá-lo como resultado do Dmitri.

### Cobertura Nmap/NSE no perfil `extensive`

O scan já configura `vulners`, `smb-protocols`, `smb2-security-mode`, `ssh-auth-methods`, `http-title`, `http-server-header`, `ssl-cert`, `ssl-enum-ciphers`, `http-methods`, `ftp-anon` e `banner` em `hardware-agent/src/agent/config.py`. Confirmar que `vulners.nse` está instalado e carregável pela imagem, pois a imagem Debian instala Nmap mas o script Vulners é externo ao pacote em uso.

| Serviço | NSE existente | Condição para produzir sinal útil | Resultado permitido na apresentação |
|---------|---------------|-----------------------------------|-------------------------------------|
| HTTP | `http-methods`, `http-title`, `http-server-header`, `vulners` | Aceitar `TRACE` ou outro método arriscado reconhecido por `http-methods`; expor versão/CPE verdadeira e identificável | Finding `http-methods`; metadados de título/banner; CVE somente se lookup CPE estruturado passar pelo parser |
| HTTPS | `ssl-cert`, `ssl-enum-ciphers`, `vulners` | Certificado de laboratório autoassinado e, se os checks reais confirmarem, assinatura fraca/chave menor que 2048; habilitar apenas TLS/cifras de laboratório que o parser reconheça | Findings independentes de certificado, protocolos/cifras e grau; CVE somente com CPE e CVE aceitos |
| SSH | `ssh-auth-methods`, `vulners` | Expor autenticação por senha com credencial fictícia local e algoritmos obsoletos para `ssh-audit`; confirmar CPE/versão do daemon | Finding de autenticação e issues de algoritmo; Vulners condicionado à correlação CPE real |
| FTP | `ftp-anon`, `banner`, `vulners` | Login anônimo aceito em modo somente leitura; versão real identificável | Finding NSE de login anônimo; Vulners apenas com versão correlacionada |
| SMB | `smb-protocols`, `smb2-security-mode`, `vulners` | Habilitar SMBv1 e assinatura não obrigatória na rede isolada, além da enumeração guest/null; identificar versão verdadeira | Findings de SMBv1 e assinatura quando reportados; Vulners condicionado à CPE |
| Telnet | `banner`, `vulners` | Banner/versão real identificável; protocolo cleartext | Evidência de banner e finding Vulners apenas se o lookup CPE passar pelo parser; `telnet-check` prova conexão clara |

O perfil `extensive` **não** executa `smb-vuln-ms17-010`; esse script só existe no perfil `nspi`, cujo fluxo não executa a etapa direcionada. Não adicionar o script ou apresentar MS17-010 como achado do Samba comum. Se a demonstração exigir essa classe de finding, será necessário decidir separadamente por um alvo realmente compatível e por alterar o conjunto NSE de `extensive`. O script `vulners` produz correlação de versão/CPE, não confirmação de exploração. A rede de alvos é `internal`; ainda assim, o agente tem saída pela rede padrão do simulador para consultas remotas do script, quando disponível.

O critério de qualidade é o conjunto de achados persistidos no mesmo scan. Para cada achado apresentado, preservar a ligação a IP/hostname, porta, ferramenta e evidência nativa disponível. A matriz final deve também mostrar ferramentas/unidades omitidas, erros, resultados sem achados e seus motivos. Validar as condições dos alvos com smoke checks diretos antes do único scan integrado destinado à apresentação; esse scan deve ser completo, identificado e consultável, sem somar findings de execuções separadas.

## Topologia

A rede Docker interna dos alvos é `172.31.13.0/28`; o agente e cinco alvos têm endereços fixos, enquanto backend, Postgres e worker permanecem na rede de aplicação. O scan usa `172.31.13.0/29` para conter apenas os alvos .2–.6; o agente fica em .13 e o gateway em .14, fora dessa faixa. Nenhum serviço de alvo publica portas no host.

Manter serviços vulneráveis sem `ports:` no Compose e sem acesso à rede implantada. O `--nspi` connect-only não deve receber os novos alvos nem um comando de scan automatizado. A operação `stop` existente remove os volumes locais. Como a descoberta pode incluir o IP do próprio agente dentro da faixa, a verificação filtra apenas os IPs dos alvos; o agente não deve oferecer serviços nas portas avaliadas.

| Alvo | Porta | Serviço/condição planejada | Seleção direcionada e NSE | Evidência mínima |
|------|-------|----------------------------|------------------|------------------|
| web | 80/tcp | HTTP com condição reportável pelo banco fixado do Nikto; arquivos/diretórios fictícios selecionados entre regras do ffuf; `TRACE` permitido; versão/CPE real | ffuf, nikto; NSE `http-methods`, `vulners` | Finding ffuf confirmado; Nikto é registrado como evidência inconclusiva pela política atual; método arriscado; CVE somente após lookup CPE aceito |
| web | 443/tcp | HTTPS com certificado de laboratório autoassinado e condições TLS escolhidas após checks reais; mesmos caminhos web; versão/CPE real | ffuf, nikto, testssl.sh; NSE `ssl-cert`, `ssl-enum-ciphers`, `vulners` | Findings suportados de certificado/protocolo/cifra e saídas direcionadas; CVE validada pelo parser |
| ssh | 22/tcp | OpenSSH de laboratório com algoritmos obsoletos e autenticação por senha habilitada para uma conta fictícia isolada; versão real | ssh-audit; NSE `ssh-auth-methods`, `vulners` | Issues de algoritmo, senha exposta e correlação CPE validada quando disponível |
| ftp | 21/tcp | FTP claro com banner/FEAT, login anônimo somente leitura, inventário fictício e versão real | ftp-check; NSE `ftp-anon`, `banner`, `vulners` | `ftp:cleartext`, `ftp:anonymous-login`, finding NSE e CPE/CVE aceitos se disponíveis |
| smb | 445/tcp (139 opcional) | Samba existente com sessão guest/null, enumeração, SMBv1 e assinatura não obrigatória; versão real | enum4linux-ng; NSE `smb-protocols`, `smb2-security-mode`, `vulners` | Achados de sessão/SMBv1/assinatura conforme evidência estruturada; CPE/CVE aceitos se disponíveis |
| telnet | 23/tcp | daemon Telnet de laboratório com banner/versão real, sem contas úteis | telnet-check; NSE `banner`, `vulners` | `telnet:cleartext`; CVE somente com CPE e finding Vulners suportados |

O alvo web precisa responder com conteúdo real e rotas desconhecidas devem retornar 404. O validador do ffuf exige duas atribuições em `.env`; usar valores inventados como `LAB_USER=demo` e `LAB_TOKEN=not-a-secret`. A política atual também reconhece assinaturas para arquivos VCS, chaves, configurações, backups, dumps, logs, endpoints de diagnóstico, métricas, listagem de diretório e páginas administrativas; consultar `hardware-agent/tests/unit/test_targeted_web.py` e o código correspondente para selecionar fixtures distintos e inofensivos, sem chaves utilizáveis, credenciais reais ou dados pessoais. Arquivos ocultos são copiados de fixtures com nomes diferentes durante o build: `.dockerignore` exclui arquivos chamados `.env`. Evitar um catch-all HTTP que devolva 200 para qualquer caminho, pois ele confunde a linha de base do ffuf. Para Nikto, escolher condições cujo teste da versão fixada produza IDs/categorias aceitos pela política carregada de `db_tests`; conferir a evidência nativa antes de afirmar os achados. Não atribuir CVE ao laboratório por versão aparente.

O certificado TLS é gerado em runtime com chave privada restrita ao container. Uma falha de confiança (autoassinado) pode ser um dos sinais; revisar também os checks de protocolo/cifras suportados e selecionar uma configuração de laboratório que gere mais achados distintos aceitos pelo parser. Para SSH, fixar os algoritmos obsoletos de KEX/cifra/MAC que a versão instalada do ssh-audit marque como issues processadas pelo parser; habilitar autenticação por senha apenas para a conta fictícia do laboratório isolado, sem credenciais reais. Para FTP/SMB, priorizar as condições de enumeração e acesso anônimo que os parsers transformam em findings, sem habilitar escrita. O Telnet deve oferecer um serviço Telnet real para o Nmap classificar corretamente o endpoint; a riqueza de seus findings fica limitada ao que `telnet-check` persiste.

## Dependências do agente

A imagem do agente local deve instalar Nmap, `vulners.nse` de commit/hash fixados e todas as ferramentas direcionadas com versões/commits verificáveis. Atualizar o índice do Nmap e validar `nmap --script-help vulners` durante o build. Instalar o banco `db_tests` no caminho esperado por `targeted/web.py`, wordlist ffuf em caminho aceito pelo adaptador e dependências do enum4linux-ng. `ssh-audit` já é dependência Python do agente; conferir seu executável no `PATH`. Reusar os pins de `hardware-agent/scripts/provision-targeted-tools.sh` quando compatíveis com a arquitetura da imagem do simulador; esse script aceita ARM, e a imagem local pode ser amd64, então a instalação Docker precisa tratar essa diferença explicitamente. O agente precisa de DNS/HTTPS de saída para lookup remoto do Vulners; a rede interna de alvos não oferece saída. Não adicionar lógica de simulação aos adaptadores de produção.

O estágio executa ferramentas em série. Há timeout por unidade (ffuf 480 s, Nikto 800 s, testssl 300 s, enum4linux 180 s, ssh-audit 60 s, FTP 15 s, Telnet 10 s). `extensive` usa ao menos 1800 s e amplia o orçamento pela soma dos limites das unidades selecionadas e 5 s de limpeza por unidade; `max` mantém 3600 s e `nspi` 1800 s fixos. Com dois endpoints web, o laboratório planeja nove unidades e requer até 3170 s incluindo limpeza, abaixo do teto `max` e do limite de 96 unidades; um plano grande em `nspi` pode deixar unidades posteriores omitidas por `stage_budget`. Medições reais do perfil amplo Nikto levaram 565 s em HTTP e 582 s em HTTPS sem atingir o teto nativo de 600 s; a configuração adotada é 700 s nativos e 800 s externos. O ensaio registra unidades planejadas, concluídas, omitidas e motivos.

## Contratos e verificação

- Um comando do simulador deve enfileirar exatamente um scan `extensive` para a faixa fixa do laboratório. Preservar o comando genérico atual e o bloqueio de `--nspi scan`.
- A matriz de verificação deve consultar um único scan local concluído e associar cada achado a ferramenta, porta/IP e metadados de cobertura. Como achados da mesma ferramenta podem ser normalizados ou filtrados, usar os campos realmente persistidos; não inferir sucesso apenas da contagem total de findings.
- O relatório de apresentação deve listar o conjunto completo de achados persistidos desse scan, agrupado por endpoint e ferramenta, além dos mínimos obrigatórios e das lacunas. Contagens ajudam a resumir, mas não substituem a evidência individual nem justificam findings duplicados.
- Um relatório de ferramenta pode terminar sem finding quando a condição não é suportada; isso é falha do cenário esperado, não falha genérica do scan. Guardar saída diagnóstica limitada e nunca imprimir token de API, chave privada ou conteúdo do `.env` fictício em logs desnecessários.
- Prova manual final: start isolado, readiness dos cinco alvos, um scan de apresentacao, matriz das sete ferramentas, achados minimos/adicionais e lacunas. Scans diagnosticos nao sao agregados. O ensaio de 2026-10-21 (`8d1fa696-6da0-4289-a959-400fe47fe848`) falhou por timeouts Nikto, falha parcial testssl e FTP chroot. O diagnostico de 2026-10-22 (`45039520-8e46-4f92-806f-89c729c63c40`) persistiu 80 achados em cinco hosts, mas Nikto atingiu o antigo teto de 250 s. Apos corrigir FTP, faixa e Git Bash, a apresentacao `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f` completou e passou no verificador: 5 hosts, 90 achados. JSON unico: `../../scan-results/targeted-lab-2026-10-22.json`. Nikto completou em HTTP/HTTPS; evidencia permanece inconclusiva pela politica atual.

## New files and naming

| Layer | Path | Mudança planejada |
|-------|------|-------------------|
| Compose lab | `docker/pi-simulator/compose.lab.yaml` | overlay com rede isolada, IPs fixos, serviços do lab e agente dual-homed; o Compose padrão continua preservando o alvo SMB antigo |
| Agent image | `docker/pi-simulator/agent.Dockerfile` | ferramentas e wordlist na imagem local |
| Web image | `docker/pi-simulator/web-target.Dockerfile` | HTTP/HTTPS e fixtures web |
| Web config | `docker/pi-simulator/targets/web/nginx.conf` | rotas, listagem/cabeçalhos de laboratório |
| Web fixture | `docker/pi-simulator/targets/web/env.fixture` | dados fictícios copiados para `.env` no container |
| Web fixture | `docker/pi-simulator/targets/web/config.fixture` | segundo arquivo identificável, se necessário para Nikto |
| SSH image | `docker/pi-simulator/ssh-target.Dockerfile` | daemon SSH e host keys efêmeras |
| SSH config | `docker/pi-simulator/targets/ssh/sshd_config` | algoritmos fracos controlados e login por senha limitado à credencial fictícia do laboratório isolado |
| FTP image | `docker/pi-simulator/ftp-target.Dockerfile` | servidor FTP local |
| FTP config | `docker/pi-simulator/targets/ftp/vsftpd.conf` | acesso anônimo e canal claro |
| SMB lab image | `docker/pi-simulator/target-lab.Dockerfile` | Samba configurado para a demonstração sem mudar a imagem do compose NSPI |
| SMB lab config | `docker/pi-simulator/smb-lab.conf` | sessão guest/null, SMBv1 e assinatura não obrigatória, share somente leitura |
| Telnet image | `docker/pi-simulator/telnet-target.Dockerfile` | daemon e banner Telnet |
| Simulator CLI | `simulator.sh` | start/scan/verify/stop do projeto isolado, sem mudar a proteção do modo implantado |
| Verifier | `docker/pi-simulator/verify_targeted_scan.py` | matriz e exit code por cenário do scan local |
| Runbook | `docker/pi-simulator/README.md` | pré-requisitos, execução de um scan, expectativa e limpeza |
| Integration test | `docker/pi-simulator/tests/test_targeted_lab.py` | configuração, seleção e matriz de verificação com dados reais/representativos |
| Code map | `.claude/docs/infra/pi-simulator.md` | registrar a nova topologia após implementar |

## Testing expectations

- Teste estático da configuração Compose: rede de alvos interna, nenhum `ports:` nos serviços vulneráveis, IPs distintos, ferramentas/scripts fixados na imagem e entrada de `--nspi` inalterada.
- Teste da matriz com payloads de scan completos e incompletos: deve falhar para ferramenta omitida, falha, sem evidência esperada ou endpoint incorreto.
- Smoke checks locais dos protocolos e Nmap `-sV` para provar nomes de serviço antes do scan.
- Ensaio completo uma vez: build, serviços saudáveis, um comando de scan `extensive`, consulta da API e matriz aprovada para targeted/NSE/Vulners. Sem mock dos sete adaptadores.

## Decisions to validate during implementation

### Laboratorio para Raspberry fisico (implementacao atual)

O Compose de `docker/targeted-lab/` inicia somente alvos, sem agente, API ou banco de resultados. O Raspberry fisico executa o hardware-agent e escaneia seis enderecos LAN em uma VM Linux com Docker Engine e rede macvlan. Docker Desktop no Windows nao suporta macvlan. Enderecos do `.env.example` sao apenas ilustrativos; reservar seis IPs fora do DHCP e configurar interface, subnet e gateway reais antes de iniciar.

Alvos: web/HTTPS, SSH, FTP, SMB, Telnet e MySQL Community Server `5.7.30`, com dados/credenciais ficticios e sem escrita anonima ou Telnet com autenticacao. Oracle lista MySQL Server `5.7.30 and prior` como afetado por CVE-2020-14559 e CVE-2020-14553. `extensive` cobre a porta 3306 por estar nos top 10.000, faz `-sV` e executa `vulners` com mincvss 3.0; `mysql-info` nao esta selecionado. Sucesso requer observar identificacao/CPE e correlacao persistida, nao presumir finding. CVE/CPE e correlacao por versao nao provam aplicabilidade nem exploracao. Fonte primaria: [Oracle CPU July 2020](https://www.oracle.com/security-alerts/cpujul2020.html); [Nmap vulners NSE](https://nmap.org/nsedoc/scripts/vulners.html).

Antes do unico scan pelo Raspberry: conferir conectividade aos seis IPs, verificacao de servicos/versoes e disponibilidade do backend no agente. Depois validar o JSON persistido por alvo, ferramenta, evidencias e cobertura. A apresentacao no relatorio explicado e o caminho Groq sao uma etapa posterior; ver [SCAN-JSON-AND-AI.md](./SCAN-JSON-AND-AI.md). Nao usar os 90 findings do scan anterior como resultado do novo topology.

### JSON do Raspberry e download explicado: revisão posterior

O [registro do fluxo atual](./SCAN-JSON-AND-AI.md) documenta o JSON do agente, a seleção limitada de achados enviada ao Groq e o caminho da opção **Baixar relatório explicado**. O download atual usa análise já disponível e conteúdo educativo; não envia automaticamente o JSON completo à IA. A revisão dessa integração foi adiada pelo usuário. Nenhuma mudança de IA faz parte da implementação atual do laboratório.

### Correção e validação iniciadas em 2026-10-22

A seleção automática por serviço em `nspi` e `extensive` permanece inalterada. O adaptador Nikto mantém o perfil amplo `2345789acf` e agora usa pausa de 0,05 s, limite nativo de 700 s e timeout externo de 800 s, baseados em medições HTTP/HTTPS de 565/582 s e 5.920 requisições por endpoint. O testssl mantém chamada, parser e política; seu diagnóstico agora inclui linhas de erro/aviso/problema sanitizadas e limitadas da saída capturada. A causa do antigo código 1 do testssl não foi reproduzida: a chamada direta terminou com código 0 em 190 s e o ensaio diagnóstico também concluiu com código 0.

O plano de correcao de Nikto/testssl registra causas, medicoes, ganhos e criterios. Implementacao, testes focados, unidades Nikto, verificador e resultado integrado final passaram.

- A assinatura exata de Nikto aceita pela política e o algoritmo SSH marcado `fail` dependem das versões instaladas; fixar ambos depois de observar a saída real e registrar no runbook.
- Confirmar se a falha TLS autoassinada gera achado suportado. Se não, ajustar somente a configuração TLS do alvo e registrar o motivo.
- Confirmar que enum4linux-ng relata `guest`/`null` no JSON para o Samba configurado; um compartilhamento aberto sozinho pode ser classificado como evidência inconclusiva pelo parser atual.
