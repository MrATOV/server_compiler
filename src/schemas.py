from pydantic import BaseModel

class CompileRequest(BaseModel):
    user_id: int
    code: str

class ExecuteRequest(BaseModel):
    user_id: int
    input_data: str = None

class Options(BaseModel):
    alpha: int
    calculate: int
    iterations: int
    koefficient: int
    saveResult: int
    threads: list[int]

class TestDataRequest(BaseModel):
    name: str
    type: str
    code: str
    files: list[str]
    options: Options
    parameters: list[dict]
