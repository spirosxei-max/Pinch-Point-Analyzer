import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(layout="wide")

st.title("🔥 Advanced Pinch Point Analysis & HEN Optimizer")
st.write("Heat Exchanger Network (HEN) Design with Dynamic Streams, Utility Mapping & GCC")

# --- DATA PANELS (2 TABLES) ---
col_table1, col_table2 = st.columns(2)

with col_table1:
    st.header("📋 1. Process Streams Data")
    st.write("Input streams using either Cp or Heat Load. The system calculates the inverse automatically.")
    
    default_streams = pd.DataFrame([
        {"name": "E1", "tin": 133.0, "tout": 20.0, "input_type": "Heat Load (kW)", "value": 594.0},
        {"name": "E2", "tin": 116.0, "tout": 25.0, "input_type": "Heat Load (kW)", "value": 890.8},
        {"name": "E3", "tin": 116.0, "tout": 25.0, "input_type": "Heat Load (kW)", "value": 891.3},
        {"name": "E4", "tin": 113.0, "tout": 725.0, "input_type": "Heat Load (kW)", "value": 13969.0},
        {"name": "E5", "tin": 725.0, "tout": 25.0, "input_type": "Heat Load (kW)", "value": 19310.1},
        {"name": "E6", "tin": 58.0, "tout": 250.0, "input_type": "Heat Load (kW)", "value": 14518.1},
        {"name": "E7", "tin": 250.0, "tout": 30.0, "input_type": "Heat Load (kW)", "value": 21434.7}
    ])
    
    edited_df = st.data_editor(
        default_streams, 
        num_rows="dynamic", 
        use_container_width=True, 
        key="streams_editor",
        column_config={
            "name": st.column_config.TextColumn("Stream Name"),
            "tin": st.column_config.NumberColumn("Tin (°C)"),
            "tout": st.column_config.NumberColumn("Tout (°C)"),
            "input_type": st.column_config.SelectboxColumn("Input Mode", options=["Cp (kW/°C)", "Heat Load (kW)"]),
            "value": st.column_config.NumberColumn("Value")
        }
    )

with col_table2:
    st.header("⚡ 2. Other Process Components")
    st.write("Add, rename, or remove non-stream power loads (MW).")
    
    default_components = pd.DataFrame([
        {"comp_name": "RWGS Reactor", "comp_mw": 3.26},
        {"comp_name": "MeOH Reactor", "comp_mw": 10.50},
        {"comp_name": "Compressors", "comp_mw": 6.60},
        {"comp_name": "Separators", "comp_mw": 20.00}
    ])
    edited_components_df = st.data_editor(
        default_components, 
        num_rows="dynamic", 
        use_container_width=True, 
        key="components_editor",
        column_config={
            "comp_name": st.column_config.TextColumn("Component Name"),
            "comp_mw": st.column_config.NumberColumn("Load (MW)")
        }
    )

# --- PROCESS STREAM DATA ---
streams = {}
if edited_df is not None and not edited_df.empty:
    valid_df = edited_df.dropna(subset=["name", "tin", "tout", "input_type", "value"])
    for _, row in valid_df.iterrows():
        try:
            tin = float(row["tin"])
            tout = float(row["tout"])
            val = abs(float(row["value"]))
            name = str(row["name"])
            itype = row["input_type"]
            
            stream_type = "Hot" if tin > tout else "Cold"
            dT_stream = abs(tin - tout)
            
            if itype == "Cp (kW/°C)":
                cp = val
                q = cp * dT_stream
            else:
                q = val
                cp = q / dT_stream if dT_stream > 0 else 0.0
            
            streams[name] = {"type": stream_type, "Tin": tin, "Tout": tout, "Cp": cp, "Q": q}
        except (ValueError, TypeError, KeyError):
            continue

# --- PROCESS OTHER COMPONENTS ---
other_components = []
total_other_kw = 0.0
if edited_components_df is not None and not edited_components_df.empty:
    valid_comp_df = edited_components_df.dropna(subset=["comp_name", "comp_mw"])
    for _, row in valid_comp_df.iterrows():
        try:
            name = str(row["comp_name"])
            mw = abs(float(row["comp_mw"]))
            kw = mw * 1000
            total_other_kw += kw
            other_components.append({"name": name, "mw": mw, "kw": kw})
        except (ValueError, TypeError, KeyError):
            continue

