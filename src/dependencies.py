from redis import Redis
from celery import Celery
from src.config import settings
from src.s3_client import S3Client

redis_client = Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db)
s3_client = S3Client()

def get_celery_app():
    app = Celery(
        'main',
        brocker=settings.broker_url,
        backend=settings.result_backend,
        include=['src.tasks']
    )
    app.conf.update(
        flower={
            'port': settings.flower_port,
            'address': '0.0.0.0'
        }
    )
    return app