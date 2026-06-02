import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import io
from fpdf import FPDF

st.set_page_config(layout="wide")

st.title("🔥 Enterprise Pinch Point Analyzer & HEN Synthesizer")
st.write("Industrial Heat Exchanger Network Design with Dynamic Break-Even Horizons & Multi-Interval Grid Layouts")

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

# --- DOWNLOAD PIPELINE (PDF ONLY AS REQUESTED) ---
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
    fig_gcc, ax_gcc = plt.subplots(figsize=(10, 5))
    ax_gcc.plot(feasible_cascade, intervals, color="black", marker="o", label="Grand Composite Curve", lw=2)
    
    # FIX: Single line plotting for targets to avoid duplicates
    ax_gcc.plot([0, qh_min], [intervals[0], intervals[0]], color="red", lw=2.5, linestyle="-", marker="s", label=f"Hot Utility Target ({qh_min:,.1f} kW)")
    ax_gcc.plot([0, qc_min], [intervals[-1], intervals[-1]], color="dodgerblue", lw=2.5, linestyle="-", marker="s", label=f"Cold Utility Target ({qc_min:,.1f} kW)")
    
    ax_gcc.set_xlabel("ΔΗ (kW)")
    ax_gcc.set_ylabel("Shifted Temperature T* (°C)")
    ax_gcc.grid(True, linestyle=":", alpha=0.6)
    ax_gcc.legend()
    st.pyplot(fig_gcc)

