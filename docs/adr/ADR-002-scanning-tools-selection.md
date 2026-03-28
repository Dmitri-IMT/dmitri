# ADR-002: Seleção de Ferramentas de Varredura

**Sprint 1 · R-02**

---

## 1. Contexto

O escopo de operação é fundamental: o scanner opera **externamente aos hosts-alvo** — posicionado na rede local e sondando outros hosts pela rede. Ele não possui acesso shell aos alvos, não realiza pós-exploração e não conduz operações autenticadas, salvo configuração explícita.

A solução é projetada como uma **plataforma modular de varredura**, onde cada etapa constrói sobre a anterior:

1. Descoberta de rede (hosts e topologia)
2. Descoberta de portas (identificação de superfície de ataque)
3. Detecção de serviços e versões
4. Análise direcionada de vulnerabilidades (baseada nos serviços detectados)

---

## 2. Critérios de Avaliação

Cada ferramenta avaliada deve satisfazer três critérios obrigatórios, alinhados com o R-06:

1. **Critério de Valor** — Produz descobertas que o Nmap/NSE não consegue produzir?
2. **Critério Ético/Legal** — Pode ser usada de forma responsável em varredura autorizada? Apresenta riscos inerentes que a tornam inadequada para um scanner de uso geral?
3. **Critério de Hardware** — Pode rodar adequadamente no Raspberry Pi 4 (4 GB RAM, ARM64) dentro das restrições do pipeline de varredura?

---

## 3. Ferramentas Avaliadas

### 3.1 Nmap


| Atributo                 | Avaliação                                                                                                   |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Propósito**            | Motor principal de varredura de rede — descoberta de hosts, varredura de portas, detecção de serviços e SO. |
| **Critério de Valor**    | Cobertura abrangente com baixo consumo de recursos. Altamente configurável e extensível via NSE.            |
| **Critério Ético/Legal** | Ferramenta de auditoria padrão da indústria. Uso ético em redes autorizadas é inequívoco.                   |
| **Critério de Hardware** | Consumo mínimo de CPU e memória. Roda perfeitamente no Pi 4.                                                |
| **Decisão**              | ✅ **INCLUIR — v1**                                                                                          |


**Capacidades:**

- Descoberta de hosts (`-sn`)
- Varredura de portas: SYN Scan (`-sS`), TCP Connect (`-sT`), UDP Scan (`-sU`)
- Detecção de serviços/versões (`-sV`)
- Detecção de SO (`-O`)

---

### 3.2 Nmap Scripting Engine (NSE)


| Atributo                 | Avaliação                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Propósito**            | Estende o Nmap com scripts Lua para detecção de vulnerabilidades, enumeração e análise de serviços. |
| **Critério de Valor**    | Expande dramaticamente as capacidades do Nmap sem nenhuma dependência adicional.                    |
| **Critério Ético/Legal** | Parte integrante do Nmap. Mesmo contexto ético.                                                     |
| **Critério de Hardware** | Scripts Lua executados dentro do processo Nmap. Sem overhead adicional.                             |
| **Decisão**              | ✅ **INCLUIR — v1**                                                                                  |


**Categorias e scripts relevantes:** `default`, `safe`, `vuln`, `auth`, `discovery` — incluindo `http-enum`, `ssh-auth-methods`, `smb-vuln-`*.

---

### 3.3 vulners NSE


| Atributo                 | Avaliação                                                                                                                                                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Propósito**            | Após detecção de versão (`-sV`), envia o CPE de cada serviço para a API Vulners e retorna CVEs com pontuação CVSS.                                                                                                          |
| **Critério de Valor**    | Preenche a lacuna mais crítica do Nmap NSE puro: o script `vuln` nativo verifica ~150 vulnerabilidades fixas; o vulners NSE mapeia qualquer serviço contra toda a base Vulners (250+ GB de CVEs). Suporta filtro `mincvss`. |
| **Critério Ético/Legal** | Passivo: não explora vulnerabilidades, apenas consulta nome e versão de software via API. Em redes com restrição de saída, simplesmente não retorna resultados.                                                             |
| **Critério de Hardware** | Script Lua executado pelo Nmap. Sem overhead além da latência de rede para a API.                                                                                                                                           |
| **Decisão**              | ✅ **INCLUIR — v1**                                                                                                                                                                                                          |


---

### 3.4 CrackMapExec / NetExec


