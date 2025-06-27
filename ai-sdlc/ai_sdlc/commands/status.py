# ai_sdlc/commands/status.py
"""`aisdlc status` – show progress through lifecycle steps."""

from ai_sdlc.utils import load_config, read_lock


def run_status() -> None:
    conf = load_config()
    steps = conf["steps"]
    lock = read_lock()
    print("Active workstreams\n------------------")
    if not lock:
        print("none – create one with `aisdlc new`")
        return
    slug = lock["slug"]
    cur = lock["current"]
    idx = steps.index(cur)
    bar = " ▸ ".join([("✅" if i <= idx else "☐") + s[2:] for i, s in enumerate(steps)])
    print(f"{slug:20} {cur:12} {bar}")
