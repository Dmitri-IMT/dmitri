# Selecao de Hardware

## Contexto

Este ADR define a plataforma de hardware do agente embarcado do scanner de vulnerabilidades. O dispositivo executara um Linux headless, rodara ferramentas locais de descoberta e enumeracao de servicos, normalizara os resultados e enviara os payloads para a API do backend.

Esta decisao precisa equilibrar:

- custo por unidade implantada
- folga de CPU e RAM para scans paralelos e processamento de resultados
- suporte Linux estavel para ferramentas da classe do Nmap
- disponibilidade de acessorios para implantacoes repetiveis
- familiaridade do time e manutencao de longo prazo

## Escopo e premissas

- Como a task cita familias de hardware, e nao SKUs exatos, esta comparacao usa as placas mais proximas em cada linha: Raspberry Pi 3 Model B+, Raspberry Pi 4 Model B, Raspberry Pi 5, Orange Pi 5B e Banana Pi BPI-M5.
- Os precos abaixo refletem valores observados em 24 de marco de 2026 nas fontes linkadas.
- Para Raspberry Pi 4 e Raspberry Pi 5, o alvo base considerado foi a variante de 4GB, pois ela atende o MVP do agente sem inflar o BOM.
- Para captura via Wi-Fi, conectividade de gerenciamento e captura de pacotes sao tratadas como necessidades separadas.

## Comparacao tecnica

| Plataforma | CPU | RAM | USB | Rede | Observacao de mercado |
| --- | --- | --- | --- | --- | --- |
| Raspberry Pi 3 Model B+ | Broadcom BCM2837B0, quad-core Cortex-A53 1.4GHz | 1GB | 4 x USB 2.0 | Ethernet 300Mb, Wi-Fi dual-band 802.11ac, BT 4.2 | Menor custo de entrada, mas ja limitado para cargas modernas de scan |
| Raspberry Pi 4 Model B | Broadcom BCM2711, quad-core Cortex-A72 1.8GHz | 1GB/2GB/4GB/8GB | 2 x USB 3.0, 2 x USB 2.0 | Gigabit Ethernet, Wi-Fi dual-band 802.11ac, BT 5.0 | Plataforma madura e suportada ate pelo menos janeiro de 2034 |
| Raspberry Pi 5 | Broadcom BCM2712, quad-core Cortex-A76 2.4GHz | 1GB/2GB/4GB/8GB/16GB | 2 x USB 3.0, 2 x USB 2.0 | Gigabit Ethernet, Wi-Fi 5 dual-band 802.11ac, BT 5.0, PCIe 2.0 x1 | Melhor desempenho dentro do ecossistema Raspberry Pi; suporte ate pelo menos janeiro de 2036 |
| Orange Pi 5B | Rockchip RK3588S, 8-core (4 x A76 + 4 x A55) ate 2.4GHz | 4GB/8GB/16GB | 1 x USB 3.0, 2 x USB 2.0 | Gigabit LAN, Wi-Fi 6, BT 5.3 | Desempenho bruto muito forte, mas com menos consistencia de software e acessorios |
| Banana Pi BPI-M5 | Amlogic S905X3, quad-core Cortex-A55 2.0GHz | 4GB | 4 x USB 3.0 | 1GbE, sem Wi-Fi onboard, 16GB eMMC | Preco competitivo, mas com SoC mais antigo e menos conveniencia de rede |

## Acessorios e observacoes de implantacao

### Refrigeracao

- O Raspberry Pi 5 deve ser implantado com refrigeracao ativa. A Raspberry Pi e a PiShop apontam o case oficial do Pi 5 com ventoinha integrada ou o Active Cooler oficial para carga sustentada.
- O Raspberry Pi 4 consegue rodar o agente, mas refrigeracao ativa tambem e recomendada para janelas longas de scan ou ambientes quentes.
- O Orange Pi 5B tambem se beneficia de refrigeracao adicional, mas o ecossistema e mais fragmentado e dependente da revisao da placa.
- Banana Pi M5 e Raspberry Pi 3 B+ suportam cenarios mais leves, mas perdem folga de desempenho antes das placas mais novas.

### Alimentacao