| Atributo                 | Avaliação                                                                                                                                                                                                                                                                         |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Propósito**            | Ferramenta de pós-exploração e movimento lateral — enumera SMB/RDP/LDAP/WMI em múltiplos hosts, executa comandos, extrai credenciais, realiza password spraying.                                                                                                                  |
| **Critério de Valor**    | Na melhor hipótese, os recursos de enumeração SMB passiva se sobrepõem ao enum4linux-ng. O restante do conjunto de recursos (execução de comandos, extração de credenciais, pass-the-hash, movimento lateral) é pós-exploração pura.                                              |
| **Critério Ético/Legal** | Desenvolvida primariamente para movimento lateral pós-exploração. Implantá-la como componente automatizado gera logs de Segurança do Windows consistentes com comprometimento, pode disparar EDR/AV e poderia ser mal utilizada se o Pi for acessado por terceiro não autorizado. |
| **Critério de Hardware** | NetExec roda em ARM64, mas seu modelo de conexões concorrentes é intensivo em memória em escala.                                                                                                                                                                                  |
| **Decisão**              | ❌ **REVALIDAR - Futuro(v3)**                                                                                                                                                                                                                                                      |


---

### 3.5 testssl.sh


| Atributo                 | Avaliação                                                                                                                                                                                                                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Propósito**            | Auditoria abrangente de configuração SSL/TLS — conjuntos de cifras, versões de protocolo, validade de certificados, vulnerabilidades conhecidas (Heartbleed, POODLE, BEAST, ROBOT, etc.).                                                                                             |
| **Critério de Valor**    | Os scripts `ssl-`* do Nmap cobrem as verificações mais críticas, mas o testssl.sh fornece auditoria TLS substancialmente mais profunda, melhor suporte a TLS 1.3 e saída estruturada mais rica. Configuração incorreta de TLS é uma das descobertas de maior valor em redes internas. |
| **Critério Ético/Legal** | A inspeção de handshake TLS é técnica de observação passiva — completa o handshake para ler a configuração do servidor, sem explorar. Equivalente ao que qualquer cliente HTTPS faz.                                                                                                  |
| **Critério de Hardware** | Script bash sem dependências pesadas (bash, openssl, ferramentas Unix padrão — todas presentes no Raspberry Pi OS). Deve ter taxa limitada em escala de rede.                                                                                                                         |
| **Decisão**              | 🔵 **INCLUIR - v2** Ativar apenas quando portas TLS (443, 8443, 993, 995, 465, etc.) estiverem confirmadamente abertas.                                                                                                                                                               |


---

### 3.6 Nikto


| Atributo                 | Avaliação                                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| **Propósito**            | Scanner de vulnerabilidades web — detecta configurações inseguras e vulnerabilidades conhecidas em servidores web. |
| **Critério de Valor**    | Limitado a serviços web. Complementar ao Nmap para hosts com HTTP/HTTPS detectados.                                |
| **Critério Ético/Legal** | Ferramenta de auditoria web padrão. Uso responsável em redes autorizadas.                                          |
| **Critério de Hardware** | Leve. Roda sem problemas no Pi 4.                                                                                  |
| **Decisão**              | 🟡 **REVALIDAR — v2.** Ativar apenas quando portas HTTP/HTTPS detectadas.                                          |


---

### 3.7 enum4linux-ng


| Atributo                 | Avaliação                                                                                                                                                                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Propósito**            | Enumeração SMB/NetBIOS — extrai compartilhamentos, usuários, grupos, informações de SO e políticas de senha via chamadas MSRPC não autenticadas.                                                             |
| **Critério de Valor**    | Os scripts `smb-`* do Nmap cobrem sobreposição significativa, mas o enum4linux-ng fornece saída estruturada mais rica e lida melhor com SMBv3. Em redes mistas Windows/Linux/NAS, preenche lacunas genuínas. |
| **Critério Ético/Legal** | Enumeração SMB não autenticada consulta serviços publicamente anunciados — dados que clientes Windows trocam durante navegação normal. Baixo risco em varredura interna autorizada.                          |
| **Critério de Hardware** | Script Python 3 leve com dependências mínimas (impacket, ldap3). Roda confortavelmente no Pi 4.                                                                                                              |
| **Decisão**              | 🔵 **INCLUIR — v2.** Ativar apenas quando portas 139/445 confirmadamente abertas.                                                                                                                            |


