# Acquisition Forecast System - System Design Document

## 1. Executive Summary
This project aims to build a **Stock & Order Monitoring System** for Mobexpert's carpet division. The goal is to assist the Product Manager (PM) in making data-driven acquisition decisions by forecasting demand and generating automated alerts when stock levels drop below a critical threshold (Reorder Point).

## 2. Core Objectives
- **Centralize Data**: Combine product details, current stock across all locations (Warehouses, Stores, Outlets), supplier parameters, and historical sales data.
- **Automated Forecasting**: Calculate dynamic Reorder Points based on sales velocity and lead times.
- **Alerting System**: Notify the PM when `(Available Stock + In Transit) <= Reorder Point`.

## 3. Data Dictionary

### 3.1 Product Identification & Cost
- **NR ART**: Unique Article Number.
- **Supplier Info**: Cost Acquisition (Last NIR), Base Price (RON/Valuta).
- **Categorization**: ABC/XYZ Classification, Lifecycle Status (Active, Phase-out, New).

### 3.2 Stock Data
- **Current Stock**:
  - Central Warehouse (Depozit)
  - Stores (Magazine) - Breakdown by location (Baneasa, Pipera, Iasi, etc.)
  - Outlets & Defective (Accidentate)
- **Stock Availability**:
  - `Stoc Disponibil` (Immediately saleable) vs. `Stoc Total` (Includes reserved/damaged).
- **In-Transit**:
  - Quantity ordered but not received.
  - ETA (Estimated Time of Arrival).

### 3.3 Sales History & Performance
- **Timeframes**:
  - Last 4 Months (Trend analysis).
  - Last 360 Days (Annual performance).
  - Historical Yearly (2018 - 2025).
- **Metrics**:
  - Quantitative Sales (Qty).
  - Value Sales (RON).
  - Margins (Value & %).
  - COGS (Cost of Goods Sold).

### 3.4 Supplier Parameters (Crucial for Logic)
- **Lead Time**: Days from order to reception.
- **MOQ**: Minimum Order Quantity.
- **Pack Size**: Multiples (e.g., box of 10).
- **Safety Stock**: Buffer stock for variability.

## 4. Key Logic & Formulas

### 4.1 Reorder Point (ROP) Calculation
The system will use the following formula to determine when to order:

```
Reorder Point = (Average Daily Sales * Lead Time) + Safety Stock
```

*   **Average Daily Sales**: Calculated from "Sales Last 4 Months" (responsive) or "Sales Last 360 Days" (stable).
*   **Safety Stock**: Can be manually set or calculated based on deviation.

### 4.2 Restocking Notification Trigger
An alert is generated if:

```
(Available Stock + Stock In Transit) <= Reorder Point
```

### 4.3 Stock Health Metrics
- **Months of Stock**: `Current Stock / Average Monthly Sales`.
- **Stock Rotation (Turnover)**: `Annual Sales / Average Stock`.

## 5. Proposed Dashboard Features
1.  **Master View**: comprehensive table with filtering by Supplier/Category.
2.  **Alerts Panel**: "Action Required" list for items below ROP.
3.  **Product Deep-Dive**: Click on an article to see sales trend graphs and stock distribution map.
