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
    }
    .death-log { color: #ff4b4b; font-weight: bold; border-left: 3px solid #ff4b4b; padding-left: 10px; }
    .connect-log { color: #28a745; border-left: 3px solid #28a745; padding-left: 10px; }
    .disconnect-log { color: #ffc107; border-left: 3px solid #ffc107; padding-left: 10px; }
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
        # Extract name
        if 'Player "' in line: 
            name = line.split('Player "')[1].split('"')[0]
        # Extract pos=<X, Z, Y> format
        if "pos=<" in line:
            raw = line.split("pos=<")[1].split(">")[0]
            parts = [p.strip() for p in raw.split(",")]
            coords = [float(parts[0]), float(parts[1])] 
    except: pass 
    return str(name), coords

def calculate_distance(p1, p2):
    if not p1 or not p2: return 999
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# 4. Filter Logic Implementation
def filter_logs(files, mode, target_player=None):
    grouped_report, player_positions, boosting_tracker = {}, {}, {}
    raw_filtered_lines, debug_log_entries = [], []
    
    # Matching the exact header from your example file
    header = "******************************************************************************\nAdminLog started on 2026-01-19 at 08:43:52\n\n"
    debug_header = f"--- DEBUG REPORT: {mode} ---\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    all_lines = []
    for uploaded_file in files:
        content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        all_lines.extend(content.splitlines())

    # Keywords strictly based on your provided ADM samples
    building_keys = ["placed", "built", "built base", "built wall", "built gate", "built platform"]
    raid_keys = ["dismantled", "folded", "unmount", "unmounted", "packed"]
    session_keys = ["connected", "disconnected", "died", "killed"]
    boosting_objects = ["fence kit", "nameless object", "fireplace", "garden plot", "barrel"]

    for i, line in enumerate(all_lines):
        if "|" not in line: continue
        
        # Clean the timestamp by removing the prefix if present
        time_part = line.split(" | ")[0]
        clean_time = time_part.split("]")[-1].strip() if "]" in time_part else time_part.strip()
        
        name, coords = extract_player_and_coords(line)
        if name != "System/Server" and coords: player_positions[name] = coords

        low = line.lower()
        should_process = False

        if mode == "Full Activity per Player":
            if target_player == name: should_process = True
        elif mode == "Building Only (Global)":
            if any(k in low for k in building_keys) and "pos=" in low: should_process = True
        elif mode == "Raid Watch (Global)":
            if any(k in low for k in raid_keys) and "pos=" in low: should_process = True
        elif mode == "Session Tracking (Global)":
            if any(k in low for k in session_keys): should_process = True
        elif mode == "Suspicious Boosting Activity":
            try: current_time = datetime.strptime(clean_time, "%H:%M:%S")
            except: continue

            if any(k in low for k in ["placed", "built"]) and any(obj in low for obj in boosting_objects):
                if name not in boosting_tracker: boosting_tracker[name] = []
                boosting_tracker[name].append({"time": current_time, "pos": coords})
                
                # Logic: 3 items within 15 meters in under 5 minutes
                if len(boosting_tracker[name]) >= 3:
                    prev = boosting_tracker[name][-3]
                    time_diff = (current_time - prev["time"]).total_seconds()
                    dist = calculate_distance(coords, prev["pos"])
                    if time_diff <= 300 and dist < 15:
                        should_process = True

        if should_process:
            last_pos = player_positions.get(name)
            link = make_izurvive_link(last_pos)
            debug_log_entries.append(f"MATCH: {line.strip()}")
            
            # FORMATTING: Match your exact file structure with blank lines and markers
            raw_filtered_lines.append(f"{line.strip()}\n") 

            if link.startswith("http") or mode == "Session Tracking (Global)":
                status = "normal"
                if mode == "Suspicious Boosting Activity" or any(d in low for d in ["died", "killed"]): status = "death"
                elif "connect" in low: status = "connect"
                elif "disconnect" in low: status = "disconnect"

                event_entry = {"time": clean_time, "text": str(line.strip()), "link": link, "status": status}
                if name not in grouped_report: grouped_report[name] = []
                grouped_report[name].append(event_entry)
    
    return grouped_report, header + "\n".join(raw_filtered_lines), debug_header + "\n".join(debug_log_entries)

# --- USER INTERFACE ---
st.markdown("#### 🛡️ CyberDayZ Scanner v26.2")

if "track_data" not in st.session_state: st.session_state.track_data = {}
if "raw_download" not in st.session_state: st.session_state.raw_download = ""
if "debug_download" not in st.session_state: st.session_state.debug_download = ""

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
            st.session_state.track_data = report
            st.session_state.raw_download = raw_file
            st.session_state.debug_download = debug_file

    if st.session_state.track_data:
        st.download_button("💾 Export Filtered ADM", data=st.session_state.raw_download, file_name="FILTERED_LOGS.adm")
        
        for p in sorted(st.session_state.track_data.keys()):
            with st.expander(f"👤 {p} ({len(st.session_state.track_data[p])} events)"):
                for ev in st.session_state.track_data[p]:
                    st.caption(f"🕒 {ev['time']}")
                    st.markdown(f"<div class='{ev['status']}-log'>{ev['text']}</div>", unsafe_allow_html=True)
                    if ev['link']: st.link_button("📍 Map", ev['link'])
                    st.divider()

with col2:
    if st.button("🔄 Refresh Map"): st.session_state.mv = st.session_state.get('mv', 0) + 1
    m_url = f"https://www.izurvive.com/serverlogs/?v={st.session_state.get('mv', 0)}"
    components.iframe(m_url, height=1000, scrolling=True)
