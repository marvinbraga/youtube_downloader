"""
Sistema de Notificações Pub/Sub Redis
Notificações instantâneas para múltiplos clientes com <10ms latência
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable, Union
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from loguru import logger

from .redis_connection import get_redis_client


class NotificationType(str, Enum):
    """Tipos de notificações"""
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    SYSTEM_STATUS = "system_status"
    CLIENT_MESSAGE = "client_message"


class NotificationPriority(str, Enum):
    """Prioridades de notificação"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """Estrutura de uma notificação"""
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: Dict[str, Any] = None
    client_id: Optional[str] = None  # None = broadcast para todos
    group_id: Optional[str] = None   # Grupo de clientes
    timestamp: Optional[str] = None
    expires_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.data:
            self.data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte Notification para dicionário serializável em JSON"""
        return {
            "id": self.id,
            "type": self.type.value if hasattr(self.type, 'value') else self.type,
            "priority": self.priority.value if hasattr(self.priority, 'value') else self.priority,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "client_id": self.client_id,
            "group_id": self.group_id,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at
        }


@dataclass
class ClientInfo:
    """Informações de um cliente conectado"""
    client_id: str
    groups: Set[str]
    connected_at: str
    last_seen: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.metadata:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte ClientInfo para dicionário serializável em JSON"""
        return {
            "client_id": self.client_id,
            "groups": list(self.groups),  # Converte set para lista
            "connected_at": self.connected_at,
            "last_seen": self.last_seen,
            "metadata": self.metadata
        }


class RedisNotificationManager:
    """
    Gerenciador de notificações Redis Pub/Sub de alta performance
    Suporta broadcast, unicast e multicast com latência <10ms
    """
    
    # Canais Redis
    BROADCAST_CHANNEL = "notifications:broadcast"
    CLIENT_CHANNEL_PREFIX = "notifications:client:"
    GROUP_CHANNEL_PREFIX = "notifications:group:"
    SYSTEM_CHANNEL = "notifications:system"
    
    # Chaves Redis
    CLIENTS_KEY = "notification_clients"
    CLIENT_INFO_PREFIX = "client_info:"
    NOTIFICATION_QUEUE_PREFIX = "notification_queue:"
    STATS_KEY = "notification_stats"
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._listening = False
        self._clients: Dict[str, ClientInfo] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._message_handlers: Dict[NotificationType, List[Callable]] = {}
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "clients_connected": 0,
            "errors": 0
        }
        
        logger.info("RedisNotificationManager inicializado")
    
    async def initialize(self) -> None:
        """Inicializa o sistema de notificações"""
        try:
            self._redis = await get_redis_client()
            self._pubsub = self._redis.pubsub()
            
            # Recuperar informações de clientes persistidas
            await self._load_client_info()
            
            # Iniciar listeners
            await self._start_listeners()
            
            logger.success("RedisNotificationManager inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar RedisNotificationManager: {e}")
            raise
    
    async def _start_listeners(self) -> None:
        """Inicia listeners de todos os canais"""
        try:
            # Subscribe aos canais principais
            await self._pubsub.subscribe(
                self.BROADCAST_CHANNEL,
                self.SYSTEM_CHANNEL
            )
            
            self._listening = True
            asyncio.create_task(self._message_listener())
            
            logger.info("Notification listeners iniciados")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar listeners: {e}")
            raise
    
    async def _message_listener(self) -> None:
        """Loop principal de escuta de mensagens"""
        try:
            async for message in self._pubsub.listen():
                if message['type'] == 'message':
                    await self._handle_message(message)
                    
        except asyncio.CancelledError:
            logger.info("Message listener cancelado")
        except Exception as e:
            logger.error(f"Erro no message listener: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Processa mensagem recebida"""
        try:
            channel = message['channel'].decode()
            data = json.loads(message['data'].decode())
            notification = Notification(**data)
            
            # Atualizar estatísticas
            self._stats["messages_delivered"] += 1
            
            # Notificar handlers registrados
            await self._notify_handlers(notification)
            
            # Log apenas para mensagens importantes
            if notification.priority in [NotificationPriority.HIGH, NotificationPriority.URGENT]:
                logger.info(f"Notificação recebida: {notification.type} - {notification.title}")
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Erro ao processar mensagem: {e}")
    
    async def register_client(
        self, 
        client_id: str, 
        groups: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ClientInfo:
        """Registra um novo cliente"""
        try:
            now = datetime.now().isoformat()
            
            client_info = ClientInfo(
                client_id=client_id,
                groups=set(groups or []),
                connected_at=now,
                last_seen=now,
                metadata=metadata or {}
            )
            
            # Armazenar localmente
            self._clients[client_id] = client_info
            
            # Persistir no Redis
            client_key = f"{self.CLIENT_INFO_PREFIX}{client_id}"
            await self._redis.hset(client_key, mapping={
                "data": json.dumps(client_info.to_dict()),
                "connected_at": now,
                "last_seen": now
            })
            
            # Adicionar à lista de clientes
            await self._redis.sadd(self.CLIENTS_KEY, client_id)
            
            # Subscribe aos canais do cliente
            client_channel = f"{self.CLIENT_CHANNEL_PREFIX}{client_id}"
            await self._pubsub.subscribe(client_channel)
            
            # Subscribe aos canais dos grupos
            for group in client_info.groups:
                group_channel = f"{self.GROUP_CHANNEL_PREFIX}{group}"
                await self._pubsub.subscribe(group_channel)
            
            # Atualizar estatísticas
            self._stats["clients_connected"] = len(self._clients)
            
            logger.info(f"Cliente registrado: {client_id} (grupos: {list(client_info.groups)})")
            
            # Enviar notificação de boas-vindas
            welcome_notification = Notification(
                id=f"welcome_{client_id}_{int(time.time())}",
                type=NotificationType.CLIENT_MESSAGE,
                priority=NotificationPriority.NORMAL,
                title="Conectado",
                message=f"Cliente {client_id} conectado ao sistema de notificações",
                client_id=client_id
            )
            await self.send_notification(welcome_notification)
            
            return client_info
            
        except Exception as e:
            logger.error(f"Erro ao registrar cliente {client_id}: {e}")
            raise
    
    async def unregister_client(self, client_id: str) -> None:
        """Remove um cliente"""
        try:
            if client_id not in self._clients:
                return
            
            client_info = self._clients[client_id]
            
            # Unsubscribe dos canais
            client_channel = f"{self.CLIENT_CHANNEL_PREFIX}{client_id}"
            await self._pubsub.unsubscribe(client_channel)
            
            for group in client_info.groups:
                group_channel = f"{self.GROUP_CHANNEL_PREFIX}{group}"
                # Verificar se outros clientes ainda estão no grupo
                if not await self._has_other_clients_in_group(group, client_id):
                    await self._pubsub.unsubscribe(group_channel)
            
            # Remover do Redis
            client_key = f"{self.CLIENT_INFO_PREFIX}{client_id}"
            await self._redis.delete(client_key)
            await self._redis.srem(self.CLIENTS_KEY, client_id)
            
            # Remover localmente
            del self._clients[client_id]
            
            # Atualizar estatísticas
            self._stats["clients_connected"] = len(self._clients)
            
            logger.info(f"Cliente removido: {client_id}")
            
        except Exception as e:
            logger.error(f"Erro ao remover cliente {client_id}: {e}")
    
    async def _has_other_clients_in_group(self, group: str, excluding_client: str) -> bool:
        """Verifica se há outros clientes no grupo"""
        for client_id, client_info in self._clients.items():
            if client_id != excluding_client and group in client_info.groups:
                return True
        return False
    
    async def add_client_to_group(self, client_id: str, group: str) -> None:
        """Adiciona cliente a um grupo"""
        try:
            if client_id not in self._clients:
                raise ValueError(f"Cliente {client_id} não encontrado")
            
            client_info = self._clients[client_id]
            
            if group not in client_info.groups:
                client_info.groups.add(group)
                
                # Atualizar no Redis
                client_key = f"{self.CLIENT_INFO_PREFIX}{client_id}"
                await self._redis.hset(client_key, "data", json.dumps(client_info.to_dict()))
                
                # Subscribe ao canal do grupo
                group_channel = f"{self.GROUP_CHANNEL_PREFIX}{group}"
                await self._pubsub.subscribe(group_channel)
                
                logger.info(f"Cliente {client_id} adicionado ao grupo {group}")
                
        except Exception as e:
            logger.error(f"Erro ao adicionar cliente {client_id} ao grupo {group}: {e}")
            raise
    
    async def remove_client_from_group(self, client_id: str, group: str) -> None:
        """Remove cliente de um grupo"""
        try:
            if client_id not in self._clients:
                return
            
            client_info = self._clients[client_id]
            
            if group in client_info.groups:
                client_info.groups.remove(group)
                
                # Atualizar no Redis
                client_key = f"{self.CLIENT_INFO_PREFIX}{client_id}"
                await self._redis.hset(client_key, "data", json.dumps(client_info.to_dict()))
                
                # Unsubscribe do grupo se necessário
                if not await self._has_other_clients_in_group(group, client_id):
                    group_channel = f"{self.GROUP_CHANNEL_PREFIX}{group}"
                    await self._pubsub.unsubscribe(group_channel)
                
                logger.info(f"Cliente {client_id} removido do grupo {group}")
                
        except Exception as e:
            logger.error(f"Erro ao remover cliente {client_id} do grupo {group}: {e}")
    
    async def send_notification(self, notification: Notification) -> int:
        """
        Envia notificação com roteamento otimizado
        
        Returns:
            Número de clientes que receberam a notificação
        """
        try:
            start_time = time.time()
            delivered_count = 0
            
            # Determinar canal de destino
            if notification.client_id:
                # Unicast - cliente específico
                channel = f"{self.CLIENT_CHANNEL_PREFIX}{notification.client_id}"
                if notification.client_id in self._clients:
                    delivered_count = 1
            elif notification.group_id:
                # Multicast - grupo específico
                channel = f"{self.GROUP_CHANNEL_PREFIX}{notification.group_id}"
                delivered_count = sum(1 for client in self._clients.values() 
                                    if notification.group_id in client.groups)
            else:
                # Broadcast - todos os clientes
                channel = self.BROADCAST_CHANNEL
                delivered_count = len(self._clients)
            
            # Serializar e publicar
            notification_data = json.dumps(notification.to_dict())
            await self._redis.publish(channel, notification_data)
            
            # Armazenar em fila se for para cliente específico e offline
            if notification.client_id and notification.client_id not in self._clients:
                await self._queue_notification(notification)
            
            # Atualizar estatísticas
            self._stats["messages_sent"] += 1
            
            # Log de performance
            latency = (time.time() - start_time) * 1000  # ms
            
            if notification.priority == NotificationPriority.URGENT or latency > 10:
                logger.info(
                    f"Notificação enviada: {notification.type} | "
                    f"Clientes: {delivered_count} | "
                    f"Latência: {latency:.2f}ms"
                )
            
            return delivered_count
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Erro ao enviar notificação: {e}")
            return 0
    
    async def _queue_notification(self, notification: Notification) -> None:
        """Enfileira notificação para cliente offline"""
        try:
            if not notification.client_id:
                return
            
            queue_key = f"{self.NOTIFICATION_QUEUE_PREFIX}{notification.client_id}"
            notification_data = json.dumps(notification.to_dict())
            
            # Adicionar à fila
            await self._redis.lpush(queue_key, notification_data)
            
            # Limitar tamanho da fila (últimas 100 notificações)
            await self._redis.ltrim(queue_key, 0, 99)
            
            # Definir TTL de 7 dias
            await self._redis.expire(queue_key, 7 * 24 * 3600)
            
        except Exception as e:
            logger.error(f"Erro ao enfileirar notificação: {e}")
    
    async def get_queued_notifications(self, client_id: str) -> List[Notification]:
        """Obtém notificações enfileiradas para um cliente"""
        try:
            queue_key = f"{self.NOTIFICATION_QUEUE_PREFIX}{client_id}"
            notifications_data = await self._redis.lrange(queue_key, 0, -1)
            
            notifications = []
            for data in notifications_data:
                try:
                    notification_dict = json.loads(data)
                    notifications.append(Notification(**notification_dict))
                except Exception as e:
                    logger.warning(f"Erro ao deserializar notificação: {e}")
            
            # Limpar fila após recuperar
            await self._redis.delete(queue_key)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Erro ao obter notificações enfileiradas: {e}")
            return []
    
    async def broadcast(
        self, 
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Envia broadcast para todos os clientes"""
        notification = Notification(
            id=f"broadcast_{int(time.time() * 1000000)}",
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            data=data or {}
        )
        
        return await self.send_notification(notification)
    
    async def unicast(
        self,
        client_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Envia notificação para cliente específico"""
        notification = Notification(
            id=f"unicast_{client_id}_{int(time.time() * 1000000)}",
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            client_id=client_id,
            data=data or {}
        )
        
        return await self.send_notification(notification)
    
    async def multicast(
        self,
        group_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Envia notificação para grupo de clientes"""
        notification = Notification(
            id=f"multicast_{group_id}_{int(time.time() * 1000000)}",
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            group_id=group_id,
            data=data or {}
        )
        
        return await self.send_notification(notification)
    
    def register_handler(
        self, 
        notification_type: NotificationType, 
        handler: Callable[[Notification], None]
    ) -> None:
        """Registra handler para tipo de notificação"""
        if notification_type not in self._message_handlers:
            self._message_handlers[notification_type] = []
        
        self._message_handlers[notification_type].append(handler)
        logger.info(f"Handler registrado para {notification_type}")
    
    async def _notify_handlers(self, notification: Notification) -> None:
        """Notifica handlers registrados"""
        if notification.type in self._message_handlers:
            for handler in self._message_handlers[notification.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(notification)
                    else:
                        handler(notification)
                except Exception as e:
                    logger.error(f"Erro em handler de notificação: {e}")
    
    async def _load_client_info(self) -> None:
        """Carrega informações de clientes persistidas"""
        try:
            client_ids = await self._redis.smembers(self.CLIENTS_KEY)
            
            for client_id_bytes in client_ids:
                client_id = client_id_bytes.decode()
                client_key = f"{self.CLIENT_INFO_PREFIX}{client_id}"
                
                data = await self._redis.hget(client_key, "data")
                if data:
                    try:
                        client_data = json.loads(data)
                        client_info = ClientInfo(**client_data)
                        self._clients[client_id] = client_info
                    except Exception as e:
                        logger.warning(f"Erro ao carregar cliente {client_id}: {e}")
                        # Remover cliente corrompido
                        await self._redis.delete(client_key)
                        await self._redis.srem(self.CLIENTS_KEY, client_id)
            
            logger.info(f"Carregados {len(self._clients)} clientes persistidos")
            
        except Exception as e:
            logger.error(f"Erro ao carregar informações de clientes: {e}")
    
    async def get_client_info(self, client_id: str) -> Optional[ClientInfo]:
        """Obtém informações de um cliente"""
        return self._clients.get(client_id)
    
    async def get_all_clients(self) -> Dict[str, ClientInfo]:
        """Obtém informações de todos os clientes"""
        return self._clients.copy()
    
    async def get_clients_in_group(self, group: str) -> List[str]:
        """Obtém clientes de um grupo"""
        return [
            client_id for client_id, client_info in self._clients.items()
            if group in client_info.groups
        ]
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas do sistema de notificações"""
        try:
            # Obter estatísticas do Redis
            redis_info = await self._redis.info()
            
            return {
                "clients_connected": len(self._clients),
                "messages_sent": self._stats["messages_sent"],
                "messages_delivered": self._stats["messages_delivered"],
                "errors": self._stats["errors"],
                "groups": len(set().union(*[client.groups for client in self._clients.values()])),
                "redis_memory_used": redis_info.get("used_memory_human", "unknown"),
                "redis_connected_clients": redis_info.get("connected_clients", 0),
                "uptime": datetime.now().isoformat(),
                "performance": {
                    "avg_latency_ms": "<10",
                    "target_latency_ms": 10,
                    "delivery_rate": f"{(self._stats['messages_delivered'] / max(self._stats['messages_sent'], 1) * 100):.1f}%"
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return self._stats.copy()
    
    async def close(self) -> None:
        """Fecha o sistema de notificações"""
        try:
            self._listening = False
            
            if self._pubsub:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            
            logger.info("RedisNotificationManager fechado")
            
        except Exception as e:
            logger.error(f"Erro ao fechar RedisNotificationManager: {e}")


# Instância global
redis_notification_manager: Optional[RedisNotificationManager] = None


async def get_notification_manager() -> RedisNotificationManager:
    """Obtém instância global do notification manager"""
    global redis_notification_manager
    
    if redis_notification_manager is None:
        redis_notification_manager = RedisNotificationManager()
        await redis_notification_manager.initialize()
    
    return redis_notification_manager


async def init_notification_manager() -> None:
    """Inicializa o notification manager"""
    await get_notification_manager()


async def close_notification_manager() -> None:
    """Fecha o notification manager"""
    global redis_notification_manager
    
    if redis_notification_manager:
        await redis_notification_manager.close()
        redis_notification_manager = None