import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import io
from fpdf import FPDF

st.set_page_config(layout="wide")

st.title("🔥 Enterprise Pinch Point Analyzer & HEN Synthesizer")
st.write("Industrial Heat Exchanger Network Design with Dynamic Interactive Economic Targeting & Automated Grid Generation")

# --- EXECUTIVE PDF REPORT GENERATION ---
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
estimated_area_base = st.sidebar.number_input("Base System Area needed (m²)", value=150)
estimated_area_integrated = st.sidebar.number_input("Integrated System Area needed (m²)", value=250)

# --- INITIALIZATION (PURE BLANK STATE - NO HARDCODED VALUES) ---
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
    st.info("📌 **Waiting for user input matrix...** Please insert your operational parameters or parse an external spreadsheet above to initialize visual architectures.")
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

# Hardware counts driven algorithmically from user metrics matrix
base_hex_count = len(stream_names_list)
capex_base = (base_hex_count * fixed_hex_cost) + (estimated_area_base * area_cost_coeff)

hot_streams_count = len([n for n in stream_names_list if streams[n]["type"] == "Hot"])
cold_streams_count = len([n for n in stream_names_list if streams[n]["type"] == "Cold"])
hx_process_count = min(hot_streams_count, cold_streams_count)

integrated_total_hex = hx_process_count + base_hex_count 
capex_integrated = (integrated_total_hex * fixed_hex_cost) + (estimated_area_integrated * area_cost_coeff)
payback_period_years = (capex_integrated - capex_base) / annual_savings if annual_savings > 0 else float('inf')

econ_summary = {
    "Operating Cost Before Integration": f"€{op_cost_before:,.2f}/yr",
    "Operating Cost After Integration": f"€{op_cost_after:,.2f}/yr",
    "Base System CAPEX Equipment Cost": f"€{capex_base:,.2f}",
    "Integrated HEN Capital Investment (CAPEX)": f"€{capex_integrated:,.2f}",
    "Simple Payback Period on Incremental Investment": f"{payback_period_years:.2f} Years"
}

# --- METRIC EXPOSURE ---
st.header("📊 Performance Metrics")
m1, m2, m3 = st.columns(3)
m1.metric("Pinch Temperature (Hot/Cold)", f"{pinch_hot} °C / {pinch_cold} °C")
m2.metric("Annual Utility Cost Saved", f"€{annual_savings:,.0f}", f"Incremental Payback: {payback_period_years:.2f} yrs")
m3.metric("True Network Units (Base vs Integrated)", f"{base_hex_count} vs {integrated_total_hex} Units")

# --- DOWNLOAD PIPELINE ---
st.subheader("💾 Cloud Reporting Infrastructure")
pdf_data = create_pdf(econ_summary, qh_min, qc_min, pinch_hot, pinch_cold)
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
    fig_gcc, ax_gcc = plt.subplots(figsize=(10, 4.5))
    ax_gcc.plot(feasible_cascade, intervals, color="black", marker="o", label="Grand Composite Curve", lw=2)
    
    # Static endpoints parsing explicitly avoids multi-line duplication artifacts
    ax_gcc.plot([0, qh_min], [intervals, intervals], color="red", lw=2.5, linestyle="-", label=f"Hot Utility ({qh_min:,.1f} kW)")
    ax_gcc.plot([0, qc_min], [intervals[-1], intervals[-1]], color="dodgerblue", lw=2.5, linestyle="-", label=f"Cold Utility ({qc_min:,.1f} kW)")
    
    ax_gcc.set_xlabel("ΔΗ (kW)")
    ax_gcc.set_ylabel("Shifted Temperature T* (°C)")
    ax_gcc.grid(True, linestyle=":", alpha=0.6)
    ax_gcc.legend()
    st.pyplot(fig_gcc)

