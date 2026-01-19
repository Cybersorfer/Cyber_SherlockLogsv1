import streamlit as st
import io
import math
from datetime import datetime
import streamlit.components.v1 as components

# 1. Setup Page Config
st.set_page_config(page_title="CyberDayZ Log Scanner", layout="wide")

# 2. CSS: Forced Dark Mode and Rounded UI
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    #MainMenu, header, footer { visibility: hidden; }
    [data-testid="stFileUploader"] {
        background-color: #161b22;
        border: 1px solid #31333F;
        border-radius: 15px;
        padding: 20px;
    }
    div.stButton > button, div.stLinkButton > a {
        background-color: #262730 !important;
        color: #ffffff !important;
        border: 1px solid #4b4b4b !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0.5rem 1rem !important;
    }
    div.stButton > button:hover, div.stLinkButton > a:hover {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
    }
    .death-log { color: #ff4b4b; font-weight: bold; border-left: 3px solid #ff4b4b; padding-left: 10px; }
    .connect-log { color: #28a745; border-left: 3px solid #28a745; padding-left: 10px; }
    .disconnect-log { color: #ffc107; border-left: 3px solid #ffc107; padding-left: 10px; }
    .block-container { padding-top: 0rem !important; max-width: 100%; }
    @media (min-width: 768px) {
        [data-testid='column'] { 
            height: 90vh !important; 
            overflow-y: auto !important; 
            padding: 15px;
            border: 1px solid #31333F;
            border-radius: 12px;
            background-color: #0d1117;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Helper Functions
def make_izurvive_link(coords):
    if coords and isinstance(coords, list) and len(coords) >= 2:
        return f"https://www.izurvive.com/chernarusplus/#location={coords[0]};{coords[1]}"
    return ""

def extract_player_and_coords(line):
    name = "System/Server"
    coords = None
    try:
        if 'Player "' in line:
            name = line.split('Player "')[1].split('"')[0]
        if "pos=<" in line:
            raw = line.split("pos=<")[1].split(">")[0]
            parts = [p.strip() for p in raw.split(",")]
            coords = [float(parts[0]), float(parts[1])]
    except:
        pass 
    return str(name), coords

# 4. Filter Logic
def filter_logs(files, mode, target_player=None):
    grouped_report = {} 
    player_positions = {} 
    boosting_tracker = {}
    raw_filtered_lines = []
    audit_log_entries = []
    
    header = "AdminLog started on 00:00:00\n******************************************************************************\n"
    audit_header = f"--- CYBERDAYZ SUSPICIOUS ACTIVITY AUDIT ---\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    all_lines = []
    for uploaded_file in files:
        content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        all_lines.extend(content.splitlines())

    # Filter Sets
    placement_keys = ["placed", "built", "folded", "shelterfabric", "mounted", "kit"]
    raid_keys = ["dismantled", "unmount", "packed", "barbedwirehit"]
    session_keys = ["connected", "disconnected", "connecting", "died", "killed", "bled out", "suicide"]
    stacking_objects = ["placed fence kit", "placed nameless object", "placed fireplace"]

    for line in all_lines:
        if "|" not in line: continue
        
        name, coords = extract_player_and_coords(line)
        if name != "System/Server" and coords:
            player_positions[name] = coords

        low = line.lower()
        should_process = False

        # --- MODES ---
        if mode == "Full Activity per Player" and target_player == name:
            should_process = True
        
        elif mode == "Session Tracking (Global)":
            if any(k in low for k in session_keys): should_process = True

        elif mode == "Building Only (Global)":
            if any(k in low for k in placement_keys) and "pos=" not in low: should_process = True

        elif mode == "Raid Watch (Global)":
            if any(k in low for k in raid_keys) and "pos=" not in low: should_process = True

        elif mode == "Suspicious Boosting Activity":
            time_str = line.split(" | ")[0]
            try: current_time = datetime.strptime(time_str, "%H:%M:%S")
            except: continue

            if any(obj in low for obj in stacking_objects):
                if name not in boosting_tracker: boosting_tracker[name] = []
                boosting_tracker[name].append(current_time)
                if len(boosting_tracker[name]) >= 3:
                    time_diff = (boosting_tracker[name][-1] - boosting_tracker[name][-3]).total_seconds()
                    if time_diff <= 60:
                        should_process = True
                        audit_log_entries.append(f"[{time_str}] ALERT: {name} placed 3+ objects in {time_diff}s at {coords}")
            elif any(reset in low for reset in ["folded fence", "dismantled", "packed"]):
                boosting_tracker[name] = []

        # iZurvive Structure Fix & UI Processing
        if should_process:
            last_pos = player_positions.get(name)
            link = make_izurvive_link(last_pos)
            
            # Formatting for iZurvive Log Parser
            if "pos=<" in line:
                raw_filtered_lines.append("##### PlayerList log: 1 players")
                raw_filtered_lines.append(line)
                raw_filtered_lines.append("#####")
            else:
                raw_filtered_lines.append(line)

            if link.startswith("http"):
                status = "normal"
                if mode == "Suspicious Boosting Activity": status = "death" 
                elif any(d in low for d in ["died", "killed", "suicide", "bled out"]): status = "death"
                elif "connect" in low: status = "connect"
                elif "disconnect" in low: status = "disconnect"

                event_entry = {"time": str(line.split(" | ")[0]), "text": str(line.strip()), "link": link, "status": status}
                if name not in grouped_report: grouped_report[name] = []
                grouped_report[name].append(event_entry)
    
    return grouped_report, header + "\n".join(raw_filtered_lines), audit_header + "\n".join(audit_log_entries)

# --- WEB UI ---
st.markdown("#### 🛡️ CyberDayZ Scanner")
col1, col2 = st.columns([1, 2.3])

with col1:
    uploaded_files = st.file_uploader("Upload .ADM", type=['adm', 'rpt'], accept_multiple_files=True)

    if uploaded_files:
        mode = st.selectbox("Select Filter", [
            "Full Activity per Player", 
            "Session Tracking (Global)", 
            "Building Only (Global)", 
            "Raid Watch (Global)", 
            "Suspicious Boosting Activity"
        ])
        
        target_player = None
        if mode == "Full Activity per Player":
            temp_all = []
            for f in uploaded_files:
                temp_all.extend(f.getvalue().decode("utf-8", errors="ignore").splitlines())
            player_list = sorted(list(set(line.split('"')[1] for line in temp_all if 'Player "' in line)))
            target_player = st.selectbox("Select Player", player_list)

        if st.button("🚀 Process"):
            report, raw_file, audit_file = filter_logs(uploaded_files, mode, target_player)
            st.session_state.track_data = report
            st.session_state.raw_download = raw_file
            st.session_state.audit_download = audit_file

    if "track_data" in st.session_state:
        st.download_button("💾 Download Filtered ADM", data=st.session_state.raw_download, file_name="CYBER_FILTERED.adm")
        if st.session_state.get("audit_download"):
            st.download_button("🚨 Download Audit Log", data=st.session_state.audit_download, file_name="SUSPICIOUS_AUDIT.txt")
        
        st.subheader("📍 Player Activity Results")
        for p in sorted(st.session_state.track_data.keys()):
            events = st.session_state.track_data[p]
            with st.expander(f"👤 {p} ({len(events)} events)"):
                for ev in events:
                    st.caption(f"🕒 {ev['time']}")
                    st.markdown(f"<div class='{ev['status']}-log'>{ev['text']}</div>", unsafe_allow_html=True)
                    st.link_button("📍 View on Map", ev['link'])
                    st.divider()

with col2:
    if st.button("🔄 Refresh Map"): st.session_state.mv = st.session_state.get('mv', 0) + 1
    m_url = f"https://www.izurvive.com/serverlogs/?v={st.session_state.get('mv', 0)}"
    components.iframe(m_url, height=1000, scrolling=True)
