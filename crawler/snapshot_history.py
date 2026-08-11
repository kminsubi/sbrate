from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
HISTORY = DATA / "history"
HISTORY.mkdir(parents=True, exist_ok=True)
KST = timezone(timedelta(hours=9))
now = datetime.now(KST)

def load(name):
    path = DATA / name
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

payload = {
    "snapshot_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    "timezone": "Asia/Seoul",
    "update_info": load("update_info.json"),
    "deposit": load("latest_rates.json"),
    "isa": load("isa_rates.json"),
    "irp": load("irp_rates.json"),
}

path = HISTORY / f"{now.strftime('%Y-%m-%d')}.json"
with path.open("w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(path)
