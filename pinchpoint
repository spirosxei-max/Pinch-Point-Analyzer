import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(layout="wide")

st.title("🔥 Advanced Pinch Point Analysis & HEN Optimizer")
st.write("Σχεδιασμός Δικτύων Εναλλακτών Θερμότητας με Δυναμικά Ρεύματα και Σύνθετες Καμπύλες")

# --- ΔΥΝΑΜΙΚΟΣ ΠΙΝΑΚΑΣ ΡΕΥΜΑΤΩΝ (USER INPUT) ---
st.header("📋 Δεδομένα Ρευμάτων Εισόδου")
st.write("Μπορείτε να τροποποιήσετε τις τιμές, να προσθέσετε νέες γραμμές στο τέλος του πίνακα ή να διαγράψετε ρεύματα.")

# Αρχικά δεδομένα (Default Data)
default_streams = pd.DataFrame([
    {"Όνομα": "Hot 1", "Τύπος": "Hot", "Tin (°C)": 150.0, "Tout (°C)": 60.0, "Cp (kW/°C)": 20.0},
    {"Όνομα": "Hot 2", "Τύπος": "Hot", "Tin (°C)": 90.0, "Tout (°C)": 60.0, "Cp (kW/°C)": 40.0},
    {"Όνομα": "Cold 1", "Τύπος": "Cold", "Tin (°C)": 50.0, "Tout (°C)": 120.0, "Cp (kW/°C)": 30.0},
    {"Όνομα": "Cold 2", "Τύπος": "Cold", "Tin (°C)": 80.0, "Tout (°C)": 120.0, "Cp (kW/°C)": 60.0}
])

# Χρήση st.data_editor για δυναμική επεξεργασία
edited_df = st.data_editor(
    default_streams, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Τύπος": st.column_config.SelectboxColumn(options=["Hot", "Cold"])
    }
)

# Μετατροπή του DataFrame σε λεξικό για τους υπολογισμούς
streams = {}
for _, row in edited_df.dropna(subset=["Όνομα"]).iterrows():
    streams[row["Όνομα"]] = {
        "type": row["Τύπος"],
        "Tin": row["Tin (°C)"],
        "Tout": row["Tout (°C)"],
        "Cp": row["Cp (kW/°C)"]
    }

# --- GUI CONTROLS FOR dT_min ---
st.sidebar.header("⚙️ Ρυθμίσεις Μοντέλου")
dT_min = st.sidebar.slider("Ελάχιστη Διαφορά Θερμοκρασίας (ΔT min) °C", 1, 50, 10)

if len(streams) < 2:
    st.warning("⚠️ Παρακαλώ προσθέστε τουλάχιστον ένα θερμό και ένα ψυχρό ρεύμα στον πίνακα για να ξεκινήσει η ανάλυση.")
    st.stop()

# --- ΜΑΘΗΜΑΤΙΚΟΣ ΥΠΟΛΟΓΙΣΜΟΣ PINCH ---
# Μετατόπιση θερμοκρασιών (Shifted Temperatures)
for name, s in streams.items():
    if s["type"] == "Hot":
        s["Tin_shift"] = s["Tin"] - dT_min / 2
        s["Tout_shift"] = s["Tout"] - dT_min / 2
    else:
        s["Tin_shift"] = s["Tin"] + dT_min / 2
        s["Tout_shift"] = s["Tout"] + dT_min / 2

# Εύρεση ορίων διαστημάτων
all_temps = set()
for s in streams.values():
    all_temps.add(s["Tin_shift"])
    all_temps.add(s["Tout_shift"])
intervals = sorted(list(all_temps), reverse=True)

# Υπολογισμός ΔΗ για κάθε διάστημα
dh_intervals = []
for i in range(len(intervals) - 1):
    Th = intervals[i]
    Tl = intervals[i+1]
    dT = Th - Tl
    
    cp_hot = sum(s["Cp"] for s in streams.values() if s["type"] == "Hot" and min(s["Tin_shift"], s["Tout_shift"]) <= Tl and max(s["Tin_shift"], s["Tout_shift"]) >= Th)
    cp_cold = sum(s["Cp"] for s in streams.values() if s["type"] == "Cold" and min(s["Tin_shift"], s["Tout_shift"]) <= Tl and max(s["Tin_shift"], s["Tout_shift"]) >= Th)
                
    dh = (cp_hot - cp_cold) * dT
    dh_intervals.append(dh)

# Cascade Algorithm
cascade = [0]
for dh in dh_intervals:
    cascade.append(cascade[-1] - dh)

min_cascade = min(cascade)
qh_min = -min_cascade if min_cascade < 0 else 0
feasible_cascade = [c + qh_min for c in cascade]
qc_min = feasible_cascade[-1]

# Εύρεση Pinch
try:
    pinch_index = feasible_cascade.index(0)
    pinch_temp_shifted = intervals[pinch_index]
    pinch_hot = pinch_temp_shifted + dT_min / 2
    pinch_cold = pinch_temp_shifted - dT_min / 2
except ValueError:
    pinch_hot, pinch_cold = "N/A", "N/A"

# Υπολογισμός Εξοικονόμησης
total_hot_load = sum((s["Tin"] - s["Tout"]) * s["Cp"] for s in streams.values() if s["type"] == "Hot")
total_cold_load = sum((s["Tout"] - s["Tin"]) * s["Cp"] for s in streams.values() if s["type"] == "Cold")

