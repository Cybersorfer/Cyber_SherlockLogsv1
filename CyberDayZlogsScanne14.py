import streamlit as st
import os
import io

# Setup Page Config
st.set_page_config(page_title="CyberDayZ Log Scanner", layout="centered")

def filter_logs(files, main_choice, target_player=None, sub_choice=None):
    all_lines = []
    header = "******************************************************************************\n"
    header += "AdminLog started on Web_Filter_Session\n"

    for uploaded_file in files:
        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
        for line in stringio:
            if "|" in line and ":" in line:
                all_lines.append(line)

    final_output = []
    placement_keys = ["placed", "built", "folded", "shelterfabric", "mounted"]
    session_keys = ["connected", "disconnected", "lost connection", "choosing to respawn"]
    raid_keys = ["dismantled", "unmount", "packed", "barbedwirehit", "fireplace", "gardenplot", "fence kit"]

    if main_choice == "Activity per Specific Player" and target_player:
        for line in all_lines:
            low = line.lower()
            if target_player in line:
                if sub_choice == "Full History": final_output.append(line)
                elif sub_choice == "Movement Only" and "pos=" in low: final_output.append(line)
                elif sub_choice == "Movement + Building":
                    if ("pos=" in low or any(k in low for k in placement_keys)) and "hit" not in low:
                        final_output.append(line)
                elif sub_choice == "Movement + Raid Watch":
                    if ("pos=" in low or any(k in low for k in raid_keys)) and "built" not in low:
                        final_output.append(line)
                elif sub_choice == "Session Tracking" and any(k in low for k in session_keywords):
                    final_output.append(line)

    elif main_choice == "All Death Locations":
        final_output = [l for l in all_lines if any(x in l.lower() for x in ["killed", "died", "suicide", "bled out"])]
    elif main_choice == "All Placements":
        final_output = [l for l in all_lines if any(x in l.lower() for x in placement_keys)]
    elif main_choice == "Session Tracking (Global)":
        final_output = [l for l in all_lines if any(x in l.lower() for x in session_keys)]
    elif main_choice == "RAID WATCH (Global)":
        final_output = [l for l in all_lines if any(x in l.lower() for x in raid_keys) and "built" not in l.lower()]

    final_output.sort()
    return header + "".join(final_output)

# --- WEB UI ---
st.title("🛡️ CyberDayZ Log Scanner")
st.markdown("Upload your **.ADM** or **.RPT** files to generate iZurvive-ready filters.")

uploaded_files = st.file_with_container = st.file_uploader("Choose Admin Logs", type=['adm', 'rpt'], accept_multiple_files=True)

if uploaded_files:
    st.sidebar.header("Filter Settings")
    mode = st.sidebar.selectbox("Main Menu", [
        "Activity per Specific Player", 
        "All Death Locations", 
        "All Placements", 
        "Session Tracking (Global)", 
        "RAID WATCH (Global)"
    ])

    target_player = None
    sub_choice = None

    if mode == "Activity per Specific Player":
        # Extract players for the dropdown
        temp_all = []
        for f in uploaded_files:
            temp_all.extend(f.getvalue().decode("utf-8", errors="ignore").splitlines())
        
        player_list = sorted(list(set(line.split('"')[1] for line in temp_all if 'Player "' in line)))
        target_player = st.sidebar.selectbox("Select Player", player_list)
        sub_choice = st.sidebar.radio("Detail Level", [
            "Full History", "Movement Only", "Movement + Building", "Movement + Raid Watch", "Session Tracking"
        ])

    if st.button("Process Logs"):
        result = filter_logs(uploaded_files, mode, target_player, sub_choice)
        
        st.text_area("Preview (First 500 chars)", result[:500], height=200)
        
        st.download_button(
            label="💾 Download Filtered File",
            data=result,
            file_name="FILTERED_LOG.adm",
            mime="text/plain"
        )