- O Raspberry Pi 5 precisa de fonte USB-C PD de 5V/5A para evitar limitacoes de desempenho e corrente nas portas USB.
- O Raspberry Pi 4 usa fonte USB-C de 5V/3A.
- O Raspberry Pi 3 B+ usa fonte micro-USB de 2.5A.
- A familia Raspberry Pi tem o caminho mais claro de fonte oficial para implantacoes repetiveis.

### Dimensionamento de armazenamento

Para o MVP do scanner, a demanda realista de armazenamento e:

| Componente | Espaco estimado |
| --- | --- |
| Raspberry Pi OS Lite + updates + margem de recuperacao | 6GB |
| Runtime Python, virtualenv, Nmap, pacotes de suporte e logs | 4GB |
| Saida temporaria de scans, JSON normalizado, logs rotacionados e pequenos pcaps | 8GB a 12GB |
| Espaco livre para upgrades, wear leveling e margem de rollback | 20GB+ |

Decisao: usar microSD de 64GB A2/V30 como minimo de producao. Cartao de 32GB fica aceitavel apenas para laboratorio com baixa retencao.

## Decisao sobre Wi-Fi e modo promiscuo

O Wi-Fi onboard e suficiente para conectividade do agente, atualizacoes e telemetria, mas nao deve ser a interface principal para scans em modo promiscuo ou monitor mode.

Motivos:

- A documentacao do Linux Wireless trata monitor mode como capacidade dependente de hardware e driver, deixando claro que nem todo dispositivo suporta isso de forma completa.
- O Aircrack-ng informa que drivers de fabricante em geral nao oferecem bom suporte a monitor mode, enquanto drivers alinhados ao ecossistema mac80211 tendem a ser mais previsiveis.
- Para um scanner implantavel em campo, precisamos de um adaptador USB repetivel e substituivel, em vez de depender do comportamento do Wi-Fi onboard de cada placa.

Decisao: usar um adaptador USB Wi-Fi dedicado para cenarios de monitor mode ou captura de pacotes, deixando o Wi-Fi onboard para trafego de gerenciamento.

Adaptador recomendado para o BOM base:

- ALFA AWUS036ACM, porque a ALFA documenta suporte Linux para o MT7612U, incluindo compatibilidade com Raspberry Pi OS, e o produto aparece com preco de varejo estavel.

## BOM da plataforma selecionada

Plataforma selecionada: Raspberry Pi 5 4GB

