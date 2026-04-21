"""Probe coolpc evaluate.php HTML: count options, check option_value stability, save fixture."""
import hashlib
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

URL = "https://www.coolpc.com.tw/evaluate.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}

FIXTURE_PATH = Path("tests/fixtures/evaluate_sample.html")


def fetch_raw() -> bytes:
    resp = httpx.get(URL, headers=HEADERS, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def inspect(html_bytes: bytes, label: str) -> dict:
    for encoding in ("utf-8", "big5hkscs", "big5", "cp950"):
        try:
            html = html_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError("Cannot decode HTML as utf-8, big5hkscs, big5, or cp950")

    soup = BeautifulSoup(html, "lxml")
    selects = soup.select("select[name^='n']")
    options = soup.select("select[name^='n'] option")
    values = [o.get("value", "") for o in options]
    optgroups = soup.select("select[name^='n'] optgroup")

    targets = {
        "cpu":    ["AMD", "R7 7700 MPK"],
        "mb":     ["B650EM", "FORCE", "WIFI6E"],
        "ram":    ["UMAX", "64GB", "雙通32GB", "6000", "CL30"],
        "ssd":    ["金士頓", "KC3000", "2TB"],
        "cooler": ["九州風神", "AG500"],
        "case":   ["視博通", "SW300", "白"],
        "psu":    ["Montech", "CENTURY II", "850W"],
        "os":     ["Windows 11", "家用彩盒版", "64位元"],
    }
    hits = {}
    for key, kws in targets.items():
        matched = [
            (o.get("value"), o.get_text(strip=True))
            for o in options
            if all(kw in o.get_text(strip=True) for kw in kws)
        ]
        hits[key] = matched

    return {
        "label": label,
        "encoding": encoding,
        "n_selects": len(selects),
        "n_options": len(options),
        "n_optgroups": len(optgroups),
        "sha256_values": hashlib.sha256("\n".join(values).encode()).hexdigest()[:16],
        "hits": hits,
    }


def main() -> None:
    snapshots = []
    for i in range(3):
        print(f"[probe] fetch {i + 1}/3 ...", file=sys.stderr)
        raw = fetch_raw()
        snapshots.append((raw, inspect(raw, f"run{i + 1}")))
        if i < 2:
            time.sleep(5)

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_bytes(snapshots[0][0])
    print(f"[probe] saved fixture to {FIXTURE_PATH}", file=sys.stderr)

    for _raw, info in snapshots:
        print(f"\n=== {info['label']} ===")
        print(f"  encoding     : {info['encoding']}")
        print(f"  <select Y*>  : {info['n_selects']}")
        print(f"  <option>     : {info['n_options']}")
        print(f"  <optgroup>   : {info['n_optgroups']}")
        print(f"  sha16(values): {info['sha256_values']}")

    print("\n=== option_value stability ===")
    hashes = {info["sha256_values"] for _, info in snapshots}
    if len(hashes) == 1:
        print("  STABLE — upgrade to C mode (fill option_value_hint in YAML)")
    else:
        print("  UNSTABLE — stay on A mode (match_all only)")
        for _, info in snapshots:
            print(f"    {info['label']}: {info['sha256_values']}")

    print("\n=== per-item hits (using run1) ===")
    for key, matched in snapshots[0][1]["hits"].items():
        print(f"  [{key}] {len(matched)} candidates")
        for value, text in matched[:3]:
            print(f"    value={value!r}  text={text[:80]!r}")
        if len(matched) > 3:
            print(f"    ... and {len(matched) - 3} more")


if __name__ == "__main__":
    main()
