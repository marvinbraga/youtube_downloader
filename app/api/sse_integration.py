"""
SSE Integration - FASE 3 Implementation
Server-Sent Events integrado com Redis Pub/Sub para notificações em tempo real
"""

import asyncio
import json
import uuid
from typing import Dict, Set, Optional, AsyncGenerator, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from fastapi import Query, Header, HTTPException
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.services.redis_connection import get_redis_client
from app.services.securities import verify_token_sync


@dataclass
class SSEEvent:
    """Estrutura padronizada para eventos SSE"""
    event_type: str
    data: Dict[str, Any]
    timestamp: str = None
    client_id: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_sse_format(self) -> str:
        """Converte para formato SSE"""
        event_data = {
            "type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "client_id": self.client_id
        }
        return f"event: {self.event_type}\ndata: {json.dumps(event_data)}\n\n"


class RedisSSEManager:
    """
    Gerenciador SSE integrado com Redis Pub/Sub
    
    Funcionalidades:
    - Múltiplos clientes simultâneos
    - Redis Pub/Sub para broadcasting
    - Heartbeat e keepalive
    - Cleanup automático de conexões órfãs
    - Métricas de conexões em tempo real
    """
    
    def __init__(self):
        self._clients: Dict[str, Dict[str, Any]] = {}
        self._redis_client = None
        self._subscriber_task = None
        self._heartbeat_task = None
        
        # Configurações
        self.HEARTBEAT_INTERVAL = 30  # segundos
        self.CLIENT_TIMEOUT = 300     # 5 minutos
        self.MAX_CLIENTS = 100
        
        # Canais Redis
        self.REDIS_CHANNELS = {
            'progress': 'sse:progress',
            'downloads': 'sse:downloads',
            'system': 'sse:system',
            'errors': 'sse:errors'
        }
        
        logger.info("RedisSSEManager initialized")
    
    async def initialize_redis(self):
        """Inicializa conexão Redis e subscriber"""
        try:
            self._redis_client = await get_redis_client()
            if self._redis_client:
                # Inicia subscriber task
                self._subscriber_task = asyncio.create_task(self._redis_subscriber())
                
                # Inicia heartbeat task
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                
                logger.info("Redis SSE integration initialized successfully")
                return True
            else:
                logger.warning("Redis not available - SSE will work without Redis integration")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize Redis SSE: {e}")
            return False
    
    async def connect_client(
        self,
        client_id: str,
        token: Optional[str] = None,
        channels: Optional[list] = None
    ) -> AsyncGenerator[str, None]:
        """
        Conecta um cliente SSE com autenticação
        
        Args:
            client_id: ID único do cliente
            token: Token de autenticação
            channels: Canais específicos para se inscrever
        """
        # Verifica limite de clientes
        if len(self._clients) >= self.MAX_CLIENTS:
            yield SSEEvent(
                event_type="error",
                data={"message": "Maximum client limit reached"}
            ).to_sse_format()
            return
        
        # Autenticação opcional
        if token:
            try:
                verify_token_sync(token)
            except Exception as e:
                yield SSEEvent(
                    event_type="error",
                    data={"message": f"Authentication failed: {str(e)}"}
                ).to_sse_format()
                return
        
        # Registra cliente
        client_info = {
            "id": client_id,
            "connected_at": datetime.now(),
            "last_ping": datetime.now(),
            "channels": channels or list(self.REDIS_CHANNELS.keys()),
            "events_sent": 0,
            "queue": asyncio.Queue(),
            "authenticated": token is not None
        }
        
        self._clients[client_id] = client_info
        
        logger.info(f"SSE client connected: {client_id} (authenticated: {client_info['authenticated']})")
        
        try:
            # Enviar evento de boas-vindas
            welcome_event = SSEEvent(
                event_type="connected",
                data={
                    "client_id": client_id,
                    "message": "Connected to real-time stream",
                    "available_channels": client_info["channels"],
                    "server_time": datetime.now().isoformat()
                },
                client_id=client_id
            )
            yield welcome_event.to_sse_format()
            
            # Loop principal de eventos
            while True:
                try:
                    # Aguarda evento com timeout para heartbeat
                    event = await asyncio.wait_for(
                        client_info["queue"].get(),
                        timeout=self.HEARTBEAT_INTERVAL
                    )
                    
                    client_info["events_sent"] += 1
                    client_info["last_ping"] = datetime.now()
                    
                    yield event.to_sse_format()
                    
                except asyncio.TimeoutError:
                    # Enviar heartbeat
                    heartbeat_event = SSEEvent(
                        event_type="heartbeat",
                        data={
                            "timestamp": datetime.now().isoformat(),
                            "events_sent": client_info["events_sent"]
                        },
                        client_id=client_id
                    )
                    yield heartbeat_event.to_sse_format()
                    
                except asyncio.CancelledError:
                    logger.info(f"SSE client disconnected: {client_id}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in SSE stream for client {client_id}: {e}")
            
            error_event = SSEEvent(
                event_type="error",
                data={"message": f"Stream error: {str(e)}"},
                client_id=client_id
            )
            yield error_event.to_sse_format()
            
        finally:
            # Cleanup
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"SSE client cleaned up: {client_id}")
    
    async def broadcast_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        channel: str = "system",
        target_clients: Optional[Set[str]] = None
    ):
        """
        Faz broadcast de evento para clientes conectados
        
        Args:
            event_type: Tipo do evento
            data: Dados do evento  
            channel: Canal Redis/SSE
            target_clients: Clientes específicos (None = todos)
        """
        event = SSEEvent(
            event_type=event_type,
            data=data
        )
        
        # Broadcast via Redis se disponível
        if self._redis_client and channel in self.REDIS_CHANNELS:
            try:
                redis_channel = self.REDIS_CHANNELS[channel]
                await self._redis_client.publish(
                    redis_channel,
                    json.dumps(asdict(event))
                )
                logger.debug(f"Event broadcasted via Redis: {event_type} on {redis_channel}")
            except Exception as e:
                logger.warning(f"Failed to broadcast via Redis: {e}")
        
        # Broadcast direto para clientes locais
        await self._broadcast_to_local_clients(event, channel, target_clients)
    
    async def _broadcast_to_local_clients(
        self,
        event: SSEEvent,
        channel: str,
        target_clients: Optional[Set[str]] = None
    ):
        """Faz broadcast para clientes conectados localmente"""
        if not self._clients:
            return
        
        clients_to_notify = []
        
        for client_id, client_info in self._clients.items():
            # Filtra por clientes específicos se fornecido
            if target_clients and client_id not in target_clients:
                continue
            
            # Filtra por canal se cliente tem preferências
            if channel not in client_info.get("channels", []):
                continue
            
            clients_to_notify.append(client_info)
        
        # Envia evento para clientes filtrados
        for client_info in clients_to_notify:
            try:
                event.client_id = client_info["id"]
                await client_info["queue"].put(event)
            except Exception as e:
                logger.warning(f"Failed to send event to client {client_info['id']}: {e}")
    
    async def _redis_subscriber(self):
        """Task que escuta eventos Redis pub/sub"""
        if not self._redis_client:
            return
        
        try:
            pubsub = self._redis_client.pubsub()
            
            # Se inscreve em todos os canais
            for channel in self.REDIS_CHANNELS.values():
                await pubsub.subscribe(channel)
            
            logger.info(f"Redis subscriber listening on channels: {list(self.REDIS_CHANNELS.values())}")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Decodifica evento Redis
                        event_data = json.loads(message["data"])
                        event = SSEEvent(**event_data)
                        
                        # Determina canal baseado no canal Redis
                        channel = None
                        for ch_name, ch_redis in self.REDIS_CHANNELS.items():
                            if message["channel"].decode() == ch_redis:
                                channel = ch_name
                                break
                        
                        if channel:
                            await self._broadcast_to_local_clients(event, channel)
                        
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Redis subscriber task cancelled")
        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")
        finally:
            try:
                await pubsub.close()
            except:
                pass
    
    async def _heartbeat_loop(self):
        """Task de heartbeat e cleanup de conexões órfãs"""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                current_time = datetime.now()
                clients_to_remove = []
                
                # Identifica clientes órfãos
                for client_id, client_info in self._clients.items():
                    last_ping = client_info["last_ping"]
                    if current_time - last_ping > timedelta(seconds=self.CLIENT_TIMEOUT):
                        clients_to_remove.append(client_id)
                
                # Remove clientes órfãos
                for client_id in clients_to_remove:
                    del self._clients[client_id]
                    logger.info(f"Removed orphaned SSE client: {client_id}")
                
                # Log estatísticas
                if self._clients:
                    logger.debug(f"Active SSE clients: {len(self._clients)}")
                
            except asyncio.CancelledError:
                logger.info("Heartbeat task cancelled")
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    def get_client_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas dos clientes conectados"""
        stats = {
            "total_clients": len(self._clients),
            "max_clients": self.MAX_CLIENTS,
            "redis_integration": self._redis_client is not None,
            "uptime_seconds": 0,  # TODO: implementar tracking de uptime
            "clients": []
        }
        
        for client_id, client_info in self._clients.items():
            client_stats = {
                "id": client_id,
                "connected_duration_seconds": int((datetime.now() - client_info["connected_at"]).total_seconds()),
                "events_sent": client_info["events_sent"],
                "authenticated": client_info["authenticated"],
                "channels": client_info["channels"],
                "last_ping_seconds_ago": int((datetime.now() - client_info["last_ping"]).total_seconds())
            }
            stats["clients"].append(client_stats)
        
        return stats
    
    async def disconnect_client(self, client_id: str):
        """Desconecta cliente específico"""
        if client_id in self._clients:
            # Envia evento de desconexão
            await self.broadcast_event(
                event_type="disconnecting",
                data={"message": "Connection being closed by server"},
                target_clients={client_id}
            )
            
            del self._clients[client_id]
            logger.info(f"Client manually disconnected: {client_id}")
    
    async def shutdown(self):
        """Shutdown graceful do manager"""
        logger.info("Shutting down RedisSSEManager...")
        
        # Cancela tasks
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Desconecta todos os clientes
        for client_id in list(self._clients.keys()):
            await self.disconnect_client(client_id)
        
        logger.info("RedisSSEManager shutdown complete")


# Instância global do manager SSE
redis_sse_manager = RedisSSEManager()


async def create_progress_stream(
    token: str = Query(None, description="Authentication token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    channels: str = Query("progress,downloads,system", description="Comma-separated channel list")
) -> EventSourceResponse:
    """
    Endpoint SSE para stream de progresso integrado com Redis
    
    Args:
        token: Token via query parameter
        authorization: Token via Authorization header
        channels: Lista de canais separados por vírgula
    """
    # Extração do token
    auth_token = None
    if authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
    elif token:
        auth_token = token
    
    # Parsing dos canais
    channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]
    if not channel_list:
        channel_list = ["progress", "downloads", "system"]
    
    # Valida canais
    valid_channels = set(redis_sse_manager.REDIS_CHANNELS.keys())
    channel_list = [ch for ch in channel_list if ch in valid_channels]
    
    if not channel_list:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channels. Available: {list(valid_channels)}"
        )
    
    # Inicializa Redis se necessário
    if not redis_sse_manager._redis_client:
        await redis_sse_manager.initialize_redis()
    
    # Gera ID único para o cliente
    client_id = str(uuid.uuid4())
    
    # Cria generator do cliente
    async def client_generator():
        async for event in redis_sse_manager.connect_client(
            client_id=client_id,
            token=auth_token,
            channels=channel_list
        ):
            yield event
    
    return EventSourceResponse(
        client_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx optimization
        }
    )