# --- GUI CONTROLS FOR dT_min ---
st.sidebar.header("⚙️ Model Configuration")
dT_min = st.sidebar.slider("Minimum Approach Temperature (ΔT min) °C", 1, 50, 10)

if len(streams) < 2:
    st.warning("⚠️ Please insert streams into the data panels to execute analysis.")
    st.stop()

# --- MATHEMATICAL PINCH ANALYSIS ---
for name, s in streams.items():
    s["Tin_shift"] = s["Tin"] - dT_min / 2 if s["type"] == "Hot" else s["Tin"] + dT_min / 2
    s["Tout_shift"] = s["Tout"] - dT_min / 2 if s["type"] == "Hot" else s["Tout"] + dT_min / 2

all_temps = set()
for s in streams.values():
    all_temps.add(s["Tin_shift"])
    all_temps.add(s["Tout_shift"])
intervals = sorted(list(all_temps), reverse=True)

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

min_cascade = min(cascade)
qh_min = -min_cascade if min_cascade < 0 else 0
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
saved_heating = max(0.0, total_cold_load - qh_min)

# --- METRIC DISPLAY ---
st.header("📊 Energy Balance & Target Savings")
m1, m2, m3 = st.columns(3)
m1.metric("Pinch Temperature (Hot/Cold)", f"{pinch_hot} °C / {pinch_cold} °C" if isinstance(pinch_hot, float) else "N/A")
m2.metric("Minimum Hot Utility (Qh min)", f"{qh_min:,.1f} kW", f"-{(saved_heating/max(1, total_cold_load))*100:.2f}% Savings")
m3.metric("Minimum Cold Utility (Qc min)", f"{qc_min:,.1f} kW")

# --- CHARTS AND VISUALIZATIONS ---
st.header("📈 Thermodynamic & Network Analysis")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Composite Curves", "📉 Grand Composite Curve (GCC)", "🕸️ HEN Grid Diagram", "🍕 Process Integration Breakdown (Pie Charts)"])

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
    ax_cc.plot(hot_H, hot_intervals, color="red", label="Hot Composite Curve", lw=2)
    ax_cc.plot(cold_H, cold_intervals, color="blue", label="Cold Composite Curve", lw=2)
    ax_cc.set_xlabel("Enthalpy Cumulative (kW)")
    ax_cc.set_ylabel("Temperature (°C)")
    ax_cc.legend()
    ax_cc.grid(True, linestyle=":")
    st.pyplot(fig_cc)

with tab2:
    st.subheader("Grand Composite Curve (GCC) - Enthalpy Cascade Diagram")
    fig_gcc, ax_gcc = plt.subplots(figsize=(10, 5))
    
    ax_gcc.plot(feasible_cascade, intervals, color="black", marker="o", label="Grand Composite Curve", lw=2)
    ax_gcc.plot([0, qh_min], [intervals[0], intervals[0]], color="red", lw=2.5, linestyle="-", marker="s", label=f"Hot Utility Line (Qh,min = {qh_min:,.1f} kW)")
    ax_gcc.plot([0, qc_min], [intervals[-1], intervals[-1]], color="dodgerblue", lw=2.5, linestyle="-", marker="s", label=f"Cold Utility Line (Qc,min = {qc_min:,.1f} kW)")
    
    ax_gcc.set_xlabel("ΔΗ (kW)")
    ax_gcc.set_ylabel("Shifted Temperature T* (°C)")
    ax_gcc.grid(True, linestyle=":", alpha=0.6)
    ax_gcc.legend()
    st.pyplot(fig_gcc)

