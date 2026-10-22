# Tasks — Laboratório local para um scan direcionado (`053-targeted-scan-lab`)

10 tarefas. Objetivo: demonstracao em um unico scan completo, com findings targeted e NSE/Vulners suportados por extensive. Implementacao concluida. O diagnostico falhou nos antigos limites Nikto; scan `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f` passou no verificador: 5 hosts, 90 achados. JSON: `../../scan-results/targeted-lab-2026-10-22.json`.

## Task 1: Isolar a rede dos alvos
- **Description**: Ampliar o Compose local com uma rede pequena dedicada, IPs fixos e agente conectado às redes de aplicação e de alvos. Colocar somente os alvos na rede vulnerável, sem publicar suas portas no host; preservar o caminho `--nspi` connect-only.
- **Dependencies**: —
- **Target Files**: `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: teste estático de IPs únicos, rede interna, ausência de `ports:` dos alvos, conectividade prevista do agente e ausência dos alvos novos em `compose.nspi.yaml`.
- **Success Criteria**: A1, A9; a faixa de scan contém os cinco alvos e não contém backend/banco; nenhuma porta vulnerável é publicada no host.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 2: Instalar as ferramentas reais na imagem local do agente
- **Description**: Primeiro registrar, por ferramenta/NSE, os sinais e formatos aceitos pelo adaptador/parser/política atuais, incluindo os findings mínimos e adicionais. Instalar ffuf, Nikto e seu `db_tests` fixado, testssl.sh, enum4linux-ng, ssh-audit, wordlist e o script externo `vulners.nse` fixado; regenerar/validar o índice NSE. Reusar pins do provisionamento Pi quando possível e tratar amd64 da imagem local sem alterar o provisionamento de produção.
- **Dependencies**: —
- **Target Files**: `specs/053-targeted-scan-lab/ARCHITECTURE.md`, `docker/pi-simulator/agent.Dockerfile`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: checagem de presença/versão e execução `--help` ou equivalente dentro da imagem; `nmap --script-help vulners`; hash do banco Nikto e wordlist no caminho esperado.
- **Success Criteria**: A2–A6, A11; matriz de sinais suportados documentada para guiar fixtures; nenhuma unidade targeted ou NSE falha por ferramenta/script ausente.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 3: Construir HTTP com evidência web verdadeira
- **Description**: Criar o alvo web com conteúdo/arquivos/diretórios fictícios reconhecidos por ffuf, condição de Nikto aceita e `TRACE` realmente habilitado para o NSE `http-methods`; rotas não definidas retornam 404. Escolher achados distintos suportados e documentar versão/CPE observados para `vulners`, sem alegar CVE sem correlação estruturada.
- **Dependencies**: Task 1, Task 2
- **Target Files**: `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/web-target.Dockerfile`, `docker/pi-simulator/targets/web/nginx.conf`, `docker/pi-simulator/targets/web/env.fixture`, `docker/pi-simulator/targets/web/config.fixture`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: HTTP 200 e corpo reconhecível para os paths escolhidos, 404 para caminho aleatório, Nmap reconhece HTTP; Nikto e ffuf reais produzem relatórios processáveis no smoke check do alvo e as regras escolhidas são confirmadas por evidência do corpo.
- **Success Criteria**: A2, A11; `WEB-SECRET-ENV-001` tem prova de duas atribuicoes ficticias, findings adicionais suportados, Nikto persiste sinais como evidencia inconclusiva sob a politica atual, e `http-methods` registra o metodo perigoso.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 4: Habilitar HTTPS e prova TLS
- **Description**: Servir o conteúdo web em 443 com certificado/chave fictícios gerados dentro do container e protocolos/cifras que `testssl.sh` e os NSEs `ssl-cert`/`ssl-enum-ciphers` realmente reconheçam. Maximizar findings independentes de certificado, protocolo, cifras e grau sem quebrar handshake/ffuf.
- **Dependencies**: Task 3
- **Target Files**: `docker/pi-simulator/web-target.Dockerfile`, `docker/pi-simulator/targets/web/nginx.conf`, `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: handshake HTTPS, Nmap classifica `https`/túnel SSL, testssl.sh gera JSON válido e pelo menos um achado de certificado/protocolo suportado; ffuf valida `.env` sobre HTTPS.
- **Success Criteria**: A2, A3, A11; evidência nativa dos findings TLS esperados e chave privada nunca está no Git nem em log do host.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 5: Construir alvo SSH auditável
- **Description**: Criar daemon SSH com algoritmos obsoletos e autenticação por senha habilitada somente para conta/credencial fictícia do laboratório isolado, produzindo findings de `ssh-audit` e `ssh-auth-methods`; registrar versão/CPE real para `vulners`.
- **Dependencies**: Task 1, Task 2
- **Target Files**: `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/ssh-target.Dockerfile`, `docker/pi-simulator/targets/ssh/sshd_config`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: Nmap reconhece SSH na porta 22; ssh-audit real produz JSON válido e issue de algoritmo com evidência positiva.
- **Success Criteria**: A4, A11; issues de algoritmo e senha exposta são comprovadas; host keys e credenciais são fictícias e efêmeras, sem acesso externo ao alvo.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 6: Construir alvo FTP anônimo
- **Description**: Configurar servidor FTP claro com banner, FEAT e login anônimo aceito; servir somente dados fictícios. Verificar todos os sinais independentes que `ftp-check` persiste e ativar os que aumentam a demonstração sem permitir escrita. Manter o serviço na rede do laboratório.
- **Dependencies**: Task 1
- **Target Files**: `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/ftp-target.Dockerfile`, `docker/pi-simulator/targets/ftp/vsftpd.conf`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: Nmap reconhece FTP na porta 21; verificação de banner, FEAT e resposta 230 ao fluxo anônimo; adaptador atual produz ambas as issues.
- **Success Criteria**: A5; FTP não aceita escrita anônima nem contém dados reais.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 7: Ajustar Samba para enumeração não autenticada
- **Description**: Preservar o alvo Samba e ativar guest/null, SMBv1 e assinatura não obrigatória somente na rede interna de laboratório para findings de enum4linux-ng, `smb-protocols` e `smb2-security-mode`; registrar a versão/CPE real para Vulners. Não alegar MS17-010: `extensive` não executa esse NSE e Samba comum não representa esse alvo.
- **Dependencies**: Task 1, Task 2
- **Target Files**: `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/target-lab.Dockerfile`, `docker/pi-simulator/smb-lab.conf`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: Nmap reconhece SMB em 445; enum4linux-ng real produz JSON válido com `guest` ou `null` e lista o compartilhamento; parser registra issue de sessão positiva.
- **Success Criteria**: A6, A11; sessão positiva e findings NSE de SMBv1/assinatura comprovados; nenhum MS17-010 atribuído ao Samba.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 8: Construir alvo Telnet
- **Description**: Criar serviço Telnet real com banner informativo e sem contas úteis. Confirmar que o banner e a conexão entregam a evidência mais rica que `telnet-check` atual persiste. Manter o serviço apenas na rede de alvos.
- **Dependencies**: Task 1
- **Target Files**: `docker/pi-simulator/compose.yaml`, `docker/pi-simulator/telnet-target.Dockerfile`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: Nmap reconhece Telnet; `telnet-check` confirma conexão e produz `telnet:cleartext`.
- **Success Criteria**: A7; conexão aceita de dentro do laboratório e nenhuma porta publicada no host.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 9: Criar comando único e verificador da matriz
- **Description**: Adicionar um comando explícito que enfileira exatamente um `extensive` para o laboratório, mantendo o comando genérico e a recusa de `--nspi scan`. Criar verificador do mesmo scan local que correlacione IP/porta, ferramenta, cobertura e evidência, liste todos os achados persistidos e separe mínimos, adicionais e lacunas. Retornar erro para qualquer cenário obrigatório faltante.
- **Dependencies**: Tasks 1–8
- **Target Files**: `simulator.sh`, `docker/pi-simulator/verify_targeted_scan.py`, `docker/pi-simulator/tests/test_verify_targeted_scan.py`
- **Tests**: dados representativos de scan completo e scan com cada ferramenta omitida, falha, evidência ausente ou endpoint errado; cada caso falho dá exit code diferente de zero.
- **Success Criteria**: A1–A8 e A10–A11; um comando enfileira um único scan e a matriz não confunde porta aberta com achado confirmado nem junta resultados de execuções diferentes.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Task 10: Registrar e executar o ensaio completo uma vez
- **Description**: Documentar pré-requisitos, rede, serviços, sinais/findings mínimos e adicionais previstos por ferramenta, comando, consulta de resultado e limpeza. Fazer smoke checks dos alvos e das ferramentas para validar as condições antes da execução integrada; então executar um único scan completo destinado à apresentação, validar a matriz e parar o ambiente. Registrar achados realmente persistidos, lacunas e desvios comprovados; corrigir fixtures e infraestrutura do laboratório dentro deste escopo. Não agregar resultados de scans distintos.
- **Dependencies**: Task 9
- **Target Files**: `docker/pi-simulator/README.md`, `.claude/docs/infra/pi-simulator.md`, `docker/pi-simulator/tests/test_targeted_lab.py`
- **Tests**: suíte específica do laboratório e ensaio completo com os sete executáveis reais e os NSEs do perfil `extensive`; conferir ingestão no backend, CPE/CVE de Vulners estruturado quando disponível, cobertura/falhas/achados por alvo.
- **Success Criteria**: A1–A11; relatório final identifica o scan único, unidades previstas/concluídas/omitidas, sete ferramentas, findings targeted/NSE mínimos e adicionais por endpoint, lacunas e remoção dos containers locais. Cada finding da apresentação é rastreável ao dado persistido e à evidência disponível.
- **Status**: COMPLETE
- **Review Rejections**: 0

