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

        status = str(match.get("status", "")).upper()
        home = match.get("home_team", match.get("homeTeam", match.get("team1", "?")))
        away = match.get("away_team", match.get("awayTeam", match.get("team2", "?")))

        score = match.get("score", {})
        if isinstance(score, dict):
            home_score = score.get("home", score.get("ft", [0, 0])[0] if isinstance(score.get("ft"), list) else 0)
            away_score = score.get("away", score.get("ft", [0, 0])[1] if isinstance(score.get("ft"), list) else 0)
        else:
            home_score = match.get("home_score", match.get("goalsHome", 0)) or 0
            away_score = match.get("away_score", match.get("goalsAway", 0)) or 0

        home_score = int(home_score or 0)
        away_score = int(away_score or 0)
        score_str = f"{home_score} - {away_score}"
        name = f"{home} vs {away}"

        current[mid] = {
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "home": home,
            "away": away,
        }

        prev = previous.get(mid, {})
        prev_status = prev.get("status", "")
        prev_home = int(prev.get("home_score", 0) or 0)
        prev_away = int(prev.get("away_score", 0) or 0)

        # Kickoff
        if status == "LIVE" and prev_status != "LIVE":
            send_notification(
                title=f"KICKOFF: {name}",
                message=f"Ο αγώνας ξεκίνησε! {name} | {now}",
                priority="high",
                tags="soccer,tada"
            )

        # Goal — home
        elif status == "LIVE" and home_score > prev_home:
            for _ in range(home_score - prev_home):
                send_notification(
                    title=f"ΓΚΟΛ! {home} σκοράρει!",
                    message=f"{name}\nΣκορ: {score_str} | {now}",
                    priority="urgent",
                    tags="soccer,goal_net"
                )

        # Goal — away
        elif status == "LIVE" and away_score > prev_away:
            for _ in range(away_score - prev_away):
                send_notification(
                    title=f"ΓΚΟΛ! {away} σκοράρει!",
                    message=f"{name}\nΣκορ: {score_str} | {now}",
                    priority="urgent",
                    tags="soccer,goal_net"
                )

        # Full time
        elif status in ("FT", "AET", "PEN", "FINISHED") and prev_status == "LIVE":
            send_notification(
                title=f"ΤΕΛΙΚΟ: {name}",
                message=f"Τελικό Σκορ: {score_str} | {status}",
                priority="high",
                tags="soccer,checkered_flag"
            )

    save_state(current)
    print(f"Done. Tracked {len(current)} matches.")

if __name__ == "__main__":
    print(f"WC2026 Notifier — {datetime.now(timezone.utc).isoformat()}")
    check_matches()
