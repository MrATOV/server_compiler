from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    broker_url: str = "redis://redis:6379/0"
    result_backend: str = "redis://redis:6379/1"
    flower_port: int = 5555
    server_lessons_url: str = "http://server_lessons:8000/notifications"
    input_analyzer_url: str = "http://input_analyzer:8003/analyze"

settings = Settings()