## Dependency graph

```text
#1 ─┬─> #3 ─> #4 ─┐
    ├─> #5 ──────┤
    ├─> #6 ──────┤
    ├─> #7 ──────┼─> #9 ─> #10
    └─> #8 ──────┤
#2 ───> #3, #5, #7 ┘
```

## Status

A correção imediata limita-se a Nikto e testssl: execução funcional e automática, coleta já suportada e estado de cobertura correto, preservando seleção em `nspi`/`extensive`, demais ferramentas e políticas de evidência. A finalidade é auditoria útil para reportar problemas e apoiar correções, não apenas iniciar executáveis ou aumentar contagens. Não ampliar parsers, classificação ou relatórios nesta fase.

O registro complementar de 2026-10-22 documenta a correcao focada. Selecao automatica nspi/extensive e politicas de evidencia permanecem inalteradas. R1-R7 concluidas. Scan final `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f`: PASS, 5 hosts, 90 achados; payload `../../scan-results/targeted-lab-2026-10-22.json`. O diagnostico `45039520-8e46-4f92-806f-89c729c63c40` nao e resultado da apresentacao.

| # | Task | Status |
|---|------|--------|
| 1 | Isolar a rede dos alvos | COMPLETE |
| 2 | Instalar ferramentas na imagem | COMPLETE |
| 3 | HTTP e evidência web | PARTIAL |
| 4 | HTTPS e TLS | PARTIAL |
| 5 | SSH | COMPLETE |
| 6 | FTP | PARTIAL |
| 7 | SMB | COMPLETE |
| 8 | Telnet | COMPLETE |
| 9 | Comando e verificador | COMPLETE |
| 10 | Ensaio completo e documentação | PARTIAL |
