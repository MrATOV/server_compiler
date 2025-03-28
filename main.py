from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import src.compiler as compiler
import os
import uuid
import asyncio
import time
import httpx
import uvicorn

from src.schemas import *
from src.s3_client import S3Client
from src.test_generator import generate_data

def clean_startup_files():
    for filename in os.listdir('/tmp'):
        if filename.endswith(('.cpp', '.out')):
            file_path = os.path.join('/tmp', filename)
            try:
                os.unlink(file_path)
                print(f"Удален старый файл: {filename}")
            except Exception as e:
                print(f"Ошибка при удалении файла {filename}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    clean_startup_files()
    cleaner_task = asyncio.create_task(clean_old_files())
    dir_path = os.path.join(os.getcwd(), ".data")
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    yield
    cleaner_task.cancel()
    try:
        await cleaner_task
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

async def clean_old_files():
    try:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            for filename in os.listdir('/tmp'):
                if filename.endswith('.cpp'):
                    file_path = os.path.join('/tmp', filename)
                    if os.stat(file_path).st_mtime < now - 600:
                        try:
                            os.unlink(file_path)
                            print(f"Удален устаревший файл: {filename}")
                        except:
                            pass
            for filename in os.listdir('./.data/1'):
                file_path = os.path.join(os.getcwd(), '.data', '1', filename)
                if os.stat(file_path).st_mtime < now - 600:
                    try:
                        os.unlink(file_path)
                        print(f"Удален устаревший файл: {filename}")
                    except:
                        pass
    except asyncio.CancelledError:
        print("Фоновая очистка файлов остановлена")

@app.post('/functions')
async def get_function_declarations(request: CompileRequest):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://input_analyzer:8003/analyze",
                json={"type": "funcs", "content": request.code}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": str(e)}

@app.post('/compile')
async def compile_code(request: CompileRequest):
    file_id = str(uuid.uuid4())
    src_filename = f"/tmp/{file_id}.cpp"
    bin_filename = f"./.data/{request.user_id}/{file_id}.out"
    
    with open(src_filename, 'w') as f:
        f.write(request.code)
    
    try:
        result = await compiler.compile(src_filename, bin_filename)

    finally:
        if os.path.exists(src_filename):
            os.unlink(src_filename)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://input_analyzer:8003/analyze",
                json={"type": "vars", "content": request.code}
            )
            response.raise_for_status()
            result["stdout"] = response.json()
        except httpx.HTTPError as e:
            raise HTTPException(500, e)
    if result["return_code"] == 1:
        return result
    strings = result["stdout"].pop("strings")
    if strings:
        for string in strings:
            s3_client.get_data_file(request.user_id, string) 
    result["file_id"] = file_id
    return result

@app.post('/execute/{file_id}')
async def execute_code(file_id: str, request: ExecuteRequest):
    bin_filename = f"./.data/{request.user_id}/{file_id}.out"
    if not os.path.exists(bin_filename):
        raise HTTPException(404, "Скомпилированный файл не найден")
    
    try:
        result = await compiler.execute(bin_filename, file_id, request.input_data)
    finally:
        if os.path.exists(bin_filename):
            os.utime(bin_filename)
    return result

@app.post('/test/{file_id}')
async def execute_test(file_id: str, request: ExecuteRequest):
    bin_filename = f"./.data/{request.user_id}/{file_id}.out"
    if not os.path.exists(bin_filename):
        raise HTTPException(404, "Скомпилированный файл не найден")
    
    try:
        result = await compiler.execute_test(bin_filename, file_id, request.input_data)
    finally:
        if os.path.exists(bin_filename):
            os.utime(bin_filename)
    if "result" in result:
        await s3_client.upload_proc_files(request.user_id, result["result"])            
    return result

@app.post('/cancel/{file_id}')
async def cancel_process(file_id: str):
    result = await compiler.cancel(file_id)
    for ext in ('.cpp'):
        filename = f"/tmp/{file_id}{ext}"
        if os.path.exists(filename):
            try:
                os.unlink(filename)
            except:
                pass
    return result

@app.post('/generate')
async def test_generate(data: TestDataRequest):
    return generate_data(data)

@app.middleware("http")
async def timeout_middleware(request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=60)
    except asyncio.TimeoutError:
        return JSONResponse(
            {"message": "Превышено время выполнения запроса"},
            status_code=504
        )

if __name__ == '__main__':
    uvicorn.run("main:app", host='0.0.0.0', port=8000, reload=True)