#!/usr/bin/env python3
"""
FASE 3 - Complete Validation Runner
Script master para executar toda a validação da FASE 3

Agent-QualityAssurance - Execução completa da validação
Executa todos os testes implementados e gera relatório final
"""

import asyncio
import sys
import os
from pathlib import Path

# Adicionar pasta tests ao path
current_dir = Path(__file__).parent
tests_dir = current_dir / "tests"
sys.path.insert(0, str(tests_dir))

from reports.fase3_validation_report import FASE3ValidationReportGenerator

from loguru import logger

# Configurar logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


def print_header():
    """Imprime cabeçalho da validação"""
    print("=" * 100)
    print("🏆 FASE 3 - COMPLETE VALIDATION SUITE")
    print("Agent-QualityAssurance - YouTube Downloader FASE 3 Validation")
    print("=" * 100)
    print("")
    print("📋 VALIDATION COMPONENTS:")
    print("  🧪 Integration Tests - API endpoints Redis vs JSON")
    print("  ⚡ Performance Benchmarks - Latency and throughput validation")
    print("  🔥 Load & Stress Tests - 1000+ connections, high concurrency")
    print("  🔄 End-to-End Scenarios - Complete workflow validation") 
    print("  📊 Final Report - Approval/rejection with detailed metrics")
    print("")
    print("🎯 APPROVAL CRITERIA:")
    print("  ✅ Integration Tests: ≥95% success rate")
    print("  ✅ Performance Benchmarks: All critical targets met")
    print("  ✅ Load Tests: ≥90% success under load")
    print("  ✅ E2E Scenarios: ≥80% working")
    print("  ✅ Zero critical blocking issues")
    print("")
    print("🚀 Starting validation in 3 seconds...")
    print("=" * 100)


async def main():
    """Função principal"""
    print_header()
    
    # Aguardar antes de iniciar
    await asyncio.sleep(3)
    
    try:
        # Inicializar gerador de relatório
        report_generator = FASE3ValidationReportGenerator()
        
        # Executar validação completa
        logger.info("🚀 Starting FASE 3 Complete Validation...")
        validation_result = await report_generator.generate_complete_validation_report()
        
        print("")
        print("=" * 100)
        print("🏁 FASE 3 VALIDATION COMPLETED")
        print("=" * 100)
        
        # Determinar resultado final
        if validation_result.overall_status == "APPROVED":
            logger.success("🎉 RESULTADO: FASE 3 APROVADA PARA PRODUÇÃO!")
            logger.success("✅ Todos os critérios críticos atendidos")
            logger.success("✅ Sistema pronto para deployment")
            logger.success("✅ Performance targets atingidos")
            logger.success("✅ Escalabilidade validada")
            logger.success("✅ Integridade de dados confirmada")
            print("")
            print("📋 PRÓXIMOS PASSOS:")
            print("  1. Proceder com cutover para produção")
            print("  2. Monitorar métricas pós-deployment")
            print("  3. Agendar review em 1 semana")
            return 0
            
        elif validation_result.overall_status == "CONDITIONAL":
            logger.warning("⚠️ RESULTADO: FASE 3 APROVAÇÃO CONDICIONAL")
            logger.warning("🔍 Deployment com monitoramento reforçado")
            logger.warning("⏰ Re-validação necessária em 72h")
            print("")
            print("📋 PRÓXIMOS PASSOS:")
            print("  1. Corrigir issues não-críticos identificados")
            print("  2. Deployment gradual com monitoramento")
            print("  3. Re-validação obrigatória")
            return 2
            
        else:
            logger.error("❌ RESULTADO: FASE 3 REPROVADA")
            logger.error("🚨 Issues críticos impedem deployment")
            logger.error("🔧 Correções obrigatórias necessárias")
            print("")
            print("📋 PRÓXIMOS PASSOS:")
            print("  1. Corrigir TODOS os issues críticos")
            print("  2. Executar nova validação completa")
            print("  3. Não proceder com deployment")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("⚠️ Validação interrompida pelo usuário")
        return 130
        
    except Exception as e:
        logger.error(f"💥 Erro crítico na validação: {e}")
        logger.error("🚨 Validação falhou - investigar imediatamente")
        return 1


def check_environment():
    """Verifica se o ambiente está pronto para os testes"""
    logger.info("🔍 Checking test environment...")
    
    # Verificar estrutura de pastas
    required_dirs = [
        tests_dir / "integration",
        tests_dir / "performance", 
        tests_dir / "load",
        tests_dir / "scenarios",
        tests_dir / "reports"
    ]
    
    for dir_path in required_dirs:
        if not dir_path.exists():
            logger.error(f"❌ Required directory missing: {dir_path}")
            return False
    
    # Verificar arquivos de teste principais
    required_files = [
        tests_dir / "integration" / "test_fase3_complete_integration.py",
        tests_dir / "performance" / "test_fase3_benchmarks.py",
        tests_dir / "load" / "test_fase3_load_stress.py", 
        tests_dir / "scenarios" / "test_fase3_end_to_end.py",
        tests_dir / "reports" / "fase3_validation_report.py"
    ]
    
    for file_path in required_files:
        if not file_path.exists():
            logger.error(f"❌ Required test file missing: {file_path}")
            return False
    
    logger.success("✅ Test environment verified")
    return True


if __name__ == "__main__":
    # Verificar ambiente antes de iniciar
    if not check_environment():
        logger.error("❌ Environment check failed - cannot proceed")
        sys.exit(1)
    
    # Executar validação
    exit_code = asyncio.run(main())
    sys.exit(exit_code)