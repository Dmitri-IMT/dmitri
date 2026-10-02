# Revisão e correções do scan extensive com Metasploitable2

Data da execução: 2026-09-29. Pi, backend e frontend estavam na mesma rede
`172.20.10.0/28`. Scan: `612a4057-e201-494e-8077-981268126eb5`.

Este documento reúne a evidência observada, o plano de correção e o resultado
da implementação na branch `fix/scan-host-identity-and-profile`.

## Resultado observado

| Ponto | Resultado do Pi | API / interface |
| --- | --- | --- |
| Hosts | 6, incluindo a VM `172.20.10.2` e o host `172.20.10.8` | O scan mostra 6; Network mostra 5 dispositivos. |
| MAC | `.2` e `.8` reportam `36:D5:B4:1F:F5:E8` | Os dois recebem o mesmo `host_id`; o link do `.2` abre o detalhe do `.8`. |
| SO da VM | Nmap identifica `Linux 2.6.9 - 2.6.33` com precisão de 100% | O dado estruturado existe na observação do scan, mas não aparece no topo do perfil compartilhado. A evidência Linux aparece em “Why this profile?”. |
| Perfil | Fabricante e modelo ausentes; `product_family=VNC` | O perfil compartilhado aparece no cadastro do `.8`. Um serviço VNC não deve, sozinho, definir a família do produto. |
| Achados da VM | 330 observações | 320 achados persistidos no scan, marcados como resolvidos; Network mostra 0 vulnerabilidades para o cadastro compartilhado. |
| Achados totais | 359 observações | 349 achados. Dez observações TLS distintas foram agrupadas em dois achados, nas portas 25 e 5432, e a evidência adicional não era incorporada. |
| Cobertura | `partial_result=true`; 19 verificações planejadas, 5 concluídas, 1 expirada e 13 puladas | A página do scan não apresentava um resumo legível da cobertura parcial e das ferramentas indisponíveis. |

O Pi identificou SO em 5 dos 6 hosts; nenhum teve modelo identificado.
Fabricante foi identificado para `.6`; família de produto veio para `.1` e
`.2`. Campos sem evidência devem permanecer desconhecidos. A precisão de 100%
é a correspondência informada pelo Nmap, não uma garantia absoluta.

## Causas identificadas

- [ADR-014](../adr/ADR-014-host-identity-resolution.md) define `mac:<MAC>`
  como identidade quando há MAC. `identity_key()` aplicava essa regra mesmo
  quando endereços IP distintos apareciam no mesmo scan. O processamento
  posterior atualizava o cadastro compartilhado e resolvia achados da VM.
- [`HostProfile.tsx`](../../frontend/src/pages/hosts/HostProfile.tsx) não
  mostrava `operating_system.name` no perfil principal. A tabela de hosts do
  scan também não exibia o SO já fornecido pela API.
- [`persistence.py`](../../backend/src/api/services/persistence.py) agrupava
  achados pela chave de deduplicação e não incorporava a evidência do registro
  adicional ao achado existente.
- A página do scan não apresentava `partial_result` com contagens e motivos
  das verificações incompletas em um resumo acessível.
- O perfil do Pi podia usar um rótulo genérico de serviço, como VNC, como
  família do produto.

## Plano de correção

1. Separar dispositivos que compartilham MAC quando aparecem em IPs distintos
   no mesmo scan, sem quebrar a continuidade de um dispositivo que muda de IP
   entre scans.
2. Reparar os vínculos históricos `scan_hosts.host_id` e reconstruir as
   projeções de portas e achados, de forma repetível, preservando histórico e
   estado correto de resolução.
3. Mostrar o SO estruturado e a precisão do Nmap no perfil do dispositivo e
   mostrar o SO por observação na tabela do scan.
4. Preservar evidências TLS distintas quando achados forem agrupados.
5. Exibir a cobertura parcial de forma resumida, com detalhes por ferramenta,
   e evitar inferir família de produto a partir de um único rótulo genérico.

## Implementação nesta branch

- A ingestão separa hosts com MAC compartilhado quando IPs distintos aparecem
  no mesmo scan. A identidade por MAC continua para observações sem colisão
  simultânea, preservando o caso de mudança de IP entre scans. A decisão está
  registrada no ADR-014.
- O comando `backend-repair-host-identities` oferece prévia dos grupos
  ambíguos; `--apply` separa os vínculos históricos e reconstrói portas e
  achados por host.
- O perfil e a tabela de hosts do scan exibem o SO estruturado e a precisão
  Nmap quando disponível.
- Achados agregados incorporam evidências distintas.
- Ao lado da duração, a página do scan mostra **Atenção: scan parcial** quando
  aplicável. O botão abre um diálogo com a cobertura organizada por ferramenta.
- O cartão de análise por IA informa quando a API retorna que a análise está
  indisponível; nesse estado, não há resumo para exibir.
- A família de produto não é inferida de um único rótulo genérico, como VNC.

## Verificações realizadas nesta branch

- Regressões de identidade e inventário no backend: 28 passaram. `ruff check
  src tests` passou.
- Frontend: 74 testes direcionados passaram; typecheck e build passaram; lint
  terminou sem erros e com três avisos existentes.
- Perfil do hardware-agent: 84 testes passaram.
- Suíte completa do backend: 1.434 passaram; uma falhou em
  `test_no_placeholder_org_id_remains` porque o Windows tentou ler um arquivo
  UTF-8 com o encoding padrão CP1252. Em uma execução direcionada que também
  incluiu `test_migrations.py`, duas verificações de downgrade falharam ao
  recriar uma coluna `NOT NULL` em tabela com linhas existentes.
- Suíte completa do hardware-agent: 1.287 passaram, 44 foram ignorados e sete
  de `test_provision.py` falharam porque o Windows não permite o `os.open` de
  diretórios usado para sincronizar `fsync`.
- A suíte completa do frontend teve falhas por timeout em testes fora das
  telas alteradas quando executada em paralelo com outros gates; os testes
  direcionados das telas alteradas passaram isoladamente.
- O reparo local identificou a colisão documentada neste scan. Após aplicar a
  correção, a prévia retornou zero grupos. A conferência mostrou seis registros
  de host na organização, IDs distintos, Linux 2.6.9–2.6.33 com 320 achados
  ativos para `.2` e Windows 11 sem achados para `.8`.

## Teste pendente

O Pi está desligado. Repetir o scan e comparar o resultado bruto do Pi, a API,
Network, os detalhes dos dois dispositivos e a página do scan quando o Pi
estiver disponível. O resultado bruto observado estava em
`/var/lib/dmitri/dmitri/results/results/2026-09-29T21-18-30_172-20-10-0_28.json`.
