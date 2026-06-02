import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(layout="wide")

st.title("🔥 Advanced Pinch Point Analysis & HEN Optimizer")
st.write("Σχεδιασμός Δικτύων Εναλλακτών Θερμότητας με βάση Θερμικά Φορτία (kW) & Διάγραμμα Πίτας CAMERE")

# --- ΔΥΝΑΜΙΚΟΣ ΠΙΝΑΚΑΣ ΡΕΥΜΑΤΩΝ (ΥΠΟΛΟΓΙΣΜΟΣ ΜΕ ΒΑΣΗ ΦΟΡΤΙΑ kW) ---
st.header("📋 Δεδομένα Ρευμάτων Εισόδου")
st.write("Εισάγετε τα ρεύματα με βάση το Θερμικό Φορτίο (kW) όπως στο PDF. Το Cp υπολογίζεται αυτόματα.")

# Αρχικά δεδομένα από το PDF (CAMERE Process - Μετατροπή σε θετικά load και σωστό τύπο)
# Σημείωση: Αν Tout < Tin είναι Hot (ψύχεται), αν Tout > Tin είναι Cold (θερμαίνεται)
default_streams = pd.DataFrame([
    {"Όνομα": "E1", "Tin (°C)": 133.0, "Tout (°C)": 20.0, "Φορτίο Q (kW)": 594.0},
    {"Όνομα": "E2", "Tin (°C)": 116.0, "Tout (°C)": 25.0, "Φορτίο Q (kW)": 890.8},
    {"Όνομα": "E3", "Tin (°C)": 116.0, "Tout (°C)": 25.0, "Φορτίο Q (kW)": 891.3},
    {"Όνομα": "E4", "Tin (°C)": 113.0, "Tout (°C)": 725.0, "Φορτίο Q (kW)": 13969.0},
    {"Όνομα": "E5", "Tin (°C)": 725.0, "Tout (°C)": 25.0, "Φορτίο Q (kW)": 19310.1},
    {"Όνομα": "E6", "Tin (°C)": 58.0, "Tout (°C)": 250.0, "Φορτίο Q (kW)": 14518.1},
    {"Όνομα": "E7", "Tin (°C)": 250.0, "Tout (°C)": 30.0, "Φορτίο Q (kW)": 21434.7}
])

edited_df = st.data_editor(default_streams, num_rows="dynamic", use_container_width=True)

# Μετατροπή δεδομένων και αυτόματος υπολογισμός Cp και Τύπου
streams = {}
for _, row in edited_df.dropna(subset=["Όνομα"]).iterrows():
    tin = row["Tin (°C)"]
    tout = row["Tout (°C)"]
    q = abs(row["Φορτίο Q (kW)"])
    
    # Αυτόματος καθορισμός τύπου ρεύματος
    stream_type = "Hot" if tin > tout else "Cold"
    
    # Αποφυγή διαίρεσης με το μηδέν αν Tin == Tout
    dT_stream = abs(tin - tout)
    cp = q / dT_stream if dT_stream > 0 else 0.0
    
    streams[row["Όνομα"]] = {
        "type": stream_type,
        "Tin": tin,
        "Tout": tout,
        "Cp": cp,
        "Q": q
    }

# --- GUI CONTROLS FOR dT_min ---
st.sidebar.header("⚙️ Ρυθμίσεις Μοντέλου")
dT_min = st.sidebar.slider("Ελάχιστη Διαφορά Θερμοκρασίας (ΔT min) °C", 1, 50, 10)

# --- ΛΟΙΠΕΣ ΕΝΕΡΓΕΙΑΚΕΣ ΑΠΑΙΤΗΣΕΙΣ (ΑΠΟ PDF) ---
st.sidebar.subheader("⚡ Λοιπά Φορτία Διεργασίας (MW)")
rwgs_load = st.sidebar.number_input("Αντιδραστήρας RWGS (MW)", value=3.26) * 1000  # Μετατροπή σε kW
meth_load = st.sidebar.number_input("Αντιδραστήρας Μεθανόλης (MW)", value=10.5) * 1000 # Απόλυτη τιμή kW
comp_load = st.sidebar.number_input("Συμπιεστές (MW)", value=6.6) * 1000
sep_load = st.sidebar.number_input("Διεργασίες Διαχωρισμού (MW)", value=20.0) * 1000

if len(streams) < 2:
    st.warning("⚠️ Παρακαλώ εισάγετε ρεύματα στον πίνακα.")
    st.stop()

# --- ΜΑΘΗΜΑΤΙΚΟΣ ΥΠΟΛΟΓΙΣΜΟΣ PINCH ---
for name, s in streams.items():
    if s["type"] == "Hot":
        s["Tin_shift"] = s["Tin"] - dT_min / 2
        s["Tout_shift"] = s["Tout"] - dT_min / 2
    else:
        s["Tin_shift"] = s["Tin"] + dT_min / 2
        s["Tout_shift"] = s["Tout"] + dT_min / 2

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
tab1, tab2, tab3 = st.tabs(["📊 Composite Curves", "🕸️ HEN Grid Diagram", "🍕 Σύγκριση Διεργασίας (Pie Charts)"])

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
    ax_cc.legend()
    ax_cc.grid(True, linestyle=":")
    st.pyplot(fig_cc)

with tab2:
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

with tab3:
    st.subheader("Κατανομή Ενεργειακών Απαιτήσεων (Πριν vs Μετά το HEN)")
    
    # Υπολογισμός Συνολικών Καταναλώσεων σε MW για τα Pie Charts
    # Πριν: Όλες οι ανάγκες θέρμανσης των ρευμάτων + RWGS + Συμπιεστές + Διαχωρισμός
    total_before = (total_cold_load + rwgs_load + comp_load + sep_load) / 1000
    # Μετά: Η Qh_min + RWGS + Συμπιεστές + Διαχωρισμός
    total_after = (qh_min + rwgs_load + comp_load + sep_load) / 1000
    
    labels = ['Θέρμανση Ρευμάτων (Hot Utilities)', 'Αντιδραστήρας RWGS', 'Συμπιεστές', 'Διεργασίες Διαχωρισμού']
    sizes_before = [total_cold_load/1000, rwgs_load/1000, comp_load/1000, sep_load/1000]
    sizes_after = [qh_min/1000, rwgs_load/1000, comp_load/1000, sep_load/1000]
    colors_pie = ['#ff9999','#66b3ff','#99ff99','#ffcc99']
    
    fig_pie, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    ax1.pie(sizes_before, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors_pie)
    ax1.set_title(f"ΠΡΙΝ την Ολοκλήρωση\n(Σύνολο: {total_before:.2f} MW)")
    
    ax2.pie(sizes_after, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors_pie)
    ax2.set_title(f"ΜΕΤΑ την Ολοκλήρωση\n(Σύνολο: {total_after:.2f} MW)")
    
    st.pyplot(fig_pie)
    st.info(f"💡 Συνολική μείωση απαιτούμενης ισχύος της μονάδας: **{total_before - total_after:.2f} MW**")