saved_heating = max(0.0, total_cold_load - qh_min)
saved_cooling = max(0.0, total_hot_load - qc_min)

# --- ΕΜΦΑΝΙΣΗ ΑΠΟΤΕΛΕΣΜΑΤΩΝ (METRICS) ---
st.header("📊 Ενεργειακό Ισοζύγιο & Εξοικονόμηση Παροχών")
m1, m2, m3 = st.columns(3)
m1.metric("Θερμοκρασία Pinch (Θερμό / Ψυχρό)", f"{pinch_hot} °C / {pinch_cold} °C" if isinstance(pinch_hot, float) else "Δεν βρέθηκε Pinch")
m2.metric("Ελάχιστη Θέρμανση (Qh min)", f"{qh_min:,.1f} kW", f"-{(saved_heating/max(1, total_cold_load))*100:.1f}% Εξοικονόμηση")
m3.metric("Ελάχιστη Ψύξη (Qc min)", f"{qc_min:,.1f} kW", f"-{(saved_cooling/max(1, total_hot_load))*100:.1f}% Εξοικονόμηση")

# --- ΔΙΑΓΡΑΜΜΑΤΑ (ΓΡΑΦΙΚΑ) ---
st.header("📈 Διαγράμματα Ανάλυσης")

tab1, tab2 = st.tabs(["📊 Composite Curves (Σύνθετες Καμπύλες)", "🕸️ HEN Grid Diagram (Διάγραμμα Πλέγματος)"])

with tab1:
    st.subheader("Σύνθετες Καμπύλες Θερμοκρασίας - Ενθαλπίας (T-H Diagram)")
    
    # Κατασκευή δεδομένων για την Hot Composite Curve
    hot_intervals = sorted(list(set([s["Tin"] for s in streams.values() if s["type"]=="Hot"] + [s["Tout"] for s in streams.values() if s["type"]=="Hot"])), reverse=True)
    hot_H = [0]
    for i in range(len(hot_intervals)-1):
        Th, Tl = hot_intervals[i], hot_intervals[i+1]
        cp_sum = sum(s["Cp"] for s in streams.values() if s["type"]=="Hot" and min(s["Tin"], s["Tout"]) <= Tl and max(s["Tin"], s["Tout"]) >= Th)
        hot_H.append(hot_H[-1] + cp_sum * (Th - Tl))
    
    # Κατασκευή δεδομένων για την Cold Composite Curve (Μετατοπισμένη κατά Qc_min)
    cold_intervals = sorted(list(set([s["Tin"] for s in streams.values() if s["type"]=="Cold"] + [s["Tout"] for s in streams.values() if s["type"]=="Cold"])), reverse=True)
    cold_H = [qc_min]
    for i in range(len(cold_intervals)-1):
        Th, Tl = cold_intervals[i], cold_intervals[i+1]
        cp_sum = sum(s["Cp"] for s in streams.values() if s["type"]=="Cold" and min(s["Tin"], s["Tout"]) <= Tl and max(s["Tin"], s["Tout"]) >= Th)
        cold_H.append(cold_H[-1] + cp_sum * (Th - Tl))
        
    fig_cc, ax_cc = plt.subplots(figsize=(10, 5))
    ax_cc.plot(hot_H, hot_intervals, color="red", label="Hot Composite Curve", lw=2.5)
    ax_cc.plot(cold_H, cold_intervals, color="blue", label="Cold Composite Curve", lw=2.5)
    
    if isinstance(pinch_hot, float):
        ax_cc.axhline(y=pinch_hot, color="gray", linestyle=":", alpha=0.7)
        ax_cc.text(max(hot_H)/2, pinch_hot + 2, f"Pinch T (Hot) = {pinch_hot}°C", color="gray", fontsize=9)
        
    ax_cc.set_xlabel("Enthalpy Cumulative / Heat Load (kW)")
    ax_cc.set_ylabel("Temperature (°C)")
    ax_cc.legend()
    ax_cc.grid(True, linestyle=":", alpha=0.6)
    st.pyplot(fig_cc)

with tab2:
    st.subheader("Διάγραμμα Πλέγματος & Τοποθέτηση Εναλλακτών")
    fig_grid, ax_grid = plt.subplots(figsize=(10, 5))
    
    y_pos = {name: len(streams) - idx for idx, name in enumerate(streams.keys())}
    colors = {"Hot": "red", "Cold": "blue"}
    
    for name, s in streams.items():
        y = y_pos[name]
        ax_grid.plot([s["Tin"], s["Tout"]], [y, y], color=colors[s["type"]], lw=3)
        ax_grid.text(s["Tin"], y + 0.1, f"{name} ({s['Tin']}°C)", fontsize=9, ha='right' if s["type"]=="Hot" else 'left')
        ax_grid.text(s["Tout"], y + 0.1, f"→ {s['Tout']}°C", fontsize=9)
    
    if isinstance(pinch_hot, float):
        ax_grid.axvline(x=pinch_hot, color="black", linestyle="--", alpha=0.6, label=f"Pinch Line ({pinch_hot}°C)")
    
    ax_grid.set_yticks(list(y_pos.values()))
    ax_grid.set_yticklabels(list(y_pos.keys()))
    ax_grid.set_xlabel("Θερμοκρασία (°C)")
    ax_grid.grid(axis='x', linestyle=':', alpha=0.5)
    st.pyplot(fig_grid)
