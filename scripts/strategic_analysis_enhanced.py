"""
Strategic Analysis Enhancement Script.

Generates comprehensive client-level analysis for Top Management:
1. Client Type Segmentation (CLIENT SPECIFIC breakdown)
2. Recurrence Analysis (One-time vs Repeat buyers)
3. Pareto Analysis (Top 20% clients contribution)
4. Average Order Value by segment
5. Client Lifetime Value estimation
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# Configuration
DATA_DIR = Path("data")
OUTPUT_FILE = "strategic_analysis_enhanced.md"

def load_all_data():
    """Load and concatenate all historical CSV files."""
    files = [
        DATA_DIR / "2019_2021.csv",
        DATA_DIR / "2022_2024.csv",
        DATA_DIR / "2025.csv"
    ]
    
    dfs = []
    for f in files:
        if f.exists():
            print(f"Loading {f.name}...")
            df = pd.read_csv(f, low_memory=False)
            dfs.append(df)
    
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total rows: {len(combined):,}")
    return combined


def analyze_client_types(df):
    """Analyze sales distribution by CLIENT SPECIFIC type."""
    print("\n=== CLIENT TYPE ANALYSIS ===")
    
    client_types = df.groupby("CLIENT SPECIFIC").agg({
        "CANTITATE FACTURATA": "sum",
        "VALOARE FACTURATA": "sum",
        "ID CLIENT": "nunique"
    }).reset_index()
    
    client_types.columns = ["Tip Client", "Cantitate", "Valoare RON", "Nr Clienti Unici"]
    client_types["% Cantitate"] = (client_types["Cantitate"] / client_types["Cantitate"].sum() * 100).round(2)
    client_types["% Valoare"] = (client_types["Valoare RON"] / client_types["Valoare RON"].sum() * 100).round(2)
    client_types["Valoare Medie/Client"] = (client_types["Valoare RON"] / client_types["Nr Clienti Unici"]).round(2)
    
    client_types = client_types.sort_values("% Valoare", ascending=False)
    
    print(client_types.to_string(index=False))
    return client_types


def analyze_recurrence(df):
    """Analyze customer recurrence patterns."""
    print("\n=== RECURRENCE ANALYSIS ===")
    
    # Count purchases per client
    client_purchases = df.groupby("ID CLIENT").agg({
        "DATA": "count",  # Number of transactions
        "CANTITATE FACTURATA": "sum",
        "VALOARE FACTURATA": "sum"
    }).reset_index()
    
    client_purchases.columns = ["ID_Client", "Nr_Tranzactii", "Cantitate_Total", "Valoare_Total"]
    
    # Categorize clients
    def categorize(n):
        if n == 1:
            return "One-Time"
        elif n <= 3:
            return "Occasional (2-3)"
        elif n <= 10:
            return "Regular (4-10)"
        else:
            return "VIP (11+)"
    
    client_purchases["Segment"] = client_purchases["Nr_Tranzactii"].apply(categorize)
    
    # Aggregate by segment
    recurrence = client_purchases.groupby("Segment").agg({
        "ID_Client": "count",
        "Nr_Tranzactii": "sum",
        "Cantitate_Total": "sum",
        "Valoare_Total": "sum"
    }).reset_index()
    
    recurrence.columns = ["Segment", "Nr Clienti", "Total Tranzactii", "Cantitate", "Valoare RON"]
    recurrence["% Clienti"] = (recurrence["Nr Clienti"] / recurrence["Nr Clienti"].sum() * 100).round(1)
    recurrence["% Valoare"] = (recurrence["Valoare RON"] / recurrence["Valoare RON"].sum() * 100).round(1)
    recurrence["Valoare Medie/Client"] = (recurrence["Valoare RON"] / recurrence["Nr Clienti"]).round(2)
    
    # Sort by importance
    order = {"VIP (11+)": 0, "Regular (4-10)": 1, "Occasional (2-3)": 2, "One-Time": 3}
    recurrence["_sort"] = recurrence["Segment"].map(order)
    recurrence = recurrence.sort_values("_sort").drop("_sort", axis=1)
    
    print(recurrence.to_string(index=False))
    return recurrence, client_purchases


def analyze_pareto(df, client_purchases):
    """Pareto analysis - Top 20% clients contribution."""
    print("\n=== PARETO ANALYSIS (80/20 Rule) ===")
    
    # Sort clients by value
    sorted_clients = client_purchases.sort_values("Valoare_Total", ascending=False)
    sorted_clients["Cumsum_Valoare"] = sorted_clients["Valoare_Total"].cumsum()
    total_value = sorted_clients["Valoare_Total"].sum()
    sorted_clients["Cumsum_%"] = (sorted_clients["Cumsum_Valoare"] / total_value * 100)
    
    total_clients = len(sorted_clients)
    top_20_count = int(total_clients * 0.20)
    top_10_count = int(total_clients * 0.10)
    top_5_count = int(total_clients * 0.05)
    top_1_count = int(total_clients * 0.01)
    
    top_20_value = sorted_clients.head(top_20_count)["Valoare_Total"].sum()
    top_10_value = sorted_clients.head(top_10_count)["Valoare_Total"].sum()
    top_5_value = sorted_clients.head(top_5_count)["Valoare_Total"].sum()
    top_1_value = sorted_clients.head(top_1_count)["Valoare_Total"].sum()
    
    pareto = {
        "Top 1%": {"clients": top_1_count, "value": top_1_value, "share": top_1_value/total_value*100},
        "Top 5%": {"clients": top_5_count, "value": top_5_value, "share": top_5_value/total_value*100},
        "Top 10%": {"clients": top_10_count, "value": top_10_value, "share": top_10_value/total_value*100},
        "Top 20%": {"clients": top_20_count, "value": top_20_value, "share": top_20_value/total_value*100},
    }
    
    for k, v in pareto.items():
        print(f"{k}: {v['clients']:,} clienti = {v['share']:.1f}% din valoare ({v['value']:,.0f} RON)")
    
    return pareto


def analyze_value_thresholds(client_purchases):
    """Analyze value thresholds for client segmentation."""
    print("\n=== VALUE THRESHOLDS ===")
    
    quantiles = client_purchases["Valoare_Total"].quantile([0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    
    print("Praguri de valoare (RON):")
    print(f"  25% clienti sub: {quantiles[0.25]:,.0f} RON")
    print(f"  50% (median): {quantiles[0.50]:,.0f} RON")
    print(f"  75% clienti sub: {quantiles[0.75]:,.0f} RON")
    print(f"  Top 10% peste: {quantiles[0.90]:,.0f} RON")
    print(f"  Top 5% peste: {quantiles[0.95]:,.0f} RON")
    print(f"  Top 1% peste: {quantiles[0.99]:,.0f} RON")
    
    return quantiles


def analyze_yearly_trends(df):
    """Analyze trends by year."""
    print("\n=== YEARLY TRENDS ===")
    
    df["YEAR"] = pd.to_datetime(df["DATA"], format="%d.%m.%Y", errors="coerce").dt.year
    
    yearly = df.groupby("YEAR").agg({
        "CANTITATE FACTURATA": "sum",
        "VALOARE FACTURATA": "sum",
        "ID CLIENT": "nunique"
    }).reset_index()
    
    yearly.columns = ["An", "Cantitate", "Valoare RON", "Clienti Unici"]
    yearly["Valoare/Client"] = (yearly["Valoare RON"] / yearly["Clienti Unici"]).round(2)
    
    print(yearly.to_string(index=False))
    return yearly


def generate_report(client_types, recurrence, pareto, thresholds, yearly):
    """Generate enhanced strategic report."""
    
    report = f"""# 📊 Raport Strategic EXTINS: Analiza Profundă Clienți

