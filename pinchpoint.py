import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import io
from fpdf import FPDF

st.set_page_config(layout="wide")

st.title("🔥 Advanced Pinch Point Analysis & Industrial HEN Optimizer")
st.write("Enterprise Heat Exchanger Network (HEN) Design with Economic Targeting, Excel I/O & PDF Reporting")

# --- EXPORT FUNCTIONS (EXCEL & PDF) ---
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
        
    return bytes(pdf.output())

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

# --- INITIALIZATION (PURE BLANK STATE) ---
st.header("📥 Data Initialization")

empty_streams = pd.DataFrame([
    {"Stream Name": "", "Tin (°C)": None, "Tout (°C)": None, "Input Mode": "Heat Load (kW)", "Value": None}
])

empty_components = pd.DataFrame([
    {"Component Name": "", "Load (MW)": None}
])

# Handle Excel Upload
uploaded_file = st.sidebar.file_uploader("Import Network Data from Excel", type=["xlsx"])
if uploaded_file is not None:
    try:
        st.session_state["streams_data"] = pd.read_excel(uploaded_file, sheet_name=0)
        st.session_state["components_data"] = pd.read_excel(uploaded_file, sheet_name=1)
        st.success("🎉 Data successfully imported from Excel sheets!")
    except Exception as e:
        st.error(f"Excel parsing failure. Check sheets layout. Error: {e}")

if "streams_data" not in st.session_state:
    st.session_state["streams_data"] = empty_streams
if "components_data" not in st.session_state:
    st.session_state["components_data"] = empty_components

# --- GUI INPUT MATRIX DATA EDITORS ---
col_table1, col_table2 = st.columns(2)

with col_table1:
    st.subheader("📋 1. Process Streams Data")
    edited_df = st.data_editor(st.session_state["streams_data"], num_rows="dynamic", use_container_width=True, key="streams_editor")

with col_table2:
    st.subheader("⚡ 2. Other Process Components")
    edited_components_df = st.data_editor(st.session_state["components_data"], num_rows="dynamic", use_container_width=True, key="components_editor")

# --- RAW SYSTEM INPUT DATA CONVERSION ---
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
if edited_components_df is not None and not edited_components_df.empty:
    valid_comp_df = edited_components_df.dropna(subset=["Component Name", "Load (MW)"])
    valid_comp_df = valid_comp_df[valid_comp_df["Component Name"].astype(str).str.strip() != ""]
    for _, row in valid_comp_df.iterrows():
        try:
            other_components.append({"name": str(row["Component Name"]), "mw": abs(float(row["Load (MW)"]))})
        except Exception:
            continue

# --- BLANK STATE INTERACTION CONTROL ---
if len(streams) < 2:
    st.markdown("---")
    st.info("📌 **Waiting for user input matrix...** Please add your stream details above or upload an Excel file to generate analysis.")
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
for dh in dh_intervals: 
    cascade.append(cascade[-1] + dh)
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
# --- FINANCIAL ACCELERATION LOGIC ---
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

# --- METRIC EXPOSURE ---
st.header("📊 Performance Metrics")
m1, m2, m3 = st.columns(3)
m1.metric("Pinch Temperature (Hot/Cold)", f"{pinch_hot} °C / {pinch_cold} °C")
m2.metric("Annual Utility Cost Saved", f"€{annual_savings:,.0f}", f"Payback: {payback_period_years:.2f} yrs")
m3.metric("True Total Exchangers Required", f"{hx_process_count + 6} Units")

# --- DOWNLOAD PIPELINES ---
st.subheader("💾 Cloud Reporting Infrastructure")
excel_data = to_excel(edited_df, edited_components_df, econ_summary)
pdf_data = create_pdf(econ_summary, qh_min, qc_min, pinch_hot, pinch_cold)

