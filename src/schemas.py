from pydantic import BaseModel

class ContentDTO(BaseModel):
    content: str

class FileDTO(ContentDTO):
    filename: str