*Confidențial - Pentru Top Management*
*Data generării: {datetime.now().strftime('%d.%m.%Y %H:%M')}*

---

## 1. 🎯 Segmentare pe Tip Client

| Tip Client | Valoare RON | % Valoare | Nr Clienți | Valoare Medie/Client |
|:-----------|------------:|----------:|-----------:|---------------------:|
"""
    for _, row in client_types.iterrows():
        report += f"| {row['Tip Client']} | {row['Valoare RON']:,.0f} | {row['% Valoare']:.1f}% | {row['Nr Clienti Unici']:,} | {row['Valoare Medie/Client']:,.0f} |\n"

    report += f"""
> **Insight Principal:** Vânzările "Client Final" sunt focusul principal, dar verificați dacă alte canale sunt sub-optimizate.

---

## 2. 🔄 Analiza Recurenței Clienților

### Segmentare după Frecvență Achiziții

| Segment | Nr Clienți | % Clienți | Valoare RON | % Valoare | Val.Medie/Client |
|:--------|----------:|----------:|------------:|----------:|-----------------:|
"""
    for _, row in recurrence.iterrows():
        report += f"| {row['Segment']} | {row['Nr Clienti']:,} | {row['% Clienti']:.1f}% | {row['Valoare RON']:,.0f} | {row['% Valoare']:.1f}% | {row['Valoare Medie/Client']:,.0f} |\n"

    report += """
