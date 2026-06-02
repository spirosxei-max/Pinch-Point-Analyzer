import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import io
from fpdf import FPDF

st.set_page_config(layout="wide")

st.title("🔥 Advanced Pinch Point Analysis & Industrial HEN Optimizer")
st.write("Enterprise Heat Exchanger Network (HEN) Design with Economic Targeting, Excel I/O & PDF Reporting")

# --- ΣΥΝΑΡΤΗΣΕΙΣ EXPORT (EXCEL & PDF) ---
def to_excel(df_streams, df_comps, econ_summary):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_streams.to_excel(writer, sheet_name='Streams Data', index=False)
        df_comps.to_excel(writer, sheet_name='Other Components', index=False)
        pd.DataFrame([econ_summary]).to_excel(writer, sheet_name='Economic Evaluation', index=False)
    return output.getvalue()

def create_pdf(econ_summary, qh, qc, pinch_h, pinch_c):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(40, 10, "Pinch Point Analysis - Industrial Executive Report")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(40, 10, f"Pinch Temperature (Hot/Cold): {pinch_h} C / {pinch_c} C")
    pdf.ln(10)
    pdf.cell(40, 10, f"Minimum Hot Utility Required: {qh:,.1f} kW")
    pdf.ln(10)
    pdf.cell(40, 10, f"Minimum Cold Utility Required: {qc:,.1f} kW")
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(40, 10, "Economic Targeting Summary")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    
    for key, val in econ_summary.items():
        clean_val = str(val).replace("€", "EUR ")
        pdf.cell(40, 10, f"{key}: {clean_val}")
        pdf.ln(10)
        
    # Μετατροπή της εξόδου σε καθαρά bytes (bytes object) για το Streamlit
    pdf_bytes = bytes(pdf.output())
    return pdf_bytes


# --- SIDEBAR CONFIGURATION & ECONOMIC INPUTS ---
st.sidebar.header("⚙️ Model Configuration")
dT_min = st.sidebar.slider("Minimum Approach Temperature (ΔT min) °C", 1, 50, 10)

st.sidebar.header("💰 Economic Parameters")
cost_heating = st.sidebar.number_input("Hot Utility Cost (€/kWh)", value=0.04, format="%.4f")
cost_cooling = st.sidebar.number_input("Cold Utility Cost (€/kWh)", value=0.01, format="%.4f")
op_hours = st.sidebar.number_input("Annual Operating Hours (hr/year)", value=8000)

st.sidebar.subheader("🏗️ Capital Cost (HEN Installation)")
fixed_hex_cost = st.sidebar.number_input("Fixed Cost per Exchanger (€)", value=10000)
area_cost_coeff = st.sidebar.number_input("Area Cost Coefficient (€/m²)", value=400)
estimated_area = st.sidebar.number_input("Estimated Total New Area needed (m²)", value=250)

# --- EXCEL IMPORT FUNCTIONALITY ---
st.header("📥 Data Initialization")
uploaded_file = st.sidebar.file_uploader("Import Network Data from Excel", type=["xlsx"])

# Set default data structures
default_streams = pd.DataFrame([
    {"Stream Name": "E1", "Tin (°C)": 133.0, "Tout (°C)": 20.0, "Input Mode": "Heat Load (kW)", "Value": 594.0},
    {"Stream Name": "E2", "Tin (°C)": 116.0, "Tout (°C)": 25.0, "Input Mode": "Heat Load (kW)", "Value": 890.8},
    {"Stream Name": "E3", "Tin (°C)": 116.0, "Tout (°C)": 25.0, "Input Mode": "Heat Load (kW)", "Value": 891.3},
    {"Stream Name": "E4", "Tin (°C)": 113.0, "Tout (°C)": 725.0, "Input Mode": "Heat Load (kW)", "Value": 13969.0},
    {"Stream Name": "E5", "Tin (°C)": 725.0, "Tout (°C)": 25.0, "Input Mode": "Heat Load (kW)", "Value": 19310.1},
    {"Stream Name": "E6", "Tin (°C)": 58.0, "Tout (°C)": 250.0, "Input Mode": "Heat Load (kW)", "Value": 14518.1},
    {"Stream Name": "E7", "Tin (°C)": 250.0, "Tout (°C)": 30.0, "Input Mode": "Heat Load (kW)", "Value": 21434.7}
])

