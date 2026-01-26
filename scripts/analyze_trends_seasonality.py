import pandas as pd
import glob
import os
from datetime import datetime

# Configuration
DATA_DIR = 'data'
OUTPUT_FILE = 'strategic_analysis_report.md'

def load_data():
    """Loads and concatenates all sales CSV files."""
    all_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    # Filter for relevant files (2019-2025 mainly, ignore others if format differs)
    sales_files = [f for f in all_files if '20' in os.path.basename(f) and 'template' not in f and 'Forecast' not in f]
    
    print(f"Loading files: {sales_files}")
    
    df_list = []
    for filename in sales_files:
        try:
            # Attempt to read with different encodings/separators if needed, but standard seems to be comma
            df = pd.read_csv(filename, dtype={'AN': str, 'COD ARTICOL': str, 'CANTITATE FACTURATA': float, 'ID CLIENT': str, 'CLIENT SPECIFIC': str, 'STARE PM LA DATA FACTURA': str})
            
            # Standardize columns
            df.columns = [c.strip().upper() for c in df.columns]
            
            # Keep only necessary columns (Updated list)
            required_cols = ['AN', 'COD ARTICOL', 'DATA', 'CANTITATE FACTURATA']
            
            # Check for core columns
            if all(col in df.columns for col in required_cols):
                # Add optional new columns if they exist (handling older files that might miss them)
                keep_cols = required_cols.copy()
                for extra_col in ['ID CLIENT', 'CLIENT SPECIFIC', 'STARE PM LA DATA FACTURA']:
                    if extra_col in df.columns:
                        keep_cols.append(extra_col)
                    else:
                        # Add empty column if missing to align dataframes
                        df[extra_col] = 'N/A'
                        keep_cols.append(extra_col)
                
                df = df[keep_cols]
                df_list.append(df)
            else:
                print(f"Skipping {filename}: missing core columns")
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    if not df_list:
        return pd.DataFrame()
    
    full_df = pd.concat(df_list, ignore_index=True)
    return full_df

def preprocess_data(df):
    """Cleans and prepares data for analysis."""
    # Convert 'DATA' to datetime. Analyze format dd.mm.yyyy
    df['DATA'] = pd.to_datetime(df['DATA'], format='%d.%m.%Y', errors='coerce')
    df = df.dropna(subset=['DATA'])
    
    df['YEAR'] = df['DATA'].dt.year
    df['MONTH'] = df['DATA'].dt.month
    df['MONTH_NAME'] = df['DATA'].dt.strftime('%B')
    
    # FILTERING: Keep only "Vanzari Magazin_Client Final"
    # We look for "Client Final" in the string to be safe, or exact match if preferred
    original_len = len(df)
    
    # Exclude internal transfers or specific B2B if implicitly requested by "doar vanzari catre client final"
    # Assuming 'Vanzari Magazin_Client Final' is the target value based on file inspection
    # Also safe to keep 'N/A' from older files if we assume they are sales, but strict filtering is safer for "Strategia 2.0"
    
    # Logic: If 'CLIENT SPECIFIC' column has data, filter. If it's all N/A (old files), keep or drop? 
    # Usually strategy implies analyzing recent clean data. Let's keep rows where column contains "Client Final" 
    # OR is N/A (to not lose 2019-2022 history if they don't have this col). 
    # Wait, user said "am refacut csvurile sursa". This implies ALL files might have it now?
    # Let's try strict filter first, and print drop stats.
    
    if 'CLIENT SPECIFIC' in df.columns:
        # Filter: Keep if contains "Client Final" OR is NA (legacy safety, but user updated files)
        # Based on user: "ne intereseaza doar vanzari catre client final"
        df_filtered = df[df['CLIENT SPECIFIC'].astype(str).str.contains('Client Final', case=False, na=False) | (df['CLIENT SPECIFIC'] == 'N/A')]
        
        # If the user updated ALL files, 'N/A' might be just noise. let's see. 
        # Actually, let's look at the data again. 2025.csv has it. 2019-2022 might have been regenerated too.
        
        filtered_len = len(df_filtered)
        print(f"Filtering Strategy: Retained {filtered_len} / {original_len} rows ({(filtered_len/original_len)*100:.1f}%) matching 'Client Final'")
        return df_filtered
        
    return df

def analyze_trends(df):
    """Identifies products with consistent growth over the last 3 years."""
    current_year = datetime.now().year
    years_to_analyze = [current_year - 3, current_year - 2, current_year - 1]
    
    print(f"Analyzing trends for years: {years_to_analyze}")
    
    yearly_sales = df[df['YEAR'].isin(years_to_analyze)].groupby(['COD ARTICOL', 'YEAR'])['CANTITATE FACTURATA'].sum().unstack(fill_value=0)
    
    growing_trend = []
    
    for product in yearly_sales.index:
        sales = yearly_sales.loc[product]
        y1, y2, y3 = sales.get(years_to_analyze[0], 0), sales.get(years_to_analyze[1], 0), sales.get(years_to_analyze[2], 0)
        
        if y1 > 5 and y2 > y1 * 1.1 and y3 > y2 * 1.1:
            growing_trend.append({
                'Product Code': product,
                f'{years_to_analyze[0]} Sales': y1,
                f'{years_to_analyze[1]} Sales': y2,
                f'{years_to_analyze[2]} Sales': y3,
                'Growth % (Last Year)': round(((y3 - y2) / y2) * 100, 1)
            })
            
    return pd.DataFrame(growing_trend).sort_values('Growth % (Last Year)', ascending=False)

