
from typing import List, Union
from models import BranchInput, BranchResult, GlobalSummary

def parse_value(value: Union[str, float]) -> float:
    """
    Parses a value that can be a float or a string with sums like "100+200".
    """
    if isinstance(value, (int, float)):
        return float(value)
    
    if not value or not isinstance(value, str):
        return 0.0

    # Remove spaces, '$', and dots (thousand separators)
    # We assume usage of CLP where dots are thousand separators and we don't expect decimals
    cleaned = value.replace(" ", "").replace("$", "").replace(".", "")
    if "+" in cleaned:
        try:
            parts = [float(x) for x in cleaned.split("+") if x]
            return sum(parts)
        except ValueError:
            return 0.0 # Or raise an error if strict validation is preferred
    else:
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

def calculate_cuadratura(inputs: List[BranchInput]) -> GlobalSummary:
    results = []
    
    global_debit = 0.0
    global_credit = 0.0
    global_sales = 0.0
    
    for item in inputs:
        debit_val = parse_value(item.debit)
        credit_val = parse_value(item.credit)
        sales_val = parse_value(item.sales_declared)
        
        total_means = debit_val + credit_val
        difference = total_means - sales_val
        
        results.append(BranchResult(
            name=item.name,
            debit=debit_val,
            credit=credit_val,
            total_means=total_means,
            sales_declared=sales_val,
            difference=difference
        ))
        
        global_debit += debit_val
        global_credit += credit_val
        global_sales += sales_val
        
    global_means = global_debit + global_credit
    global_difference = global_means - global_sales
    
    if global_difference == 0:
        status_message = "LA CAJA ESTÁ CUADRADA PERFECTAMENTE ($0)"
    elif global_difference > 0:
        status_message = f"SOBRA DINERO: ${global_difference:,.0f}"
    else:
        status_message = f"FALTA DINERO: ${global_difference:,.0f}"

    return GlobalSummary(
        branches=results,
        global_debit=global_debit,
        global_credit=global_credit,
        global_means=global_means,
        global_sales=global_sales,
        global_difference=global_difference,
        status_message=status_message
    )
