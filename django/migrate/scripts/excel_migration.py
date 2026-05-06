import json
import os
import pandas as pd
import warnings
import re
import datetime

# Mute openpyxl data validation and extension warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

class ExcelMigrationProcessor:
    """
    Reads excel stock data based on a JSON configuration and 
    extracts the inventory movement history to a JSON array.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize with a path to a JSON configuration file.
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.export_list = []
        
        # Resolve paths relative to the config file
        self.base_dir = os.path.dirname(os.path.abspath(config_path))

    def _load_config(self) -> dict:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def process_all(self):
        """Process all data sets defined in the config."""
        for key, data_config in self.config.items():
            print(f"Processing data group: {key}")
            self.process_data_group(data_config)
            
    def process_data_group(self, data_config: dict):
        filename = data_config['filename']
        # The config uses relative paths (e.g. '../data/minmin.xlsx') 
        # which are meant to be relative to the notebook folder.
        # Since our config is in the data folder, we'll assume paths are relative to the notebook folder's parent
        # For safety, let's join it using the directory of this script or just resolve cleanly.
        
        # If config is in private/data, base_dir is private/data. 
        # '../data/minmin.xlsx' from private/data resolves to private/data/minmin.xlsx
        excel_path = os.path.normpath(os.path.join(self.base_dir, filename))
        
        if not os.path.exists(excel_path):
            print(f"Warning: Excel file not found at {excel_path}")
            return
            
        items = data_config['items']
        warehouse = data_config['warehouse']
        
        for item_key, item_info in items.items():
            sheet_name = item_info['sheet']
            sku = item_info['sku']
            
            try:
                df = pd.read_excel(excel_path, sheet_name=sheet_name)
            except Exception as e:
                print(f"Error reading sheet '{sheet_name}' from {excel_path}: {e}")
                continue

            self._clean_df(df, sku, warehouse, sheet_name)
                
    def _clean_df(self, df: pd.DataFrame, sku: str, warehouse: str, sheet_name: str):
        # Drop rows where Date is NaT (to remove empty excel rows)
        df.dropna(subset=['วันที่'], inplace=True)
        
        df['sku'] = sku
        df['วันที่'] = pd.to_datetime(df['วันที่'], format='mixed')
        df['warehouse'] = warehouse

        def parse_expire_and_lot(val):
            if pd.isna(val):
                return pd.NaT, f"LOT-{sku}-NONE"
                
            if isinstance(val, (pd.Timestamp, datetime.datetime)):
                ts = pd.Timestamp(val)
                date_str = ts.strftime('%d-%m-%Y')
                return ts, f"LOT-{sku}-{date_str}"
                
            val_str = str(val).strip()
            
            # Match date pattern like 11/3/2028 or 11-03-2028 at the start
            match = re.match(r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(.*)$', val_str)
            if match:
                date_raw = match.group(1)
                keyword = match.group(2).strip()
                try:
                    exp_date = pd.to_datetime(date_raw, format='mixed', dayfirst=True)
                    date_formatted = exp_date.strftime('%d-%m-%Y')
                except:
                    exp_date = pd.NaT
                    date_formatted = date_raw.replace('/', '-')
                    
                if keyword:
                    lot_str = f"LOT-{sku}-{date_formatted}-{keyword}"
                else:
                    lot_str = f"LOT-{sku}-{date_formatted}"
                return exp_date, lot_str
            else:
                try:
                    exp_date = pd.to_datetime(val_str, format='mixed', dayfirst=True)
                    date_formatted = exp_date.strftime('%d-%m-%Y')
                    return exp_date, f"LOT-{sku}-{date_formatted}"
                except:
                    # No date, just a keyword like "ตลับUSA"
                    return pd.NaT, f"LOT-{sku}-{val_str}"

        parsed = df['วันหมดอายุ'].apply(parse_expire_and_lot)
        df['วันหมดอายุ_parsed'] = parsed.apply(lambda x: x[0])
        df['lot'] = parsed.apply(lambda x: str(x[1]) if x[1] is not None else None)
        df['วันหมดอายุ'] = df['วันหมดอายุ_parsed']
        
        self._extract_records(df, sheet_name)
        return df
            
    def _extract_records(self, df: pd.DataFrame, sheet_name: str):
        # Filter out empty rows (where Date is NaT)
        clean_df = df.dropna(subset=['วันที่']).copy()
        
        for _, row in clean_df.iterrows():
            # 1. Determine Quantity and Direction
            qty_in = row.get('จำนวนรับ', 0)
            qty_out = row.get('จำนวนเบิก', 0)
            qty_return = row.get('จำนวนรับคืน', 0)
            
            qty = 0
            move_type = "inbound"
            
            if pd.notna(qty_in) and qty_in > 0:
                qty = qty_in
                move_type = "inbound"
            elif pd.notna(qty_out) and qty_out > 0:
                qty = qty_out
                move_type = "outbound"
            elif pd.notna(qty_return) and qty_return > 0:
                qty = qty_return
                move_type = "inbound" # Returns are usually inbound
                
            # 2. Build the Record
            record = {
                "warehouse": row['warehouse'],
                "sku": str(row['sku']),
                "date": row['วันที่'].strftime('%Y-%m-%d') if pd.notna(row['วันที่']) else None,
                "exp_date": row['วันหมดอายุ'].strftime('%Y-%m-%d') if pd.notna(row['วันหมดอายุ']) else None,
                "lot": str(row['lot']) if pd.notna(row.get('lot')) else None,
                "doc_no": str(row['เลขที่ใบเบิก']) if pd.notna(row['เลขที่ใบเบิก']) else None,
                "quantity": float(qty),
                "type": move_type,
                "partner": str(row['ชื่อ']) if pd.notna(row['ชื่อ']) else None,
                "note": f"[{row.get('เงื่อนไข', '')}] {row.get('จุดประสงค์', '')}".strip(),
                "metadata": {
                    "source_sheet": sheet_name,
                    "raw_condition": str(row.get('เงื่อนไข')) if pd.notna(row.get('เงื่อนไข')) else None
                }
            }
            self.export_list.append(record)

    def save_to_json(self, output_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.export_list, f, ensure_ascii=False, indent=2)
            
        print(f"✅ Success! Exported {len(self.export_list)} records to {output_path}")

if __name__ == "__main__":
    # Get paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to our new JSON configuration
    config_file = os.path.join(script_dir, '../data/migration_config.json')
    
    # Target output path
    output_file = os.path.join(script_dir, '../data/stock_migration.json')
    
    print(f"Starting Excel Migration...")
    print(f"Reading config from: {config_file}")
    
    processor = ExcelMigrationProcessor(config_path=config_file)
    processor.process_all()
    processor.save_to_json(output_path=output_file)