| Item | Qtd | Preco unitario | Fonte |
| --- | --- | --- | --- |
| Raspberry Pi 5 4GB | 1 | $85.00 | [PiShop](https://www.pishop.us/product/raspberry-pi-5-4gb/) |
| Case do Raspberry Pi 5 com ventoinha integrada | 1 | $10.95 | [PiShop](https://www.pishop.us/product/raspberry-pi-case-for-pi-5-red-white/) |
| Fonte Raspberry Pi 27W USB-C | 1 | $12.95 | [PiShop](https://www.pishop.us/product/raspberry-pi-27w-usb-c-power-supply-black-us/) |
| microSD oficial Raspberry Pi 64GB, A2/V30 | 1 | $19.95 | [PiShop](https://www.pishop.us/product/official-raspberry-pi-microsd-card-with-raspberry-pi-os-64-bit-64gb/) |
| Adaptador USB Wi-Fi ALFA AWUS036ACM | 1 | $46.97 | [Rokland](https://store.rokland.com/collections/all-alfa-network-products/802-11ac) |
| Adaptador USB 3.0 para gigabit Ethernet (opcional) | 1 | $24.99 | [Best Buy](https://www.bestbuy.com/site/j5create-usb-3-0-gigabit-ethernet-adapter-silver/2001047.p) |

Total do BOM base (sem a segunda Ethernet opcional): $175.82

Total do BOM expandido (com a segunda Ethernet opcional): $200.81

Observacoes:

- O adaptador USB-to-Ethernet opcional so e necessario se quisermos implantacao dual-homed, espelhamento de trafego ou um uplink de gerenciamento dedicado.
- O case do Pi 5 ja inclui refrigeracao ativa, entao nao e necessario adicionar um cooler separado no BOM base.

## Rubrica de pontuacao

Pesos:

- Desempenho: 30
- Suporte da comunidade e maturidade de software: 25
- Custo: 20
- Disponibilidade e ciclo de vida: 15
- Familiaridade do time: 10

Escala:

- 1 = ruim
- 3 = aceitavel
- 5 = excelente

## Matriz de pontuacao

| Plataforma | Desempenho (30) | Comunidade (25) | Custo (20) | Disponibilidade (15) | Familiaridade (10) | Nota ponderada / 100 |
| --- | --- | --- | --- | --- | --- | --- |
| Raspberry Pi 5 4GB | 5 | 5 | 4 | 5 | 5 | 96 |
| Raspberry Pi 4 4GB | 3 | 5 | 5 | 4 | 5 | 85 |
| Orange Pi 5B | 5 | 2 | 3 | 2 | 1 | 56 |
| Raspberry Pi 3 Model B+ | 1 | 4 | 5 | 2 | 4 | 52 |
| Banana Pi BPI-M5 | 2 | 2 | 4 | 2 | 1 | 44 |

## Decisao

Adotar o Raspberry Pi 5 4GB como plataforma padrao de hardware para o MVP e para os primeiros pilotos.

Motivos:

- Ele entrega a melhor nota total quando desempenho, ciclo de vida, maturidade de software e familiaridade do time sao avaliados em conjunto.
- A diferenca de custo em relacao ao Raspberry Pi 4 4GB e pequena o bastante para justificar a folga extra de CPU, I/O mais rapido e ciclo de vida maior.
- Ele preserva o ecossistema Raspberry Pi ja assumido no repositorio, reduzindo risco operacional frente a Orange Pi ou Banana Pi.
- Ele mantem um caminho limpo de evolucao para NVMe, pipelines de scan mais pesados ou cache local sem precisar trocar de familia de placa.
- Com o case oficial e a fonte de 27W, a receita de implantacao fica repetivel e simples de repassar ao time.

## Alternativas rejeitadas

### Raspberry Pi 4 4GB

Rejeitado como alvo principal, mas mantido como fallback.

Motivos para nao selecionar:

- Continua viavel, mas tem folga de CPU claramente inferior ao Raspberry Pi 5.
- Nao oferece a mesma margem para expansao de armazenamento e processamento local futuro.
- O lado do hardware-agent tende a crescer, entao comprar a placa mais antiga para producao encurta demais a vida util da decisao.

### Orange Pi 5B

Rejeitado por risco operacional, nao por falta de desempenho.

Motivos para nao selecionar:

- O silicio e excelente, mas a consistencia de distro, a qualidade da documentacao e o suporte de longo prazo sao inferiores aos do Raspberry Pi.
- O sourcing de acessorios e mais fragmentado e mais sujeito a mudar conforme revisao da placa ou regiao.
- A familiaridade do time e baixa, o que aumenta esforco de setup e suporte durante a sprint e na implantacao.

### Banana Pi BPI-M5

Rejeitado por oferecer pouco ganho frente a Raspberry Pi 4 e Raspberry Pi 5.

Motivos para nao selecionar:

- A folga de CPU e modesta para um dispositivo que deve executar scans repetidos, normalizacao, logs e transporte seguro.
- Nao traz a mesma profundidade de ecossistema do Raspberry Pi.
- A ausencia de Wi-Fi onboard adiciona mais partes moveis antes mesmo de considerar monitor mode.

### Raspberry Pi 3 Model B+

Rejeitado por ficar apertado demais para o baseline do MVP.

Motivos para nao selecionar:

- 1GB de RAM e muito pouco para updates modernos de Linux, ferramental de scan e buffering de resultados.
- I/O limitado a USB 2.0 vira gargalo assim que entram adaptadores externos.
- Pode funcionar para demos ou laboratorios muito pequenos, mas nao e uma base segura para producao.

## Consequencias

- Futuras tasks de implementacao devem alinhar a documentacao que ainda referencia Raspberry Pi 4 como dispositivo padrao.
- A aquisicao deve padronizar Raspberry Pi 5 4GB, armazenamento 64GB A2/V30 e adaptador USB Wi-Fi dedicado para fluxos de captura.
- Se o projeto crescer para grandes capturas de pacotes ou bases locais de enriquecimento, devemos revisitar o Raspberry Pi 5 com NVMe em vez de trocar novamente de familia de placa.

## Referencias

- Raspberry Pi. [Raspberry Pi 5](https://www.raspberrypi.com/products//raspberry-pi-5/). Acesso em 24 de marco de 2026.
- Raspberry Pi. [Raspberry Pi 4 Model B specifications](https://www.raspberrypi.com/products//raspberry-pi-4-model-b/specifications/?variant=raspberry-pi-4-model-b-8gb). Acesso em 24 de marco de 2026.
- Raspberry Pi Documentation. [Raspberry Pi computer hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html). Acesso em 24 de marco de 2026.
- PiShop US. [Raspberry Pi 5 4GB](https://www.pishop.us/product/raspberry-pi-5-4gb/). Acesso em 24 de marco de 2026.
- PiShop US. [Raspberry Pi Case for Pi 5](https://www.pishop.us/product/raspberry-pi-case-for-pi-5-red-white/). Acesso em 24 de marco de 2026.
- PiShop US. [Raspberry Pi 27W USB-C Power Supply](https://www.pishop.us/product/raspberry-pi-27w-usb-c-power-supply-black-us/). Acesso em 24 de marco de 2026.
- PiShop US. [Official Raspberry Pi microSD Card with Raspberry Pi OS 64-bit - 64GB](https://www.pishop.us/product/official-raspberry-pi-microsd-card-with-raspberry-pi-os-64-bit-64gb/). Acesso em 24 de marco de 2026.
- PiShop US. [Raspberry Pi boards price list](https://www.pishop.us/first-look-at-raspberry-pi-4/). Acesso em 24 de marco de 2026.
- PiShop US. [Raspberry Pi 3 Model B+ bulk listing](https://www.pishop.us/product/raspberry-pi-3-model-b-plus-bulk-purchase/). Acesso em 24 de marco de 2026.
- Orange Pi. [Orange Pi 5B](https://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5B.html). Acesso em 24 de marco de 2026.
- ProE. [Orange Pi 5B 8GB RAM 64GB eMMC](https://www.proe.vn/orange-pi-5b-8gb-ram-64gb-emmc). Acesso em 24 de marco de 2026.
- Banana Pi Wiki. [Getting Started with M5/M2Pro](https://wiki.banana-pi.org/Getting_Started_with_M5/M2Pro). Acesso em 24 de marco de 2026.
- 52Pi Store. [Banana Pi BPI-M5](https://52pi.com/products/banana-pi-bpi-m5-amlogic-s905x3-quad-core-arm-mali-g31-4gb-lpddr4-ram-16gb-emmc-flash-support-linux-ubuntu-debian-single-board). Acesso em 24 de marco de 2026.
- Linux Wireless Documentation. [Wireless modes](https://wireless.docs.kernel.org/en/latest/en/users/documentation/modes.html). Acesso em 24 de marco de 2026.
- Linux Wireless Documentation. [MediaTek driver family](https://wireless.docs.kernel.org/en/latest/en/users/drivers/mediatek.html). Acesso em 24 de marco de 2026.
- Aircrack-ng. [compatibility_drivers](https://aircrack-ng.org/doku.php?id=compatibility_drivers). Acesso em 24 de marco de 2026.
- ALFA Network. [AWUS036ACM](https://www.alfa.com.tw/products/awus036acm_1). Acesso em 24 de marco de 2026.
- ALFA Network Docs. [Linux support for MT7612U based products](https://docs.alfa.com.tw/Support/Linux/MT7612U/). Acesso em 24 de marco de 2026.
- Rokland. [ALFA products collection](https://store.rokland.com/collections/all-alfa-network-products/802-11ac). Acesso em 24 de marco de 2026.
- Best Buy. [j5create USB 3.0 Gigabit Ethernet Adapter](https://www.bestbuy.com/site/j5create-usb-3-0-gigabit-ethernet-adapter-silver/2001047.p). Acesso em 24 de marco de 2026.
