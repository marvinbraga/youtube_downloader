import os
from datetime import timedelta, datetime

import jwt as PyJWT
from dotenv import load_dotenv, find_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger

from app.services.configs import security

load_dotenv(find_dotenv())
# Altere para uma chave segura em produção
SECRET_KEY = os.environ.get("SECRET_KEY", "seu_secret_key_muito_secreto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

AUTHORIZED_CLIENTS = {
    "your_client_id": {
        "secret": "your_client_secret",
        "name": "Your Application"
    }
}


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Cria um novo token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = PyJWT.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    logger.debug("encoded_jwt: {}".format(encoded_jwt))
    if isinstance(encoded_jwt, bytes):
        return encoded_jwt.decode('utf-8')
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verifica se o token é válido"""
    try:
        token = credentials.credentials
        payload = PyJWT.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: str = payload.get("sub")

        if client_id not in AUTHORIZED_CLIENTS:
            raise HTTPException(
                status_code=401,
                detail="Cliente não autorizado"
            )

        return payload
    except PyJWT.ExpiredSignatureError:
        logger.error("Token expirado.")
        raise HTTPException(
            status_code=401,
            detail="Token expirado"
        )
    except PyJWT.PyJWTError:
        logger.error("Token invalido.")
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )


def verify_token_sync(token: str) -> dict:
    """
    Versão síncrona de verify_token para uso em contextos não-async
    """
    try:
        payload = PyJWT.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: str = payload.get("sub")

        if client_id not in AUTHORIZED_CLIENTS:
            raise HTTPException(
                status_code=401,
                detail="Cliente não autorizado"
            )

        return payload
    except PyJWT.ExpiredSignatureError:
        logger.error("Token expirado.")
        raise HTTPException(
            status_code=401,
            detail="Token expirado"
        )
    except PyJWT.PyJWTError:
        logger.error("Token invalido.")
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )
