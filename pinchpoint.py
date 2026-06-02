import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(layout="wide")

st.title("🔥 Advanced Pinch Point Analysis & HEN Optimizer")
st.write("Σχεδιασμός Δικτύων Εναλλακτών Θερμότητας με Δυναμικά Ρεύματα, Δυναμικά Φορτία Μονάδας & GCC")

# --- ΤΑΜΠΛΟ ΔΕΔΟΜΕΝΩΝ (2 ΠΙΝΑΚΕΣ) ---
col_table1, col_table2 = st.columns()

with col_table1:
    st.header("📋 1. Δεδομένα Ρευμάτων Εισόδου")
    st.write("Εισάγετε τα ρεύματα με βάση το Θερμικό Φορτίο (kW) όπως στο PDF.")
    
    # Χρησιμοποιούμε απλά ονόματα στηλών (English keys) για ασφάλεια στον κώδικα
    default_streams = pd.DataFrame([
        {"name": "E1", "tin": 133.0, "tout": 20.0, "q_load": 594.0},
        {"name": "E2", "tin": 116.0, "tout": 25.0, "q_load": 890.8},
        {"name": "E3", "tin": 116.0, "tout": 25.0, "q_load": 891.3},
        {"name": "E4", "tin": 113.0, "tout": 725.0, "q_load": 13969.0},
        {"name": "E5", "tin": 725.0, "tout": 25.0, "q_load": 19310.1},
        {"name": "E6", "tin": 58.0, "tout": 250.0, "q_load": 14518.1},
        {"name": "E7", "tin": 250.0, "tout": 30.0, "q_load": 21434.7}
    ])
    
    # Αλλάζουμε ΜΟΝΟ την εμφάνιση των τίτλων για τον χρήστη
    edited_df = st.data_editor(
        default_streams, 
        num_rows="dynamic", 
        use_container_width=True, 
        key="streams_editor",
        column_config={
            "name": st.column_config.TextColumn("Όνομα"),
            "tin": st.column_config.NumberColumn("Tin (°C)"),
            "tout": st.column_config.NumberColumn("Tout (°C)"),
            "q_load": st.column_config.NumberColumn("Φορτίο Q (kW)")
        }
    )

with col_table2:
    st.header("⚡ 2. Λοιπά Φορτία Διεργασίας")
    st.write("Προσθέστε, μετονομάστε ή αφαιρέστε καταναλωτές ενέργειας (MW).")
    
    default_components = pd.DataFrame([
        {"comp_name": "Αντιδραστήρας RWGS", "comp_mw": 3.26},
        {"comp_name": "Αντιδραστήρας Μεθανόλης", "comp_mw": 10.50},
        {"comp_name": "Συμπιεστές", "comp_mw": 6.60},
        {"comp_name": "Διεργασίες Διαχωρισμού", "comp_mw": 20.00}
    ])
    edited_components_df = st.data_editor(
        default_components, 
        num_rows="dynamic", 
        use_container_width=True, 
        key="components_editor",
        column_config={
            "comp_name": st.column_config.TextColumn("Όνομα Εξαρτήματος"),
            "comp_mw": st.column_config.NumberColumn("Φορτίο (MW)")
        }
    )

# --- ΑΣΦΑΛΗΣ ΕΠΕΞΕΡΓΑΣΙΑ ΔΕΔΟΜΕΝΩΝ ΡΕΥΜΑΤΩΝ ---
streams = {}
if edited_df is not None and not edited_df.empty:
    valid_df = edited_df.dropna(subset=["name", "tin", "tout", "q_load"])
    for _, row in valid_df.iterrows():
        try:
            tin = float(row["tin"])
            tout = float(row["tout"])
            q = abs(float(row["q_load"]))
            name = str(row["name"])
            
            stream_type = "Hot" if tin > tout else "Cold"
            dT_stream = abs(tin - tout)
            cp = q / dT_stream if dT_stream > 0 else 0.0
            
            streams[name] = {"type": stream_type, "Tin": tin, "Tout": tout, "Cp": cp, "Q": q}
        except (ValueError, TypeError, KeyError):
            continue # Αγνοεί τυχόν μισοσυμπληρωμένες γραμμές χωρίς να κρασάρει

# --- ΑΣΦΑΛΗΣ ΕΠΕΞΕΡΓΑΣΙΑ ΔΕΔΟΜΕΝΩΝ ΛΟΙΠΩΝ ΕΞΑΡΤΗΜΑΤΩΝ ---
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
st.sidebar.header("⚙️ Ρυθμίσεις Μοντέλου")
dT_min = st.sidebar.slider("Ελάχιστη Διαφορά Θερμοκρασίας (ΔT min) °C", 1, 50, 10)

if len(streams) < 2:
    st.warning("⚠️ Παρακαλώ εισάγετε ρεύματα στους πίνακες.")
    st.stop()

# --- ΜΑΘΗΜΑΤΙΚΟΣ ΥΠΟΛΟΓΙΣΜΟΣ PINCH ---
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

# --- ΕΜΦΑΝΙΣΗ ΑΠΟΤΕΛΕΣΜΑΤΩΝ ---
st.header("📊 Ενεργειακό Ισοζύγιο & Εξοικονόμηση")
m1, m2, m3 = st.columns(3)
m1.metric("Θερμοκρασία Pinch (Hot/Cold)", f"{pinch_hot} °C / {pinch_cold} °C" if isinstance(pinch_hot, float) else "N/A")
m2.metric("Ελάχιστη Θέρμανση (Qh min)", f"{qh_min:,.1f} kW", f"-{(saved_heating/max(1, total_cold_load))*100:.2f}%")
m3.metric("Ελάχιστη Ψύξη (Qc min)", f"{qc_min:,.1f} kW")

# --- ΔΙΑΓΡΑΜΜΑΤΑ ---
st.header("📈 Διαγράμματα Ανάλυσης")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Composite Curves", "📉 Grand Composite Curve (GCC)", "🕸️ HEN Grid Diagram", "🍕 Σύγκριση Διεργασίας (Pie Charts)"])

with tab1:
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
    st.subheader("Grand Composite Curve (GCC) - Διάγραμμα Καταρράκτη Ενέργειας")
    fig_gcc, ax_gcc = plt.subplots(figsize=(10, 5))
    
    ax_gcc.plot(feasible_cascade, intervals, color="black", marker="o", label="Grand Composite Curve", lw=2)
    ax_gcc.plot(qc_min, intervals[-1], marker="o", color="dodgerblue", markersize=8, label=f"Qc,min = {qc_min:,.1f} kW")
    ax_gcc.plot(qh_min, intervals[0], marker="o", color="red", markersize=8, label=f"Qh,min = {qh_min:,.1f} kW")
    
    ax_gcc.set_xlabel("ΔΗ (kW)")
    ax_gcc.set_ylabel("Shifted Temperature T (°C)")
    ax_gcc.grid(True, linestyle=":", alpha=0.6)
    ax_gcc.legend()
    st.pyplot(fig_gcc)

with tab3:
    fig_grid, ax_grid = plt.subplots(figsize=(10, 4))
    y_pos = {name: len(streams) - idx for idx, name in enumerate(streams.keys())}
    for name, s in streams.items():
        y = y_pos[name]
        ax_grid.plot([s["Tin"], s["Tout"]], [y, y], color="red" if s["type"]=="Hot" else "blue", lw=3)
        ax_grid.text(s["Tin"], y + 0.1, f"{name} ({s['Tin']}°C)", fontsize=8, ha='right' if s["type"]=="Hot" else 'left')
    if isinstance(pinch_hot, float):
        ax_grid.axvline(x=pinch_hot, color="black", linestyle="--", alpha=0.5)
    ax_grid.set_yticks(list(y_pos.values()))
    ax_grid.set_yticklabels(list(y_pos.keys()))
    st.pyplot(fig_grid)

with tab4:
    st.subheader("Κατανομή Ενεργειακών Απαιτήσεων βάσει των Δυναμικών Εξαρτημάτων")
    
    labels = ['Θέρμανση Ρευμάτων (Hot Utilities)'] + [c["name"] for c in other_components]
    sizes_before = [total_cold_load / 1000] + [c["mw"] for c in other_components]
    sizes_after = [qh_min / 1000] + [c["mw"] for c in other_components]
    
    total_before = sum(sizes_before)
    total_after = sum(sizes_after)
    
    fig_pie, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    ax1.pie(sizes_before, labels=labels, autopct='%1.1f%%', startangle=140)
    ax1.set_title(f"ΠΡΙΝ την Ολοκλήρωση\n(Σύνολο: {total_before:.2f} MW)")
    
    ax2.pie(sizes_after, labels=labels, autopct='%1.1f%%', startangle=140)
    ax2.set_title(f"ΜΕΤΑ την Ολοκλήρωση\n(Σύνολο: {total_after:.2f} MW)")
    
    st.pyplot(fig_pie)
