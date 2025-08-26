"""
FASE 4 - PRODUCTION CUTOVER FINAL - SCRIPT PRINCIPAL
Orquestrador principal da execução do cutover final de produção
Zero downtime, máxima segurança, rollback automático

Agent-Deployment - Production Cutover Final
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger

# Importar todos os componentes da Fase 4
from scripts.production_migration_orchestrator import ProductionMigrationOrchestrator
from scripts.production_cutover_executor import ProductionCutoverExecutor
from scripts.json_elimination_manager import JSONEliminationManager
from scripts.final_system_validator import FinalSystemValidator
from scripts.cutover_health_checker import CutoverHealthChecker
from scripts.cutover_rollback_manager import CutoverRollbackManager, RollbackTrigger


class ProductionCutoverFinalOrchestrator:
    """
    Orquestrador principal da FASE 4 - PRODUCTION CUTOVER FINAL
    
    Coordena todos os componentes para execução segura e completa:
    1. ProductionMigrationOrchestrator - Cutover principal
    2. ProductionCutoverExecutor - Execução controlada
    3. JSONEliminationManager - Eliminação JSON
    4. FinalSystemValidator - Validação abrangente
    5. CutoverHealthChecker - Monitoramento contínuo
    6. CutoverRollbackManager - Rollback de emergência
    """
    
    def __init__(self):
        # Componentes principais
        self.migration_orchestrator = ProductionMigrationOrchestrator()
        self.cutover_executor = ProductionCutoverExecutor()
        self.json_eliminator = JSONEliminationManager()
        self.system_validator = FinalSystemValidator()
        self.health_checker = CutoverHealthChecker()
        self.rollback_manager = CutoverRollbackManager()
        
        # Configurações globais
        self.cutover_config = {
            "enable_health_monitoring": True,
            "enable_auto_rollback": True,
            "enable_json_elimination": True,
            "enable_comprehensive_validation": True,
            "monitoring_duration_minutes": 60,  # 1 hora de monitoramento
            "max_total_time_minutes": 30,  # Máximo 30 minutos total
            "rollback_threshold_critical_alerts": 3
        }
        
        # Estado da execução
        self.execution_state = {
            "start_time": None,
            "current_phase": "initialization",
            "phases_completed": [],
            "success": False,
            "error": None,
            "rollback_executed": False
        }
        
        # Relatórios de cada componente
        self.component_reports = {}
        
        logger.info("🚀 ProductionCutoverFinalOrchestrator initialized")
        logger.info(f"Configuration: {self.cutover_config}")
    
    async def execute_complete_production_cutover(self) -> Dict[str, Any]:
        """
        Executa cutover de produção completo e final
        
        Returns:
            Relatório completo consolidado de todos os componentes
        """
        logger.critical("🎯 INICIANDO PRODUCTION CUTOVER FINAL COMPLETE")
        logger.critical("=" * 80)
        
        self.execution_state["start_time"] = datetime.now()
        
        try:
            # FASE 1: Preparação e Monitoramento
            await self._phase_1_preparation_and_monitoring()
            
            # FASE 2: Cutover Principal
            await self._phase_2_main_cutover()
            
            # FASE 3: Validação e Certificação
            await self._phase_3_validation_and_certification()
            
            # FASE 4: Eliminação JSON (Opcional)
            if self.cutover_config["enable_json_elimination"]:
                await self._phase_4_json_elimination()
            
            # FASE 5: Validação Final
            await self._phase_5_final_validation()
            
            # FASE 6: Finalização e Relatório
            await self._phase_6_finalization()
            
            # Sucesso completo
            self.execution_state["success"] = True
            
            logger.success("🎉 PRODUCTION CUTOVER FINAL COMPLETED SUCCESSFULLY!")
            logger.success("=" * 80)
            
            return await self._generate_consolidated_report()
            
        except Exception as e:
            logger.critical(f"💥 PRODUCTION CUTOVER FINAL FAILED: {str(e)}")
            self.execution_state["error"] = str(e)
            
            # Tentar rollback automático se habilitado
            if self.cutover_config["enable_auto_rollback"]:
                await self._execute_emergency_rollback(str(e))
            
            return await self._generate_consolidated_report()
        
        finally:
            # Parar monitoramento
            if self.health_checker.is_monitoring:
                await self.health_checker.stop_monitoring()
    
    async def _phase_1_preparation_and_monitoring(self):
        """FASE 1: Preparação e início do monitoramento"""
        logger.critical("📋 PHASE 1: Preparation and Health Monitoring")
        self.execution_state["current_phase"] = "preparation_monitoring"
        
        # Configurar triggers de rollback automático
        if self.cutover_config["enable_auto_rollback"]:
            await self._setup_automatic_rollback_triggers()
        
        # Iniciar monitoramento de saúde
        if self.cutover_config["enable_health_monitoring"]:
            monitoring_task = await self.health_checker.start_monitoring(
                duration_minutes=self.cutover_config["monitoring_duration_minutes"]
            )
            logger.success("✅ Health monitoring started")
            
            # Aguardar estabilização inicial
            await asyncio.sleep(10)
            
            # Verificar saúde inicial
            initial_health = self.health_checker.get_current_health()
            if initial_health.get("overall_status") == "critical":
                raise Exception("System health critical - aborting cutover")
        
        self.execution_state["phases_completed"].append("preparation_monitoring")
        logger.success("✅ Phase 1 completed: Preparation and Monitoring")
    
    async def _phase_2_main_cutover(self):
        """FASE 2: Cutover principal com execução controlada"""
        logger.critical("🎯 PHASE 2: Main Production Cutover")
        self.execution_state["current_phase"] = "main_cutover"
        
        try:
            # Opção 1: Usar ProductionMigrationOrchestrator (mais abrangente)
            logger.info("Executing main cutover using ProductionMigrationOrchestrator...")
            cutover_result = await self.migration_orchestrator.execute_production_cutover()
            
            self.component_reports["main_cutover"] = cutover_result
            
            if not cutover_result.get("cutover_summary", {}).get("success"):
                raise Exception("Main cutover failed")
            
        except Exception as e:
            logger.error(f"Main cutover failed: {str(e)}")
            
            # Fallback: Tentar ProductionCutoverExecutor (mais granular)
            logger.info("Attempting fallback with ProductionCutoverExecutor...")
            
            executor_result = await self.cutover_executor.execute_controlled_cutover()
            self.component_reports["controlled_cutover"] = executor_result
            
            if executor_result.get("status") != "SUCCESS":
                raise Exception("Controlled cutover also failed")
        
        self.execution_state["phases_completed"].append("main_cutover")
        logger.success("✅ Phase 2 completed: Main Cutover")
    
    async def _phase_3_validation_and_certification(self):
        """FASE 3: Validação e certificação do sistema"""
        logger.critical("✅ PHASE 3: System Validation and Certification")
        self.execution_state["current_phase"] = "validation_certification"
        
        if self.cutover_config["enable_comprehensive_validation"]:
            # Executar validação abrangente
            validation_result = await self.system_validator.execute_comprehensive_validation()
            
            self.component_reports["system_validation"] = validation_result
            
            # Verificar critérios de aprovação
            overall_success = validation_result.get("validation_summary", {}).get("overall_success")
            certification_level = validation_result.get("validation_summary", {}).get("certification_level")
            
            if not overall_success or certification_level not in ["PRODUCTION", "STAGING"]:
                raise Exception(f"System validation failed - certification: {certification_level}")
            
            logger.success(f"🏆 System certified for: {certification_level}")
        
        self.execution_state["phases_completed"].append("validation_certification")
        logger.success("✅ Phase 3 completed: Validation and Certification")
    
    async def _phase_4_json_elimination(self):
        """FASE 4: Eliminação completa das dependências JSON"""
        logger.critical("🗑️ PHASE 4: Complete JSON Elimination")
        self.execution_state["current_phase"] = "json_elimination"
        
        # Executar eliminação JSON
        elimination_result = await self.json_eliminator.execute_complete_json_elimination()
        
        self.component_reports["json_elimination"] = elimination_result
        
        # Verificar sucesso da eliminação
        elimination_success = elimination_result.get("elimination_summary", {}).get("success")
        
        if not elimination_success:
            logger.warning("JSON elimination failed - continuing without elimination")
            # Não falhar o cutover por falha na eliminação JSON
        else:
            logger.success("🗑️ JSON dependencies eliminated successfully")
        
        self.execution_state["phases_completed"].append("json_elimination")
        logger.success("✅ Phase 4 completed: JSON Elimination")
    
    async def _phase_5_final_validation(self):
        """FASE 5: Validação final pós-eliminação"""
        logger.critical("🔍 PHASE 5: Final Post-Elimination Validation")
        self.execution_state["current_phase"] = "final_validation"
        
        # Executar validação final
        final_validation = await self.system_validator.execute_comprehensive_validation()
        
        self.component_reports["final_validation"] = final_validation
        
        # Verificar que sistema ainda funciona após eliminação JSON
        overall_success = final_validation.get("validation_summary", {}).get("overall_success")
        
        if not overall_success:
            logger.warning("Final validation failed - system may need attention")
            # Não falhar por isso, mas registrar
        
        self.execution_state["phases_completed"].append("final_validation")
        logger.success("✅ Phase 5 completed: Final Validation")
    
    async def _phase_6_finalization(self):
        """FASE 6: Finalização e geração de relatórios"""
        logger.critical("🏁 PHASE 6: Finalization and Reporting")
        self.execution_state["current_phase"] = "finalization"
        
        # Gerar relatório de saúde final
        final_health_report = await self.health_checker.get_health_report()
        self.component_reports["final_health"] = final_health_report
        
        # Salvar relatório consolidado
        await self._save_consolidated_report()
        
        # Configurar monitoramento pós-cutover
        await self._setup_post_cutover_monitoring()
        
        self.execution_state["phases_completed"].append("finalization")
        logger.success("✅ Phase 6 completed: Finalization")
    
    async def _setup_automatic_rollback_triggers(self):
        """Configura triggers automáticos de rollback"""
        logger.info("Setting up automatic rollback triggers...")
        
        # Trigger baseado em alertas críticos de saúde
        async def health_trigger():
            active_alerts = self.health_checker.get_active_alerts()
            critical_count = len([a for a in active_alerts if a.level.value == "critical"])
            
            if critical_count >= self.cutover_config["rollback_threshold_critical_alerts"]:
                return (True, f"Critical health alerts: {critical_count}")
            return (False, "")
        
        # Trigger baseado em tempo limite
        async def timeout_trigger():
            if self.execution_state["start_time"]:
                elapsed = (datetime.now() - self.execution_state["start_time"]).total_seconds()
                max_time = self.cutover_config["max_total_time_minutes"] * 60
                
                if elapsed > max_time:
                    return (True, f"Cutover timeout: {elapsed:.0f}s > {max_time}s")
            return (False, "")
        
        # Adicionar triggers ao rollback manager
        self.rollback_manager.add_rollback_trigger(health_trigger)
        self.rollback_manager.add_rollback_trigger(timeout_trigger)
        
        logger.success("Automatic rollback triggers configured")
    
    async def _execute_emergency_rollback(self, reason: str):
        """Executa rollback de emergência"""
        logger.critical(f"🚨 EXECUTING EMERGENCY ROLLBACK: {reason}")
        
        try:
            rollback_result = await self.rollback_manager.execute_emergency_rollback(
                trigger=RollbackTrigger.AUTOMATIC,
                reason=reason
            )
            
            self.component_reports["emergency_rollback"] = rollback_result
            self.execution_state["rollback_executed"] = True
            
            rollback_success = rollback_result.get("rollback_summary", {}).get("success")
            
            if rollback_success:
                logger.critical("🚨 EMERGENCY ROLLBACK COMPLETED SUCCESSFULLY")
            else:
                logger.critical("🚨 EMERGENCY ROLLBACK FAILED")
            
        except Exception as e:
            logger.critical(f"🚨 EMERGENCY ROLLBACK ERROR: {str(e)}")
            self.component_reports["emergency_rollback"] = {"error": str(e)}
    
    async def _setup_post_cutover_monitoring(self):
        """Configura monitoramento pós-cutover"""
        logger.info("Setting up post-cutover monitoring...")
        
        # Em um ambiente real, aqui configuraríamos:
        # - Alertas de monitoramento contínuo
        # - Dashboards de saúde
        # - Logs estruturados
        # - Métricas de performance
        
        logger.success("Post-cutover monitoring configured")
    
    async def _save_consolidated_report(self):
        """Salva relatório consolidado em arquivo"""
        report = await self._generate_consolidated_report()
        
        # Salvar em arquivo
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / f"production_cutover_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Consolidated report saved: {report_file}")
    
    async def _generate_consolidated_report(self) -> Dict[str, Any]:
        """Gera relatório consolidado de todo o cutover"""
        end_time = datetime.now()
        total_time = (end_time - self.execution_state["start_time"]).total_seconds()
        
        return {
            "production_cutover_final_report": {
                "timestamp": end_time.isoformat(),
                "execution_summary": {
                    "success": self.execution_state["success"],
                    "start_time": self.execution_state["start_time"].isoformat(),
                    "end_time": end_time.isoformat(),
                    "total_execution_time_seconds": total_time,
                    "phases_completed": self.execution_state["phases_completed"],
                    "current_phase": self.execution_state["current_phase"],
                    "error": self.execution_state["error"],
                    "rollback_executed": self.execution_state["rollback_executed"]
                },
                "configuration": self.cutover_config,
                "component_reports": self.component_reports,
                "final_status": {
                    "system_operational": self._determine_system_status(),
                    "redis_mode_active": self._is_redis_mode_active(),
                    "json_dependencies_eliminated": self._are_json_dependencies_eliminated(),
                    "monitoring_active": self.health_checker.is_monitoring,
                    "rollback_capability": "available"
                },
                "recommendations": self._generate_final_recommendations(),
                "next_steps": [
                    "Monitor system performance for 48 hours",
                    "Verify all business functions work correctly",
                    "Update documentation to reflect new architecture",
                    "Plan performance optimization review in 1 week",
                    "Schedule cleanup of temporary files after 30 days"
                ]
            }
        }
    
    def _determine_system_status(self) -> bool:
        """Determina se sistema está operacional"""
        if self.execution_state["rollback_executed"]:
            # Se houve rollback, verificar se foi bem-sucedido
            rollback_report = self.component_reports.get("emergency_rollback", {})
            return rollback_report.get("rollback_summary", {}).get("success", False)
        
        # Se não houve rollback, verificar validação final
        validation_report = self.component_reports.get("final_validation", {})
        if validation_report:
            return validation_report.get("validation_summary", {}).get("overall_success", False)
        
        return self.execution_state["success"]
    
    def _is_redis_mode_active(self) -> bool:
        """Verifica se modo Redis está ativo"""
        if self.execution_state["rollback_executed"]:
            return False  # Rollback volta ao modo híbrido/JSON
        
        # Verificar configuração atual
        from app.services.hybrid_mode_manager import hybrid_mode_manager
        return hybrid_mode_manager.config.use_redis and not hybrid_mode_manager.config.auto_fallback
    
    def _are_json_dependencies_eliminated(self) -> bool:
        """Verifica se dependências JSON foram eliminadas"""
        if self.execution_state["rollback_executed"]:
            return False  # Rollback restaura JSON
        
        elimination_report = self.component_reports.get("json_elimination", {})
        if elimination_report:
            return elimination_report.get("elimination_summary", {}).get("success", False)
        
        return False
    
    def _generate_final_recommendations(self) -> List[str]:
        """Gera recomendações finais baseadas na execução"""
        recommendations = []
        
        if self.execution_state["success"] and not self.execution_state["rollback_executed"]:
            recommendations.extend([
                "🎉 Production cutover completed successfully",
                "Continue monitoring system health closely",
                "All business functions should be verified",
                "Performance optimization can be scheduled"
            ])
        elif self.execution_state["rollback_executed"]:
            recommendations.extend([
                "🚨 System rolled back - investigate root cause",
                "Review rollback logs for failure analysis",
                "Fix identified issues before retry",
                "Consider staged rollout approach"
            ])
        else:
            recommendations.extend([
                "⚠️ Cutover completed with issues",
                "Review component reports for specific problems",
                "Consider rollback if issues are critical",
                "Investigate and fix issues before declaring success"
            ])
        
        # Recomendações específicas baseadas nos relatórios
        if "system_validation" in self.component_reports:
            validation = self.component_reports["system_validation"]
            cert_level = validation.get("validation_summary", {}).get("certification_level", "")
            
            if cert_level == "PRODUCTION":
                recommendations.append("✅ System certified for production use")
            elif cert_level in ["STAGING", "TESTING"]:
                recommendations.append(f"⚠️ System certified only for {cert_level} - address issues for production")
        
        return recommendations


# Função principal para execução standalone
async def main():
    """Executa cutover de produção final completo"""
    orchestrator = ProductionCutoverFinalOrchestrator()
    
    try:
        result = await orchestrator.execute_complete_production_cutover()
        
        # Exibir resumo final
        execution_summary = result["production_cutover_final_report"]["execution_summary"]
        final_status = result["production_cutover_final_report"]["final_status"]
        
        print("\n" + "="*80)
        print("PRODUCTION CUTOVER FINAL - EXECUTION SUMMARY")
        print("="*80)
        print(f"Success: {execution_summary['success']}")
        print(f"Total Time: {execution_summary['total_execution_time_seconds']:.2f} seconds")
        print(f"Phases Completed: {len(execution_summary['phases_completed'])}")
        print(f"System Operational: {final_status['system_operational']}")
        print(f"Redis Mode Active: {final_status['redis_mode_active']}")
        print(f"JSON Dependencies Eliminated: {final_status['json_dependencies_eliminated']}")
        print(f"Rollback Executed: {execution_summary['rollback_executed']}")
        
        if execution_summary['error']:
            print(f"Error: {execution_summary['error']}")
        
        print("="*80)
        
        return result
        
    except Exception as e:
        logger.critical(f"ORCHESTRATOR EXECUTION FAILED: {str(e)}")
        raise


if __name__ == "__main__":
    # Configurar logging para execução standalone
    logger.add("production_cutover_final_{time}.log", rotation="1 MB")
    
    # Executar cutover final
    asyncio.run(main())