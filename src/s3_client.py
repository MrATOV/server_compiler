import boto3
from fastapi import HTTPException
from botocore.client import Config
import os

class S3Client:
    def __init__(self):
        self.endpoint = os.getenv("S3_ENDPOINT")
        self.bucket = os.getenv("S3_BUCKET_NAME")
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
            config=Config(signature_version='s3v4')
        )
        self._ensure_buckets_exist()

    def _ensure_buckets_exist(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except:
            self.client.create_bucket(Bucket=self.bucket)

    async def upload_proc_files(self, user_id: str, results: dict):
        try:
            for res in results:
                dirname = os.path.join(os.getcwd(), '.data', f"{user_id}", res["dir"])
                if not os.path.exists(dirname):
                    continue
                
                for filename in os.listdir(dirname):
                    if filename == 'result.json':
                        continue
                    filepath = os.path.join(dirname, filename)

                    s3_key = f"{user_id}/proc/{res["dir"]}/{filename}"
    
                    self.client.upload_file(
                        filepath,
                        self.bucket,
                        s3_key
                    )
                
        except Exception as e:
            raise HTTPException(500, f"Error uploading file: {e}")
        
    def get_data_file(self, user_id: int, file_name: str):
        s3_key = f'{user_id}/{file_name}'
        dir_path = os.path.join(os.getcwd(), ".data", f"{user_id}")
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_path = os.path.join(dir_path, file_name)
        try:
            self.client.download_file(self.bucket, s3_key, file_path)
        except Exception as e:
            raise HTTPException(404, f"File not found: {e}")
        
        