import asyncio
import subprocess
import os
import threading
import json
import glob
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from collections import defaultdict
from contextlib import contextmanager
from src.parallel_implemantation_analyzer import analyze_parallel_performance

processes = defaultdict(dict)
lock = threading.Lock()

@contextmanager
def change_directory(destination: str):
    original_dir = os.getcwd()
    try:
        os.chdir(destination)
        yield
    finally:
        os.chdir(original_dir)


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

def compile(src_filename: str, bin_filename: str):
    file_id = os.path.basename(src_filename).split('.')[0]
    command = [
        "g++", 
        "-fopenmp",
        src_filename,
        "-o", bin_filename,
        "-L/usr/lib",
        "-lavcodec", "-lavformat", "-lavutil", "-lswscale",
    ]
    try:
        return_code, stdout, stderr = run_subprocess(command, file_id)
        
        if return_code != 0:
            return {
                "message": f"Ошибка компиляции: {stderr}",
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code
            }
        return {
            "message": "Сборка прошла успешно",
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка компиляции: {str(e)}")

def execute(bin_filename: str, file_id: str, input_data: str = None):
    file_dir = os.path.dirname(bin_filename)
    filename = os.path.basename(bin_filename)
    command = [f"./{filename}"]
    
    try:
        with change_directory(file_dir):
            return_code, stdout, stderr = run_subprocess(command, file_id, 600, input_data)
        
        return {
            "message": "Выполнение завершено",
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка выполнения: {str(e)}")

def execute_test(bin_filename: str, file_id: str, input_data: str = None):
    file_dir = os.path.dirname(bin_filename)
    filename = os.path.basename(bin_filename)
    command = [f"./{filename}"]
    
    try:
        with change_directory(file_dir):
            return_code, stdout, stderr = run_subprocess(command, file_id, 60, input_data)
            result = []
            
            for dir_entry in os.scandir('.'):
                if dir_entry.is_dir():
                    file_path = os.path.join(dir_entry.path, 'result.json')
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                load_data = json.load(f)
                                data = analyze_parallel_performance(load_data)
                                data['dir'] = dir_entry.name
                                result.append(data)
                        except Exception as e:
                            raise HTTPException(500, f"Error read result file: {str(e)}")
        if len(result) == 0:
            return {
                "message": "Выполнение завершено",
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code
            }    

        return {
            "message": "Выполнение завершено",
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
            "result": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка выполнения: {str(e)}")


def cancel(file_id: str):
    with lock:
        if file_id in processes and processes[file_id].get('process'):
            process = processes[file_id]['process']
            try:
                process.terminate()
                time.sleep(1)
                if process.poll() is None:
                    process.kill()
                return {"message": "Процесс остановлен"}
            except Exception as e:
                return {"message": f"Ошибка отмены: {str(e)}"}
    
    return {"message": "Процесс не найден"}