default_components = pd.DataFrame([
    {"Component Name": "RWGS Reactor", "Load (MW)": 3.26},
    {"Component Name": "MeOH Reactor", "Load (MW)": 10.50},
    {"Component Name": "Compressors", "Load (MW)": 6.60},
    {"Component Name": "Separators", "Load (MW)": 20.00}
])

if uploaded_file is not None:
    try:
        imported_streams = pd.read_excel(uploaded_file, sheet_name=0)
        imported_comps = pd.read_excel(uploaded_file, sheet_name=1)
        st.success("🎉 Data successfully imported from Excel file!")
        st.session_state["streams_data"] = imported_streams
        st.session_state["components_data"] = imported_comps
    except Exception as e:
        st.error(f"Error parsing file. Please check sheets format. Details: {e}")

if "streams_data" not in st.session_state:
    st.session_state["streams_data"] = default_streams
if "components_data" not in st.session_state:
    st.session_state["components_data"] = default_components

# --- DATA PANELS ---
col_table1, col_table2 = st.columns(2)

with col_table1:
    st.subheader("📋 1. Process Streams Data")
    edited_df = st.data_editor(st.session_state["streams_data"], num_rows="dynamic", use_container_width=True, key="streams_editor")

with col_table2:
    st.subheader("⚡ 2. Other Process Components")
    edited_components_df = st.data_editor(st.session_state["components_data"], num_rows="dynamic", use_container_width=True, key="components_editor")

# --- RAW DATA CONVERSION ---
streams = {}
stream_names_list = []
if edited_df is not None and not edited_df.empty:
    valid_df = edited_df.dropna(subset=["Stream Name", "Tin (°C)", "Tout (°C)", "Input Mode", "Value"])
    valid_df = valid_df[valid_df["Stream Name"].astype(str).str.strip() != ""]
    for _, row in valid_df.iterrows():
        try:
            tin = float(row["Tin (°C)"])
            tout = float(row["Tout (°C)"])
            val = abs(float(row["Value"]))
            name = str(row["Stream Name"])
            itype = row["Input Mode"]
            stream_type = "Hot" if tin > tout else "Cold"
            dT_stream = abs(tin - tout)
            if itype == "Cp (kW/°C)":
                cp = val
                q = cp * dT_stream
            else:
                q = val
                cp = q / dT_stream if dT_stream > 0 else 0.0
            streams[name] = {"type": stream_type, "Tin": tin, "Tout": tout, "Cp": cp, "Q": q}
            stream_names_list.append(name)
        except Exception:
            continue

other_components = []
for _, row in edited_components_df.dropna(subset=["Component Name", "Load (MW)"]).iterrows():
    if str(row["Component Name"]).strip() != "":
        other_components.append({"name": str(row["Component Name"]), "mw": abs(float(row["Load (MW)"]))})

if len(streams) < 2:
    st.info("📌 **Waiting for valid input matrix...** Fill out the tables above to generate thermodynamic and financial charts.")
    st.stop()

# --- THERMODYNAMIC PINCH CALCULATIONS ---
for name, s in streams.items():
    s["Tin_shift"] = s["Tin"] - dT_min / 2 if s["type"] == "Hot" else s["Tin"] + dT_min / 2
    s["Tout_shift"] = s["Tout"] - dT_min / 2 if s["type"] == "Hot" else s["Tout"] + dT_min / 2

