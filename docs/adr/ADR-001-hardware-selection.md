# R-01 — Seleção de Hardware

## Contexto

O dispositivo executará um Linux headless, rodará ferramentas locais de descoberta e enumeração de serviços, normalizará os resultados e enviará os payloads para a API do backend.

Esta decisão precisa equilibrar:

- custo por unidade dentro do orçamento de **R$ 1.250**
- folga de CPU e RAM para scans paralelos e processamento de resultados
- suporte Linux estável para ferramentas da classe do Nmap
- disponibilidade de acessórios em território nacional para implantações repetíveis
- familiaridade do time e manutenção de longo prazo

## Escopo e premissas

- O orçamento máximo aprovado para o BOM completo (placa + refrigeração + fonte + armazenamento + adaptador Wi-Fi) é de **R$ 1.250**, referência de março de 2026.
- Todas as fontes de preço são distribuidores com operação no Brasil e emissão de nota fiscal: RoboCore (distribuidora oficial da Raspberry Pi no Brasil), FilipeFlop, MakerHero e NextPi — conforme a disponibilidade por item.
- Os preços refletem valores de varejo observados em 28 de março de 2026 com pagamento via Pix/boleto, quando aplicável.
- O contexto de alta de preços da DRAM em 2026 — documentado pelo portal SempreUpdate — pressiona significativamente o custo do Raspberry Pi 5, cujo kit completo (placa + case + fonte) supera R$ 950 nos distribuidores nacionais, tornando inviável encaixar os demais componentes no orçamento de R$ 1.250.
- Para captura via Wi-Fi, conectividade de gerenciamento e captura de pacotes são tratadas como necessidades separadas.

## Restrição orçamentária: por que o Raspberry Pi 5 não cabe no limite

A NextPi — revendedora com operação nacional e estoque regular — lista o **Kit Raspberry Pi 5 4GB com case oficial e fonte original por R$ 959,89** (com desconto de 5% no Pix, R$ 911,90). Somados os itens restantes do BOM (cartão microSD e adaptador Wi-Fi), o total ultrapassaria R$ 1.250 com facilidade. Essa restrição é a principal razão pela qual o Raspberry Pi 5 é descartado como alvo de produção nesta iteração do projeto.

## Comparação técnica

| Plataforma | CPU | RAM | USB | Rede | Observação de mercado |
|---|---|---|---|---|---|
| Raspberry Pi 3 Model B+ | Broadcom BCM2837B0, quad-core Cortex-A53 1.4 GHz | 1 GB | 4 × USB 2.0 | Ethernet 300 Mb, Wi-Fi dual-band 802.11ac, BT 4.2 | Menor custo de entrada, mas já limitado para cargas modernas de scan |
| Raspberry Pi 4 Model B | Broadcom BCM2711, quad-core Cortex-A72 1.8 GHz | 1 GB / 2 GB / 4 GB / 8 GB | 2 × USB 3.0, 2 × USB 2.0 | Gigabit Ethernet, Wi-Fi dual-band 802.11ac, BT 5.0 | Plataforma madura e com ampla disponibilidade nacional nos distribuidores oficiais |
| Raspberry Pi 5 | Broadcom BCM2712, quad-core Cortex-A76 2.4 GHz | 1 GB / 2 GB / 4 GB / 8 GB / 16 GB | 2 × USB 3.0, 2 × USB 2.0 | Gigabit Ethernet, Wi-Fi 5 dual-band 802.11ac, BT 5.0, PCIe 2.0 ×1 | Melhor desempenho dentro do ecossistema; inviável no orçamento de R$ 1.250 em março de 2026 |
| Orange Pi 5B | Rockchip RK3588S, 8 núcleos (4 × A76 + 4 × A55) até 2.4 GHz | 4 GB / 8 GB / 16 GB | 1 × USB 3.0, 2 × USB 2.0 | Gigabit LAN, Wi-Fi 6, BT 5.3 | Desempenho bruto elevado, mas suporte de software e ecossistema de acessórios nacionais é fragmentado |
| Banana Pi BPI-M5 | Amlogic S905X3, quad-core Cortex-A55 2.0 GHz | 4 GB | 4 × USB 3.0 | 1 GbE, sem Wi-Fi onboard, 16 GB eMMC | SoC mais antigo; sem distribuidor oficial no Brasil com suporte estruturado |