---

### 3.8 sqlmap


| Atributo                 | Avaliação                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Propósito**            | Ferramenta automatizada de detecção e exploração de SQL injection em aplicações web.                |
| **Critério de Valor**    | Detecta SQL injection, identifica tipos de banco de dados. Limitado a aplicações web.               |
| **Critério Ético/Legal** | Pode ser intrusivo. Requer escopo e autorização explícita para uso em testes.                       |
| **Critério de Hardware** | Leve. Roda no Pi 4.                                                                                 |
| **Decisão**              | 🟡 **REVALIDAR — v2.** Expansão futura para análise de SQL injection em serviços web identificados. |


---

### 3.9 masscan


| Atributo                 | Avaliação                                                                   |
| ------------------------ | --------------------------------------------------------------------------- |
| **Propósito**            | Scanner de portas de alta performance para redes grandes.                   |
| **Critério de Valor**    | Velocidade superior ao Nmap, mas não detecta serviços nem vulnerabilidades. |
| **Critério Ético/Legal** | Velocidade pode causar alertas de IDS em redes monitoradas.                 |
| **Critério de Hardware** | Alta velocidade pode saturar a NIC do Pi.                                   |
| **Decisão**              | ❌ **EXCLUIR da v1.** Nmap cobre o caso de uso com melhor integração.        |


---

### 3.10 Metasploit


| Atributo                 | Avaliação                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------- |
| **Propósito**            | Framework completo de exploração — varredura, exploração, pós-exploração.                 |
| **Critério de Valor**    | Capacidades avançadas de exploração, muito além do escopo desta plataforma de descoberta. |
| **Critério Ético/Legal** | Framework ofensivo. Requer autorização explícita de pentest para uso legal.               |
| **Critério de Hardware** | Alto consumo de recursos. Incompatível com ambiente embarcado no Pi 4.                    |
| **Decisão**              | ❌ **EXCLUIR.** Incompatível com hardware e escopo.                                        |


---

### 3.11 OpenVAS / Greenbone


| Atributo                 | Avaliação                                                                                                                                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Propósito**            | Scanner de vulnerabilidades completo baseado em feed — executa mais de 100.000 NVTs contra hosts-alvo, com correlação CVSS.                                                                                        |
| **Critério de Valor**    | Profundidade de verificação de CVE muito superior ao Nmap NSE, com feed atualizado diariamente. Porém o vulners NSE cobre os casos mais relevantes sem a sobrecarga arquitetural.                                  |
| **Critério Ético/Legal** | Ferramenta legítima para gestão de vulnerabilidades em redes autorizadas.                                                                                                                                          |
| **Critério de Hardware** | Stack de múltiplos serviços (openvas-scanner, gvmd, ospd-openvas, Redis, PostgreSQL, servidor web). Exige mínimo de 4 GB de RAM só para a sincronização do feed — sem sobra para o agente Python e demais módulos. |
| **Decisão**              | ❌ **EXCLUIR.** Barreira de hardware intransponível no contexto deste projeto.                                                                                                                                      |


---

## 4. Matriz de Pontuação


| Ferramenta   | Uso de Recursos | Cobertura | Integração | Parsing | Adequação | Score   |
| ------------ | --------------- | --------- | ---------- | ------- | --------- | ------- |
| Nmap         | 9               | 9         | 10         | 9       | 10        | **9.5** |
| Nmap NSE     | 8               | 10        | 9          | 9       | 10        | **9.5** |
| vulners NSE  | 10              | 9         | 10         | 9       | 10        | **9.6** |
| Nikto        | 7               | 7         | 8          | 7       | 7         | **7.2** |
| testssl.sh   | 7               | 7         | 8          | 7       | 7         | **7.2** |
| sqlmap       | 7               | 8         | 6          | 7       | 7         | **7.0** |
| masscan      | 10              | 5         | 7          | 7       | 6         | **7.0** |
| CrackMapExec | 8               | 7         | 8          | 7       | 8         | **7.6** |
| Metasploit   | 3               | 10        | 6          | 6       | 4         | **5.8** |
| OpenVAS      | 2               | 10        | 5          | 6       | 3         | **5.2** |


---

## 5. Distinção Passivo vs. Ativo