c_exp1, c_exp2 = st.columns(2)
with c_exp1:
    st.download_button(label="📥 Download Data & Financial Targets (Excel)", data=excel_data, file_name="HEN_Optimization_Framework.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with c_exp2:
    st.download_button(label="📥 Download Executive Technical Report (PDF)", data=pdf_data, file_name="Pinch_Analysis_Report.pdf", mime="application/pdf")

# --- GRAPHICAL ANALYTICAL TABS ---
st.header("📈 Thermodynamic, Financial & Network Visualizations")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Composite Curves", "📉 Grand Composite Curve (GCC)", "🕸️ HEN Grid Layout", "🍕 Energy Allocation (Pies)", "💰 Capital vs Operating Economics"])

with tab1:
    st.subheader("Temperature - Enthalpy Cumulative Diagrams (T-H Curves)")
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
        
    fig_cc, ax_cc = plt.subplots(figsize=(10, 4))
    ax_cc.plot(hot_H, hot_intervals, color="red", label="Hot Composite Curve", lw=2.5)
    ax_cc.plot(cold_H, cold_intervals, color="blue", label="Cold Composite Curve", lw=2.5)
    ax_cc.set_xlabel("Enthalpy Cumulative (kW)")
    ax_cc.set_ylabel("Temperature (°C)")
    ax_cc.legend()
    ax_cc.grid(True, linestyle=":")
    st.pyplot(fig_cc)

with tab2:
    st.subheader("Grand Composite Curve (GCC) - Enthalpy Cascade Diagram")
    fig_gcc, ax_gcc = plt.subplots(figsize=(10, 5))
    
    # Σχεδίαση της κύριας καμπύλης GCC
    ax_gcc.plot(feasible_cascade, intervals, color="black", marker="o", label="Grand Composite Curve", lw=2)
    
    # ΔΙΟΡΘΩΣΗ: Σχεδίαση μίας μόνο καθαρής οριζόντιας γραμμής για το κάθε Utility
    # Η Hot Utility γραμμή μπαίνει στην ανώτερη μετατοπισμένη θερμοκρασία (πρώτο interval)
    ax_gcc.plot([0, qh_min], [intervals[0], intervals[0]], color="red", lw=2.5, linestyle="-", marker="s", label=f"Hot Utility Target ({qh_min:,.1f} kW)")
    # Η Cold Utility γραμμή μπαίνει στην κατώτερη μετατοπισμένη θερμοκρασία (τελευταίο interval)
    ax_gcc.plot([0, qc_min], [intervals[-1], intervals[-1]], color="dodgerblue", lw=2.5, linestyle="-", marker="s", label=f"Cold Utility Target ({qc_min:,.1f} kW)")
    
    ax_gcc.set_xlabel("ΔΗ (kW)")
    ax_gcc.set_ylabel("Shifted Temperature T* (°C)")
    ax_gcc.grid(True, linestyle=":", alpha=0.6)
    ax_gcc.legend()
    st.pyplot(fig_gcc)

with tab3:
    st.subheader("Heat Exchanger Network (HEN) Grid Layout & True Inventory")
    fig_grid, ax_grid = plt.subplots(figsize=(12, 6))
    y_pos = {name: len(streams) - idx for idx, name in enumerate(streams.keys())}
    
    for name, s in streams.items():
        y = y_pos[name]
        ax_grid.plot([s["Tin"], s["Tout"]], [y, y], color="red" if s["type"]=="Hot" else "blue", lw=3.5)
        ax_grid.text(s["Tin"], y + 0.15, f"{name} ({s['Tin']}°C)", fontsize=9, ha='right' if s["type"]=="Hot" else 'left', weight="bold")
        ax_grid.text(s["Tout"], y - 0.25, f"{s['Tout']}°C", fontsize=9, ha='left' if s["type"]=="Hot" else 'right')
        
    if isinstance(pinch_hot, float):
        ax_grid.axvline(x=pinch_hot, color="gray", linestyle="--", alpha=0.7, lw=2)
        ax_grid.text(pinch_hot, len(streams) + 0.5, f"Pinch ({pinch_hot}°C)", color="gray", ha="center", weight="bold")

    # Dynamic index-based process heat recovery connections
    hx_count = 0
    if len(stream_names_list) >= 7:
        index_matches = [
            (stream_names_list[4], stream_names_list[3], 450), 
            (stream_names_list[6], stream_names_list[5], 150)
        ]
    else:
        index_matches = []
        hot_st = [n for n in stream_names_list if streams[n]["type"]=="Hot"]
        cold_st = [n for n in stream_names_list if streams[n]["type"]=="Cold"]
        for i in range(min(len(hot_st), len(cold_st))):
            index_matches.append((hot_st[i], cold_st[i], (streams[hot_st[i]]["Tin"] + streams[cold_st[i]]["Tin"])/2))

    for hot_st, cold_st, x_pos in index_matches:
        if hot_st in y_pos and cold_st in y_pos:
            hx_count += 1
            y_hot = y_pos[hot_st]
            y_cold = y_pos[cold_st]
            ax_grid.plot([x_pos, x_pos], [y_hot, y_cold], color="green", linestyle="-", lw=2, zorder=3)
            ax_grid.plot([x_pos, x_pos], [y_hot, y_cold], marker="o", color="green", markersize=10, zorder=4)
            ax_grid.text(x_pos + 6, (y_hot + y_cold)/2, f"HX {hx_count}", color="green", weight="bold", fontsize=10)

    # Rendering Auxiliary Units (Heaters / Coolers)
    hu_count, cu_count = 0, 0
    for name, s in streams.items():
        y = y_pos[name]
        if s["type"] == "Cold" and s["Tout"] > 400: 
            hu_count += 1
            hu_x = s["Tout"] - 30
            ax_grid.plot(hu_x, y, marker="o", color="darkred", markersize=11, zorder=5)
            ax_grid.text(hu_x, y + 0.15, f"HU {hu_count}", color="darkred", weight="bold", fontsize=9, ha="center")
        if s["type"] == "Hot" and s["Tout"] < 40: 
            cu_count += 1
            cu_x = s["Tout"] + 15
            ax_grid.plot(cu_x, y, marker="o", color="blue", markersize=11, zorder=5)
            ax_grid.text(cu_x, y + 0.15, f"CU {cu_count}", color="blue", weight="bold", fontsize=9, ha="center")

    ax_grid.set_yticks(list(y_pos.values()))
    ax_grid.set_yticklabels(list(y_pos.keys()), weight="bold")
    ax_grid.set_xlabel("Temperature (°C)", weight="bold")
    ax_grid.grid(axis='x', linestyle=':', alpha=0.5)
    st.pyplot(fig_grid)
    st.success(f"Network Balance Inventory -> Process Exchangers: {hx_count} | Heaters (HU): {hu_count} | Coolers (CU): {cu_count} || Total Fleet: {hx_count + hu_count + cu_count}")

with tab4:
    st.subheader("Global Process Energy Allocation (Pie Charts)")
    labels = ['Hot Utilities', 'Cold Utilities'] + [c["name"] for c in other_components]
    sizes_before = [total_cold_load / 1000, total_hot_load / 1000] + [c["mw"] for c in other_components]
    sizes_after = [qh_min / 1000, qc_min / 1000] + [c["mw"] for c in other_components]
    
    total_before = sum(sizes_before)
    total_after = sum(sizes_after)
    
    colors_map = ['#FF0000', '#0070C0', '#FFC000', '#7030A0', '#ED7D31', '#70AD47']
    if len(labels) > len(colors_map):
        colors_map += plt.cm.Accent(np.linspace(0, 1, len(labels) - len(colors_map))).tolist()
    current_colors = colors_map[:len(labels)]
    
    fig_pie, (ax_p1, ax_p2) = plt.subplots(1, 2, figsize=(14, 6))
    ax_p1.pie(sizes_before, autopct='%1.0f%%', startangle=140, colors=current_colors)
    ax_p1.set_title(f"Before Heat Integration\n(Total: {total_before:.2f} MW)", weight='bold')
    
    ax_p2.pie(sizes_after, autopct='%1.0f%%', startangle=140, colors=current_colors)
    ax_p2.set_title(f"After Heat Integration\n(Total: {total_after:.2f} MW)", weight='bold')
    
    fig_pie.legend(labels=labels, loc='lower center', ncol=3)
    plt.subplots_adjust(bottom=0.2)
    st.pyplot(fig_pie)

with tab5:
    st.subheader("💰 Capital & Operating Expenditure Analysis (CAPEX vs OPEX)")
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("**1. Annual Operating Expenditures (OPEX Comparison)**")
        fig_opex, ax_opex = plt.subplots(figsize=(8, 5))
        
        bars_op = ax_opex.bar(
            ["Base System (No Integration)", "Integrated HEN System"], 
            [op_cost_before, op_cost_after], 
            color=["#D9534F", "#5CB85C"], 
            width=0.4
        )
        ax_opex.set_ylabel("Annual Utility Cost (€/year)", weight="bold")
        ax_opex.grid(axis='y', linestyle=':', alpha=0.5)
        
        for bar in bars_op:
            yval = bar.get_height()
        for bar in bars_op:
            yval = bar.get_height()
            ax_opex.text(bar.get_x() + bar.get_width()/2, yval + (op_cost_before * 0.02), f"€{yval:,.0f}/yr", ha='center', va='bottom', weight='bold')
            
        st.pyplot(fig_opex)
        st.caption("Shows the direct reduction in utility bills achieved through process heat integration.")
        
    with col_g2:
        st.markdown("**2. Upfront Capital Expenditures (CAPEX Investment Required)**")
        fig_capex, ax_capex = plt.subplots(figsize=(8, 5))
        
        bars_cap = ax_capex.bar(
            ["Base System (No Integration)", "Integrated HEN System"], 
            [0.0, capex_investment], 
            color=["#777777", "#428BCA"], 
            width=0.4
        )
        ax_capex.set_ylabel("Initial Capital Investment (€)", weight="bold")
        ax_capex.grid(axis='y', linestyle=':', alpha=0.5)
        
        for bar in bars_cap:
            yval = bar.get_height()
            ax_capex.text(bar.get_x() + bar.get_width()/2, yval + (capex_investment * 0.02 if capex_investment > 0 else 1000), f"€{yval:,.0f}", ha='center', va='bottom', weight='bold')
            
        st.pyplot(fig_capex)
        st.caption("Represents the asset hardware installation cost (New Heat Exchangers + Area adjustments).")
