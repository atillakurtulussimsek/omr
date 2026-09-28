"""Tek yönetici şifresiyle koruma. ADMIN_PASSWORD verilmişse /api altındaki her istek (sağlık ve
giriş uçları hariç) imzalı oturum çerezi ister; verilmemişse uygulama açık çalışır (yalnız yerel kullanım)."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Dict, Tuple

from fastapi import APIRouter, Body, HTTPException, Request, Response

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
COOKIE = "omrSession"
COOKIE_MAX_AGE = 30 * 24 * 3600
OPEN_PATHS = {"/api/health", "/api/auth", "/api/auth/login"}
MAX_FAILURES = 8            # bu kadar yanlış denemeden sonra IP kilitlenir
LOCK_SECONDS = 300

router = APIRouter(prefix="/api/auth")
failures: Dict[str, Tuple[int, float]] = {}   # ip -> (deneme, son deneme zamanı)
failLock = threading.Lock()


def isRequired() -> bool:
    return bool(ADMIN_PASSWORD)


def sessionToken() -> str:
    """Şifreden türetilen sabit imza; şifre değişince eski oturumlar düşer."""
    key = hashlib.sha256(("omr-session:" + ADMIN_PASSWORD).encode()).digest()
    return hmac.new(key, b"session-v1", hashlib.sha256).hexdigest()


def isAuthenticated(request: Request) -> bool:
    if not isRequired():
        return True
    token = request.cookies.get(COOKIE, "")
    return bool(token) and hmac.compare_digest(token, sessionToken())


def clientIp(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "?")


def checkLock(ip: str) -> None:
    with failLock:
        count, last = failures.get(ip, (0, 0.0))
        if count >= MAX_FAILURES and time.time() - last < LOCK_SECONDS:
            raise HTTPException(429, "Çok fazla yanlış deneme; birkaç dakika sonra tekrar deneyin")


def noteFailure(ip: str) -> None:
    with failLock:
        count, last = failures.get(ip, (0, 0.0))
        if time.time() - last > LOCK_SECONDS:
            count = 0
        failures[ip] = (count + 1, time.time())


async def requireSession(request: Request, callNext):
    path = request.url.path
    if path.startswith("/api") and path not in OPEN_PATHS and not isAuthenticated(request):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Giriş gerekli"}, status_code=401)
    return await callNext(request)


@router.get("")
def authStatus(request: Request) -> dict:
    return {"required": isRequired(), "authenticated": isAuthenticated(request)}


@router.post("/login")
def login(request: Request, response: Response, password: str = Body(..., embed=True)) -> dict:
    if not isRequired():
        return {"authenticated": True}
    ip = clientIp(request)
    checkLock(ip)
    if not hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode()):
        noteFailure(ip)
        time.sleep(0.5 + secrets.randbelow(500) / 1000)   # kaba kuvveti yavaşlat
        raise HTTPException(401, "Şifre yanlış")
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(COOKIE, sessionToken(), max_age=COOKIE_MAX_AGE, httponly=True,
                        samesite="lax", secure=secure, path="/api")
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/api")
    return {"authenticated": False}