> **Decizie Strategică:**
> - **VIP (11+ achiziții):** Prioritate maximă pentru retenție. Oferte personalizate.
> - **One-Time:** Oportunitate de conversie. Campanii de re-engagement.

---

## 3. 📈 Analiza Pareto (Regula 80/20)

"""
    for k, v in pareto.items():
        report += f"- **{k}:** {v['clients']:,} clienți generează **{v['share']:.1f}%** din valoare ({v['value']:,.0f} RON)\n"

    report += """
> **Insight:** Concentrarea pe Top 10% clienți maximizează ROI-ul pe eforturi de vânzare.

---

## 4. 🎚️ Praguri de Valoare pentru Segmentare

| Prag | Valoare RON | Interpretare |
|:-----|------------:|:-------------|
"""
    report += f"| Median | {thresholds[0.50]:,.0f} | Jumătate din clienți sub această valoare |\n"
    report += f"| Top 25% | {thresholds[0.75]:,.0f} | 25% din clienți peste această valoare |\n"
    report += f'| Top 10% | {thresholds[0.90]:,.0f} | Pragul pentru clienți "importanți" |\n'
    report += f'| Top 5% | {thresholds[0.95]:,.0f} | Pragul pentru clienți "VIP" |\n'
    report += f"| Top 1% | {thresholds[0.99]:,.0f} | Clienți strategici (account management dedicat) |\n"

    report += """
> **Recomandare pentru CRM:**
> - Peste {:.0f} RON → Alertă automată "Client Valoros"
> - Peste {:.0f} RON → Atribuire Account Manager dedicat
""".format(thresholds[0.90], thresholds[0.99])

    report += """
---

## 5. 📅 Evoluție Anuală

| An | Cantitate | Valoare RON | Clienți Unici | Val/Client |
|---:|----------:|------------:|--------------:|-----------:|
"""
    for _, row in yearly.iterrows():
        if pd.notnull(row["An"]):
            report += f"| {int(row['An'])} | {row['Cantitate']:,.0f} | {row['Valoare RON']:,.0f} | {row['Clienti Unici']:,} | {row['Valoare/Client']:,.0f} |\n"

    report += """
---

## 6. 📋 Acțiuni Recomandate pentru Management

### Imediate (Q1)
1. **Identificare clienți Top 1%** - Atribuire account manager, întâlniri trimestriale
2. **Campanie re-engagement** pentru clienți One-Time din ultimele 12 luni
3. **Program fidelizare** pentru clienți Regular (4-10 achiziții)

### Pe Termen Mediu (6 luni)
1. **Scoring automat clienți** bazat pe pragurile de valoare
2. **Alertă CRM** când un client depășește pragul Top 10%
3. **Analiză churn** - identificare clienți VIP care nu au cumpărat recent

### Pe Termen Lung (12 luni)
1. **Predicție CLV** (Customer Lifetime Value) pentru prioritizare achiziții
2. **Segmentare dinamică** integrată în ERP
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nRaport salvat: {OUTPUT_FILE}")
    return report


def main():
    print("=" * 60)
    print("STRATEGIC ANALYSIS ENHANCEMENT")
    print("=" * 60)
    
    df = load_all_data()
    
    # Convert values to numeric
    df["CANTITATE FACTURATA"] = pd.to_numeric(df["CANTITATE FACTURATA"], errors="coerce").fillna(0)
    df["VALOARE FACTURATA"] = pd.to_numeric(df["VALOARE FACTURATA"], errors="coerce").fillna(0)
    
    client_types = analyze_client_types(df)
    recurrence, client_purchases = analyze_recurrence(df)
    pareto = analyze_pareto(df, client_purchases)
    thresholds = analyze_value_thresholds(client_purchases)
    yearly = analyze_yearly_trends(df)
    
    generate_report(client_types, recurrence, pareto, thresholds, yearly)


if __name__ == "__main__":
    main()
