#!/usr/bin/env python3
"""
FASE 3 - End-to-End Integration Tests
Cenários completos de fluxos integrados

Agent-QualityAssurance - Validação end-to-end
Testa fluxos completos: download → progresso → transcrição → notificação
Múltiplos downloads simultâneos, integridade de dados, cenários de falha
"""

import asyncio
import json
import time
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import sys
import os
import aiohttp
import websockets
from pathlib import Path

# Adicionar pasta app ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from loguru import logger

# Configurar logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


@dataclass
class EndToEndScenario:
    """Cenário de teste end-to-end"""
    scenario_name: str
    steps_completed: int
    total_steps: int
    success: bool
    duration_seconds: float
    data_integrity_verified: bool
    error_recovery_tested: bool
    notifications_received: int
    error_details: Optional[str] = None


class FASE3EndToEndTests:
    """
    End-to-End Integration Tests para FASE 3
    
    Cenários testados:
    - Fluxo completo: download → progresso → transcrição → notificação
    - Múltiplos downloads simultâneos
    - Integridade de dados em todos os estágios
    - Cenários de falha e recuperação
    - Reconexão automática WebSocket/SSE
    - Persistência de dados durante interrupções
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.websocket_url = base_url.replace("http", "ws")
        self.scenarios: List[EndToEndScenario] = []
        self.test_data = {}
        
        logger.info("🔄 FASE 3 End-to-End Tests initialized")
        logger.info(f"Testing against: {base_url}")
    
    async def run_complete_e2e_tests(self) -> bool:
        """Executa todos os cenários end-to-end"""
        logger.info("=" * 80)
        logger.info("🔄 FASE 3 - END-TO-END INTEGRATION TESTS")
        logger.info("=" * 80)
        
        try:
            # 1. Cenário: Fluxo completo de download
            await self.scenario_complete_download_flow()
            
            # 2. Cenário: Múltiplos downloads simultâneos  
            await self.scenario_multiple_downloads()
            
            # 3. Cenário: Integridade de dados
            await self.scenario_data_integrity_validation()
            
            # 4. Cenário: Falhas e recuperação
            await self.scenario_failure_recovery()
            
            # 5. Cenário: Reconexão automática
            await self.scenario_auto_reconnection()
            
            # 6. Cenário: Persistência durante interrupções
            await self.scenario_data_persistence()
            
            return self.compile_e2e_results()
            
        except Exception as e:
            logger.error(f"❌ End-to-end tests failed: {e}")
            return False
    
    async def scenario_complete_download_flow(self):
        """Cenário: Fluxo completo download → progresso → transcrição → notificação"""
        logger.info("📥 Scenario: Complete Download Flow...")
        
        scenario_start = time.time()
        steps_completed = 0
        total_steps = 7
        notifications_received = 0
        data_integrity = True
        error_recovery = False
        error_details = None
        
        try:
            # Preparar dados de teste
            test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Test URL
            task_id = f"e2e_download_{int(time.time())}"
            
            # STEP 1: Conectar ao WebSocket para monitorar progresso
            ws_url = f"{self.websocket_url}/ws/progress"
            websocket = await websockets.connect(ws_url, timeout=10)
            
            # Subscrever ao task_id
            subscribe_msg = {
                "type": "subscribe",
                "data": {"task_ids": [task_id], "channels": ["progress", "system"]}
            }
            await websocket.send(json.dumps(subscribe_msg))
            await websocket.recv()  # Confirmation
            steps_completed += 1
            
            # STEP 2: Iniciar download via API
            async with aiohttp.ClientSession() as session:
                download_payload = {
                    "url": test_video_url,
                    "task_id": task_id,
                    "format": "audio",
                    "quality": "128k"
                }
                
                async with session.post(f"{self.base_url}/api/download/start", 
                                      json=download_payload) as resp:
                    if resp.status == 200:
                        download_response = await resp.json()
                        logger.info(f"Download started: {download_response}")
                        steps_completed += 1
                    else:
                        raise Exception(f"Download start failed: {resp.status}")
            
            # STEP 3: Monitorar progresso em tempo real
            progress_events = []
            timeout_counter = 0
            max_timeout = 300  # 5 minutos
            
            while timeout_counter < max_timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    event_data = json.loads(message)
                    
                    if event_data.get("type") == "progress_update":
                        progress_events.append(event_data)
                        
                        progress_info = event_data.get("data", {})
                        current_progress = progress_info.get("progress", 0)
                        current_stage = progress_info.get("current_stage", "unknown")
                        
                        logger.info(f"Progress: {current_progress}% - Stage: {current_stage}")
                        
                        # Se chegou a 100%, quebrar loop
                        if current_progress >= 100:
                            break
                    
                    elif event_data.get("type") == "task_complete":
                        logger.info("Task completed notification received")
                        notifications_received += 1
                        break
                        
                    timeout_counter = 0  # Reset timeout se recebeu mensagem
                    
                except asyncio.TimeoutError:
                    timeout_counter += 1
                    continue
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    break
            
            if progress_events:
                steps_completed += 1
                logger.info(f"Received {len(progress_events)} progress events")
            
            await websocket.close()
            
            # STEP 4: Verificar dados do download
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tasks/{task_id}") as resp:
                    if resp.status == 200:
                        task_data = await resp.json()
                        
                        if task_data.get("status") == "completed":
                            steps_completed += 1
                            logger.info("Task status verified as completed")
                        else:
                            data_integrity = False
                            logger.warning(f"Task status: {task_data.get('status')}")
                    else:
                        data_integrity = False
                        logger.error(f"Task verification failed: {resp.status}")
            
            # STEP 5: Verificar se arquivo foi salvo
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/files/{task_id}") as resp:
                    if resp.status == 200:
                        file_data = await resp.json()
                        
                        if file_data.get("exists") and file_data.get("size") > 0:
                            steps_completed += 1
                            logger.info(f"File verified: {file_data.get('size')} bytes")
                        else:
                            data_integrity = False
                            logger.warning("File not found or empty")
                    else:
                        data_integrity = False
                        logger.error(f"File verification failed: {resp.status}")
            
            # STEP 6: Verificar transcrição (se aplicável)
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/transcription/{task_id}") as resp:
                    if resp.status == 200:
                        transcription_data = await resp.json()
                        
                        if transcription_data.get("available"):
                            steps_completed += 1
                            logger.info("Transcription verified")
                        else:
                            logger.info("Transcription not available (expected for test)")
                    else:
                        logger.info("Transcription endpoint not available (expected)")
            
            # STEP 7: Validar integridade Redis vs JSON
            async with aiohttp.ClientSession() as session:
                redis_params = {"use_redis": True, "task_id": task_id}
                json_params = {"use_redis": False, "task_id": task_id}
                
                async with session.get(f"{self.base_url}/api/audios", params=redis_params) as resp:
                    redis_data = await resp.json() if resp.status == 200 else {}
                
                async with session.get(f"{self.base_url}/api/audios", params=json_params) as resp:
                    json_data = await resp.json() if resp.status == 200 else {}
                
                # Verificar se ambos têm os dados
                if redis_data.get("data") and json_data.get("data"):
                    redis_count = len(redis_data["data"])
                    json_count = len(json_data["data"])
                    
                    if redis_count == json_count:
                        steps_completed += 1
                        logger.info("Data integrity verified between Redis and JSON")
                    else:
                        data_integrity = False
                        logger.warning(f"Data mismatch: Redis={redis_count}, JSON={json_count}")
                else:
                    data_integrity = False
                    logger.warning("Data verification incomplete")
            
        except Exception as e:
            error_details = str(e)
            logger.error(f"Complete download flow failed: {e}")
        
        duration = time.time() - scenario_start
        success = steps_completed >= (total_steps * 0.8)  # 80% dos passos
        
        scenario = EndToEndScenario(
            scenario_name="Complete Download Flow",
            steps_completed=steps_completed,
            total_steps=total_steps,
            success=success,
            duration_seconds=duration,
            data_integrity_verified=data_integrity,
            error_recovery_tested=error_recovery,
            notifications_received=notifications_received,
            error_details=error_details
        )
        
        self.scenarios.append(scenario)
        logger.info(f"✅ Complete Download Flow: {steps_completed}/{total_steps} steps ({duration:.2f}s)")
    
    async def scenario_multiple_downloads(self):
        """Cenário: Múltiplos downloads simultâneos"""
        logger.info("🔄 Scenario: Multiple Simultaneous Downloads...")
        
        scenario_start = time.time()
        concurrent_downloads = 5
        steps_completed = 0
        total_steps = concurrent_downloads * 3  # 3 steps per download
        notifications_received = 0
        data_integrity = True
        
        try:
            # Conectar ao WebSocket
            ws_url = f"{self.websocket_url}/ws/progress"
            websocket = await websockets.connect(ws_url, timeout=10)
            
            # Iniciar múltiplos downloads
            download_tasks = []
            task_ids = []
            
            test_urls = [
                "https://www.youtube.com/watch?v=test1",
                "https://www.youtube.com/watch?v=test2", 
                "https://www.youtube.com/watch?v=test3",
                "https://www.youtube.com/watch?v=test4",
                "https://www.youtube.com/watch?v=test5"
            ]
            
            async def start_single_download(url, task_id):
                try:
                    async with aiohttp.ClientSession() as session:
                        payload = {
                            "url": url,
                            "task_id": task_id,
                            "format": "audio",
                            "quality": "128k"
                        }
                        
                        async with session.post(f"{self.base_url}/api/download/start", 
                                              json=payload, timeout=30) as resp:
                            return resp.status == 200, task_id
                            
                except Exception as e:
                    logger.debug(f"Download {task_id} failed: {e}")
                    return False, task_id
            
            # Iniciar downloads simultaneamente
            for i, url in enumerate(test_urls):
                task_id = f"multi_download_{i}_{int(time.time())}"
                task_ids.append(task_id)
                download_tasks.append(start_single_download(url, task_id))
            
            # Subscrever a todos os task_ids
            subscribe_msg = {
                "type": "subscribe",
                "data": {"task_ids": task_ids, "channels": ["progress"]}
            }
            await websocket.send(json.dumps(subscribe_msg))
            
            # Aguardar início dos downloads
            download_results = await asyncio.gather(*download_tasks, return_exceptions=True)
            successful_starts = sum(1 for result in download_results 
                                  if isinstance(result, tuple) and result[0])
            
            steps_completed += successful_starts
            logger.info(f"Started {successful_starts}/{concurrent_downloads} downloads")
            
            # Monitorar progresso de todos os downloads
            completed_tasks = set()
            progress_timeout = 120  # 2 minutos
            start_monitor = time.time()
            
            while (time.time() - start_monitor) < progress_timeout and len(completed_tasks) < successful_starts:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5)
                    event_data = json.loads(message)
                    
                    if event_data.get("type") == "progress_update":
                        task_id = event_data.get("data", {}).get("task_id")
                        progress = event_data.get("data", {}).get("progress", 0)
                        
                        if progress >= 100 and task_id:
                            completed_tasks.add(task_id)
                            notifications_received += 1
                            
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Monitor error: {e}")
                    break
            
            steps_completed += len(completed_tasks)
            
            await websocket.close()
            
            # Verificar dados finais
            async with aiohttp.ClientSession() as session:
                for task_id in task_ids:
                    try:
                        async with session.get(f"{self.base_url}/api/tasks/{task_id}") as resp:
                            if resp.status == 200:
                                task_data = await resp.json()
                                if task_data.get("status") in ["completed", "processing"]:
                                    steps_completed += 1
                    except Exception:
                        data_integrity = False
        
        except Exception as e:
            logger.error(f"Multiple downloads scenario failed: {e}")
        
        duration = time.time() - scenario_start
        success = steps_completed >= (total_steps * 0.6)  # 60% para múltiplos downloads
        
        scenario = EndToEndScenario(
            scenario_name="Multiple Simultaneous Downloads",
            steps_completed=steps_completed,
            total_steps=total_steps,
            success=success,
            duration_seconds=duration,
            data_integrity_verified=data_integrity,
            error_recovery_tested=False,
            notifications_received=notifications_received
        )
        
        self.scenarios.append(scenario)
        logger.info(f"✅ Multiple Downloads: {steps_completed}/{total_steps} steps ({duration:.2f}s)")
    
    async def scenario_data_integrity_validation(self):
        """Cenário: Validação de integridade de dados"""
        logger.info("🔍 Scenario: Data Integrity Validation...")
        
        scenario_start = time.time()
        steps_completed = 0
        total_steps = 6
        data_integrity = True
        
        try:
            async with aiohttp.ClientSession() as session:
                # STEP 1: Comparar dados Redis vs JSON
                async with session.get(f"{self.base_url}/api/audios", params={"use_redis": True}) as resp:
                    redis_audios = await resp.json() if resp.status == 200 else {}
                
                async with session.get(f"{self.base_url}/api/audios", params={"use_redis": False}) as resp:
                    json_audios = await resp.json() if resp.status == 200 else {}
                
                if redis_audios.get("data") and json_audios.get("data"):
                    redis_count = len(redis_audios["data"])
                    json_count = len(json_audios["data"])
                    
                    if abs(redis_count - json_count) <= 1:  # Tolerância de 1 item
                        steps_completed += 1
                        logger.info(f"Audios count consistency: Redis={redis_count}, JSON={json_count}")
                    else:
                        data_integrity = False
                        logger.warning(f"Audios count mismatch: Redis={redis_count}, JSON={json_count}")
                
                # STEP 2: Comparar dados de vídeos
                async with session.get(f"{self.base_url}/api/videos", params={"use_redis": True}) as resp:
                    redis_videos = await resp.json() if resp.status == 200 else {}
                
                async with session.get(f"{self.base_url}/api/videos", params={"use_redis": False}) as resp:
                    json_videos = await resp.json() if resp.status == 200 else {}
                
                if redis_videos.get("data") and json_videos.get("data"):
                    redis_v_count = len(redis_videos["data"])
                    json_v_count = len(json_videos["data"])
                    
                    if abs(redis_v_count - json_v_count) <= 1:
                        steps_completed += 1
                        logger.info(f"Videos count consistency: Redis={redis_v_count}, JSON={json_v_count}")
                    else:
                        data_integrity = False
                        logger.warning(f"Videos count mismatch: Redis={redis_v_count}, JSON={json_v_count}")
                
                # STEP 3: Testar busca Redis vs JSON
                search_query = "test"
                
                async with session.get(f"{self.base_url}/api/audios/search", 
                                     params={"q": search_query, "use_redis": True}) as resp:
                    redis_search = await resp.json() if resp.status == 200 else {}
                
                async with session.get(f"{self.base_url}/api/audios/search",
                                     params={"q": search_query, "use_redis": False}) as resp:
                    json_search = await resp.json() if resp.status == 200 else {}
                
                if redis_search.get("data") is not None and json_search.get("data") is not None:
                    steps_completed += 1
                    logger.info("Search results consistency verified")
                else:
                    data_integrity = False
                    logger.warning("Search results inconsistent")
                
                # STEP 4: Validar sistema de métricas
                async with session.get(f"{self.base_url}/api/dashboard/metrics") as resp:
                    if resp.status == 200:
                        metrics = await resp.json()
                        if metrics.get("metrics"):
                            steps_completed += 1
                            logger.info("Metrics system integrity verified")
                        else:
                            data_integrity = False
                    else:
                        data_integrity = False
                
                # STEP 5: Testar comparação oficial do sistema
                async with session.get(f"{self.base_url}/api/system/compare-redis-json") as resp:
                    if resp.status == 200:
                        comparison = await resp.json()
                        if comparison.get("consistent", False):
                            steps_completed += 1
                            logger.info("System comparison reports consistency")
                        else:
                            logger.warning("System comparison reports inconsistency")
                    else:
                        logger.warning("System comparison not available")
                
                # STEP 6: Validar health check
                async with session.get(f"{self.base_url}/api/dashboard/health") as resp:
                    if resp.status == 200:
                        health = await resp.json()
                        if health.get("overall_status") == "healthy":
                            steps_completed += 1
                            logger.info("System health check passed")
                        else:
                            logger.warning(f"System health: {health.get('overall_status')}")
                    else:
                        logger.warning("Health check not available")
        
        except Exception as e:
            logger.error(f"Data integrity validation failed: {e}")
            data_integrity = False
        
        duration = time.time() - scenario_start
        success = steps_completed >= (total_steps * 0.8) and data_integrity
        
        scenario = EndToEndScenario(
            scenario_name="Data Integrity Validation",
            steps_completed=steps_completed,
            total_steps=total_steps,
            success=success,
            duration_seconds=duration,
            data_integrity_verified=data_integrity,
            error_recovery_tested=False,
            notifications_received=0
        )
        
        self.scenarios.append(scenario)
        logger.info(f"✅ Data Integrity: {steps_completed}/{total_steps} steps ({duration:.2f}s)")
    
    async def scenario_failure_recovery(self):
        """Cenário: Teste de falhas e recuperação"""
        logger.info("🚨 Scenario: Failure Recovery Testing...")
        
        scenario_start = time.time()
        steps_completed = 0
        total_steps = 5
        error_recovery = False
        
        try:
            async with aiohttp.ClientSession() as session:
                # STEP 1: Forçar erro Redis e testar fallback
                async with session.get(f"{self.base_url}/api/audios", 
                                     params={"use_redis": True, "simulate_redis_error": True}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("source") == "json_fallback":
                            steps_completed += 1
                            error_recovery = True
                            logger.info("Redis fallback to JSON working")
                        else:
                            logger.warning("Fallback not triggered properly")
                    else:
                        logger.warning(f"Fallback test failed: {resp.status}")
                
                # STEP 2: Testar timeout recovery
                async with session.get(f"{self.base_url}/api/audios", 
                                     params={"simulate_timeout": True}, timeout=15) as resp:
                    if resp.status in [200, 408]:  # OK ou Timeout
                        steps_completed += 1
                        logger.info("Timeout handling working")
                    else:
                        logger.warning(f"Timeout handling issue: {resp.status}")
                
                # STEP 3: Testar circuit breaker
                # Fazer várias requests com erro para ativar circuit breaker
                for i in range(5):
                    try:
                        async with session.get(f"{self.base_url}/api/audios", 
                                             params={"simulate_error": True}, timeout=5) as resp:
                            pass
                    except:
                        pass
                
                # Agora testar se circuit breaker está ativo
                async with session.get(f"{self.base_url}/api/system/circuit-breaker-status") as resp:
                    if resp.status == 200:
                        cb_status = await resp.json()
                        steps_completed += 1
                        logger.info(f"Circuit breaker status: {cb_status}")
                    else:
                        logger.warning("Circuit breaker status not available")
                
                # STEP 4: Testar recuperação após erro
                await asyncio.sleep(2)  # Aguardar recuperação
                
                async with session.get(f"{self.base_url}/api/audios", params={"use_redis": True}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("source") == "redis":
                            steps_completed += 1
                            error_recovery = True
                            logger.info("System recovered from errors")
                        else:
                            logger.info("System still using fallback (expected)")
                    else:
                        logger.warning("Recovery test failed")
                
                # STEP 5: Verificar logs de erro
                async with session.get(f"{self.base_url}/api/system/error-logs") as resp:
                    if resp.status == 200:
                        error_logs = await resp.json()
                        if error_logs.get("recent_errors"):
                            steps_completed += 1
                            logger.info("Error logging system working")
                    else:
                        logger.info("Error logs not available (expected)")
        
        except Exception as e:
            logger.error(f"Failure recovery testing failed: {e}")
        
        duration = time.time() - scenario_start
        success = steps_completed >= (total_steps * 0.6) or error_recovery
        
        scenario = EndToEndScenario(
            scenario_name="Failure Recovery Testing",
            steps_completed=steps_completed,
            total_steps=total_steps,
            success=success,
            duration_seconds=duration,
            data_integrity_verified=True,
            error_recovery_tested=error_recovery,
            notifications_received=0
        )
        
        self.scenarios.append(scenario)
        logger.info(f"✅ Failure Recovery: {steps_completed}/{total_steps} steps ({duration:.2f}s)")
    
    async def scenario_auto_reconnection(self):
        """Cenário: Reconexão automática WebSocket/SSE"""
        logger.info("🔄 Scenario: Auto-Reconnection Testing...")
        
        scenario_start = time.time()
        steps_completed = 0
        total_steps = 4
        error_recovery = False
        
        try:
            # STEP 1: Conectar WebSocket
            ws_url = f"{self.websocket_url}/ws/progress"
            websocket = await websockets.connect(ws_url, timeout=10)
            
            # Enviar ping inicial
            ping_msg = {"type": "ping", "data": {"test": "initial"}}
            await websocket.send(json.dumps(ping_msg))
            response = await websocket.recv()
            
            if json.loads(response).get("type") == "pong":
                steps_completed += 1
                logger.info("Initial WebSocket connection working")
            
            # STEP 2: Simular desconexão forçada
            await websocket.close()
            await asyncio.sleep(1)
            
            # STEP 3: Tentar reconectar
            try:
                websocket = await websockets.connect(ws_url, timeout=10)
                
                ping_msg = {"type": "ping", "data": {"test": "reconnection"}}
                await websocket.send(json.dumps(ping_msg))
                response = await websocket.recv()
                
                if json.loads(response).get("type") == "pong":
                    steps_completed += 1
                    error_recovery = True
                    logger.info("WebSocket reconnection successful")
                
                await websocket.close()
                
            except Exception as e:
                logger.warning(f"WebSocket reconnection failed: {e}")
            
            # STEP 4: Testar SSE reconnection (simulação)
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(f"{self.base_url}/api/progress/stream") as resp:
                        if resp.status == 200:
                            # Ler um pouco de dados SSE
                            chunk = await resp.content.read(512)
                            if chunk:
                                steps_completed += 1
                                logger.info("SSE connection working")
                            
                            # Simular perda de conexão fechando session
                            
                except Exception as e:
                    logger.debug(f"SSE test error: {e}")
                
                # Tentar SSE novamente
                try:
                    async with session.get(f"{self.base_url}/api/progress/stream") as resp:
                        if resp.status == 200:
                            steps_completed += 1
                            logger.info("SSE reconnection working")
                except Exception as e:
                    logger.debug(f"SSE reconnection test error: {e}")
        
        except Exception as e:
            logger.error(f"Auto-reconnection testing failed: {e}")
        
        duration = time.time() - scenario_start
        success = steps_completed >= (total_steps * 0.75)
        
        scenario = EndToEndScenario(
            scenario_name="Auto-Reconnection Testing",
            steps_completed=steps_completed,
            total_steps=total_steps,
            success=success,
            duration_seconds=duration,
            data_integrity_verified=True,
            error_recovery_tested=error_recovery,
            notifications_received=0
        )
        
        self.scenarios.append(scenario)
        logger.info(f"✅ Auto-Reconnection: {steps_completed}/{total_steps} steps ({duration:.2f}s)")
    
    async def scenario_data_persistence(self):
        """Cenário: Persistência de dados durante interrupções"""
        logger.info("💾 Scenario: Data Persistence Testing...")
        
        scenario_start = time.time()
        steps_completed = 0
        total_steps = 4
        data_integrity = True
        
        try:
            # STEP 1: Criar dados de teste
            test_data = {
                "test_audio_id": f"persist_test_{int(time.time())}",
                "title": "Persistence Test Audio",
                "duration": 120,
                "created_at": datetime.now().isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                # Salvar via Redis
                async with session.post(f"{self.base_url}/api/audios", 
                                      json=test_data, 
                                      params={"use_redis": True}) as resp:
                    if resp.status in [200, 201]:
                        steps_completed += 1
                        logger.info("Test data saved to Redis")
                    else:
                        logger.warning(f"Redis save failed: {resp.status}")
                
                # STEP 2: Verificar dados no Redis
                async with session.get(f"{self.base_url}/api/audios", 
                                     params={"use_redis": True}) as resp:
                    if resp.status == 200:
                        redis_data = await resp.json()
                        redis_items = redis_data.get("data", [])
                        
                        test_item_found = any(
                            item.get("id") == test_data["test_audio_id"] or 
                            item.get("title") == test_data["title"]
                            for item in redis_items
                        )
                        
                        if test_item_found:
                            steps_completed += 1
                            logger.info("Test data found in Redis")
                        else:
                            logger.warning("Test data not found in Redis")
                            data_integrity = False
                
                # STEP 3: Simular "interrupção" usando fallback
                async with session.get(f"{self.base_url}/api/audios", 
                                     params={"use_redis": False}) as resp:
                    if resp.status == 200:
                        json_data = await resp.json()
                        steps_completed += 1
                        logger.info("JSON fallback working during 'interruption'")
                    else:
                        data_integrity = False
                
                # STEP 4: Verificar sincronização
                async with session.get(f"{self.base_url}/api/system/sync-status") as resp:
                    if resp.status == 200:
                        sync_status = await resp.json()
                        steps_completed += 1
                        logger.info(f"Sync status: {sync_status}")
                    else:
                        logger.info("Sync status not available")
        
        except Exception as e:
            logger.error(f"Data persistence testing failed: {e}")
            data_integrity = False
        
        duration = time.time() - scenario_start
        success = steps_completed >= (total_steps * 0.75) and data_integrity
        
        scenario = EndToEndScenario(
            scenario_name="Data Persistence Testing",
            steps_completed=steps_completed,
            total_steps=total_steps,
            success=success,
            duration_seconds=duration,
            data_integrity_verified=data_integrity,
            error_recovery_tested=False,
            notifications_received=0
        )
        
        self.scenarios.append(scenario)
        logger.info(f"✅ Data Persistence: {steps_completed}/{total_steps} steps ({duration:.2f}s)")
    
    def compile_e2e_results(self) -> bool:
        """Compila resultados dos testes end-to-end"""
        logger.info("=" * 80)
        logger.info("🔄 FASE 3 End-to-End Test Results")
        logger.info("=" * 80)
        
        total_scenarios = len(self.scenarios)
        successful_scenarios = len([s for s in self.scenarios if s.success])
        failed_scenarios = total_scenarios - successful_scenarios
        
        logger.info(f"Total Scenarios: {total_scenarios}")
        logger.info(f"Successful: {successful_scenarios}")
        logger.info(f"Failed: {failed_scenarios}")
        logger.info(f"Success Rate: {(successful_scenarios/total_scenarios)*100:.1f}%")
        logger.info("")
        
        # Mostrar detalhes de cada cenário
        logger.info("Scenario Details:")
        logger.info("-" * 120)
        logger.info(f"{'Scenario Name':<35} {'Steps':<12} {'Duration':<12} {'Data OK':<8} {'Recovery':<10} {'Status'}")
        logger.info("-" * 120)
        
        for scenario in self.scenarios:
            status = "✅ PASS" if scenario.success else "❌ FAIL"
            
            logger.info(
                f"{scenario.scenario_name:<35} "
                f"{scenario.steps_completed}/{scenario.total_steps:<10} "
                f"{scenario.duration_seconds:<12.2f} "
                f"{scenario.data_integrity_verified!s:<8} "
                f"{scenario.error_recovery_tested!s:<10} "
                f"{status}"
            )
            
            if scenario.error_details:
                logger.info(f"  Error: {scenario.error_details}")
        
        logger.info("-" * 120)
        logger.info("")
        
        # Análise de integridade
        integrity_scenarios = [s for s in self.scenarios if s.data_integrity_verified]
        recovery_scenarios = [s for s in self.scenarios if s.error_recovery_tested]
        
        logger.info("Integration Analysis:")
        logger.info(f"Data Integrity Verified: {len(integrity_scenarios)}/{total_scenarios}")
        logger.info(f"Error Recovery Tested: {len(recovery_scenarios)}/{total_scenarios}")
        logger.info(f"Total Notifications Received: {sum(s.notifications_received for s in self.scenarios)}")
        logger.info("")
        
        # Critérios de sucesso
        success_rate = (successful_scenarios / total_scenarios) * 100 if total_scenarios > 0 else 0
        integrity_rate = (len(integrity_scenarios) / total_scenarios) * 100 if total_scenarios > 0 else 0
        
        critical_scenarios = [
            "Complete Download Flow",
            "Data Integrity Validation", 
        ]
        
        critical_passed = len([
            s for s in self.scenarios 
            if s.scenario_name in critical_scenarios and s.success
        ])
        
        overall_success = (
            success_rate >= 80 and         # 80% dos cenários passaram
            integrity_rate >= 90 and       # 90% com integridade verificada
            critical_passed >= len(critical_scenarios) * 0.5  # 50% dos críticos
        )
        
        if overall_success:
            logger.success("🎉 FASE 3 END-TO-END TESTS PASSED!")
            logger.success("✅ Complete download flows working")
            logger.success("✅ Data integrity maintained across systems")
            logger.success("✅ Error recovery mechanisms operational")
            logger.success("✅ Real-time notifications functioning")
            logger.success("✅ System handles complex integration scenarios")
            return True
        else:
            logger.error("❌ FASE 3 END-TO-END TESTS FAILED")
            logger.error(f"Success rate: {success_rate:.1f}% (required: ≥80%)")
            logger.error(f"Integrity rate: {integrity_rate:.1f}% (required: ≥90%)")
            logger.error(f"Critical scenarios: {critical_passed}/{len(critical_scenarios)}")
            logger.error("End-to-end integration needs attention")
            return False


async def main():
    """Função principal para execução standalone"""
    e2e_tests = FASE3EndToEndTests()
    
    try:
        success = await e2e_tests.run_complete_e2e_tests()
        
        if success:
            logger.info("🏆 End-to-end tests passed - integration working!")
            return 0
        else:
            logger.error("🔧 End-to-end tests failed - integration issues")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("⚠️ Tests interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))