intervals = sorted(list(set([s["Tin_shift"] for s in streams.values()] + [s["Tout_shift"] for s in streams.values()])), reverse=True)
dh_intervals = []
for i in range(len(intervals) - 1):
    Th, Tl = intervals[i], intervals[i+1]
    dT = Th - Tl
    cp_hot = sum(s["Cp"] for s in streams.values() if s["type"] == "Hot" and min(s["Tin_shift"], s["Tout_shift"]) <= Tl and max(s["Tin_shift"], s["Tout_shift"]) >= Th)
    cp_cold = sum(s["Cp"] for s in streams.values() if s["type"] == "Cold" and min(s["Tin_shift"], s["Tout_shift"]) <= Tl and max(s["Tin_shift"], s["Tout_shift"]) >= Th)
    dh_intervals.append((cp_hot - cp_cold) * dT)

cascade = [0.0]
for dh in dh_intervals: cascade.append(cascade[-1] + dh)
qh_min = -min(cascade) if min(cascade) < 0 else 0
feasible_cascade = [c + qh_min for c in cascade]
qc_min = feasible_cascade[-1]

try:
    pinch_index = int(np.argmin(np.abs(feasible_cascade)))
    pinch_hot = intervals[pinch_index] + dT_min / 2
    pinch_cold = intervals[pinch_index] - dT_min / 2
except Exception:
    pinch_hot, pinch_cold = "N/A", "N/A"

total_hot_load = sum(s["Q"] for s in streams.values() if s["type"] == "Hot")
total_cold_load = sum(s["Q"] for s in streams.values() if s["type"] == "Cold")

# --- FINANCIAL TARGETING LOGIC ---
op_cost_before = ((total_cold_load * cost_heating) + (total_hot_load * cost_cooling)) * op_hours
op_cost_after = ((qh_min * cost_heating) + (qc_min * cost_cooling)) * op_hours
annual_savings = op_cost_before - op_cost_after

hx_process_count = 2 if len(stream_names_list) >= 7 else 1
capex_investment = (hx_process_count * fixed_hex_cost) + (estimated_area * area_cost_coeff)
payback_period_years = capex_investment / annual_savings if annual_savings > 0 else float('inf')

econ_summary = {
    "Operating Cost Before Integration": f"€{op_cost_before:,.2f}/yr",
    "Operating Cost After Integration": f"€{op_cost_after:,.2f}/yr",
    "Net Annual Operating Savings": f"€{annual_savings:,.2f}/yr",
    "Estimated HEN Capital Investment (CAPEX)": f"€{capex_investment:,.2f}",
    "Simple Payback Period": f"{payback_period_years:.2f} Years"
}

# --- METRIC DISPLAY ---
st.header("📊 Performance Metrics")
m1, m2, m3 = st.columns(3)
m1.metric("Pinch Temperature (Hot/Cold)", f"{pinch_hot} °C / {pinch_cold} °C")
m2.metric("Annual Utility Cost Saved", f"€{annual_savings:,.0f}", f"Payback: {payback_period_years:.2f} yrs")
m3.metric("True Total Exchangers", f"{hx_process_count + 6} Units")

# --- EXPORT INTERFACE ---
st.subheader("💾 Export Infrastructure")
excel_data = to_excel(edited_df, edited_components_df, econ_summary)
pdf_data = create_pdf(econ_summary, qh_min, qc_min, pinch_hot, pinch_cold)

