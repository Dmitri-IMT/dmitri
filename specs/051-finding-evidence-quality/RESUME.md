# Retomada da Entrega A — 051-finding-evidence-quality

## Limite atual

Usuário limitou a execução em 2026-10-10: concluir somente tarefa 4 com testes e aprovação, salvar contexto e parar antes da tarefa 5. Tarefas 5–11 e gates completos de backend/frontend/hardware permanecem pendentes. Não presumir API de leitura, UI, relatórios, IA ou emissão do agente concluídos.

## Checkout e segurança operacional

- Repo: C:/Users/mathf/OneDrive/Documentos/imt/TCC/dmitri-repo/dmitri.
- Branch: feature/scan-adjusts-improve. Base HEAD: 471739f2fd44beb44ccfb4e895b9ab6ee537234f.
- Código está apenas no working tree; sem commit, push, PR ou deploy.
- Nenhum scan real, SSH ou nova verificação ativa.
- Backend testado somente em dmitri_test. Banco dev não foi migrado por esta execução; serviços existentes não foram interrompidos.
- Revisão nova: 20261010_40, pai20261002_39. Pytest conftest pode terminar fazendo downgrade da base de teste; não inferir head atual sem verificar/preparar dmitri_test.

## Decisão de vínculo

ISSUE_KEY_DECISION.md e adendos ARCHITECTURE/INTEGRATION definem issue_key opcional1–256/null no ingest, metadado nullable em FindingRecord e booleano interno issue_key_ambiguous absorvente. Sem alterar dedupe_key, identidade SQL ou HostFindingRecord. Chave/fonte/regra não confirmam sem fatos/alcance validados. Configuração com CVE referenciada conserva condição da configuração. Agente mantém exclude=True até tarefa10; rollout backend/API/worker/revisão antes do agente. Não há capability fallback ou reenvio422 sem metadados.

## Execução e revisão

Tarefas1–3 APPROVE independente. Tarefa4 corrigindo REJECT1: CPE job precisa unir standalone MS17 negativo persistido; merge standalone precisa cap512/flag monotônica; negativo não fecha histórico; standalone-only reingest recalcula findings existentes/snapshots. Resultado final de tarefa4 será registrado em PROGRESS/TASKS antes da parada.

Fluxo autorizado: coder/tester Luna medium; reviewer Sol6.1 high para parser/contrato/política/reconciliação e medium apresentação. Seleção real fork_turns none; TOMLs referência. USAGE registra despachos reais, sem tokens/quota/custo/service-tier medidos.

## Runner backend reutilizável

TEMP: C:/Users/mathf/AppData/Local/Temp/dmitri-backend-focal.ps1. Se ausente, recriar com o conteúdo abaixo. Não registrar URL/credenciais resolvidas em saída. O script captura DATABASE_URL_DIRECT internamente do API existente e troca apenas database para dmitri_test; Docker efêmero usa mesma rede/venv, repo inteiro readonly /workspace. Isso resolve contracts/frontend/scripts relativos sem cópias no serviço.

Uso PowerShell:

```powershell
& 'C:/Users/mathf/AppData/Local/Temp/dmitri-backend-focal.ps1' tests/test_scan_evidence.py -q
```

```powershell
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = 'Stop'
$taskRepoRoot = 'C:\Users\mathf\OneDrive\Documentos\imt\TCC\dmitri-repo\dmitri'
$taskArgumentJson = ConvertTo-Json -InputObject @($PytestArgs) -Compress
$taskArgumentJsonBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($taskArgumentJson))
$taskDirectUrl = (& docker exec dmitri-main-test-api-1 /opt/venv/bin/python -c "import os; print(os.environ['DATABASE_URL_DIRECT'])").Trim()
$taskRunnerScript = @'
import json
import base64
import os
import subprocess
import sys
from sqlalchemy.engine import make_url
test_url = make_url(os.environ["DATABASE_URL_DIRECT"]).set(database="dmitri_test")
assert test_url.database == "dmitri_test"
test_env = os.environ.copy()
test_env["DATABASE_URL_TEST"] = test_url.render_as_string(hide_password=False)
test_args = json.loads(base64.b64decode(os.environ["DMITRI_FOCAL_ARGS_B64"]))
raise SystemExit(subprocess.run([sys.executable, "-m", "pytest", *test_args], cwd="/workspace/backend", env=test_env).returncode)
'@
$taskDockerArgs = @(
    'run', '--rm', '-i',
    '--network', 'dmitri-main-test_default',
    '--volumes-from', 'dmitri-main-test-api-1',
    '--mount', "type=bind,source=$taskRepoRoot,target=/workspace,readonly",
    '--env', "DMITRI_FOCAL_ARGS_B64=$taskArgumentJsonBase64",
    '--env', "DATABASE_URL_DIRECT=$taskDirectUrl",
    '--env', 'PYTHONPATH=/workspace/backend/src',
    '--workdir', '/workspace/backend',
    'dmitri-sim-backend:local',
    '/opt/venv/bin/python', '-'
)
$taskRunnerScript | & docker @taskDockerArgs
exit $LASTEXITCODE
```

