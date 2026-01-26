import json
import os

CONFIG_PATH = "data/supplier_config.json"

def load_supplier_config():
    """Load supplier configuration from JSON file."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"default": {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1}}

def save_supplier_config(config):
    """Save supplier configuration to JSON file."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
