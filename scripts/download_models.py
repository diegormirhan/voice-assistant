import sys
import urllib.request
from pathlib import Path

from servers.models import MODELS, all_downloads

def download(dest: str, url: str) -> None:
    target = MODELS / dest
    if target.exists():
        print(f"[skip] {dest} ja existe")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[down] {dest}")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(target, "wb") as f:
            while chunk := resp.read(1 << 16):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded/1e6:.1f}/{total/1e6:.0f} MB ({pct:.0f}%)", end="", flush=True)
    print()


def main() -> None:
    profile = sys.argv[1] if len(sys.argv) > 1 else "padrao"
    if profile not in ("leve", "padrao"):
        print("Uso: python scripts/download_models.py [leve|padrao]")
        sys.exit(1)
    print(f"Perfil: {profile}")
    for dest, url in all_downloads(profile):
        download(dest, url)


if __name__ == "__main__":
    main()