with tab3:
    st.subheader("Heat Exchanger Network (HEN) Automatic Synthesis Layout")
    fig_grid, ax_grid = plt.subplots(figsize=(12, 5.5))
    y_pos = {name: len(streams) - idx for idx, name in enumerate(streams.keys())}
    
    # Process stream rendering
    for name, s in streams.items():
        y = y_pos[name]
        ax_grid.plot([s["Tin"], s["Tout"]], [y, y], color="red" if s["type"]=="Hot" else "blue", lw=3.5)
        ax_grid.text(s["Tin"], y + 0.15, f"{name}", fontsize=10, ha='right' if s["type"]=="Hot" else 'left', weight="bold")
        
        if s["type"] == "Cold":
            ax_grid.plot(s["Tout"], y, marker="o", color="darkred", markersize=12, zorder=5)
            ax_grid.text(s["Tin"], y - 0.28, f"In: {s['Tin']}°C", fontsize=8, color="dimgray")
            ax_grid.text(s["Tout"], y - 0.28, f"Out: {s['Tout']}°C", fontsize=8, color="darkred", weight="bold")
        else:
            ax_grid.plot(s["Tout"], y, marker="o", color="dodgerblue", markersize=12, zorder=5)
            ax_grid.text(s["Tin"], y - 0.28, f"In: {s['Tin']}°C", fontsize=8, color="dimgray")
            ax_grid.text(s["Tout"], y - 0.28, f"Out: {s['Tout']}°C", fontsize=8, color="dodgerblue", weight="bold")

    # --- AUTOMATED PROCESS-TO-PROCESS INTER-STREAM COUPLING MAP ---
    hot_st = [n for n in stream_names_list if streams[n]["type"]=="Hot"]
    cold_st = [n for n in stream_names_list if streams[n]["type"]=="Cold"]
    
    hx_idx = 0
    for i in range(min(len(hot_st), len(cold_st))):
        h_name, c_name = hot_st[i], cold_st[i]
        h_s, c_s = streams[h_name], streams[c_name]
        
        match_temp = (max(h_s["Tout"], c_s["Tin"]) + min(h_s["Tin"], c_s["Tout"])) / 2
        if min(h_s["Tin"], h_s["Tout"]) <= match_temp <= max(h_s["Tin"], h_s["Tout"]):
            hx_idx += 1
            y_h = y_pos[h_name]
            y_c = y_pos[c_name]
            ax_grid.plot([match_temp, match_temp], [y_h, y_c], color="green", linestyle="-", lw=2, zorder=3)
            ax_grid.plot([match_temp, match_temp], [y_h, y_c], marker="o", color="green", markersize=10, zorder=4)

    if isinstance(pinch_hot, float):
        ax_grid.axvline(x=pinch_hot, color="gray", linestyle="--", alpha=0.5, lw=1.5)
    
    # Standard consolidated unified legend architecture at base (FIXED SYNTAX)
    from matplotlib.lines import Line2D
    custom_legend = [
        Line2D([0], [0], marker='o', color='w', label='Process-to-Process Exchanger (Recovery)', markerfacecolor='green', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Heater (Auxiliary Hot Utility)', markerfacecolor='darkred', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Cooler (Auxiliary Cold Utility)', markerfacecolor='dodgerblue', markersize=10)
    ]
    ax_grid.legend(handles=custom_legend, loc='lower center', bbox_to_anchor=(0.5, -0.25), ncol=3, fontsize=9)
    
    ax_grid.set_yticks(list(y_pos.values()))
    ax_grid.set_yticklabels(list(y_pos.keys()), weight="bold")
    ax_grid.set_xlabel("Temperature Scale (°C)", weight="bold")
    ax_grid.set_ylim(0.3, len(streams) + 0.6)
    ax_grid.grid(axis='x', linestyle=':', alpha=0.5)
    st.pyplot(fig_grid)

with tab4:
    labels = ['Hot Utilities', 'Cold Utilities'] + [c["name"] for c in other_components]
    sizes_before = [total_cold_load / 1000, total_hot_load / 1000] + [c["mw"] for c in other_components]
    sizes_after = [qh_min / 1000, qc_min / 1000] + [c["mw"] for c in other_components]
    
    colors_map = ['#FF0000', '#0070C0', '#FFC000', '#7030A0', '#ED7D31', '#70AD47']
    if len(labels) > len(colors_map):
        colors_map += plt.cm.Accent(np.linspace(0, 1, len(labels) - len(colors_map))).tolist()
    current_colors = colors_map[:len(labels)]
    
    fig_pie, (ax_p1, ax_p2) = plt.subplots(1, 2, figsize=(14, 6))
    ax_p1.pie(sizes_before, autopct='%1.0f%%', startangle=140, colors=current_colors)
    ax_p1.set_title(f"Before Heat Integration\n(Total: {sum(sizes_before):,.2f} MW)", weight='bold')
    
    ax_p2.pie(sizes_after, autopct='%1.0f%%', startangle=140, colors=current_colors)
    ax_p2.set_title(f"After Heat Integration\n(Total: {sum(sizes_after):,.2f} MW)", weight='bold')
    
    fig_pie.legend(labels=labels, loc='lower center', ncol=3)
    plt.subplots_adjust(bottom=0.2)
    st.pyplot(fig_pie)

with tab5:
    st.subheader("💰 Non-Accumulative Interactive Financial Projections")
    col_g1, col_g2 = st.columns(2)
    years_range = list(range(0, 11))
    
    # Isolated trajectories generation
    base_capex_vector = [capex_base] * len(years_range)
    base_opex_vector = [op_cost_before] * len(years_range)
    base_opex_vector[0] = 0 # Year 0 tracking only equipment CAPEX injection
    
    int_capex_vector = [capex_integrated] * len(years_range)
    int_opex_vector = [op_cost_after] * len(years_range)
    int_opex_vector[0] = 0
    
    with col_g1:
        st.markdown("**1. Unintegrated Base Plant Cost Profile**")
        df_base_financials = pd.DataFrame({
            "Operating Year": years_range,
            "Pure CAPEX Asset Value (€)": base_capex_vector,
            "Annual Running Utilities (OPEX) (€/yr)": base_opex_vector
        })
        df_base_financials.set_index("Operating Year", inplace=True)
        
        # Interactive cloud data frame line plot integration
        st.line_chart(df_base_financials, color=["#777777", "#FF0000"])
        st.caption("Hover over the line vectors to explore isolated tracking of CAPEX machinery alongside high recurring utility demands.")
        
    with col_g2:
        st.markdown("**2. Integrated HEN System Financial Profile**")
        df_int_financials = pd.DataFrame({
            "Operating Year": years_range,
            "Upfront Fixed CAPEX (€)": int_capex_vector,
            "Optimized Running Utilities (OPEX) (€/yr)": int_opex_vector
        })
        df_int_financials.set_index("Operating Year", inplace=True)
        
        st.line_chart(df_int_financials, color=["#428BCA", "#5CB85C"])
        st.caption("Displays the step-change upgrade: higher equipment allocation CAPEX contrasted against heavily minimized operational OPEX.")
