def filter_logs(files, mode, target_player=None, sub_choice=None):
    grouped_report = {} 
    player_positions = {} 
    # Track timestamps for boosting: { player_name: [list_of_datetime_objects] }
    boosting_tracker = {}
    raw_filtered_lines = []
    
    header = "AdminLog started on 00:00:00\n******************************************************************************\n"

    all_lines = []
    for uploaded_file in files:
        content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        all_lines.extend(content.splitlines())

    # Keywords for suspicious stacking behavior
    placement_keys = ["placed", "built", "folded", "shelterfabric", "mounted"]
    # Added "nameless object" and "fireplace" for stacking detection
    stacking_objects = ["placed fence kit", "placed nameless object", "placed fireplace"] 
    raid_keys = ["dismantled", "unmount", "packed", "barbedwirehit", "fireplace", "gardenplot"]
    session_keys = ["connected", "disconnected", "connecting", "died", "killed", "bled out", "suicide"]

    for line in all_lines:
        if "|" not in line: continue
        
        name, coords = extract_player_and_coords(line)
        if name != "System/Server" and coords:
            player_positions[name] = coords

        low = line.lower()
        should_process = False

        # --- EXISTING MODES ---
        if mode == "Activity per Specific Player" and target_player == name:
            if sub_choice == "Full History": should_process = True
            elif sub_choice == "Movement Only" and "pos=" in low: should_process = True
            elif sub_choice == "Movement + Building":
                if ("pos=" in low or any(k in low for k in placement_keys)) and "hit" not in low: should_process = True
            elif sub_choice == "Movement + Raid Watch":
                if ("pos=" in low or any(k in low for k in raid_keys)) and "built" not in low: should_process = True
        
        elif mode == "Session Tracking (Global)":
            if any(k in low for k in session_keys): should_process = True

        # --- UPDATED MODE: SUSPICIOUS BOOSTING (STacking Detector) ---
        elif mode == "Suspicious Boosting Activity":
            time_str = line.split(" | ")[0]
            try:
                current_time = datetime.strptime(time_str, "%H:%M:%S")
            except:
                continue

            # Detect rapid placement of Fence Kits, Garden Plots, or Fireplaces
            if any(obj in low for obj in stacking_objects):
                if name not in boosting_tracker: 
                    boosting_tracker[name] = []
                boosting_tracker[name].append(current_time)
                
                # Check if 3+ stacking objects were placed within 60 seconds
                if len(boosting_tracker[name]) >= 3:
                    time_diff = (boosting_tracker[name][-1] - boosting_tracker[name][-3]).total_seconds()
                    if time_diff <= 60:
                        should_process = True
            
            # Reset tracker if they fold a fence or dismantle/pack an object (cleaning up/not stacking)
            elif any(reset in low for reset in ["folded fence", "dismantled", "packed"]):
                boosting_tracker[name] = []

        if should_process:
            last_pos = player_positions.get(name)
            link = make_izurvive_link(last_pos)
            raw_filtered_lines.append(line)

            if link.startswith("http"):
                status = "normal"
                # Mark boosting as "death" status to reuse your red CSS color
                if mode == "Suspicious Boosting Activity": status = "death" 
                elif any(d in low for d in ["died", "killed", "suicide", "bled out"]): status = "death"
                elif "connect" in low: status = "connect"
                elif "disconnect" in low: status = "disconnect"

                event_entry = {
                    "time": str(line.split(" | ")[0]),
                    "text": str(line.strip()),
                    "link": link,
                    "status": status
                }

                if name not in grouped_report: 
                    grouped_report[name] = []
                grouped_report[name].append(event_entry)
    
    return grouped_report, header + "\n".join(raw_filtered_lines)
