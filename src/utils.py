import os
import time
import asyncio
import httpx

from typing import Dict, Any
from src.config import settings
from src.dependencies import redis_client

async def clean_old_files(directory: str, extension: str, max_age: int):
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for filename in os.listdir(directory):
            if filename.endswith(extension):
                file_path = os.path.join(directory, filename)
                if os.stat(file_path).st_mtime < now - max_age:
                    try:
                        os.unlink(file_path)
                        print(f"Удален устаревший файл: {filename}")
                    except:
                        pass

async def send_notification(task_id: str, user_id: int, operation: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                settings.server_lessons_url,
                json={
                    "task_id": task_id,
                    "text": operation,
                    "user_id": user_id
                }
            )
        except httpx.HTTPError:
            pass

async def check_unacknowledged_tasks():
    try:
        while True:
            await asyncio.sleep(10)
            for key in redis_client.scan_iter("pending_ack:*"):
                ttl = redis_client.ttl(key)
                task_data = redis_client.hgetall(key)
                
                if not task_data:
                    continue
                
                if ttl <= 10:
                    task_id = key.decode().split(":")[1]
                    if redis_client.hget(key, "extended") != b"1":
                        await send_notification(
                            task_id=task_id,
                            user_id=task_data[b'user_id'].decode(),
                            operation=task_data[b'operation'].decode()
                        )
                        
                        redis_client.hset(key, "extended", "1")
                        redis_client.expire(key, 24 * 3600)
                    else:
                        redis_client.delete(key)
                        redis_client.delete(f"task_info:{task_id}")
                        
    except asyncio.CancelledError:
        print("Проверка неподтвержденных задач остановлена")