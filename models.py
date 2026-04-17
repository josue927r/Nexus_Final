from pydantic import BaseModel
from typing import List, Union, Optional

class BranchInput(BaseModel):
    name: str
    debit: Union[str, float]  # Allows "100+200" or raw float
    credit: Union[str, float]
    sales_declared: Union[str, float]
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "SUCURSAL CENTRAL",
                "debit": "100+50",
                "credit": 500,
                "sales_declared": 650
            }
        }

class BranchResult(BaseModel):
    name: str
    debit: float
    credit: float
    total_means: float
    sales_declared: float
    difference: float
    
class GlobalSummary(BaseModel):
    branches: List[BranchResult]
    global_debit: float
    global_credit: float
    global_means: float
    global_sales: float
    global_difference: float
    status_message: str