## Acessórios e observações de implantação

### Refrigeração

- O Raspberry Pi 4 suporta operação headless com dissipador passivo para cargas leves, mas refrigeração ativa é recomendada para janelas longas de scan ou ambientes quentes.
- Cases com cooler integrado para Raspberry Pi 4 estão amplamente disponíveis nos distribuidores nacionais (RoboCore, FilipeFlop, MakerHero) por valores entre R$ 50 e R$ 100.
- Orange Pi e Banana Pi têm ecossistema de acessórios mais fragmentado e menos disponível no varejo brasileiro.

### Alimentação

- O Raspberry Pi 4 usa fonte USB-C de 5 V / 3 A. Fontes compatíveis estão disponíveis nos distribuidores nacionais por valores entre R$ 50 e R$ 80.
- O Raspberry Pi 3 B+ usa fonte micro-USB de 2,5 A.

### Dimensionamento de armazenamento

Para o MVP do scanner, a demanda realista de armazenamento é:

| Componente | Espaço estimado |
|---|---|
| Raspberry Pi OS Lite + updates + margem de recuperação | 6 GB |
| Runtime Python, virtualenv, Nmap, pacotes de suporte e logs | 4 GB |
| Saída temporária de scans, JSON normalizado, logs rotacionados | 8 GB a 12 GB |
| Espaço livre para upgrades, wear leveling e margem de rollback | 20 GB+ |

Decisão: usar cartão microSD de 64 GB classe A2/V30 como mínimo de produção. Cartões nessa especificação estão disponíveis nas lojas de eletrônicos e grandes varejistas nacionais (Kabum, Amazon.com.br, Magazine Luiza) por valores entre R$ 50 e R$ 80.

## Decisão sobre Wi-Fi e modo promíscuo

O Wi-Fi onboard é suficiente para conectividade do agente, atualizações e telemetria, mas não deve ser a interface principal para scans em modo promíscuo ou monitor mode.

Motivos:

- A documentação do Linux Wireless trata monitor mode como capacidade dependente de hardware e driver, deixando claro que nem todo dispositivo suporta isso de forma completa.
- O Aircrack-ng informa que drivers de fabricante em geral não oferecem bom suporte a monitor mode, enquanto drivers alinhados ao ecossistema mac80211 tendem a ser mais previsíveis.
- Para um scanner implantável em campo, precisamos de um adaptador USB repetível e substituível, em vez de depender do comportamento do Wi-Fi onboard de cada placa.

Decisão: usar um adaptador USB Wi-Fi dedicado para cenários de monitor mode ou captura de pacotes, deixando o Wi-Fi onboard para tráfego de gerenciamento.

**Adaptador para o BOM base:** O ALFA AWUS036ACM está disponível na Amazon.com.br, com chipset MediaTek MT7612U e suporte documentado à família de drivers mac80211 no Linux. É a mesma especificação de chipset usada na análise original, agora adquirível com nota fiscal nacional.

## BOM da plataforma selecionada

**Plataforma selecionada: Raspberry Pi 4 Model B 4 GB**

