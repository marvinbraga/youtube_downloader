#!/usr/bin/env python3
"""
96-Hour Continuous Validation Executor - Agent-QualityAssurance FASE 4
Script principal para executar validação contínua pós-cutover por 96 horas

Este script executa o sistema de validação contínua completo que:
- Valida integridade de dados a cada 5 minutos
- Monitora performance do sistema
- Valida experiência do usuário
- Monitora taxas de erro
- Gera relatórios automáticos
- Mantém dashboard em tempo real
- Produz relatório final de aprovação após 96h

Uso:
    python run_96h_continuous_validation.py [--config-file CONFIG] [--log-level LEVEL]
"""

import asyncio
import argparse
import logging
import signal
import sys
import json
from pathlib import Path
from datetime import datetime
import traceback

# Importar o sistema de validação
from validation import ContinuousValidationManager, ValidationConfig

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configurar sistema de logging"""
    
    # Create logs directory
    logs_dir = Path("validation/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # File handler
    log_file = logs_dir / f"96h_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

def load_validation_config(config_file: str = None) -> ValidationConfig:
    """Carregar configuração de validação"""
    
    if config_file and Path(config_file).exists():
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            return ValidationConfig(
                validation_interval=config_data.get('validation_interval', 300),
                validation_duration=config_data.get('validation_duration', 96 * 3600),
                critical_alert_threshold=config_data.get('critical_alert_threshold'),
                warning_alert_threshold=config_data.get('warning_alert_threshold')
            )
        except Exception as e:
            print(f"Warning: Failed to load config file {config_file}: {e}")
            print("Using default configuration...")
    
    # Use default configuration
    return ValidationConfig()

def create_default_config_file():
    """Criar arquivo de configuração padrão"""
    config_dir = Path("validation/config")
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / "validation_config.json"
    
    default_config = {
        "validation_interval": 300,  # 5 minutes
        "validation_duration": 345600,  # 96 hours in seconds
        "critical_alert_threshold": {
            "data_corruption": True,
            "performance_degradation": 50,
            "error_spike": 5,
            "availability": 95
        },
        "warning_alert_threshold": {
            "performance_degradation": 20,
            "error_spike": 2,
            "availability": 99
        }
    }
    
    with open(config_file, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    return str(config_file)

async def run_validation_system(config: ValidationConfig, logger: logging.Logger):
    """Executar sistema de validação"""
    
    validation_manager = None
    
    try:
        logger.info("🚀 Starting 96-Hour Continuous Validation System...")
        logger.info("=" * 60)
        logger.info("Agent-QualityAssurance FASE 4 - Continuous Validation")
        logger.info("=" * 60)
        
        # Print configuration
        logger.info(f"Configuration:")
        logger.info(f"  - Validation interval: {config.validation_interval} seconds")
        logger.info(f"  - Total duration: {config.validation_duration / 3600:.1f} hours")
        logger.info(f"  - Critical alert threshold: {config.critical_alert_threshold}")
        logger.info(f"  - Warning alert threshold: {config.warning_alert_threshold}")
        
        # Initialize validation manager
        validation_manager = ContinuousValidationManager(config)
        
        # Start the 96-hour validation process
        logger.info("🔍 Initiating continuous validation for 96 hours...")
        logger.info("📊 Dashboard available at: validation/dashboard/validation_dashboard.html")
        logger.info("📁 Reports will be generated in: validation/reports/")
        logger.info("")
        
        # Run the validation
        final_report = await validation_manager.start_continuous_validation()
        
        # Process final results
        logger.info("=" * 60)
        logger.info("🏁 96-HOUR VALIDATION COMPLETED")
        logger.info("=" * 60)
        
        # Print final results
        approval_status = final_report.get('approval_status', {})
        
        if approval_status.get('approved', False):
            logger.info("✅ SYSTEM APPROVED FOR PRODUCTION!")
            logger.info("🎉 All success criteria have been met.")
            logger.info(f"📋 Approval timestamp: {approval_status.get('approval_timestamp')}")
            
            # Print success metrics
            success_criteria = final_report.get('success_criteria', {})
            logger.info("\n📊 Success Criteria Results:")
            for criterion, details in success_criteria.items():
                status_icon = "✅" if details.get('met', False) else "❌"
                logger.info(f"  {status_icon} {criterion}: {details.get('actual', 'N/A')}% (target: {details.get('target', 'N/A')}%)")
        else:
            logger.warning("❌ SYSTEM NOT APPROVED FOR PRODUCTION")
            logger.warning("⚠️  Additional work required before deployment.")
            
            # Print what needs to be fixed
            recommendations = final_report.get('recommendations', [])
            if recommendations:
                logger.warning("\n🔧 Required Actions:")
                for i, recommendation in enumerate(recommendations, 1):
                    logger.warning(f"  {i}. {recommendation}")
        
        # Print overall statistics
        overall_stats = final_report.get('overall_statistics', {})
        logger.info(f"\n📈 Validation Statistics:")
        logger.info(f"  - Total validations: {overall_stats.get('total_validations', 0)}")
        logger.info(f"  - Passed: {overall_stats.get('passed_validations', 0)}")
        logger.info(f"  - Warnings: {overall_stats.get('warning_validations', 0)}")
        logger.info(f"  - Critical: {overall_stats.get('critical_validations', 0)}")
        
        success_rates = [
            ('Data Integrity', overall_stats.get('data_integrity_success_rate', 0)),
            ('Performance', overall_stats.get('performance_success_rate', 0)),
            ('User Experience', overall_stats.get('user_experience_success_rate', 0)),
            ('Error Rates', overall_stats.get('error_rate_success_rate', 0))
        ]
        
        logger.info(f"\n📊 Success Rates:")
        for name, rate in success_rates:
            logger.info(f"  - {name}: {rate:.1f}%")
        
        # Final recommendations
        logger.info(f"\n📋 Next Steps: {approval_status.get('next_steps', 'Review results')}")
        
        logger.info("=" * 60)
        logger.info("Thank you for using Agent-QualityAssurance FASE 4!")
        logger.info("=" * 60)
        
        return final_report
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Validation interrupted by user")
        return {"status": "interrupted", "message": "Validation stopped by user"}
        
    except Exception as e:
        logger.error(f"\n❌ Validation failed with error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"status": "failed", "error": str(e)}
        
    finally:
        # Cleanup
        if validation_manager:
            try:
                await validation_manager.cleanup()
                logger.info("✅ Cleanup completed")
            except Exception as e:
                logger.error(f"⚠️  Cleanup failed: {e}")

def handle_signal(signum, frame):
    """Handle interrupt signals"""
    print(f"\n\nReceived signal {signum}. Stopping validation...")
    sys.exit(0)

async def main():
    """Função principal"""
    
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="96-Hour Continuous Validation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_96h_continuous_validation.py
    python run_96h_continuous_validation.py --log-level DEBUG
    python run_96h_continuous_validation.py --config-file custom_config.json

This system will run for 96 hours continuously validating:
- Data integrity every 5 minutes
- System performance metrics
- User experience indicators
- Error rates and patterns

Dashboard will be available at: validation/dashboard/validation_dashboard.html
Reports will be generated in: validation/reports/

For questions or support, refer to the Agent-QualityAssurance documentation.
        """
    )
    
    parser.add_argument(
        '--config-file',
        type=str,
        help='Path to validation configuration JSON file'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--create-config',
        action='store_true',
        help='Create a default configuration file and exit'
    )
    
    parser.add_argument(
        '--dashboard-only',
        action='store_true',
        help='Start only the dashboard server (useful for viewing existing results)'
    )
    
    args = parser.parse_args()
    
    # Create default config if requested
    if args.create_config:
        config_file = create_default_config_file()
        print(f"✅ Default configuration file created: {config_file}")
        print("You can edit this file and use it with --config-file option")
        return
    
    # Setup logging
    logger = setup_logging(args.log_level)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Load configuration
    config = load_validation_config(args.config_file)
    
    # Show startup banner
    print("=" * 80)
    print("🔍 AGENT-QUALITYASSURANCE FASE 4 - CONTINUOUS VALIDATION SYSTEM")
    print("=" * 80)
    print("📅 Starting 96-hour continuous validation...")
    print(f"⏱️  Validation interval: {config.validation_interval} seconds")
    print(f"⏰ Total duration: {config.validation_duration / 3600:.1f} hours")
    print("📊 Dashboard: validation/dashboard/validation_dashboard.html")
    print("📁 Reports: validation/reports/")
    print("🚦 Status: Initializing...")
    print("=" * 80)
    print("\n🚀 Press Ctrl+C to stop the validation at any time\n")
    
    # Dashboard only mode
    if args.dashboard_only:
        print("📊 Starting dashboard-only mode...")
        print("Dashboard available at: validation/dashboard/validation_dashboard.html")
        print("Press Ctrl+C to stop...")
        
        try:
            from validation import ValidationDashboard
            dashboard = ValidationDashboard()
            await dashboard.start()
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
            return
    
    # Run the full validation system
    try:
        final_report = await run_validation_system(config, logger)
        
        # Exit with appropriate code
        if final_report.get('approval_status', {}).get('approved', False):
            print("\n🎉 System validation completed successfully!")
            print("✅ System is APPROVED for production deployment.")
            sys.exit(0)
        else:
            print("\n⚠️  System validation completed with issues.")
            print("❌ System requires additional work before deployment.")
            sys.exit(1)
            
    except Exception as e:
        logger.critical(f"Critical error in validation system: {e}")
        print(f"\n💥 Critical error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Validation stopped by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(2)