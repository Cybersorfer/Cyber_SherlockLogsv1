import streamlit as st
import io
import math
from datetime import datetime
import streamlit.components.v1 as components

# 1. Setup Page Config
st.set_page_config(page_title="CyberDayZ Log Scanner", layout="wide")

# 2. CSS: Professional Dark UI
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
        display: inline-flex !important;
        padding: 0.5rem 1rem !important;
    }
    .death-log { color: #ff4b4b; font-weight: bold; border-left: 3px solid #ff4b4b; padding-left: 10px; }
    .connect-log { color: #28a745; border-left: 3px solid #28a745; padding-left: 10px; }
    .disconnect-log { color: #ffc107; border-left: 3px solid #ffc107; padding-left: 10px; }
    .block-container { padding-top: 0rem !important; max-width: 100%; }
    @media (min-width: 768px) {
        [data-testid='column'] { 
            height: 92vh !important; overflow-y: auto !important; 
            padding: 15px; border: 1px solid #31333F; border-radius: 12px; background-color: #0d1117;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Core Functions
def make_izurvive_link(coords):
    if coords and len(coords) >= 2:
        return f"https://www.izurvive.com/chernarusplus/#location={coords[0]};{coords[1]}"
    return ""

def extract_player_and_coords(line):
    name, coords = "System/Server", None
    try:
        # Handles standard and prefixed logs 
        if 'Player "' in line: 
            name = line.split('Player "')[1].split('"')[0]
        if "pos=<" in line:
            raw = line.split("pos=<")[1].split(">")[0]
            parts = [p.strip() for p in raw.split(",")]
            # X, Z are horizontal planes for iZurvive 
            coords = [float(parts[0]), float(parts[1])] 
    except: pass 
    return str(name), coords

def calculate_distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# 4. Filter Logic Implementation
def filter_logs(files, mode, target_player=None):
    grouped_report, player_positions, boosting_tracker = {}, {}, {}
    raw_filtered_lines, debug_log_entries = [], []
    
    header = "AdminLog started on 00:00:00\n******************************************************************************\n"
    debug_header = f"--- DEBUG REPORT: {mode} ---\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    all_lines = []
    for uploaded_file in files:
        content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        all_lines.extend(content.splitlines())

    # Keywords refined from your example file 
    building_keys = ["placed", "built", "built base", "built wall", "built gate", "built platform"]
    raid_keys = ["dismantled", "folded", "unmount", "unmounted", "packed"]
    session_keys = ["connected", "disconnected", "died", "killed"]
    boosting_objects = ["fence kit", "nameless object", "fireplace", "garden plot", "barrel"]

    for line in all_lines:
        if "|" not in line: continue
        name, coords = extract_player_and_coords(line)
        if name != "System/Server" and coords: player_positions[name] = coords

        low = line.lower()
        should_process = False

        if mode == "Full Activity per Player":
            if target_player == name: should_process = True

        elif mode == "Building Only (Global)":
            if any(k in low for k in building_keys) and "pos=" in low:
                should_process = True
        
        elif mode == "Raid Watch (Global)":
            if any(k in low for k in raid_keys) and "pos=" in low:
                should_process = True
            
        elif mode == "Session Tracking (Global)":
            if any(k in low for k in session_keys): should_process = True

        elif mode == "Suspicious Boosting Activity":
            time_str = line.split(" | ")[0].split("]")[-1].strip() # Handles time shift 
            try: current_time = datetime.strptime(time_str, "%H:%M:%S")
            except: continue

            if any(k in low for k in ["placed", "built"]) and any(obj in low for obj in boosting_objects):
                if name not in boosting_tracker: boosting_tracker[name] = []
                boosting_tracker[name].append({"time": current_time, "pos": coords})
                
                # Alert if 3 items placed within 10 meters in under 3 minutes 
                if len(boosting_tracker[name]) >= 3:
                    prev = boosting_tracker[name][-3]
                    time_diff = (current_time - prev["time"]).total_seconds()
                    dist = calculate_distance(coords, prev["pos"]) if coords and prev["pos"] else 999
                    
                    if time_diff <= 180 and dist < 10:
                        should_process = True

        if should_process:
            last_pos = player_positions.get(name)
            link = make_izurvive_link(last_pos)
            debug_log_entries.append(f"MATCH: {line.strip()}")
            
            # iZurvive ADM wrapping logic [cite: 1]
            if "pos=<" in line:
                raw_filtered_lines.append("##### PlayerList log: 1 players")
                raw_filtered_lines.append(line)
                raw_filtered_lines.append("#####")
            else:
                raw_filtered_lines.append(line)

            if link.startswith("http"):
                status = "normal"
                if mode == "Suspicious Boosting Activity": status = "death"
                elif any(d in low for d in ["died", "killed"]): status = "death"
                elif "connect" in low: status = "connect"
                elif "disconnect" in low: status = "disconnect"

                event_entry = {"time": time_str, "text": str(line.strip()), "link": link, "status": status}
                if name not in grouped_report: grouped_report[name] = []
                grouped_report[name].append(event_entry)
    
    return grouped_report, header + "\n".join(raw_filtered_lines), debug_header + "\n".join(debug_log_entries)

# --- USER INTERFACE ---
st.markdown("#### 🛡️ CyberDayZ Scanner v26")
col1, col2 = st.columns([1, 2.3])

with col1:
    uploaded_files = st.file_uploader("Upload Admin Logs", type=['adm', 'rpt'], accept_multiple_files=True)
    if uploaded_files:
        mode = st.selectbox("Select Filter", ["Full Activity per Player", "Session Tracking (Global)", "Building Only (Global)", "Raid Watch (Global)", "Suspicious Boosting Activity"])
        target_player = None
        if mode == "Full Activity per Player":
            all_content = [f.getvalue().decode("utf-8", errors="ignore") for f in uploaded_files]
            player_list = sorted(list(set(line.split('"')[1] for c in all_content for line in c.splitlines() if 'Player "' in line)))
            target_player = st.selectbox("Select Player", player_list)

        if st.button("🚀 Process"):
            report, raw_file, debug_file = filter_logs(uploaded_files, mode, target_player)
            st.session_state.track_data, st.session_state.raw_download, st.session_state.debug_download = report, raw_file, debug_file

    if "track_data" in st.session_state:
        st.download_button("💾 Export iZurvive ADM", data=st.session_state.raw_download, file_name="CYBER_IZURVIVE.adm")
        st.download_button("📂 Download Debug Report", data=st.session_state.debug_download, file_name="SCAN_DEBUG_REPORT.txt")
        
        for p in sorted(st.session_state.track_data.keys()):
            with st.expander(f"👤 {p} ({len(st.session_state.track_data[p])} events)"):
                for ev in st.session_state.track_data[p]:
                    st.caption(f"🕒 {ev['time']}")
                    st.markdown(f"<div class='{ev['status']}-log'>{ev['text']}</div>", unsafe_allow_html=True)
                    st.link_button("📍 View on Map", ev['link'])
                    st.divider()

with col2:
    if st.button("🔄 Refresh Map"): st.session_state.mv = st.session_state.get('mv', 0) + 1
    m_url = f"https://www.izurvive.com/serverlogs/?v={st.session_state.get('mv', 0)}"
    components.iframe(m_url, height=1000, scrolling=True)
