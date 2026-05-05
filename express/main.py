import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from dbfread import DBF
from dotenv import load_dotenv
import pandas as pd

pd.set_option('display.float_format', '{:.2f}'.format)

ENV_PATH = Path(__file__).resolve().parent.parent / "secrets" / "express.env"

# Load configuration from .env
load_dotenv(ENV_PATH)

app = FastAPI(title="Express ERP Bridge")

EXPRESS_PATH = os.getenv("EXPRESS_PATH")
PORT = os.getenv("PORT", 8001)
HOST = os.getenv("HOST", "0.0.0.0")

try:
    COMPANIES = json.loads(os.getenv("COMPANIES", "{}"))
except Exception:
    COMPANIES = {}

@app.get("/")
def read_root():
    return {"status": "online", "companies": list(COMPANIES.keys())}

@app.get("/stock/{company_id}")
def get_stock(company_id: str):
    """
    Reads STLOC.DBF for the given company and returns SKU -> Balance for Stock 1 (01).
    """
    if company_id not in COMPANIES:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not configured")

    data_path = os.path.join(EXPRESS_PATH, COMPANIES[company_id])
    path = os.path.join(data_path, 'STLOC.DBF')
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Stock data file not found")

    balances = []
    try:
        with DBF(f"{data_path}/STMAS.DBF", load=True, encoding='cp874', char_decode_errors='ignore', ignore_missing_memofile=True) as table:
            stmas_df = pd.DataFrame(table)
        with DBF(f"{data_path}/STLOC.DBF", load=True, encoding='cp874', char_decode_errors='ignore', ignore_missing_memofile=True) as table:
            stloc_df = pd.DataFrame(table)
            
        merge_df: pd.DataFrame = pd.merge(stmas_df, stloc_df, how='left', on='STKCOD')
        selected_columns: list[str] = ['STKCOD', 'STKDES', 'STKDES2', 'LOCBAL', 'QUCOD', 'LOCCOD']
        selected_df: pd.DataFrame = merge_df[selected_columns]
        selected_df: pd.DataFrame = selected_df[selected_df['LOCCOD'] == '01']
        
        # Clean up any NaN values before converting to dict
        selected_df = selected_df.fillna(0)

        # Change column name
        selected_df = selected_df.rename(columns={
            'STKCOD': 'sku', 
            'LOCBAL': 'balance',
            'STKDES': 'name',
            'STKDES2': 'name2',
            'QUCOD': 'unit'})

        # remove LOCCOD column
        selected_df.drop(columns=['LOCCOD'], inplace=True)

        # final json look like this:
        # {
        #   "sku": "20-000001",
        #   "name": "Test Product 1",
        #   "name2": "Test Product 1 English",
        #   "balance": 100,
        #   "unit": "EA"
        # }
        
        # Convert to list of dicts; FastAPI will automatically serialize this to JSON
        return selected_df.to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return balances

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(PORT))
