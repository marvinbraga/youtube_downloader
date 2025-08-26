"""
Validation Module - Agent-QualityAssurance FASE 4
Sistema de validação contínua pós-cutover por 96 horas
"""

from .continuous_validation_manager import ContinuousValidationManager, ValidationConfig, ValidationResult
from .data_integrity_validator import DataIntegrityValidator
from .performance_validator import PerformanceValidator
from .user_experience_validator import UserExperienceValidator
from .error_rate_validator import ErrorRateValidator
from .validation_reporter import ValidationReporter
from .validation_dashboard import ValidationDashboard

__version__ = "1.0.0"
__author__ = "Agent-QualityAssurance FASE 4"

__all__ = [
    'ContinuousValidationManager',
    'ValidationConfig',
    'ValidationResult',
    'DataIntegrityValidator',
    'PerformanceValidator', 
    'UserExperienceValidator',
    'ErrorRateValidator',
    'ValidationReporter',
    'ValidationDashboard'
]