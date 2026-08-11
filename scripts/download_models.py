import sys

try:  # imported as a package (python main.py)
    from .downloads import batch
except ImportError:  # run directly (python scripts/download_models.py)
    from downloads import batch

from servers.models import MODELS, all_downloads

def download_all(profile: str, progress = None):
    """Downloads COMMON + given profile's LLM files; skips existing."""
    files = [(MODELS / dest, url) for dest, url in all_downloads(profile)]
    batch(files, progress)

def main() -> None:
    profile = sys.argv[1] if len(sys.argv) > 1 else "padrao"
    if profile not in ("leve", "padrao"):
        print("Uso: python scripts/download_models.py [leve|padrao]")
        sys.exit(1)
    print(f"Perfil: {profile}")
    download_all(profile)

if __name__ == "__main__":
    main()