As ferramentas incluídas situam-se na **extremidade de observação passiva do espectro**: leem informações que os serviços anunciam publicamente. Não se autenticam, não executam código nos alvos e não tentam explorar vulnerabilidades.

Ferramentas que cruzam para o território de ataque ativo estão **categoricamente fora do escopo da v1**:

- **Força bruta de credenciais** — causa bloqueios de conta e interrupções de serviço
- **Execução de código remoto** — requer autorização explícita de pentest por escrito
- **Reverse shells e movimento lateral** — incompatíveis com o propósito declarado do sistema

---

## 6. Decisão


| Ferramenta    | Versão | Decisão                    | Justificativa                                                                         |
| ------------- | ------ | -------------------------- | ------------------------------------------------------------------------------------- |
| Nmap          | v1     | INCLUIR                    | Motor principal — baixo consumo, altamente flexível.                                  |
| Nmap NSE      | v1     | INCLUIR                    | Estende o Nmap com detecção de vulnerabilidades sem overhead extra.                   |
| vulners NSE   | v1     | INCLUIR                    | Correlação de CVE passiva via API Vulners. Cobertura muito superior ao `vuln` nativo. |
| enum4linux-ng | v2     | INCLUIR (v2)               | Enumeração SMB rica. Ativar apenas quando portas 139/445 abertas.                     |
| testssl.sh    | v2     | INCLUIR (v2)               | Auditoria TLS profunda. Ativar apenas em portas TLS confirmadas.                      |
| Nikto         | v2     | REVALIDAR (v2)             | Scanner web leve. Útil quando HTTP/HTTPS detectados.                                  |
| sqlmap        | v2     | REVALIDAR (v2)             | Expansão futura para análise de SQL injection em serviços web.                        |
| CrackMapExec  | —      | **REVALIDAR - Futuro(v3)** | Ferramenta ofensiva de pós-exploração.                                                |
| masscan       | —      | ❌ EXCLUIR                  | Nmap cobre o caso de uso com melhor integração.                                       |
| Metasploit    | —      | ❌ EXCLUIR                  | Consumo de recursos proibitivo. Incompatível com ambiente embarcado.                  |
| OpenVAS       | —      | ❌ EXCLUIR                  | Stack muito pesada para Pi 4. Inviável no contexto do agente.                         |


---

## 7. Versões do Projeto

- **v1** — Scanner principal: Nmap + NSE + vulners NSE. Apenas ferramentas passivas, sem dependências adicionais.
- **v2** — Scanner estendido: adiciona enum4linux-ng, testssl.sh, Nikto e possibilidade de verificações de credenciais limitadas (ex.: admin/admin) com número controlado de tentativas.
- **v3** — Solução personalizada: scripts avançados usando credenciais da empresa, possibilidade de Vuls para inventário de patches em infraestrutura gerenciada, revalidação de LinPEAS/WinPEAS com autorização explícita.

---

## 8. Consequências

- O escopo da v1 está fixo: apenas Nmap + NSE + vulners NSE. Nenhuma ferramenta ativa adicional.
- Qualquer funcionalidade futura pode referenciar enum4linux-ng e testssl.sh, mas não deve depender deles para a entrega da v1.
- Qualquer adição de ferramenta na v2 ou v3 requer seu próprio card de implementação no backlog e deve estar em conformidade com a arquitetura do pipeline (A-04) e o contrato de API (A-03).
- As ferramentas **EXCLUIR** não devem ser adicionadas ao projeto sob nenhuma circunstância sem um novo ADR, revisão legal e aprovação explícita do instrutor/stakeholder.
- Os resultados de varredura podem conter informações sensíveis (portas abertas, banners de serviço, certificados TLS, nomes SMB). O backend deve impor controles de acesso apropriados e as descobertas não devem ser transmitidas por canais não criptografados.

---

## 9. Referências

- [Documentação Nmap NSE](https://nmap.org/nsedoc/)
- [nmap-vulners GitHub](https://github.com/vulnersCom/nmap-vulners)
- [enum4linux-ng GitHub](https://github.com/cddmp/enum4linux-ng)
- [testssl.sh GitHub](https://github.com/drwetter/testssl.sh)
- [OpenVAS / Greenbone Community Edition](https://greenbone.github.io/docs/latest/)
- OWASP Testing Guide — Testes de Infraestrutura de Rede
- ADR R-06 — Ferramentas Adicionais de Pentest e Enumeração (referência interna)

