import asyncio
import subprocess
import os
import threading
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from collections import defaultdict

executor = ThreadPoolExecutor()
processes = defaultdict(dict)
lock = threading.Lock()

def run_subprocess(command: list, file_id: str, timeout: int = 30, input_data: str = None):
    with lock:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True
        )
        processes[file_id]['process'] = process
    
    try:
        stdout, stderr = process.communicate(input=input_data, timeout=timeout)
        return_code = process.returncode
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return_code = -1
    finally:
        with lock:
            if file_id in processes:
                del processes[file_id]
    
    return return_code, stdout, stderr

async def compile(src_filename: str, bin_filename: str):
    file_id = os.path.basename(src_filename).split('.')[0]
    command = [
        "clang++-18", 
        src_filename,
        "-o", bin_filename,
        "-fopenmp",
        '-lomp'
    ]
    
    loop = asyncio.get_running_loop()
    try:
        return_code, stdout, stderr = await loop.run_in_executor(
            executor,
            run_subprocess,
            command,
            file_id
        )
        
        if return_code != 0:
            return {
                "message": f"Ошибка компиляции: {stderr}",
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code
            }

        input_analyzer_command = [
            "./InputAnalyzer",
            "-p", "./",
            "--mode=vars",
            src_filename,
        ]
        analyzer_rc, analyzer_stdout, analyzer_stderr = await loop.run_in_executor(
            executor,
            run_subprocess,
            input_analyzer_command,
            file_id
        )

        return {
            "message": "Сборка прошла успешно",
            "stdout": json.loads(analyzer_stdout),
            "stderr": stderr,
            "return_code": return_code,
            "bin_filename": bin_filename
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка компиляции: {str(e)}")

async def execute(bin_filename: str, file_id: str, input_data: str = None):
    command = [bin_filename]
    loop = asyncio.get_running_loop()
    
    try:
        return_code, stdout, stderr = await loop.run_in_executor(
            executor,
            run_subprocess,
            command,
            file_id,
            60,
            input_data
        )
        
        return {
            "message": "Выполнение завершено",
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка выполнения: {str(e)}")

async def function_declarations(src_filename):
    file_id = os.path.basename(src_filename).split('.')[0]
    command = [
        "./InputAnalyzer",
        "-p", "./",
        "--mode=funcs",
        src_filename,
    ]

    loop = asyncio.get_running_loop()
    try:
        return_code, stdout, stderr = await loop.run_in_executor(
                executor,
                run_subprocess,
                command,
                file_id
            )
        if return_code != 0:
            return {
                "message": f"Ошибка анализа: {stderr}",
                "stdout": None,
                "stderr": stderr,
                "return_code": return_code
            }
        
        return {
            "message": "Сборка прошла успешно",
            "stdout": json.loads(stdout),
            "stderr": stderr,
            "return_code": return_code,
        }
    except Exception as e:
        raise HTTPException(500, f"Ошибка компиляции: {str(e)}")

async def cancel(file_id: str):
    with lock:
        if file_id in processes and processes[file_id].get('process'):
            process = processes[file_id]['process']
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.poll() is None:
                    process.kill()
                return {"message": "Процесс остановлен"}
            except Exception as e:
                return {"message": f"Ошибка отмены: {str(e)}"}
    
    return {"message": "Процесс не найден"}