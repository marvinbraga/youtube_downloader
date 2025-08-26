#!/usr/bin/env python3
"""
Test Validation System - Agent-QualityAssurance FASE 4
Script de teste para verificar se o sistema de validação está funcionando

Este script executa testes rápidos dos componentes de validação para garantir
que tudo está configurado corretamente antes de iniciar a validação de 96 horas.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_redis_connection():
    """Testar conexão com Redis"""
    try:
        import redis.asyncio as redis
        
        client = redis.Redis(host='localhost', port=int(os.getenv('REDIS_PORT', 6379)), decode_responses=True)
        await client.ping()
        await client.close()
        
        logger.info("✅ Redis connection test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Redis connection test failed: {e}")
        return False

async def test_validators():
    """Testar validators individuais"""
    try:
        from validation import (
            DataIntegrityValidator,
            PerformanceValidator,
            UserExperienceValidator,
            ErrorRateValidator
        )
        
        # Test Data Integrity Validator
        data_validator = DataIntegrityValidator()
        await data_validator.initialize()
        logger.info("✅ Data Integrity Validator initialized")
        
        # Test Performance Validator
        perf_validator = PerformanceValidator()
        await perf_validator.initialize()
        logger.info("✅ Performance Validator initialized")
        
        # Test User Experience Validator
        ux_validator = UserExperienceValidator()
        await ux_validator.initialize()
        logger.info("✅ User Experience Validator initialized")
        
        # Test Error Rate Validator
        error_validator = ErrorRateValidator()
        await error_validator.initialize()
        logger.info("✅ Error Rate Validator initialized")
        
        # Cleanup
        await data_validator.cleanup()
        await perf_validator.cleanup()
        await ux_validator.cleanup()
        await error_validator.cleanup()
        
        return True
    except Exception as e:
        logger.error(f"❌ Validators test failed: {e}")
        return False

async def test_dashboard():
    """Testar sistema de dashboard"""
    try:
        from validation import ValidationDashboard
        
        dashboard = ValidationDashboard()
        
        # Check if dashboard files exist
        dashboard_files = [
            dashboard.dashboard_html_file,
            dashboard.dashboard_css_file,
            dashboard.dashboard_js_file
        ]
        
        for file_path in dashboard_files:
            if not file_path.exists():
                logger.error(f"❌ Dashboard file missing: {file_path}")
                return False
        
        logger.info("✅ Dashboard files test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Dashboard test failed: {e}")
        return False

async def test_reporter():
    """Testar sistema de relatórios"""
    try:
        from validation import ValidationReporter
        
        reporter = ValidationReporter()
        
        # Check if report directories exist
        if not reporter.reports_dir.exists():
            logger.error("❌ Reports directory missing")
            return False
        
        logger.info("✅ Reporter test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Reporter test failed: {e}")
        return False

async def test_validation_manager():
    """Testar validation manager"""
    try:
        from validation import ContinuousValidationManager, ValidationConfig
        
        # Create test config with short duration
        test_config = ValidationConfig(
            validation_interval=10,  # 10 seconds for testing
            validation_duration=60   # 1 minute for testing
        )
        
        manager = ContinuousValidationManager(test_config)
        
        # Test initialization
        await manager.initialize_redis()
        
        logger.info("✅ Validation Manager test passed")
        
        # Cleanup
        await manager.cleanup()
        
        return True
    except Exception as e:
        logger.error(f"❌ Validation Manager test failed: {e}")
        return False

async def test_quick_validation_cycle():
    """Executar um ciclo rápido de validação para teste"""
    try:
        from validation import (
            DataIntegrityValidator,
            PerformanceValidator,
            UserExperienceValidator,
            ErrorRateValidator
        )
        
        logger.info("🔍 Running quick validation cycle...")
        
        # Initialize validators
        validators = [
            DataIntegrityValidator(),
            PerformanceValidator(),
            UserExperienceValidator(),
            ErrorRateValidator()
        ]
        
        # Initialize all validators
        for validator in validators:
            await validator.initialize()
        
        # Run validation
        results = []
        for validator in validators:
            result = await validator.validate()
            results.append(result)
            
            validator_name = validator.__class__.__name__
            status = result['status']
            logger.info(f"  - {validator_name}: {status}")
        
        # Cleanup
        for validator in validators:
            await validator.cleanup()
        
        # Check if any critical issues
        critical_count = sum(1 for r in results if r['status'] == 'critical')
        
        if critical_count > 0:
            logger.warning(f"⚠️  {critical_count} validators returned critical status")
        else:
            logger.info("✅ Quick validation cycle completed successfully")
        
        return True
    except Exception as e:
        logger.error(f"❌ Quick validation cycle failed: {e}")
        return False

async def main():
    """Função principal de teste"""
    print("=" * 70)
    print("🧪 TESTING VALIDATION SYSTEM - Agent-QualityAssurance FASE 4")
    print("=" * 70)
    print()
    
    # Lista de testes
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Validators", test_validators),
        ("Dashboard", test_dashboard),
        ("Reporter", test_reporter),
        ("Validation Manager", test_validation_manager),
        ("Quick Validation Cycle", test_quick_validation_cycle)
    ]
    
    # Executar testes
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_function in tests:
        print(f"🧪 Testing {test_name}...")
        
        try:
            result = await test_function()
            if result:
                passed_tests += 1
            print()
        except Exception as e:
            logger.error(f"❌ Test {test_name} crashed: {e}")
            print()
    
    # Resultados finais
    print("=" * 70)
    print("📊 TEST RESULTS")
    print("=" * 70)
    print(f"✅ Tests passed: {passed_tests}/{total_tests}")
    print(f"❌ Tests failed: {total_tests - passed_tests}/{total_tests}")
    print(f"📈 Success rate: {(passed_tests/total_tests)*100:.1f}%")
    print()
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Validation system is ready for 96-hour continuous validation")
        print()
        print("To start the 96-hour validation, run:")
        print("python run_96h_continuous_validation.py")
        return True
    else:
        print("⚠️  SOME TESTS FAILED!")
        print("❌ Please fix the issues before starting the 96-hour validation")
        print()
        print("Common fixes:")
        print("- Ensure Redis is running: redis-server")
        print("- Install dependencies: pip install -r requirements.txt")
        print("- Check Redis connection: redis-cli ping")
        return False

def create_sample_test_data():
    """Criar dados de teste para validação"""
    try:
        import redis
        
        client = redis.Redis(host='localhost', port=int(os.getenv('REDIS_PORT', 6379)), decode_responses=True)
        
        # Sample audio data
        audio_data = {
            'id': 'test_audio_001',
            'title': 'Test Audio File',
            'url': 'https://example.com/test-audio',
            'status': 'completed',
            'duration': '180.5',
            'download_date': datetime.now().isoformat(),
            'file_path': '/test/path/audio.mp3',
            'transcription_status': 'completed'
        }
        
        # Sample video data
        video_data = {
            'id': 'test_video_001',
            'title': 'Test Video File',
            'url': 'https://example.com/test-video',
            'status': 'completed',
            'duration': '300.0',
            'download_date': datetime.now().isoformat(),
            'file_path': '/test/path/video.mp4',
            'quality': '720p',
            'format': 'mp4'
        }
        
        # Store test data
        client.hset('audio:test_audio_001', mapping=audio_data)
        client.hset('video:test_video_001', mapping=video_data)
        
        # Add to indices
        client.sadd('audio:index', 'test_audio_001')
        client.sadd('video:index', 'test_video_001')
        
        logger.info("✅ Sample test data created")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create test data: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting validation system tests...")
    print()
    
    # Create sample test data first
    print("📝 Creating sample test data...")
    create_sample_test_data()
    print()
    
    # Run tests
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 Tests interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(2)