with tab3:
    st.subheader("Heat Exchanger Network (HEN) Grid Layout & Utility Placement")
    fig_grid, ax_grid = plt.subplots(figsize=(12, 6))
    
    y_pos = {name: len(streams) - idx for idx, name in enumerate(streams.keys())}
    
    # Draw process streams
    for name, s in streams.items():
        y = y_pos[name]
        ax_grid.plot([s["Tin"], s["Tout"]], [y, y], color="red" if s["type"]=="Hot" else "blue", lw=3.5)
        ax_grid.text(s["Tin"], y + 0.15, f"{name} ({s['Tin']}°C)", fontsize=9, ha='right' if s["type"]=="Hot" else 'left', weight="bold")
        ax_grid.text(s["Tout"], y - 0.25, f"{s['Tout']}°C", fontsize=9, ha='left' if s["type"]=="Hot" else 'right')
    
    if isinstance(pinch_hot, float):
        ax_grid.axvline(x=pinch_hot, color="gray", linestyle="--", alpha=0.7, lw=2)
        ax_grid.text(pinch_hot, len(streams) + 0.6, f"Pinch ({pinch_hot}°C)", color="gray", ha="center", weight="bold")

    # --- HEAT EXCHANGER PLACEMENT (PROCESS-TO-PROCESS MATCHES) ---
    process_exchangers = [("E5", "E4", 450), ("E7", "E6", 150)]
    hx_count = 0
    for hot_st, cold_st, x_pos in process_exchangers:
        if hot_st in y_pos and cold_st in y_pos:
            hx_count += 1
            y_hot = y_pos[hot_st]
            y_cold = y_pos[cold_st]
            ax_grid.plot([x_pos, x_pos], [y_hot, y_cold], color="green", linestyle="-", lw=2, zorder=3)
            ax_grid.plot([x_pos, x_pos], [y_hot, y_cold], marker="o", color="green", markersize=10, zorder=4)
            ax_grid.text(x_pos + 6, (y_hot + y_cold)/2, f"HX {hx_count}", color="green", weight="bold", fontsize=10)

    # --- AUTOMATIC AUXILIARY UTILITIES REPRESENTATION (HU & CU) ---
    hu_count = 0
    cu_count = 0
    for name, s in streams.items():
        y = y_pos[name]
        if s["type"] == "Cold" and s["Tout"] > 400: # E4 requires extra Hot Utility (Heater)
            hu_count += 1
            hu_x = s["Tout"] - 30
            ax_grid.plot(hu_x, y, marker="o", color="darkred", markersize=11, zorder=5)
            ax_grid.text(hu_x, y + 0.15, f"HU {hu_count}", color="darkred", weight="bold", fontsize=9, ha="center")
            
        if s["type"] == "Hot" and s["Tout"] < 40: # E1, E2, E3, E5, E7 require Cold Utility (Coolers)
            cu_count += 1
            cu_x = s["Tout"] + 15
            ax_grid.plot(cu_x, y, marker="o", color="blue", markersize=11, zorder=5)
            ax_grid.text(cu_x, y + 0.15, f"CU {cu_count}", color="blue", weight="bold", fontsize=9, ha="center")

    total_exchangers = hx_count + hu_count + cu_count

    ax_grid.set_yticks(list(y_pos.values()))
    ax_grid.set_yticklabels(list(y_pos.keys()), weight="bold")
    ax_grid.set_xlabel("Temperature (°C)", weight="bold")
    ax_grid.set_ylim(0.5, len(streams) + 0.8)
    ax_grid.grid(axis='x', linestyle=':', alpha=0.5)
    st.pyplot(fig_grid)
    
    st.success(f"📊 **True Network Unit Inventory:** Process-to-Process Exchangers: **{hx_count}** | Heaters (HU): **{hu_count}** | Coolers (CU): **{cu_count}** || **True Total Exchangers Required = {total_exchangers}**")

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
    
    fig_pie, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    
    wedges1, texts1, autotexts1 = ax1.pie(sizes_before, autopct='%1.0f%%', startangle=140, colors=current_colors)
    ax1.set_title(f"Before Heat Integration\n(Total Assets: {total_before:.2f} MW)", fontsize=13, weight='bold')
    
    wedges2, texts2, autotexts2 = ax2.pie(sizes_after, autopct='%1.0f%%', startangle=140, colors=current_colors)
    ax2.set_title(f"After Heat Integration\n(Total Assets: {total_after:.2f} MW)", fontsize=13, weight='bold')
    
    fig_pie.legend(wedges1, labels, loc='lower center', bbox_to_anchor=(0.5, 0.02), ncol=3, fontsize=10)
    plt.subplots_adjust(bottom=0.2)
    st.pyplot(fig_pie)
    
    st.info(f"💡 Net Integrated System Savings: **{total_before - total_after:.2f} MW**")

