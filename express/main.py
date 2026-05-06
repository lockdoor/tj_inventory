import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from dbfread import DBF
from dotenv import load_dotenv

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
        with DBF(path, encoding='cp874', char_decode_errors='ignore', ignore_missing_memofile=True) as table:
            for record in table:
                if 'LOCCOD' in record and record.get('LOCCOD', '').strip() != '01':
                    continue
                
                sku = record.get('STKCOD', '').strip()
                # STLOC uses LOCBAL, STMAS uses BALQTY
                balance = record.get('LOCBAL') or record.get('BALQTY', 0)
                
                if sku:
                    balance_dict = {'sku': sku, 'balance': float(balance)}
                    balances.append(balance_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return balances

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(PORT))