Ruff real: pyproject.toml da RAIZ contém E/F/I; backend/pyproject.toml não contém seção Ruff. Rodar cwd backend com --config absoluto raiz. Não forçar TOML backend nem repetir diagnóstico460 derivado de configuração inválida; esse número não é baseline.

Executar um único pytest por vez em dmitri_test. Sempre aguardar a chamada/guardar session_id, output final e exitcode; após timeout, poll da mesma sessão. Não iniciar nova suite enquanto runner próprio anterior estiver ativo. Resultado parcial sem exitcode não estabelece gate verde.

```powershell
uvx ruff check --config 'C:/Users/mathf/OneDrive/Documentos/imt/TCC/dmitri-repo/dmitri/pyproject.toml' src/api/services/persistence.py
```

database.ps1 -NoClean foi tentado: SupabaseCLI ausentePATH. Docker existente dmitri-main-test_default/API+DB tem dmitri_test. Não executar cleanup padrão do helper. Windows Application Control bloqueou alguns executáveis .venv; uv run --no-sync depois funcionou para agent, alternativa Python uv3.12.13 externo com PYTHONPATH TEMP/dmitri-task1-hardware-agent-venv/Lib/site-packages. Nunca usar banco dev no pytest ou formatador global.

## Próxima sessão

Ler AGENTS.md, TASKS.md, PROGRESS.md e decisão issue_key; conferir branch/HEAD/status preservando working tree. Não reabrir aprovação inicial. Com task4 aprovada e limite usuário liberado, continuar tarefa5 (reads/resumo global antes paginação),6(relatórios/PDFskillrenderQA),7(IA+backendfullgate),8(frontendtypes/UI/fullgate npm.cmd),9(adaptadores/policylocal),10(emissão/todosfrontdoors/transporte),11(TUI/corpus/fullgateagent), docs-sync uma vez. Próxima sessão precisa autorização para retomar além do limite atual. Sem commit/push/deploy automático.

## Arquivos alterados e resultado final

Consultar git status --short e ledger; resultado final e lista abaixo refletem o fechamento parcial.

## Fechamento final deste limite

Tarefas1–4 COMPLETE com review APPROVE independente; Task4 teve3 rejeições corrigidas, último review em2026-10-10: narrow6 passed/20 deselected18,37s exit0; Ruff raiz final passed2,32s exit0. Migração40 foi testada upgrade/downgrade/upgrade em dmitri_test com head40 e finalizer; fullgates permanecem pendentes. Nenhum pytest ativo no handoff final. Full inventory25 cuja sessão foi perdida NÃO conta como aprovação. Alteração incidental de hardware-agent/uv.lock versão1.0.4→1.0.5 causada pelo ambiente foi removida; dependências não mudaram.

Docs-sync completo não executado no fechamento parcial por limite explícito do usuário; .claude/docs pode estar defasado até entrega completa. Specs/PROGRESS/TASKS/USAGE/RESUME guardam fatos atuais. Nenhum commit/push/deploy/scan/PR; nenhuma migração dev.

Arquivos no working tree ao encerrar (inclui aprovações preexistentes de specs):

- `backend/src/api/models/persistence.py`
- `backend/src/api/schemas/read.py`
- `backend/src/api/schemas/scan.py`
- `backend/src/api/services/enrichment.py`
- `backend/src/api/services/inventory.py`
- `backend/src/api/services/persistence.py`
- `backend/src/api/services/scan_evidence.py`
- `backend/tests/test_contract_fidelity.py`
- `backend/tests/test_enrichment_retries.py`
- `backend/tests/test_ingest_scan.py`
- `backend/tests/test_ingest_schema.py`
- `backend/tests/test_inventory_reconcile.py`
- `backend/tests/test_scan_evidence.py`
- `backend/tests/test_scan_ingest_route.py`
- `contracts/examples/scan_result.example.json`
- `contracts/openapi/openapi.yaml`
- `hardware-agent/src/agent/normalize/contracts.py`
- `hardware-agent/src/agent/normalize/findings.py`
- `hardware-agent/tests/test_contract_models.py`
- `hardware-agent/tests/test_findings.py`
- `hardware-agent/uv.lock`
- `specs/051-finding-evidence-quality/ARCHITECTURE.md`
- `specs/051-finding-evidence-quality/DESIGN.md`
- `specs/051-finding-evidence-quality/INTEGRATION.md`
- `specs/051-finding-evidence-quality/PROGRESS.md`
- `specs/051-finding-evidence-quality/TRUTH.md`
- `specs/051-finding-evidence-quality/USAGE.md`
- `backend/alembic/versions/20261010_40_finding_evidence_quality.py`
- `backend/tests/test_finding_evidence_quality_migration.py`
- `specs/051-finding-evidence-quality/ISSUE_KEY_DECISION.md`
- `specs/051-finding-evidence-quality/RESUME.md`
- `specs/051-finding-evidence-quality/TASKS.md`
