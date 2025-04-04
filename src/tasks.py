from celery import shared_task
from src.dependencies import redis_client, s3_client
from src.config import settings
import httpx
import os
import uuid
import src.compiler as compiler
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

def _store_task_info(task_id: str, user_id: str, operation: str):
    redis_client.hset(
        f"task_info:{task_id}",
        mapping={
            "user_id": user_id,
            "operation": operation
        }
    )
    redis_client.expire(f"task_info:{task_id}", 3600)

@shared_task(bind=True)
def compile_task(self, code: str, user_id: str):
    _store_task_info(self.request.id, user_id, "compile")
    file_id = str(uuid.uuid4())
    src_filename = f"/tmp/{file_id}.cpp"
    bin_filename = f"./.data/{user_id}/{file_id}.out"

    with open(src_filename, 'w') as f:
        f.write(code)

    try:
        result = compiler.compile(src_filename, bin_filename)
        
        with httpx.Client() as client:
            try:
                response = client.post(
                    settings.input_analyzer_url,
                    json={"type": "vars", "content": code}
                )
                response.raise_for_status()
                result["stdout"] = response.json()
            except httpx.HTTPError as e:
                raise self.retry(exp=e, countdown=5)
        if result["return_code"] == 1:
            return result
        
        strings = result["stdout"].pop("strings")
        print(strings)
        if strings:
            for string in strings:
                s3_client.get_data_file(user_id, string["type"], string["filename"])

        result["file_id"] = file_id

        redis_client.hset(
            f"pending_ack:{self.request.id}",
            mapping={
                'user_id': user_id,
                'operation': "compile",
                'extended': "0"
            }
        )
        redis_client.expire(f"pending_ack:{self.request.id}", 20)
        return result
    except Exception as e:
        redis_client.delete(f"pending_ack:{self.request.id}")
    finally:
        if os.path.exists(src_filename):
            os.unlink(src_filename)
    
@shared_task(bind=True)
def execute_task(self, file_id: str, user_id: str, input_data: str = None):
    _store_task_info(self.request.id, user_id, "execute")
    bin_filename = f"./.data/{user_id}/{file_id}.out"
    if not os.path.exists(bin_filename):
        raise self.retry(countdown=5)
    
    try:
        result = compiler.execute(bin_filename, file_id, input_data)
        
        redis_client.hset(
            f"pending_ack:{self.request.id}",
            mapping={
                'user_id': user_id,
                'operation': "execute",
                'extended': "0"
            }
        )
        redis_client.expire(f"pending_ack:{self.request.id}", 20)

        return result
    except Exception as e:
        redis_client.delete(f"pending_ack:{self.request.id}")
    finally:
        if os.path.exists(bin_filename):
            os.utime(bin_filename)

@shared_task(bind=True)
def execute_test_task(self, file_id: str, user_id: str, input_data: str = None):
    _store_task_info(self.request.id, user_id, "test_execution")
    bin_filename = f"./.data/{user_id}/{file_id}.out"
    if not os.path.exists(bin_filename):
        raise self.retry(countdown=5)
    
    try:
        result = compiler.execute_test(bin_filename, file_id, input_data)
        if "result" in result:
            s3_client.upload_proc_files(user_id, result["result"])

        redis_client.hset(
            f"pending_ack:{self.request.id}",
            mapping={
                'user_id': user_id,
                'operation': "test_execution",
                'extended': "0"
            }
        )
        redis_client.expire(f"pending_ack:{self.request.id}", 20)

        return result
    except Exception as e:
        redis_client.delete(f"pending_ack:{self.request.id}")
    finally:
        if os.path.exists(bin_filename):
            os.utime(bin_filename)

@shared_task(bind=True)
def cancel_task(self, file_id: str):
    result = compiler.cancel(file_id)
    for ext in ('.cpp',):
        filename = f"/tmp/{file_id}{ext}"
        if os.path.exists(filename):
            try:
                os.unlink(filename)
            except:
                pass
    return result