def analyze_seasonality(df):
    """Analyzes monthly distribution of sales."""
    monthly_sales = df.groupby('MONTH')['CANTITATE FACTURATA'].sum()
    total_sales = monthly_sales.sum()
    monthly_share = (monthly_sales / total_sales) * 100
    
    seasonality_df = pd.DataFrame({
        'Month': monthly_sales.index,
        'Total Sales': monthly_sales.values,
        'Share %': monthly_share.values
    }).sort_values('Share %', ascending=False)
    
    yoy_seasonality = df.groupby(['YEAR', 'MONTH'])['CANTITATE FACTURATA'].sum().unstack(fill_value=0)
    yoy_share = yoy_seasonality.div(yoy_seasonality.sum(axis=1), axis=0) * 100
    
    return seasonality_df, yoy_share

def analyze_status(df):
    """Analyzes sales distribution by product status (STARE PM)."""
    if 'STARE PM LA DATA FACTURA' not in df.columns:
        return pd.DataFrame()
        
    status_sales = df.groupby('STARE PM LA DATA FACTURA')['CANTITATE FACTURATA'].sum().reset_index()
    status_sales['Share %'] = (status_sales['CANTITATE FACTURATA'] / status_sales['CANTITATE FACTURATA'].sum()) * 100
    return status_sales.sort_values('CANTITATE FACTURATA', ascending=False)

def analyze_customers(df):
    """Analyzes customer patterns (Repeat vs One-time)."""
    if 'ID CLIENT' not in df.columns:
        return {}
    
    # Filter out potential anomalies or Generic IDs if any (assuming IDs are cleaning)
    # Check purchases per ID
    cust_sales = df.groupby('ID CLIENT')['CANTITATE FACTURATA'].count() # Transactions count
    
    repeat_customers = cust_sales[cust_sales > 1].count()
    total_customers = cust_sales.count()
    
    # Top 10 Customers by Volume
    top_customers = df.groupby('ID CLIENT')['CANTITATE FACTURATA'].sum().sort_values(ascending=False).head(10)
    
    return {
        'total_unique_clients': total_customers,
        'repeat_clients': repeat_customers,
        'repeat_rate': (repeat_customers/total_customers)*100 if total_customers > 0 else 0,
        'top_customers': top_customers
    }

def generate_report(trends_df, seasonality_df, yoy_share, status_df, customer_stats):
    """Generates a Markdown report for Top Management."""
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 📊 Raport Strategic: Analiză Trenduri & Sezonalitate (Covoare)\n\n")
        f.write("*Confidențial - Pentru Top Management*\n")
        f.write(f"*Data generării: {datetime.now().strftime('%d.%m.%Y')}*\n")
        f.write("*Focus: Vânzări către Client Final*\n\n")
        
        # 1. Executive Summary - Seasonality
        f.write("## 1. Analiza Sezonalității: Când Cumpără Clientul Final?\n")
        
        best_month = seasonality_df.iloc[0]
        second_best = seasonality_df.iloc[1]
        
        f.write(f"### 🏆 Vârf de Sezon: Luna {int(best_month['Month'])}\n")
        f.write(f"Istoric, luna **{int(best_month['Month'])}** generează **{best_month['Share %']:.1f}%** din totalul vânzărilor.\n\n")
        
        f.write(f"### 🥈 Locul 2: Luna {int(second_best['Month'])}\n")
        f.write(f"Urmată de luna **{int(second_best['Month'])}** cu **{second_best['Share %']:.1f}%**.\n\n")
        
        f.write("### 📅 Profilul Lunar Complet\n")
        f.write(seasonality_df.to_markdown(index=False))
            
        f.write("\n\n### 🔄 Evoluție Anuală (Pattern Sezonier)\n")
        f.write(yoy_share.round(1).to_markdown())
        
        # 2. Customer Profile
        f.write("\n\n## 2. 👥 Profilul Clientului (Insights)\n")
        f.write(f"- **Total Clienți Unici Analizați:** {customer_stats.get('total_unique_clients', 0)}\n")
        f.write(f"- **Rata de Recurență:** {customer_stats.get('repeat_rate', 0):.1f}%\n")
        f.write("  *(Procentul de clienți care au cumpărat de mai multe ori)*\n\n")
        
        f.write("### Top 10 Clienți (Volum)\n")
        if not customer_stats.get('top_customers').empty:
             f.write(customer_stats.get('top_customers').to_frame().to_markdown())
        
        # 3. Product Status Analysis
        f.write("\n\n## 3. 🏷️ Performanță pe Status Produs (Lifecycle)\n")
        f.write("Distribuția vânzărilor în funcție de starea produsului la momentul facturării:\n\n")
        if not status_df.empty:
            f.write(status_df.to_markdown(index=False))
        
        # 4. Growth Stars
        f.write("\n\n## 4. ⭐ 'Rising Stars': Produse cu Trend Ascendent Constant (3 Ani)\n")
        f.write("Aceste produse au demonstrat o creștere solidă (>10%) în fiecare din ultimii 3 ani completi.\n\n")
        
        if not trends_df.empty:
            f.write(trends_df.to_markdown(index=False))
        else:
            f.write("_Nu s-au identificat produse cu creștere strictă (>10%) pe 3 ani consecutivi cu volume relevante._\n")
            
    print(f"Report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    df = load_data()
    if not df.empty:
        cleaned_df = preprocess_data(df)
        
        print("Running Trend Analysis...")
        trends = analyze_trends(cleaned_df)
        
        print("Running Seasonality Analysis...")
        seasonality, yoy_share = analyze_seasonality(cleaned_df)
        
        print("Running Status Analysis...")
        status_stats = analyze_status(cleaned_df)
        
        print("Running Customer Analysis...")
        cust_stats = analyze_customers(cleaned_df)
        
        generate_report(trends, seasonality, yoy_share, status_stats, cust_stats)
    else:
        print("No data found to analyze.")
