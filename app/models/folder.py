# app/models/folder.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    """Modelo para criação de pasta"""
    name: str = Field(..., min_length=1, max_length=255, description="Nome da pasta")
    parent_id: Optional[str] = Field(None, description="ID da pasta pai (None para raiz)")
    description: Optional[str] = Field(None, description="Descrição da pasta")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Cor em hex (ex: #FF5733)")
    icon: Optional[str] = Field(None, max_length=50, description="Ícone da pasta")


class FolderUpdate(BaseModel):
    """Modelo para atualização de pasta"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nome da pasta")
    parent_id: Optional[str] = Field(None, description="ID da pasta pai")
    description: Optional[str] = Field(None, description="Descrição da pasta")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Cor em hex")
    icon: Optional[str] = Field(None, max_length=50, description="Ícone da pasta")


class FolderResponse(BaseModel):
    """Modelo de resposta para pasta"""
    id: str
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class FolderTreeResponse(FolderResponse):
    """Modelo de resposta para pasta com árvore de filhos"""
    children: List["FolderTreeResponse"] = []
    item_count: int = 0


class FolderWithItemsResponse(FolderResponse):
    """Modelo de resposta para pasta com itens"""
    audios: List[dict] = []
    videos: List[dict] = []
    item_count: int = 0


class FolderPathResponse(BaseModel):
    """Modelo de resposta para caminho da pasta"""
    path: List[FolderResponse]
    full_path: str  # ex: "Raiz / Subpasta / Subsubpasta"


class MoveItemRequest(BaseModel):
    """Modelo para mover item para pasta"""
    folder_id: Optional[str] = Field(None, description="ID da pasta destino (None para raiz)")


class BulkMoveRequest(BaseModel):
    """Modelo para mover múltiplos itens"""
    audio_ids: List[str] = Field(default_factory=list, description="IDs dos áudios")
    video_ids: List[str] = Field(default_factory=list, description="IDs dos vídeos")
    folder_id: Optional[str] = Field(None, description="ID da pasta destino (None para raiz)")


# Necessário para auto-referência em FolderTreeResponse
FolderTreeResponse.model_rebuild()