| Item | Qtd | Preço estimado (Pix) | Fonte sugerida |
|---|---|---|---|
| Raspberry Pi 4 Model B 4 GB (homologado ANATEL) | 1 | R$ 490,00 | [RoboCore](https://www.robocore.net/placa-raspberry-pi/raspberry-pi-4-4gb) / [FilipeFlop](https://www.filipeflop.com) / [MakerHero](https://www.makerhero.com/produto/raspberry-pi-4-model-b/) |
| Case com cooler ativo para Raspberry Pi 4 | 1 | R$ 70,00 | RoboCore / FilipeFlop / MakerHero |
| Fonte USB-C 5 V / 3 A para Raspberry Pi 4 | 1 | R$ 60,00 | RoboCore / FilipeFlop / MakerHero |
| Cartão microSD 64 GB A2/V30 | 1 | R$ 65,00 | Amazon.com.br / Kabum / Magazine Luiza |
| Adaptador USB Wi-Fi ALFA AWUS036ACM | 1 | R$ 350,00 | [Amazon.com.br](https://www.amazon.com.br/Adaptador-AC1200-alcance-antenas-externas/dp/B08BJS8FXD) |

**Total estimado do BOM base: R$ 1.035,00**

**Folga orçamentária: ~R$ 215,00** (cabos, frete, eventuais variações de preço)

> **Nota sobre preços:** Os valores acima são estimativas de varejo observadas em março de 2026. Preços de Raspberry Pi estão em alta desde o final de 2025 devido à escassez de DRAM LPDDR4 globalmente. Recomenda-se confirmar os valores atuais diretamente nos distribuidores antes da aquisição.

> **Nota sobre o ALFA AWUS036ACM:** O produto é importado e vendido por terceiros na Amazon.com.br. O preço pode variar. Caso não esteja disponível, alternativas com chipset MT7612U (mesmo driver) podem ser consideradas — o critério é o chipset, não o fabricante. Essa substituição não requer um novo ADR, apenas confirmação técnica de que o chipset é idêntico.

## Rubrica de pontuação

**Pesos:**

- Desempenho: 30
- Suporte da comunidade e maturidade de software: 25
- Custo (dentro do orçamento de R$ 1.250): 20
- Disponibilidade nacional e ciclo de vida: 15
- Familiaridade do time: 10

**Escala:** 1 = ruim, 3 = aceitável, 5 = excelente

## Matriz de pontuação

| Plataforma | Desempenho (30) | Comunidade (25) | Custo no BR (20) | Disponibilidade (15) | Familiaridade (10) | Nota ponderada / 100 |
|---|---|---|---|---|---|---|
| Raspberry Pi 4 4 GB | 3 | 5 | 5 | 5 | 5 | **88** |
| Raspberry Pi 5 4 GB | 5 | 5 | 1 | 4 | 5 | **77** |
| Orange Pi 5B | 5 | 2 | 3 | 2 | 1 | **56** |
| Raspberry Pi 3 Model B+ | 1 | 4 | 5 | 3 | 4 | **55** |
| Banana Pi BPI-M5 | 2 | 2 | 3 | 1 | 1 | **36** |

> O Raspberry Pi 5 cai para nota 77 neste contexto porque o critério de custo é avaliado em relação ao orçamento de R$ 1.250 — e o Pi 5 simplesmente não cabe. Se o orçamento fosse flexível, ele pontuaria mais alto que o Pi 4, como demonstrado na análise original.

## Decisão

Adotar o **Raspberry Pi 4 Model B 4 GB** como plataforma padrão de hardware para o MVP.

Motivos:

- É a única plataforma que entrega desempenho adequado para o agente de scan, permanece dentro do orçamento de R$ 1.250, e está disponível com nota fiscal e suporte nos distribuidores oficiais no Brasil (RoboCore, FilipeFlop, MakerHero).
- O ecossistema Raspberry Pi preserva a familiaridade do time e o suporte de longo prazo — a placa segue em produção e com suporte de software ativo.
- O adaptador ALFA AWUS036ACM com chipset MT7612U está disponível na Amazon.com.br, mantendo a mesma decisão técnica do documento original quanto ao driver de captura sem fio.
- A folga orçamentária de aproximadamente R$ 215 cobre variações de frete e eventuais oscilações de preço.

## Caminho de upgrade

Se o projeto crescer para pipelines de scan mais pesados ou o orçamento for revisado em iterações futuras, o Raspberry Pi 5 4 GB é o upgrade natural dentro do mesmo ecossistema — sem troca de família de placa, sistema operacional ou receita de implantação. Essa migração exigirá um novo ADR no momento em que a necessidade for identificada.

## Alternativas rejeitadas

### Raspberry Pi 5 4 GB

Rejeitado por inviabilidade orçamentária nesta iteração.

- O kit completo (placa + case + fonte oficial) custa R$ 959,89 na NextPi em março de 2026 — restando menos de R$ 300 para cartão microSD e adaptador Wi-Fi, o que não é suficiente para cobrir o ALFA AWUS036ACM (~R$ 350).
- Tecnicamente é a escolha superior (CPU A76, PCIe, maior ciclo de vida), mas o critério orçamentário é uma restrição de projeto, não de preferência.
- Mantido como fallback explícito para versões futuras caso o orçamento seja aumentado.

### Orange Pi 5B

Rejeitado por risco operacional e falta de distribuidor nacional.

- Não há distribuidor oficial com estoque regular e nota fiscal no Brasil. A aquisição depende de importação direta, o que reduz repetibilidade e aumenta risco logístico.
- A familiaridade do time é baixa, o que aumenta o esforço de setup e suporte durante a sprint.

### Banana Pi BPI-M5

Rejeitado por ausência de ecossistema nacional e SoC mais antigo.

- Sem distribuidor oficial no Brasil com suporte estruturado.
- A ausência de Wi-Fi onboard adiciona componentes extras antes mesmo de considerar monitor mode.
- Folga de CPU modesta para scans repetidos, normalização e transporte.

### Raspberry Pi 3 Model B+

Rejeitado por insuficiência técnica para o baseline do MVP.

- 1 GB de RAM é muito pouco para updates modernos de Linux, ferramental de scan e buffering de resultados.
- I/O limitado a USB 2.0 vira gargalo assim que entram adaptadores externos.

## Consequências

- A aquisição deve padronizar Raspberry Pi 4 Model B 4 GB, cartão microSD 64 GB A2/V30 e adaptador USB Wi-Fi com chipset MT7612U.
- Distribuidores oficiais no Brasil (RoboCore, FilipeFlop, MakerHero) emitem nota fiscal e garantem compatibilidade com homologação ANATEL — a aquisição deve priorizar esses canais.
- Futuras tasks de implementação devem referenciar o Raspberry Pi 4 como dispositivo padrão desta iteração.
- Se o projeto crescer ou o orçamento for revisado, a migração para Raspberry Pi 5 deve ser formalizada com um novo ADR antes de qualquer aquisição.

## Referências

- NextPi. [Kit Raspberry Pi 5 4GB c/ Case Oficial e Fonte Original](https://www.nextpi.com.br/loja/kit-raspberry-pi-5-4gb-c-case-oficial-e-fonte-original/). Acesso em 28 de março de 2026.
- NextPi. [Raspberry Pi 5 4GB Anatel](https://www.nextpi.com.br/loja/raspberry-pi-5-4gb/). Acesso em 28 de março de 2026.
- RoboCore. [Raspberry Pi 5 4GB](https://www.robocore.net/placa-raspberry-pi/raspberry-pi-5-4gb). Acesso em 28 de março de 2026.
- RoboCore. [Raspberry Pi 4 4GB — Model B Anatel](https://www.robocore.net/placa-raspberry-pi/raspberry-pi-4-4gb). Acesso em 28 de março de 2026.
- RoboCore. [Raspberry Pi — Página da categoria](https://www.robocore.net/raspberry-pi). Acesso em 28 de março de 2026.
- MakerHero. [Raspberry Pi 4 Model B Anatel](https://www.makerhero.com/produto/raspberry-pi-4-model-b/). Acesso em 28 de março de 2026.
- FilipeFlop. [Categoria Raspberry Pi](https://www.filipeflop.com). Acesso em 28 de março de 2026.
- SempreUpdate. [Preço Raspberry Pi 2026: Crise da IA e DRAM encarece modelos em 70%](https://sempreupdate.com.br/aumento-preco-raspberry-pi-2026-crise-ia-dram/). Acesso em 28 de março de 2026.
- CNX Software. [Raspberry Pi 4 dual RAM variant introduced to mitigate RAM price increases](https://www.cnx-software.com/2026/02/05/raspberry-pi-4-dual-ram-variant-introduced-to-mitigate-ram-price-increases-and-supply-challenges/). Acesso em 28 de março de 2026.
- Amazon.com.br. [ALFA Network AWUS036ACM Adaptador Wi-Fi AC1200](https://www.amazon.com.br/Adaptador-AC1200-alcance-antenas-externas/dp/B08BJS8FXD). Acesso em 28 de março de 2026.
- Linux Wireless Documentation. [Wireless modes](https://wireless.docs.kernel.org/en/latest/en/users/documentation/modes.html). Acesso em 28 de março de 2026.
- Aircrack-ng. [compatibility_drivers](https://aircrack-ng.org/doku.php?id=compatibility_drivers). Acesso em 28 de março de 2026.
- ALFA Network Docs. [Linux support for MT7612U based products](https://docs.alfa.com.tw/Support/Linux/MT7612U/). Acesso em 28 de março de 2026.
- Raspberry Pi Documentation. [Raspberry Pi 4 Model B specifications](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/). Acesso em 28 de março de 2026.
- Orange Pi. [Orange Pi 5B](https://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5B.html). Acesso em 28 de março de 2026.