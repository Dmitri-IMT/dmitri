# Roteiro de laboratório — NSPi Modbus inventory

Este roteiro cobre o primeiro incremento implementado do novo NSPi. Ele deve
ser usado somente na rede de laboratório autorizada. O `inventory` é ativo: o
Nmap executa o `modbus-discover` existente e o agente pode enviar uma consulta
FC43/MEI 14 para completar a identificação. Esta versão não executa FC01-FC06,
não mapeia endereços de processo e não envia escrita Modbus.

## 1. Preparar o Raspberry Pi

No repositório e na branch `feature/nspi-modbus-methodology`:

```bash
cd hardware-agent
uv sync --extra dev --locked
uv run pytest tests/integration/test_modbus_lab.py -q
```

O teste local esperado termina com `3 passed`. Ele sobe um servidor apenas em
`127.0.0.1`, valida o FC43 e encerra o servidor ao final.

Confirme a interface e o CIDR que pertencem ao laboratório:

```bash
ip -br address
ip route
```

## 2. Executar o inventory real

Substitua o CIDR abaixo pelo CIDR autorizado. Prefira uma janela em que os
responsáveis pelo laboratório possam observar os CLPs.

```bash
uv run dmitri agent nspi 192.168.10.0/24 \
  2>nspi-inventory-progress.log | tee nspi-inventory-run.json
```

A linha final contém `outcome`, `scan_id` e o caminho absoluto em
`result_path`. Esse caminho é a fonte mais confiável para localizar o JSON.
Como alternativa:

```bash
find "$HOME/.local/share/dmitri" -type f -name '*.json' -print
```

## 3. Inspecionar o resultado

```bash
RESULT_PATH=$(jq -r '.result_path' nspi-inventory-run.json)
jq '.metadata | {
  nspi_submode,
  modbus_candidates,
  modbus_confirmed,
  modbus_units,
  modbus_requests_sent,
  modbus_timeouts,
  modbus_write_requests_sent
}' "$RESULT_PATH"
```

Para listar apenas os equipamentos com inventário industrial:

```bash
jq '.hosts[]
  | select(.industrial_services | length > 0)
  | {
      ip,
      hostname,
      services: [.industrial_services[] | {
        port,
        confidence,
        evidence_sources,
        units
      }]
    }' "$RESULT_PATH"
```

Interpretação esperada:

- `suspected`: TCP/502 está aberto, mas não houve resposta Modbus conclusiva;
- `confirmed`: o serviço do Nmap ou uma resposta Modbus confirmou o protocolo;
- `unit_id`: endereço lógico respondente atrás daquele endpoint/gateway;
- `device_identification`: objetos padronizados retornados por FC43, quando o
  equipamento os implementa;
- `exception`, `timeout` ou `error`: evidência inconclusiva ou rejeição do
  equipamento, sem inventar fabricante, versão ou vulnerabilidade;
- `modbus_write_requests_sent`: deve permanecer `0` no inventory.

Ausência de fabricante/produto/firmware não significa falha do scan: muitos
equipamentos não implementam todos os objetos FC43.

## 4. Evidência de que não houve escrita

Opcionalmente capture somente o tráfego TCP/502 durante o teste:

```bash
sudo tcpdump -i eth0 -nn -s0 -w nspi-inventory.pcap 'tcp port 502'
```

Depois do scan, confirme em Wireshark/tshark que a captura não contém FC05,
FC06, FC15 ou FC16. O `inventory` ainda conterá consultas ativas de descoberta
e identificação; ele não deve ser confundido com monitoramento passivo.

## 5. O que registrar para o TCC

- modelo do Raspberry, versão do SO, do agente e do Nmap;
- CIDR, interface, horário e duração total;
- quantidade de hosts, candidatos Modbus, endpoints confirmados e Unit IDs;
- requisições, timeouts, tamanho do JSON e pico observado de CPU/memória;
- JSON, logs, PCAP e confirmação do responsável pelo laboratório;
- divergências entre o inventário e a lista conhecida de CLPs/gateways.

O `read_only_mapping` permanece como o próximo incremento. Ele só será
habilitado depois que seus limites de faixa, orçamento de requisições, atraso e
captura de valores estiverem implementados e testados.
