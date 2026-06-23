import os
import requests
import json
from datetime import datetime, timezone

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
STATE_FILE = "match_state.json"

def send_notification(title, message, priority="default", tags="soccer"):
    try:
        requests.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": tags,
            },
            timeout=10
        )
        print(f"SENT: {title} — {message}")
    except Exception as e:
        print(f"ERROR sending notification: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_matches():
    try:
        response = requests.get(
            "https://worldcup26.ir/get/games",
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        return data.get("games", data.get("matches", data.get("data", [])))
    except Exception as e:
        print(f"ERROR fetching matches: {e}")
        return []

def is_live(match):
    finished = str(match.get("finished", "")).upper()
    if finished == "TRUE":
        return False
    elapsed = str(match.get("time_elapsed", "")).lower().strip()
    if not elapsed or elapsed in ("null", "none", "", "finished", "notstarted"):
        return False
    # Must look like a minute number e.g. "23", "45+2", "HT", "90+4"
    return True

def is_finished(match):
    finished = str(match.get("finished", "")).upper()
    return finished == "TRUE"

def check_matches():
    previous = load_state()
    current = {}
    matches = get_matches()

    if not matches:
        print("No match data returned.")
        save_state(current)
        return

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    for match in matches:
        mid = str(match.get("id", match.get("_id", "")))
        if not mid:
            continue

        home = match.get("home_team_name_en", "?")
        away = match.get("away_team_name_en", "?")
        raw_home = match.get("home_score", "0")
        raw_away = match.get("away_score", "0")
        home_score = int(raw_home) if str(raw_home).lstrip('-').isdigit() else 0
        away_score = int(raw_away) if str(raw_away).lstrip('-').isdigit() else 0
        score_str = f"{home_score} - {away_score}"
        name = f"{home} vs {away}"
        elapsed = str(match.get("time_elapsed", "")).strip()
        live = is_live(match)
        finished = is_finished(match)

        current[mid] = {
            "live": live,
            "finished": finished,
            "home_score": home_score,
            "away_score": away_score,
            "elapsed": elapsed,
        }

        prev = previous.get(mid, {})
        prev_live = prev.get("live", False)
        prev_finished = prev.get("finished", False)
        prev_home = int(prev.get("home_score", 0) or 0)
        prev_away = int(prev.get("away_score", 0) or 0)

        # Kickoff
        if live and not prev_live:
            print(f"KICKOFF detected: {name} | elapsed={elapsed}")
            send_notification(
                title=f"KICKOFF: {name}",
                message=f"Ο αγώνας ξεκίνησε! {name} | {now}",
                priority="high",
                tags="soccer,tada"
            )

        # Goal — home
        elif live and home_score > prev_home:
            for _ in range(home_score - prev_home):
                send_notification(
                    title=f"ΓΚΟΛ! {home} σκοράρει!",
                    message=f"{name}\nΣκορ: {score_str} | {elapsed}' | {now}",
                    priority="urgent",
                    tags="soccer,goal_net"
                )

        # Goal — away
        elif live and away_score > prev_away:
            for _ in range(away_score - prev_away):
                send_notification(
                    title=f"ΓΚΟΛ! {away} σκοράρει!",
                    message=f"{name}\nΣκορ: {score_str} | {elapsed}' | {now}",
                    priority="urgent",
                    tags="soccer,goal_net"
                )

        # Full time
        elif finished and prev_live and not prev_finished:
            send_notification(
                title=f"ΤΕΛΙΚΟ: {name}",
                message=f"Τελικό Σκορ: {score_str}",
                priority="high",
                tags="soccer,checkered_flag"
            )

    save_state(current)
    print(f"Done. Tracked {len(current)} matches.")

if __name__ == "__main__":
    print(f"WC2026 Notifier — {datetime.now(timezone.utc).isoformat()}")
    check_matches()