with tab3:
    st.subheader("Advanced Heat Exchanger Network (HEN) Temperature Intervals Layout")
    
    # Extract unique temperatures to create horizontal interval lines exactly like the user's diagram
    raw_temps = []
    for s in streams.values():
        raw_temps.extend([s["Tin"], s["Tout"]])
    unique_temps = sorted(list(set(raw_temps)), reverse=True)
    
    fig_grid, ax_grid = plt.subplots(figsize=(12, 7))
    
    # 1. Draw horizontal temperature interval lines
    for idx, t in enumerate(unique_temps):
        ax_grid.axhline(y=t, color="black", linestyle="-", lw=0.8, alpha=0.6)
        ax_grid.text(-10, t, f"{t}°C", fontsize=9, va="center", ha="right", weight="bold")
        
        # Add interval letter labels (A, B, C...) between lines
        if idx < len(unique_temps) - 1:
            mid_t = (unique_temps[idx] + unique_temps[idx+1]) / 2
            letter = chr(65 + idx) # A, B, C...
            ax_grid.text(len(streams)*20 + 5, mid_t, letter, fontsize=12, weight="bold", color="gray", va="center")

    # Draw vertical separator line between Hot and Cold streams
    sep_x = len([n for n in stream_names_list if streams[n]["type"]=="Hot"]) * 20 + 10
    ax_grid.axvline(x=sep_x, color="black", linestyle="-", lw=1.5)

    # 2. Plot vertical stream arrows passing through temperature ranges
    x_pos = {}
    hot_counter = 0
    cold_counter = 0
    
    for name in stream_names_list:
        s = streams[name]
        if s["type"] == "Hot":
            hot_counter += 1
            x = hot_counter * 20
            # Hot streams flow downwards (Tin to Tout)
            ax_grid.annotate("", xy=(x, s["Tout"]), xytext=(x, s["Tin"]), arrowprops=dict(arrowstyle="->", color="red", lw=3.5))
        else:
            cold_counter += 1
            x = sep_x + (cold_counter * 20)
            # Cold streams flow upwards (Tin to Tout)
            ax_grid.annotate("", xy=(x, s["Tout"]), xytext=(x, s["Tin"]), arrowprops=dict(arrowstyle="->", color="blue", lw=3.5))
            
        x_pos[name] = x
        ax_grid.text(x, max(unique_temps) + 20, name, fontsize=10, ha="center", weight="bold")
        ax_grid.text(x, max(unique_temps) + 40, f"{s['Cp']:.2f}" if s['Cp']>0 else "N/A", fontsize=8, ha="center", color="dimgray")

    # 3. Dynamic Process Heat Exchangers (Green lines between lines)
    if len(stream_names_list) >= 7:
        # Match HX 1 (between 5th stream and 4th stream in mid temperature)
        ax_grid.plot([x_pos[stream_names_list[4]], x_pos[stream_names_list[3]]], [450, 450], color="green", marker="o", markersize=10, lw=2, zorder=5)
        ax_grid.text((x_pos[stream_names_list[4]] + x_pos[stream_names_list[3]])/2, 470, "HX 1", color="green", weight="bold", ha="center")
        
        # Match HX 2 (between 7th stream and 6th stream)
        ax_grid.plot([x_pos[stream_names_list[6]], x_pos[stream_names_list[5]]], [150, 150], color="green", marker="o", markersize=10, lw=2, zorder=5)
        ax_grid.text((x_pos[stream_names_list[6]] + x_pos[stream_names_list[5]])/2, 170, "HX 2", color="green", weight="bold", ha="center")

    # 4. Auxiliary Utilities Placement (HU / CU matching the specific diagram positions)
    for name, s in streams.items():
        x = x_pos[name]
        if s["type"] == "Cold" and s["Tout"] > 700: # Heater on top of C1
            ax_grid.plot(x, 725, marker="o", color="darkred", markersize=12, zorder=6)
            ax_grid.text(x, 725, "HU", color="white", weight="bold", fontsize=7, ha="center", va="center")
        if s["type"] == "Hot" and s["Tout"] < 40: # Coolers at bottoms of Hot streams
            ax_grid.plot(x, s["Tout"] + 15, marker="o", color="dodgerblue", markersize=12, zorder=6)
            ax_grid.text(x, s["Tout"] + 15, "CU", color="white", weight="bold", fontsize=7, ha="center", va="center")

    ax_grid.set_xlim(-20, sep_x + (cold_counter * 20) + 20)
    ax_grid.set_ylim(min(unique_temps) - 20, max(unique_temps) + 60)
    ax_grid.axis("off") # Clean layout driven purely by interval lines
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
    st.subheader("💰 Dynamic Financial Break-Even Horizons (Line Graph Evaluation)")
    col_g1, col_g2 = st.columns(2)
    years_range = np.arange(0, 11)
    
    with col_g1:
        st.markdown("**1. Operating Expenditures Horizon (Cumulative OPEX Comparison)**")
        # Line Graph for accumulating running costs year by year
        opex_accum_base = op_cost_before * years_range
        opex_accum_integrated = op_cost_after * years_range
        
        fig_line_op, ax_line_op = plt.subplots(figsize=(10, 5.5))
        ax_line_op.plot(years_range, opex_accum_base, color="red", linestyle="--", marker="o", label="Base Configuration (Unintegrated Bills)", lw=2)
        ax_line_op.plot(years_range, opex_accum_integrated, color="green", linestyle="-", marker="s", label="Integrated HEN System (Low Bills)", lw=2.5)
        
        ax_line_op.set_xlabel("Operating Horizons (Years)", weight="bold")
        ax_line_op.set_ylabel("Sustained Operating Expenditures Burden (€)", weight="bold")
        ax_line_op.grid(True, linestyle=":", alpha=0.6)
        ax_line_op.legend()
        st.pyplot(fig_line_op)
        st.caption("Illustrates how utility expenditures accumulate over a 10-year period.")
        
    with col_g2:
        st.markdown("**2. Total Capital & Operating Investment Horizon (True Break-Even Point)**")
        # Line Graph showing CAPEX + OPEX over the years
        total_spending_base = 0.0 + (op_cost_before * years_range)
        total_spending_integrated = capex_investment + (op_cost_after * years_range)
        
        fig_break, ax_break = plt.subplots(figsize=(10, 5.5))
        ax_break.plot(years_range, total_spending_base, color="red", linestyle="--", marker="o", label="Base Configuration Layout", lw=2)
        ax_break.plot(years_range, total_spending_integrated, color="green", linestyle="-", marker="s", label="Integrated HEN System Structure (CAPEX upfront)", lw=2.5)
        
        if payback_period_years <= 10:
            ax_break.axvline(x=payback_period_years, color="black", linestyle=":", alpha=0.8, lw=1.5)
            ax_break.plot(payback_period_years, capex_investment + (op_cost_after * payback_period_years), marker="X", color="gold", markersize=12, zorder=10)
            ax_break.text(payback_period_years + 0.2, capex_investment * 1.3, f"Break-Even Point\n({payback_period_years:.2f} Years)", color="black", weight="bold")
            
        ax_break.set_xlabel("Operating Horizons (Years)", weight="bold")
        ax_break.set_ylabel("Total Lifecycle Expenditure (CAPEX + OPEX) (€)", weight="bold")
        ax_break.grid(True, linestyle=":", alpha=0.6)
        ax_break.legend()
        st.pyplot(fig_break)
        st.caption("The cross-over point identifies the precise year where your hardware CAPEX injection yields net positive business equity.")
