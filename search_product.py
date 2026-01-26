
import pandas as pd
import glob
import os

target_product = "OUTPAPILLONPI060"
data_dir = "data"
files = [
    "2019_2021.csv",
    "2022_2024.csv", 
    "2025.csv",
    "Tcioara Forecast_.csv"
]

print(f"Searching for {target_product}...")

for filename in files:
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        print(f"Skipping {filename} (not found)")
        continue
        
    print(f"Scanning {filename}...")
    try:
        # Read in chunks
        chunk_size = 50000
        found = False
        # Try diff encodings
        encodings = ['utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                for chunk in pd.read_csv(filepath, chunksize=chunk_size, low_memory=False, encoding=encoding):
                    # Convert all to string and search
                    mask = chunk.apply(lambda x: x.astype(str).str.contains(target_product, case=False).any(), axis=1)
                    if mask.any():
                        print(f"FOUND in {filename}:")
                        print(chunk[mask].to_string())
                        found = True
                break # encoding worked
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error with encoding {encoding}: {e}")
                
    except Exception as e:
        print(f"Error processing {filename}: {e}")
    print("-" * 50)
