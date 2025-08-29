"""
Redis API Endpoints - FASE 3 Implementation
Endpoints híbridos que suportam Redis e JSON com fallback automático
"""

import time
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from fastapi import Query, Depends, HTTPException
from loguru import logger

from app.services.redis_audio_manager import RedisAudioManager
from app.services.redis_video_manager import RedisVideoManager
from app.services.files import scan_audio_directory, scan_video_directory
from app.services.securities import verify_token


class HybridResponse:
    """Classe para padronizar respostas híbridas com métricas de performance"""
    
    @staticmethod
    def create_response(
        data: Any,
        source: str,
        performance_ms: float,
        error: Optional[str] = None,
        fallback: bool = False
    ) -> Dict[str, Any]:
        """Cria resposta padronizada com métricas"""
        response = {
            "data": data,
            "source": source,
            "performance_ms": round(performance_ms, 2),
            "timestamp": datetime.now().isoformat(),
            "fallback": fallback
        }
        
        if error:
            response["error"] = error
            
        return response


class RedisAPIEndpoints:
    """Endpoints API híbridos Redis/JSON com modo controlado"""
    
    def __init__(self):
        self.redis_audio_manager = None
        self.redis_video_manager = None
        
    async def _get_redis_managers(self):
        """Inicializa managers Redis se necessário"""
        if self.redis_audio_manager is None:
            try:
                self.redis_audio_manager = RedisAudioManager()
                await self.redis_audio_manager.ensure_connection()
            except Exception as e:
                logger.warning(f"Redis Audio Manager não disponível: {e}")
                self.redis_audio_manager = False
                
        if self.redis_video_manager is None:
            try:
                self.redis_video_manager = RedisVideoManager()
                await self.redis_video_manager.ensure_connection()
            except Exception as e:
                logger.warning(f"Redis Video Manager não disponível: {e}")
                self.redis_video_manager = False
    
    async def get_audios(
        self,
        use_redis: bool = True,
        compare_mode: bool = False,
        token_data: dict = Depends(verify_token)
    ) -> Dict[str, Any]:
        """
        Endpoint híbrido /api/audios - Redis/JSON com toggle
        
        Args:
            use_redis: Se deve tentar usar Redis primeiro
            compare_mode: Se deve comparar Redis vs JSON (modo validação)
            token_data: Token de autenticação
        """
        start_time = time.time()
        
        try:
            await self._get_redis_managers()
            
            # Modo comparação - executa ambos para validar
            if compare_mode and self.redis_audio_manager:
                try:
                    # Executa Redis e JSON em paralelo
                    redis_task = self._get_audios_from_redis()
                    # audios.json eliminado - sem fallback JSON
                    json_task = None
                    
                    redis_result, json_result = await asyncio.gather(
                        redis_task, json_task, return_exceptions=True
                    )
                    
                    # Compara resultados
                    comparison = await self._compare_audio_results(redis_result, json_result)
                    
                    performance_ms = (time.time() - start_time) * 1000
                    
                    return {
                        "audios": redis_result if not isinstance(redis_result, Exception) else json_result,
                        "source": "comparison_mode",
                        "performance_ms": round(performance_ms, 2),
                        "comparison": comparison,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    logger.error(f"Erro no modo comparação: {e}")
                    # Fallback para modo normal
                    use_redis = True
            
            # Modo Redis primeiro
            if use_redis and self.redis_audio_manager:
                try:
                    audios = await self._get_audios_from_redis()
                    performance_ms = (time.time() - start_time) * 1000
                    
                    logger.info(f"Audios obtidos do Redis em {performance_ms:.2f}ms")
                    
                    return HybridResponse.create_response(
                        data=audios,
                        source="redis",
                        performance_ms=performance_ms
                    )
                    
                except Exception as e:
                    logger.warning(f"Falha no Redis, usando fallback JSON: {e}")
                    # Auto-fallback para JSON
                    # audios.json eliminado - usar apenas Redis
                    audios = []
                    performance_ms = (time.time() - start_time) * 1000
                    
                    return HybridResponse.create_response(
                        data=audios,
                        source="json_fallback", 
                        performance_ms=performance_ms,
                        error=str(e),
                        fallback=True
                    )
            
            # Modo JSON direto
            else:
                # audios.json eliminado - usar apenas Redis
                audios = []
                performance_ms = (time.time() - start_time) * 1000
                
                return HybridResponse.create_response(
                    data=audios,
                    source="json",
                    performance_ms=performance_ms
                )
                
        except Exception as e:
            performance_ms = (time.time() - start_time) * 1000
            logger.error(f"Erro crítico em get_audios: {e}")
            
            return HybridResponse.create_response(
                data=[],
                source="error",
                performance_ms=performance_ms,
                error=str(e)
            )
    
    async def search_audios(
        self,
        query: str,
        use_redis: bool = True,
        limit: int = Query(50, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        token_data: dict = Depends(verify_token)
    ) -> Dict[str, Any]:
        """
        Endpoint híbrido /api/audios/search - Busca otimizada Redis/JSON
        
        Args:
            query: Termo de busca
            use_redis: Se deve usar Redis para busca
            limit: Limite de resultados
            offset: Offset para paginação
            token_data: Token de autenticação
        """
        start_time = time.time()
        
        try:
            await self._get_redis_managers()
            
            # Busca Redis otimizada
            if use_redis and self.redis_audio_manager:
                try:
                    results = await self._search_audios_redis(query, limit, offset)
                    performance_ms = (time.time() - start_time) * 1000
                    
                    logger.info(f"Busca Redis completada em {performance_ms:.2f}ms para query: '{query}'")
                    
                    return HybridResponse.create_response(
                        data={
                            "results": results,
                            "query": query,
                            "limit": limit,
                            "offset": offset,
                            "total_found": len(results)
                        },
                        source="redis_search",
                        performance_ms=performance_ms
                    )
                    
                except Exception as e:
                    logger.warning(f"Falha na busca Redis, usando fallback: {e}")
                    # Auto-fallback para busca JSON
                    results = await self._search_audios_json(query, limit, offset)
                    performance_ms = (time.time() - start_time) * 1000
                    
                    return HybridResponse.create_response(
                        data={
                            "results": results,
                            "query": query,
                            "limit": limit,
                            "offset": offset,
                            "total_found": len(results)
                        },
                        source="json_search_fallback",
                        performance_ms=performance_ms,
                        error=str(e),
                        fallback=True
                    )
            
            # Busca JSON
            else:
                results = await self._search_audios_json(query, limit, offset)
                performance_ms = (time.time() - start_time) * 1000
                
                return HybridResponse.create_response(
                    data={
                        "results": results,
                        "query": query,
                        "limit": limit,
                        "offset": offset,
                        "total_found": len(results)
                    },
                    source="json_search",
                    performance_ms=performance_ms
                )
                
        except Exception as e:
            performance_ms = (time.time() - start_time) * 1000
            logger.error(f"Erro crítico em search_audios: {e}")
            
            return HybridResponse.create_response(
                data={
                    "results": [],
                    "query": query,
                    "error": str(e)
                },
                source="error",
                performance_ms=performance_ms,
                error=str(e)
            )
    
    async def _get_audios_from_redis(self) -> List[Dict[str, Any]]:
        """Obtém audios do Redis"""
        if not self.redis_audio_manager:
            raise Exception("Redis Audio Manager não disponível")
            
        return await self.redis_audio_manager.get_all_audios()
    
    async def _get_audios_from_json(self) -> List[Dict[str, Any]]:
        """Função obsoleta - audios.json eliminado"""
        logger.warning("_get_audios_from_json() called but audios.json is no longer used")
        return []
    
    async def _search_audios_redis(self, query: str, limit: int, offset: int) -> List[Dict[str, Any]]:
        """Busca otimizada no Redis"""
        if not self.redis_audio_manager:
            raise Exception("Redis Audio Manager não disponível")
            
        # Usa busca avançada do Redis
        return await self.redis_audio_manager.search_audios(
            query=query,
            limit=limit,
            offset=offset
        )
    
    async def _search_audios_json(self, query: str, limit: int, offset: int) -> List[Dict[str, Any]]:
        """Busca básica no JSON"""
        loop = asyncio.get_event_loop()
        # audios.json eliminado - retorna lista vazia
        all_audios = []
        
        # Busca simples por título e descrição
        query_lower = query.lower()
        results = []
        
        for audio in all_audios:
            if (query_lower in audio.get("name", "").lower() or 
                query_lower in audio.get("description", "").lower()):
                results.append(audio)
        
        # Aplica paginação
        start_idx = offset
        end_idx = offset + limit
        
        return results[start_idx:end_idx]
    
    async def _compare_audio_results(self, redis_result: Any, json_result: Any) -> Dict[str, Any]:
        """Compara resultados Redis vs JSON para validação"""
        comparison = {
            "redis_success": not isinstance(redis_result, Exception),
            "json_success": not isinstance(json_result, Exception),
            "redis_count": 0,
            "json_count": 0,
            "discrepancies": []
        }
        
        if comparison["redis_success"]:
            comparison["redis_count"] = len(redis_result) if isinstance(redis_result, list) else 0
            
        if comparison["json_success"]:
            comparison["json_count"] = len(json_result) if isinstance(json_result, list) else 0
        
        # Detecta discrepâncias
        if comparison["redis_success"] and comparison["json_success"]:
            if comparison["redis_count"] != comparison["json_count"]:
                comparison["discrepancies"].append(
                    f"Count mismatch: Redis={comparison['redis_count']}, JSON={comparison['json_count']}"
                )
            
            # Compara IDs dos primeiros 10 items
            redis_ids = {item.get('id') for item in redis_result[:10]} if redis_result else set()
            json_ids = {item.get('id') for item in json_result[:10]} if json_result else set()
            
            missing_in_redis = json_ids - redis_ids
            missing_in_json = redis_ids - json_ids
            
            if missing_in_redis:
                comparison["discrepancies"].append(f"Missing in Redis: {list(missing_in_redis)}")
            if missing_in_json:
                comparison["discrepancies"].append(f"Missing in JSON: {list(missing_in_json)}")
        
        # Log discrepâncias
        if comparison["discrepancies"]:
            logger.warning(f"Redis/JSON comparison discrepancies: {comparison['discrepancies']}")
        
        return comparison


# Instância global dos endpoints
redis_api_endpoints = RedisAPIEndpoints()