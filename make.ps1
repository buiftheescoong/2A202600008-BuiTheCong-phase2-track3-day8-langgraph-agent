# Windows helper — thay thế lệnh make cho PowerShell
# Dùng: .\make.ps1 test | .\make.ps1 run-scenarios | .\make.ps1 grade-local | .\make.ps1 lint

param([string]$Target = "help")

$python = ".venv\Scripts\python.exe"

switch ($Target) {
    "install" {
        Write-Host ">>> pip install -e .[dev]" -ForegroundColor Cyan
        & $python -m pip install -e ".[dev]"
    }
    "test" {
        Write-Host ">>> pytest tests/ -v" -ForegroundColor Cyan
        & $python -m pytest tests/ -v
    }
    "lint" {
        Write-Host ">>> ruff check src tests" -ForegroundColor Cyan
        & $python -m ruff check src tests
    }
    "typecheck" {
        Write-Host ">>> mypy src" -ForegroundColor Cyan
        & $python -m mypy src
    }
    "run-scenarios" {
        Write-Host ">>> run-scenarios" -ForegroundColor Cyan
        & $python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
    }
    "grade-local" {
        Write-Host ">>> validate-metrics" -ForegroundColor Cyan
        & $python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
    }
    "export-diagram" {
        Write-Host ">>> export-diagram" -ForegroundColor Cyan
        & $python -m langgraph_agent_lab.cli export-diagram --output outputs/graph.mmd
    }
    "all" {
        Write-Host "=== Running all checks ===" -ForegroundColor Yellow
        & $python -m ruff check src tests
        & $python -m pytest tests/ -q
        & $python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
        & $python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
    }
    default {
        Write-Host "Available targets:" -ForegroundColor Yellow
        Write-Host "  .\make.ps1 install        - Install dependencies"
        Write-Host "  .\make.ps1 test           - Run pytest (make test)"
        Write-Host "  .\make.ps1 lint           - Run ruff linter (make lint)"
        Write-Host "  .\make.ps1 typecheck      - Run mypy (make typecheck)"
        Write-Host "  .\make.ps1 run-scenarios  - Run all scenarios (make run-scenarios)"
        Write-Host "  .\make.ps1 grade-local    - Validate metrics (make grade-local)"
        Write-Host "  .\make.ps1 export-diagram - Export graph Mermaid diagram"
        Write-Host "  .\make.ps1 all            - Run lint + test + scenarios + grade"
    }
}
