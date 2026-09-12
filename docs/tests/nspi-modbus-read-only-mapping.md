# Roteiro de laboratório — NSPi Modbus `read_only_mapping`

Este roteiro valida o mapeamento ativo somente de leitura em uma rede OT
controlada e autorizada. O modo mantém o pipeline Nmap/NSE do NSPi, identifica
endpoints e Unit IDs e envia somente FC01, FC02, FC03, FC04 e FC43. Ele não
possui método de escrita Modbus.

## 1. Preparar e validar o agente

Na branch da funcionalidade:

```bash
cd hardware-agent
uv sync --extra dev --locked
uv run pytest tests/integration/test_modbus_lab.py -q
```

Sem arquivo de política, o agente usa automaticamente a amostra genérica:
endereços zero-based `0-3` em cada um dos quatro espaços Modbus, no máximo
quatro Unit IDs descobertos, intervalo de 100 ms e limite compartilhado de 32
requisições Modbus por host.

Para usar faixas conhecidas do laboratório, copie e revise o exemplo:

```bash
mkdir -p "$HOME/.config/dmitri"
cp ../docs/examples/ot-policy.example.json \
  "$HOME/.config/dmitri/ot-policy.json"
```

O seletor CIDR e cada faixa precisam corresponder ao ambiente autorizado. O
arquivo é configuração local do instalador; ele não é recebido da interface web
nem do comando remoto. Um JSON inválido interrompe a etapa em vez de ampliar a
varredura silenciosamente. O caminho pode ser substituído explicitamente com
`DMITRI_OT_POLICY_PATH`.

Uma correspondência apenas por fabricante ou produto só pode selecionar faixas
contidas nos endereços `0-3` da amostra genérica, com limites iguais ou menores.
Faixas fora dessa amostra exigem correspondência por CIDR ou MAC. Se um host
alcançar seu limite de tempo, o agente conserva o que coletou e tenta os hosts
seguintes enquanto ainda houver tempo na etapa OT.

## 2. Executar pela CLI

Confirme primeiro a interface e a rota do laboratório:

```bash
ip -br address
ip route
```

Depois execute, substituindo o CIDR pelo autorizado:

```bash
uv run dmitri agent nspi read_only_mapping 192.168.10.0/24 \
  2>nspi-mapping-progress.log | tee nspi-mapping-run.json
```

A linha JSON de saída contém `outcome`, `scan_id` e `result_path`. Obtenha o
caminho sem procurar diretórios manualmente:

```bash
RESULT_PATH=$(jq -r '.result_path' nspi-mapping-run.json)
```

Na TUI, o caminho equivalente é **Start scan → interface → NSPi → Read-only
mapping**. Active validation is disabled on the TUI mode list and is not offered
in the web UI.

## 3. Conferir o resultado

```bash
jq '.metadata | {
  nspi_submode,
  modbus_candidates,
  modbus_confirmed,
  modbus_units,
  modbus_requests_sent,
  modbus_mapping_requests_sent,
  modbus_mapping_ranges_readable,
  modbus_mapping_ranges_skipped,
  modbus_cpe_candidates,
  modbus_write_requests_sent
}' "$RESULT_PATH"
```

Liste as faixas observadas:

```bash
jq '.hosts[]
  | .ip as $ip
  | .industrial_services[]
  | .port as $port
  | .mapping_source as $mapping_source
  | .units[]
  | {
      ip: $ip,
      port: $port,
      mapping_source: $mapping_source,
      unit_id,
      identification_sources,
      device_identification,
      address_ranges
    }' "$RESULT_PATH"
```

Um trecho esperado é:

```json
{
  "mapping_source": "generic_baseline",
  "unit_id": 1,
  "identification_sources": ["pymodbus-fc43"],
  "device_identification": {
    "vendor_name": "Schneider Electric",
    "product_code": "BMX P34",
    "major_minor_revision": "2.60"
  },
  "address_ranges": [
    {
      "address_space": "holding_register",
      "start_address": 0,
      "count": 4,
                      "status": "readable",
                      "label": "generic baseline sample",
                      "value_digest": "hmac-sha256:..."
    }
  ]
}
```

`readable` produz o finding contextual de leitura sem autenticação. Uma exceção
ou timeout permanece observação, não CVE. Se FC43 identificar de forma exata um
Modicon M340/M580 Schneider e uma revisão numérica, o agente adiciona um CPE de
firmware à porta; o backend usa seu fluxo existente NVD/KEV/EPSS para procurar
vulnerabilidades conhecidas. Dados incompletos ou ambíguos não geram CPE.

## 4. Evidência de segurança e dados para o TCC

Durante o teste, uma captura opcional permite provar as funções enviadas:

```bash
sudo tcpdump -i eth0 -nn -s0 -w nspi-read-only-mapping.pcap 'tcp port 502'
```

Confirme que não existem FC05, FC06, FC15, FC16, FC22 ou FC23. Registre modelo
do Raspberry, versões, duração, pico de CPU/RSS, tamanho do JSON, número de
requisições/timeouts/faixas e a comparação com o mapa conhecido do laboratório.
Não interprete um valor de registrador como uma ação física sem documentação ou
experimento controlado separado.
