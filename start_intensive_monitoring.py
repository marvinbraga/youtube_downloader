#!/usr/bin/env python3
"""
Start Intensive Monitoring - Main Script
Script principal para iniciar o sistema de monitoramento intensivo pós-cutover

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from monitoring import (
    intensive_monitoring_scheduler,
    get_system_info,
    initialize_monitoring_system,
    start_intensive_monitoring,
    get_monitoring_status
)


def setup_logging():
    """Configura logging para o sistema de monitoramento"""
    # Remove default handler
    logger.remove()
    
    # Add console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # Add file handler for monitoring logs
    log_file = f"logs/monitoring/intensive_monitoring_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        compression="zip"
    )
    
    logger.info("Logging configured for intensive monitoring")


async def display_system_banner():
    """Exibe banner do sistema"""
    system_info = get_system_info()
    
    banner = f"""
{'='*80}
{system_info['name']} v{system_info['version']}
{system_info['description']}

Phase: {system_info['phase']}
Agent: {system_info['agent']}

Components:
{chr(10).join(['  - ' + comp for comp in system_info['components']])}

Capabilities:
{chr(10).join(['  - ' + cap for cap in system_info['capabilities']])}
{'='*80}
    """
    
    print(banner)
    logger.info("Production Monitoring System started")


async def validate_system_requirements():
    """Valida requisitos do sistema"""
    logger.info("Validating system requirements...")
    
    # Verifica se Redis está disponível
    try:
        from app.services.redis_connection import get_redis_client
        redis_client = await get_redis_client()
        
        if redis_client:
            await redis_client.ping()
            logger.info("✓ Redis connection validated")
        else:
            logger.error("✗ Redis connection failed")
            return False
    except Exception as e:
        logger.error(f"✗ Redis validation error: {e}")
        return False
    
    # Verifica estrutura de diretórios
    required_dirs = [
        "logs/monitoring",
        "reports/monitoring", 
        "backups/monitoring"
    ]
    
    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Directory created/verified: {dir_path}")
    
    logger.info("System requirements validated successfully")
    return True


async def run_health_check():
    """Executa verificação de saúde do sistema"""
    logger.info("Running system health check...")
    
    try:
        status = await get_monitoring_status()
        
        print("\n" + "="*50)
        print("SYSTEM HEALTH CHECK")
        print("="*50)
        
        # Status dos componentes
        components = status["components_status"]
        
        for component_name, component_data in components.items():
            active = component_data["active"]
            status_indicator = "🟢" if active else "🔴"
            print(f"{status_indicator} {component_name.replace('_', ' ').title()}: {'Active' if active else 'Inactive'}")
        
        print("="*50)
        
        # Verifica se componentes críticos estão ativos
        critical_components = ["production_monitoring", "alert_system"]
        all_critical_active = all(
            components[comp]["active"] for comp in critical_components
        )
        
        if all_critical_active:
            logger.info("✓ All critical components are active")
            return True
        else:
            logger.warning("⚠ Some critical components are inactive")
            return False
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


async def start_monitoring_with_cutover_time(cutover_time: datetime):
    """Inicia monitoramento com tempo de cutover específico"""
    try:
        logger.info(f"Starting intensive monitoring with cutover time: {cutover_time.isoformat()}")
        
        await intensive_monitoring_scheduler.start_intensive_monitoring(cutover_time)
        
        logger.info("Intensive monitoring started successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start intensive monitoring: {e}")
        return False


async def interactive_startup():
    """Processo interativo de inicialização"""
    print("\n🚀 Starting Interactive Setup...")
    
    # 1. Validate system
    if not await validate_system_requirements():
        print("❌ System validation failed. Please check the logs.")
        return False
    
    # 2. Initialize components
    print("\n📦 Initializing monitoring components...")
    initialized = await initialize_monitoring_system()
    
    print(f"✅ Initialized {len(initialized)} components:")
    for component in initialized:
        print(f"   - {component}")
    
    # 3. Health check
    if not await run_health_check():
        print("\n⚠️  Some components failed health check. Continue anyway? (y/n): ", end="")
        response = input().lower()
        if response != 'y':
            print("Startup cancelled.")
            return False
    
    # 4. Ask for cutover time
    print("\n⏰ Cutover Time Setup:")
    print("1. Use current time (start monitoring now)")
    print("2. Specify custom cutover time")
    
    choice = input("Choose option (1/2): ").strip()
    
    if choice == "1":
        cutover_time = datetime.now()
        print(f"Using current time: {cutover_time.isoformat()}")
    
    elif choice == "2":
        print("Enter cutover time (format: YYYY-MM-DD HH:MM:SS)")
        time_str = input("Cutover time: ").strip()
        
        try:
            cutover_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print("❌ Invalid time format. Using current time.")
            cutover_time = datetime.now()
    
    else:
        print("Invalid option. Using current time.")
        cutover_time = datetime.now()
    
    # 5. Start intensive monitoring
    print(f"\n🎯 Starting 48-hour intensive monitoring...")
    print(f"Cutover time: {cutover_time.isoformat()}")
    
    success = await start_monitoring_with_cutover_time(cutover_time)
    
    if success:
        print("\n✅ INTENSIVE MONITORING STARTED SUCCESSFULLY!")
        print("\n📊 Dashboard available at: http://localhost:8000/")
        print("📋 Check logs in: logs/monitoring/")
        print("📈 Reports will be saved to: reports/monitoring/")
        
        # Show monitoring schedule
        schedule_status = await intensive_monitoring_scheduler.get_monitoring_status()
        if schedule_status.get("monitoring_schedule"):
            schedule = schedule_status["monitoring_schedule"]
            current_phase = schedule["current_phase"]
            hours_since_cutover = schedule.get("hours_since_cutover", 0)
            
            print(f"\n📅 Current Phase: {current_phase.replace('_', ' ').title()}")
            print(f"⏱️  Hours since cutover: {hours_since_cutover:.1f}")
        
        return True
    else:
        print("\n❌ Failed to start intensive monitoring. Check logs for details.")
        return False


async def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description="Start Production Intensive Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_intensive_monitoring.py                    # Interactive startup
  python start_intensive_monitoring.py --auto            # Auto start with current time
  python start_intensive_monitoring.py --cutover "2024-08-26 15:30:00"
  python start_intensive_monitoring.py --health-check    # Health check only
        """
    )
    
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Start automatically with current time as cutover"
    )
    
    parser.add_argument(
        "--cutover",
        type=str,
        help="Cutover time in format 'YYYY-MM-DD HH:MM:SS'"
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check only"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show system status and exit"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Show banner
    await display_system_banner()
    
    try:
        # Health check only
        if args.health_check:
            await validate_system_requirements()
            await initialize_monitoring_system()
            success = await run_health_check()
            sys.exit(0 if success else 1)
        
        # Status only
        if args.status:
            await initialize_monitoring_system()
            status = await get_monitoring_status()
            print(f"\nSystem Status: {status}")
            return
        
        # Auto start
        if args.auto:
            await validate_system_requirements()
            await initialize_monitoring_system()
            await run_health_check()
            
            cutover_time = datetime.now()
            success = await start_monitoring_with_cutover_time(cutover_time)
            
            if success:
                print("✅ Auto-started intensive monitoring successfully!")
                await keep_running()
            else:
                print("❌ Failed to auto-start monitoring")
                sys.exit(1)
        
        # Cutover time specified
        elif args.cutover:
            await validate_system_requirements()
            await initialize_monitoring_system()
            
            try:
                cutover_time = datetime.strptime(args.cutover, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.error("Invalid cutover time format. Use 'YYYY-MM-DD HH:MM:SS'")
                sys.exit(1)
            
            success = await start_monitoring_with_cutover_time(cutover_time)
            
            if success:
                print(f"✅ Started intensive monitoring with cutover time: {cutover_time.isoformat()}")
                await keep_running()
            else:
                print("❌ Failed to start monitoring")
                sys.exit(1)
        
        # Interactive mode (default)
        else:
            success = await interactive_startup()
            
            if success:
                await keep_running()
            else:
                sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        await shutdown_monitoring()
        print("\n👋 Monitoring system shutdown complete.")
    
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        await shutdown_monitoring()
        sys.exit(1)


async def keep_running():
    """Mantém o sistema rodando"""
    print("\n🔄 Monitoring system is running...")
    print("Press Ctrl+C to stop")
    
    try:
        # Check status every 5 minutes
        while True:
            await asyncio.sleep(300)
            
            # Quick status check
            if intensive_monitoring_scheduler.is_running:
                status = await intensive_monitoring_scheduler.get_monitoring_status()
                if status.get("monitoring_schedule"):
                    schedule = status["monitoring_schedule"]
                    current_phase = schedule.get("current_phase", "unknown")
                    hours_elapsed = schedule.get("hours_since_cutover", 0)
                    
                    logger.info(f"Status: Phase {current_phase} | Hours elapsed: {hours_elapsed:.1f}")
            else:
                logger.warning("Intensive monitoring scheduler is not running")
    
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error(f"Error in keep_running loop: {e}")
        raise


async def shutdown_monitoring():
    """Shutdown graceful do sistema de monitoramento"""
    logger.info("Shutting down monitoring system...")
    
    try:
        if intensive_monitoring_scheduler.is_running:
            await intensive_monitoring_scheduler.stop_intensive_monitoring()
        
        logger.info("Monitoring system shutdown completed")
    
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    # Ensure we're using Python 3.7+
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required")
        sys.exit(1)
    
    # Run main function
    asyncio.run(main())