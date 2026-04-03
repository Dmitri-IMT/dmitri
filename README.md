# Vulnerability Scanner Device

Monorepo do Trabalho de Conclusão de Curso (Engenharia de Computação) que irá entregar um dispositivo embarcado capaz de conectar-se a uma rede local, executar varreduras com o Nmap e disponibilizar relatários abrangentes através de um backend e de um aplicativo mobile.

# Integrantes
- Giuliano Rodrigues Tumoli // 21.00036-0
- Guilherme Thomasi Ronca // 22.00522-6
- Joao Vitor Marques Ferrenha Cerqueira // 22.00085-2
- Matheus Santos Feitosa // 20.00628-4
- Rafael Maciel Bertani // 21.00634-2

## Componentes do sistema
1. **Hardware Agent (Raspberry Pi 4 + Python + Nmap)**: Executará varreduras rápidas ou completas, normalizará os resultados segundo os schemas compartilhados e enviará os relatários ao backend via REST/HTTPS.
2. **Backend API (FastAPI + PostgreSQL)**: Receberá e validará os resultados, armazenará em PostgreSQL e fornecerá endpoints para consulta pelos clientes.
3. **Banco de Dados (PostgreSQL)**: Fonte única para histórico de scans, dispositivos, portas, findings e telemetria de agentes.
4. **Aplicativo Mobile (Flutter)**: Interface destinada a usuários finais para acompanhar status do dispositivo, resultados e recomendações.
5. **Contratos Compartilhados**: JSON Schemas, OpenAPI e exemplos que asseguram alinhamento entre todos os componentes.
6. **Infraestrutura & CI**: Docker, docker-compose, templates de variáveis de ambiente e pipelines de validação contínua.

## Estrutura do Monorepo
```
docs/                  Documentação inicial (arquitetura, API, ameaça, roteiros de demo)
contracts/             Schemas JSON, OpenAPI e exemplos de payloads
hardware-agent/        Pacote Python para o agente embarcado (placeholders)
backend/               Esqueleto FastAPI + Dockerfile + layout de camadas
mobile/                Diretrizes do aplicativo Flutter (README)
infra/                 docker-compose, env.example, instruções de infraestrutura
.github/workflows/     Pipeline CI para checar schemas e compilar fontes
LICENSE, README.md, .gitignore
```

## Fluxo de alto nível
1. O agente de hardware agenda e executa scans (quick/full) usando o Nmap na sub-rede configurada.
2. Os resultados são normalizados em JSON conforme `contracts/schemas/scan_result.schema.json`.
3. O backend recebe os payloads, persiste no PostgreSQL e prepara dados agregados.
4. O aplicativo mobile consome os endpoints documentados em `docs/api.md` para exibir históricos, alertas e recomendações.

## Estado Atual
- Estrutura de diretórios, arquivos placeholder e documentação inicial concluídos.
- Sem qualquer lógica de negócio implementada (scans, validações, rotas, persistência ou UI).
- Ferramentas de desenvolvimento, testes automatizados e integrações externas serão definidas nas próximas fases.

**Documentação completa de arquitetura:** [ARCHITECTURE.md](ARCHITECTURE.md)

## Setup

Siga o guia completo:

→ [docs/DEV-SETUP.md](docs/DEV-SETUP.md)

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md)