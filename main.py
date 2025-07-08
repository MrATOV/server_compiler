from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import asyncio
import httpx
import uvicorn
from celery.signals import worker_process_init

from src.dependencies import get_celery_app, redis_client
from src.config import settings
from src.utils import *
from src.tasks import *
from src.schemas import *
from src.s3_client import S3Client
from src.test_generator import generate_data
from src.system_info import get_system_info

router = APIRouter()

app_celery = get_celery_app()

@worker_process_init.connect
def configure_flower(sender=None, conf=None, **kwargs):
    if sender and sender.hostname.startswith('celery@'):
        from flower.app import Flower
        flower = Flower(celery_app=sender.app)
        flower.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleaner_task = asyncio.create_task(clean_old_files("/tmp", ".cpp", 60))
    checker_task = asyncio.create_task(check_unacknowledged_tasks())
    dir_path = os.path.join(os.getcwd(), ".data")
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    yield
    cleaner_task.cancel()
    checker_task.cancel()
    try:
        await asyncio.gather(cleaner_task, checker_task)
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600
)

s3_client = S3Client()

@app.get('/system')
async def get_processor_info():
    return get_system_info()

@app.post('/functions')
async def get_function_declarations(request: CompileRequest):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.input_analyzer_url,
                json={"type": "funcs", "content": request.code}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": str(e)}

@app.post('/compile')
async def compile_code(request: CompileRequest):
    task = compile_task.delay(request.code, request.user_id)
    return {"task_id": task.id}

@app.post('/execute/{file_id}')
async def execute_code(file_id: str, request: ExecuteRequest):
    task = execute_task.delay(file_id, request.user_id, request.input_data)
    return {"task_id": task.id}

@app.post('/test/{file_id}')
async def execute_test(file_id: str, request: ExecuteRequest):
    task = execute_test_task.delay(file_id, request.user_id, request.input_data)
    return {"task_id": task.id}

@app.post('/cancel/{file_id}')
async def cancel_process(file_id: str):
    task = cancel_task.delay(file_id)
    return {"task_id": task.id}

@app.post('/generate')
async def test_generate(data: TestDataRequest):
    return generate_data(data)

@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str, ack: bool = True):
    task_result = app_celery.AsyncResult(task_id)
    
    if task_result.state == 'SUCCESS':
        if ack:
            redis_client.delete(f"pending_ack:{task_id}")
        needs_ack = redis_client.exists(f"pending_ack:{task_id}")
        return {
            "status": "SUCCESS",
            "result": task_result.result,
            "requires_acknowledgment": bool(needs_ack) if not ack else False
        }
    
    return {"status": task_result.state}

@router.post("/task/{task_id}/acknowledge")
async def acknowledge_result(task_id: str, user_id: str):
    redis_client.delete(f"pending_ack:{task_id}")
    return {"status": "acknowledged"}

@app.middleware("http")
async def timeout_middleware(request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=600)
    except asyncio.TimeoutError:
        return JSONResponse(
            {"message": "Превышено время выполнения запроса"},
            status_code=504
        )

if __name__ == '__main__':
    uvicorn.run("main:app", host='0.0.0.0', port=8000, reload=True)