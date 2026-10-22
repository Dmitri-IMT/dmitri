# TRUTH - Laboratorio local para um scan direcionado

## Narrative

O laboratório é uma demonstração reproduzível do que o Dmitri consegue encontrar numa rede com serviços expostos. Ele deve produzir, em um único scan real, a maior quantidade prática de achados úteis que as ferramentas direcionadas e os parsers atuais suportam para HTTP/HTTPS, SSH, FTP, SMB e Telnet. Os alvos são controlados, descartáveis e usam somente dados fictícios. O scan persistido será o resultado de apresentação; ele deve permitir explicar cada achado pela ferramenta, alvo, porta e evidência original.

## Business rules

- Validacao final em 2026-10-22: scan `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f` passou no verificador estrito, com 5 hosts e 90 findings. JSON: `../../scan-results/targeted-lab-2026-10-22.json`. Ambas as unidades Nikto completaram; suas evidencias continuam inconclusivas pela politica atual. O scan diagnostico anterior nao foi agregado.

- A correção imediata cobre somente a execução de Nikto e testssl e sua coleta já suportada, preservando a seleção automática existente em `nspi`/`extensive`, as demais ferramentas e as políticas de evidência. O objetivo é auditoria automatizada útil para reportar problemas e orientar possíveis correções. Após validar ambas, retomar o laboratório; não reduzir cobertura apenas para aprovar os fixtures. O escopo detalhado está em [WEB-TOOLS-REMEDIATION.md](./WEB-TOOLS-REMEDIATION.md#objetivo-e-escopo-confirmado).

- Um único comando de scan no modo `extensive` cobre os serviços HTTP, HTTPS, SSH, FTP, SMB e Telnet do laboratório; não se combinam resultados de scans diferentes para compor a demonstração.
- O desenho dos alvos prioriza variedade e qualidade de achados verificáveis em cada ferramenta direcionada, dentro do que os adaptadores, parsers e políticas atuais reconhecem. Não se contam portas abertas, mensagens sem evidência ou resultados fabricados como achados.
- O mesmo scan também deve explorar os NSEs já configurados no perfil `extensive`, incluindo condições úteis para `vulners`, `ftp-anon`, `http-methods`, `ssl-cert`, `ssl-enum-ciphers`, `smb-protocols` e `smb2-security-mode`. CVEs só são apresentadas quando há correlação de CPE/versão real e registro estruturado aceito pelo parser; correlação é identificada como provável, não como exploração confirmada.
- Antes de fixar cada fixture, a implementação deve mapear os sinais que o parser atual realmente aceita para aquela ferramenta e selecionar condições seguras que produzam esses sinais. O conjunto esperado é documentado por ferramenta e endpoint; achados adicionais só entram na apresentação depois de confirmados no resultado persistido.
- O relatório final registra todos os achados do único scan, inclusive achados adicionais além dos mínimos de aceitação, e identifica unidades omitidas, falhas ou sem evidência. Um alvo que só prova conectividade não satisfaz a demonstração.
- O Dmitri escolhe as ferramentas a partir dos serviços e portas descobertos. O laboratório não injeta resultados nem chama adaptadores diretamente como substituto do scan.
- HTTP/HTTPS oferecem arquivos fictícios expostos, incluindo `.env`, para a validação do ffuf. Nikto é planejado como cobertura obrigatória, mas sua aceitação depende de evidência persistida; no ensaio de 2026-10-21 as unidades expiraram sem achado.
- HTTPS apresentou condicao TLS reconhecida por testssl/NSE; SSH expos algoritmo fraco; FTP aceitou login anonimo sem TLS (chroot validado no scan); SMB aceitou guest/null; Telnet aceitou conexao.
- Os sete resultados esperados são `ffuf`, `nikto`, `testssl.sh`, `enum4linux-ng`, `ssh-audit`, `ftp-check` e `telnet-check`. Uma ferramenta ausente, omitida, falha ou sem evidência esperada é falha do ensaio, com o motivo registrado.
- Os alvos são acessíveis somente na rede Docker local de laboratório; nenhum serviço vulnerável é publicado na máquina hospedeira. Arquivos, credenciais e certificados do alvo são fictícios.
- A execução contra backend implantado fica fora do procedimento do laboratório. O ensaio usa o backend e o banco locais do simulador.

## User stories

1. Como desenvolvedor, quero iniciar um laboratório reproduzível e lançar um scan, para verificar o fluxo real de seleção e ingestão.
2. Como revisor, quero uma matriz de resultado por ferramenta, porta e evidência, para distinguir um achado real de uma lacuna de cobertura.
3. Como operador, quero encerrar o laboratório e descartar os dados, para repetir o ensaio do zero.

## Acceptance criteria (verifiable)

| ID | Given | When | Then |
|----|-------|------|------|
| A1 | O simulador local está pronto | O operador inicia um scan `extensive` na rede do laboratório | Uma única execução alcança os alvos, termina e gera um scan persistido. |
| A2 | HTTP e HTTPS disponiveis | Scan direcionado completo | Nikto e ffuf selecionados; sinal Nikto aceito persistido como inconclusivo pela politica atual, e evidencia HTTP para `.env`. |
| A3 | HTTPS apresenta condição TLS intencional | O scan conclui | testssl.sh gera relatório válido e ao menos um achado TLS/certificado suportado. |
| A4 | SSH anuncia algoritmo fraco intencional | O scan conclui | ssh-audit gera relatório válido e ao menos um achado suportado de algoritmo. |
| A5 | FTP claro permite login anônimo | O scan conclui | ftp-check confirma canal claro e login anônimo. |
| A6 | SMB permite sessão não autenticada | O scan conclui | enum4linux-ng completa e registra ao menos a sessão convidada ou anônima; o compartilhamento fica visível como evidência adicional. |
| A7 | Telnet responde na porta 23 | O scan conclui | telnet-check confirma que a conexão TCP foi aceita. |
| A8 | O scan foi persistido | O operador consulta a matriz de verificação | A matriz cobre as sete ferramentas no mesmo scan e mostra endpoint, estado, lacuna de cobertura e cada achado comprovado; nenhuma é aprovada apenas por porta aberta. |
| A10 | Os alvos e sinais foram escolhidos com base nos parsers e políticas atuais | O único scan é concluído | A apresentação contém a maior variedade prática de achados suportados planejada para cada ferramenta, com evidência rastreável; o relatório separa mínimos obrigatórios, achados adicionais e lacunas. |
| A11 | Os alvos e ferramentas NSE estão prontos | O único scan `extensive` é concluído | O resultado inclui findings para cada condição NSE planejada que o perfil `extensive` suporta; `vulners` só é aprovado quando CPE, CVE e saída estruturada passam pelo parser. Scripts sem finding esperado aparecem como lacuna com evidência/motivo, não como sucesso presumido. |
| A9 | O laboratório está ativo | O operador encerra o simulador | Containers e dados locais descartáveis são removidos; nenhum serviço vulnerável usa porta publicada no host. |

## Out of scope (v1)

A correcao de Nikto/testssl e a validacao do laboratorio foram concluidas em 2026-10-22; veja `WEB-TOOLS-REMEDIATION.md` e `ARCHITECTURE.md`. O escopo concluido preservou selecao automatica e politicas atuais.

A correcao de Nikto/testssl e a validacao do laboratorio foram concluidas em 2026-10-22. Veja `WEB-TOOLS-REMEDIATION.md` e `ARCHITECTURE.md`; o escopo preservou selecao automatica e politicas atuais. O scan final passou no verificador conforme registrado acima.

- Exploração, força bruta, credenciais reais, CVE específico ou garantia de detecção de uma versão vulnerável arbitrária.
- Mudança nos seletores ou parsers de produção para fazer o laboratório passar; qualquer defeito real identificado será tratado em trabalho próprio.
- Nova tela, novo contrato de API ou testes no ambiente implantado.

## Related specs

- `ARCHITECTURE.md`
- `TASKS.md`