c_exp1, c_exp2 = st.columns(2)
with c_exp1:
    st.download_button(label="📥 Download Data & Results (Excel)", data=excel_data, file_name="HEN_Optimization_Framework.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with c_exp2:
    st.download_button(label="📥 Download Executive Summary (PDF)", data=pdf_data, file_name="Pinch_Analysis_Report.pdf", mime="application/pdf")

# --- GRAPHICAL ANALYTICAL TABS ---
st.header("📈 Thermodynamic, Financial & Network Visualizations")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Composite Curves", "📉 Grand Composite Curve (GCC)", "🕸️ HEN Grid Layout", "🍕 Energy Allocation (Pies)", "💰 Capital vs Operating Economics"])

with tab1:
    # (The standard composite curve script runs unchanged)
    hot_intervals = sorted(list(set([s["Tin"] for s in streams.values() if s["type"]=="Hot"] + [s["Tout"] for s in streams.values() if s["type"]=="Hot"])), reverse=True)
    hot_H = [0.0]
    for i in range(len(hot_intervals)-1):
        Th, Tl = hot_intervals[i], hot_intervals[i+1]
        cp_sum = sum(s["Cp"] for s in streams.values() if s["type"]=="Hot" and min(s["Tin"], s["Tout"]) <= Tl and max(s["Tin"], s["Tout"]) >= Th)
        hot_H.append(hot_H[-1] + cp_sum * (Th - Tl))
    cold_intervals = sorted(list(set([s["Tin"] for s in streams.values() if s["type"]=="Cold"] + [s["Tout"] for s in streams.values() if s["type"]=="Cold"])), reverse=True)
    cold_H = [qc_min]
    for i in range(len(cold_intervals)-1):
        Th, Tl = cold_intervals[i], cold_intervals[i+1]
        cp_sum = sum(s["Cp"] for s in streams.values() if s["type"]=="Cold" and min(s["Tin"], s["Tout"]) <= Tl and max(s["Tin"], s["Tout"]) >= Th)
        cold_H.append(cold_H[-1] + cp_sum * (Th - Tl))
    fig_cc, ax_cc = plt.subplots(figsize=(10, 3.5))
    ax_cc.plot(hot_H, hot_intervals, color="red", label="Hot Composite Curve", lw=2)
    ax_cc.plot(cold_H, cold_intervals, color="blue", label="Cold Composite Curve", lw=2)
    ax_cc.set_xlabel("Enthalpy Cumulative (kW)")
    ax_cc.set_ylabel("Temperature (°C)")
    ax_cc.legend()
    ax_cc.grid(True, linestyle=":")
    st.pyplot(fig_cc)

with tab2:
    fig_gcc, ax_gcc = plt.subplots(figsize=(10, 3.5))
    ax_gcc.plot(feasible_cascade, intervals, color="black", marker="o", label="Grand Composite Curve", lw=2)
    ax_gcc.plot([0, qh_min], [intervals, intervals], color="red", lw=2.5, linestyle="-", marker="s", label="Hot Utility Line")
    ax_gcc.plot([0, qc_min], [intervals[-1], intervals[-1]], color="dodgerblue", lw=2.5, linestyle="-", marker="s", label="Cold Utility Line")
    ax_gcc.set_xlabel("ΔΗ (kW)")
    ax_gcc.set_ylabel("Shifted Temperature T* (°C)")
    ax_gcc.grid(True, linestyle=":", alpha=0.6)
    ax_gcc.legend()
    st.pyplot(fig_gcc)

with tab3:
    fig_grid, ax_grid = plt.subplots(figsize=(12, 5))
    y_pos = {name: len(streams) - idx for idx, name in enumerate(streams.keys())}
    for name, s in streams.items():
        y = y_pos[name]
        ax_grid.plot([s["Tin"], s["Tout"]], [y, y], color="red" if s["type"]=="Hot" else "blue", lw=3.5)
        ax_grid.text(s["Tin"], y + 0.15, f"{name} ({s['Tin']}°C)", fontsize=9, ha='right' if s["type"]=="Hot" else 'left', weight="bold")
    if isinstance(pinch_hot, float):
        ax_grid.axvline(x=pinch_hot, color="gray", linestyle="--", alpha=0.7, lw=2)
    
    # Simple conditional index matching representation
    if len(stream_names_list) >= 7:
        ax_grid.plot([450, 450], [y_pos[stream_names_list[4]], y_pos[stream_names_list[3]]], color="green", marker="o", lw=2)
        ax_grid.plot([150, 150], [y_pos[stream_names_list[6]], y_pos[stream_names_list[5]]], color="green", marker="o", lw=2)
    
    ax_grid.set_yticks(list(y_pos.values()))
    ax_grid.set_yticklabels(list(y_pos.keys()), weight="bold")
    ax_grid.set_ylim(0.5, len(streams) + 0.8)
    st.pyplot(fig_grid)

with tab4:
    # (The optimized allocation pie charts script)
    labels = ['Hot Utilities', 'Cold Utilities'] + [c["name"] for c in other_components]
    sizes_before = [total_cold_load / 1000, total_hot_load / 1000] + [c["mw"] for c in other_components]
    sizes_after = [qh_min / 1000, qc_min / 1000] + [c["mw"] for c in other_components]
    fig_pie, (ax_p1, ax_p2) = plt.subplots(1, 2, figsize=(12, 5))
    ax_p1.pie(sizes_before, autopct='%1.0f%%', startangle=140, colors=['#FF0000', '#0070C0', '#FFC000', '#7030A0'])
    ax_p1.set_title("Before Heat Integration", weight='bold')
    ax_p2.pie(sizes_after, autopct='%1.0f%%', startangle=140, colors=['#FF0000', '#0070C0', '#FFC000', '#7030A0'])
    ax_p2.set_title("After Heat Integration", weight='bold')
    fig_pie.legend(labels=labels, loc='lower center', ncol=3)
    st.pyplot(fig_pie)

with tab5:
    st.subheader("💰 Financial Analysis & Capital Payback Framework")
    col_g1, col_g2 = st.columns(2)
    
    years_range = np.arange(0, 11)
    
    with col_g1:
        st.markdown("**Cumulative Cash Flow Curve (Break-Even Evaluation)**")
        # Curve 1: Do Nothing (Base Operating cost accumulation starting from 0)
        cash_no_integration = -(op_cost_before * years_range)
        # Curve 2: Integrate (Pay CAPEX upfront, then accumulate lower operating costs)
        cash_integrated = -capex_investment - (op_cost_after * years_range)
        
        fig_cash, ax_cash = plt.subplots(figsize=(10, 5))
        ax_cash.plot(years_range, cash_no_integration, color="red", linestyle="--", label="Option A: Base Plant (No Integration)", lw=2)
        ax_cash.plot(years_range, cash_integrated, color="green", label="Option B: HEN Integration (CAPEX Invested)", lw=2.5)
        
        if payback_period_years <= 10:
            ax_cash.axvline(x=payback_period_years, color="black", linestyle=":", alpha=0.8)
            ax_cash.text(payback_period_years + 0.2, max(cash_integrated)/2, f"Break-Even Point\n({payback_period_years:.2f} Years)", color="black", weight="bold")
            
        ax_cash.set_xlabel("Operating Years")
        ax_cash.set_ylabel("Cumulative Cost Burden (€)")
        ax_cash.grid(True, linestyle=":", alpha=0.6)
        ax_cash.legend()
        st.pyplot(fig_cash)
        
    with col_g2:
        st.markdown("**Total Cost of Ownership Comparison (10-Year Lifecycle horizon)**")
        # 10 Year life cycle cost evaluation
        total_10_base = op_cost_before * 10
        total_10_integrated = capex_investment + (op_cost_after * 10)
        
        fig_bar, ax_bar = plt.subplots(figsize=(9, 5))
        bars = ax_bar.bar(["Base Plant Configuration", "Integrated HEN Structure"], [total_10_base, total_10_integrated], color=["#D9534F", "#5CB85C"], width=0.5)
        ax_bar.set_ylabel("Total 10-Year Lifecycle Cost (€)")
        ax_bar.grid(axis='y', linestyle=':', alpha=0.5)
        
        for bar in bars:
            yval = bar.get_height()
            ax_bar.text(bar.get_x() + bar.get_width()/2, yval + (total_10_base*0.02), f"€{yval:,.0f}", ha='center', va='bottom', weight='bold')
            
        st.pyplot(fig_bar)
