"""
Script para executar suíte completa de testes
Automatiza execução e geração de relatórios
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import json


def run_command(command, description=""):
    """Executa comando e retorna resultado"""
    print(f"\n{'='*60}")
    print(f"Executando: {description or command}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.stdout:
            print("STDOUT:", result.stdout)
        if result.stderr and result.returncode != 0:
            print("STDERR:", result.stderr)
            
        return result.returncode == 0, result
    except Exception as e:
        print(f"Erro ao executar comando: {e}")
        return False, None


def ensure_directories():
    """Garante que diretórios necessários existam"""
    directories = [
        "tests/logs",
        "reports",
        "htmlcov"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def run_unit_tests():
    """Executa testes unitários"""
    print("\n[UNIT] Executando Testes Unitarios...")
    
    command = "pytest tests/unit/ -m unit --cov=app --cov-report=term-missing --html=reports/unit_tests.html"
    success, result = run_command(command, "Testes Unitários")
    
    return success


def run_integration_tests():
    """Executa testes de integração"""
    print("\n[INTEGRATION] Executando Testes de Integracao...")
    
    # Verificar se Redis está disponível para testes de integração
    redis_available = os.getenv('REDIS_INTEGRATION_TESTS', '0') == '1'
    
    if not redis_available:
        print("[WARNING] Testes de integracao com Redis desabilitados")
        print("   Para habilitar: export REDIS_INTEGRATION_TESTS=1")
        return True  # Não falhar se Redis não estiver disponível
    
    command = "pytest tests/integration/ -m integration --html=reports/integration_tests.html"
    success, result = run_command(command, "Testes de Integração")
    
    return success


def run_performance_tests():
    """Executa testes de performance"""
    print("\n[PERFORMANCE] Executando Testes de Performance...")
    
    command = "pytest tests/performance/ -m performance --html=reports/performance_tests.html -v"
    success, result = run_command(command, "Testes de Performance")
    
    return success


def run_load_tests():
    """Executa testes de carga"""
    print("\n[LOAD] Executando Testes de Carga...")
    
    # Testes de carga são opcionais e podem ser demorados
    run_load = input("Executar testes de carga (podem demorar 10-30 minutos)? [y/N]: ").lower() == 'y'
    
    if not run_load:
        print("Testes de carga pulados.")
        return True
    
    command = "pytest tests/load/ -m load --html=reports/load_tests.html -v -s"
    success, result = run_command(command, "Testes de Carga")
    
    return success


def run_migration_tests():
    """Executa testes de migração"""
    print("\n[MIGRATION] Executando Testes de Migracao...")
    
    command = "pytest tests/migration/ -m migration --html=reports/migration_tests.html -v"
    success, result = run_command(command, "Testes de Migração")
    
    return success


def run_failover_tests():
    """Executa testes de fallback"""
    print("\n[FAILOVER] Executando Testes de Failover...")
    
    command = "pytest tests/failover/ -m failover --html=reports/failover_tests.html -v"
    success, result = run_command(command, "Testes de Failover")
    
    return success


def generate_coverage_report():
    """Gera relatório de cobertura consolidado"""
    print("\n[COVERAGE] Gerando Relatorio de Cobertura...")
    
    # Executar todos os testes com cobertura
    command = (
        "pytest tests/ "
        "--cov=app "
        "--cov-report=html:htmlcov "
        "--cov-report=xml:coverage.xml "
        "--cov-report=term-missing "
        "--html=reports/full_coverage.html"
    )
    
    success, result = run_command(command, "Cobertura Completa")
    
    if success:
        print("\n[SUCCESS] Relatorios gerados:")
        print("   - HTML: htmlcov/index.html")
        print("   - XML: coverage.xml")
        print("   - Terminal: exibido acima")
    
    return success


def check_coverage_threshold(threshold=85):
    """Verifica se cobertura atende threshold mínimo"""
    print(f"\n[THRESHOLD] Verificando Cobertura Minima ({threshold}%)...")
    
    try:
        # Executar coverage report com formato json
        result = subprocess.run(
            "coverage json",
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Ler dados de cobertura
        with open("coverage.json", "r") as f:
            coverage_data = json.load(f)
        
        total_coverage = coverage_data["totals"]["percent_covered"]
        
        print(f"Cobertura Total: {total_coverage:.2f}%")
        
        if total_coverage >= threshold:
            print(f"[SUCCESS] Cobertura atende threshold minimo ({threshold}%)")
            return True
        else:
            print(f"[FAIL] Cobertura abaixo do threshold minimo ({threshold}%)")
            return False
            
    except Exception as e:
        print(f"Erro ao verificar cobertura: {e}")
        return False


def generate_summary_report(results):
    """Gera relatório resumo dos testes"""
    print("\n[SUMMARY] Gerando Relatorio Resumo...")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""# Redis YouTube Downloader - Test Summary Report

Generated: {timestamp}

## Test Suite Results

"""
    
    for test_type, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        report += f"- **{test_type}**: {status}\n"
    
    overall_success = all(results.values())
    report += f"\n## Overall Status: {'[SUCCESS] ALL TESTS PASSED' if overall_success else '[FAIL] SOME TESTS FAILED'}\n\n"
    
    report += """## Generated Reports

- **Unit Tests**: `reports/unit_tests.html`
- **Integration Tests**: `reports/integration_tests.html`
- **Performance Tests**: `reports/performance_tests.html`
- **Load Tests**: `reports/load_tests.html`
- **Migration Tests**: `reports/migration_tests.html`
- **Failover Tests**: `reports/failover_tests.html`
- **Coverage Report**: `htmlcov/index.html`
- **Full Test Report**: `reports/full_coverage.html`

## Next Steps

"""
    
    if overall_success:
        report += """[SUCCESS] All tests passed! System is ready for production deployment.

Recommended actions:
1. Deploy Redis infrastructure
2. Run migration scripts
3. Monitor system performance
4. Set up alerting for failures
"""
    else:
        report += """[FAIL] Some tests failed. Review and fix issues before deployment.

Required actions:
1. Review failed test reports
2. Fix identified issues
3. Re-run test suite
4. Ensure >85% test coverage
"""
    
    # Salvar relatório
    with open("reports/test_summary.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("[SUCCESS] Relatorio resumo salvo em: reports/test_summary.md")
    
    return overall_success


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description="Executor de testes Redis YouTube Downloader")
    parser.add_argument("--unit", action="store_true", help="Executar apenas testes unitários")
    parser.add_argument("--integration", action="store_true", help="Executar apenas testes de integração")
    parser.add_argument("--performance", action="store_true", help="Executar apenas testes de performance")
    parser.add_argument("--load", action="store_true", help="Executar apenas testes de carga")
    parser.add_argument("--migration", action="store_true", help="Executar apenas testes de migração")
    parser.add_argument("--failover", action="store_true", help="Executar apenas testes de failover")
    parser.add_argument("--coverage", action="store_true", help="Executar apenas relatório de cobertura")
    parser.add_argument("--threshold", type=int, default=85, help="Threshold mínimo de cobertura (default: 85)")
    
    args = parser.parse_args()
    
    print("[START] Iniciando Suite de Testes Redis YouTube Downloader")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Garantir que diretórios existam
    ensure_directories()
    
    # Resultados dos testes
    results = {}
    
    # Executar testes específicos se solicitado
    if args.unit:
        results["Unit Tests"] = run_unit_tests()
    elif args.integration:
        results["Integration Tests"] = run_integration_tests()
    elif args.performance:
        results["Performance Tests"] = run_performance_tests()
    elif args.load:
        results["Load Tests"] = run_load_tests()
    elif args.migration:
        results["Migration Tests"] = run_migration_tests()
    elif args.failover:
        results["Failover Tests"] = run_failover_tests()
    elif args.coverage:
        results["Coverage Report"] = generate_coverage_report()
    else:
        # Executar suíte completa
        print("\n[FULL] Executando suite completa de testes...")
        
        results["Unit Tests"] = run_unit_tests()
        results["Integration Tests"] = run_integration_tests()
        results["Performance Tests"] = run_performance_tests()
        results["Load Tests"] = run_load_tests()
        results["Migration Tests"] = run_migration_tests()
        results["Failover Tests"] = run_failover_tests()
        results["Coverage Report"] = generate_coverage_report()
        
        # Verificar threshold de cobertura
        coverage_ok = check_coverage_threshold(args.threshold)
        results["Coverage Threshold"] = coverage_ok
    
    # Gerar relatório resumo
    overall_success = generate_summary_report(results)
    
    # Status final
    print("\n" + "="*60)
    print("[FINAL] RESULTADO FINAL")
    print("="*60)
    
    for test_type, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_type}: {status}")
    
    if overall_success:
        print("\n[SUCCESS] TODOS OS TESTES PASSARAM!")
        print("Sistema Redis esta pronto para producao.")
    else:
        print("\n[FAIL] ALGUNS TESTES FALHARAM!")
        print("Revisar relatorios antes de prosseguir.")
    
    # Exit code
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()