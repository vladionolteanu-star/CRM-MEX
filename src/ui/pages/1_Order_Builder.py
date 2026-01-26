import streamlit as st
import sys
import os

# Add project root to path so we can import src modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import necessary modules
try:
    from src.ui.order_builder import render_order_builder_v2
    from src.core.cubaj_loader import get_cubaj_map
except ImportError as e:
    st.error(f"Eroare la import: {e}. Vă rugăm să rulați aplicația din folderul rădăcină al proiectului.")
    st.stop()

# Page Config
st.set_page_config(
    page_title="Order Builder | Indomex",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for "Blank Canvas" feel requested by user
st.markdown("""
<style>
    /* Remove default top padding */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
    }
    /* Hide header decoration */
    header {visibility: hidden;}
    /* Hide footer */
    footer {visibility: hidden;}
    
    /* Make metrics stand out */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Main Application Logic
def main():
    # Simple Config (in app.py this comes from json)
    config = {
        "default": {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1}
    }
    
    # Load Cubaj Data
    try:
        cubaj_data = get_cubaj_map()
    except:
        cubaj_data = {}

    # Render Builder
    render_order_builder_v2(config, cubaj_data)

if __name__ == "__main__":
    main()
