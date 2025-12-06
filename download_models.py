from pathlib import Path
from huggingface_hub import snapshot_download


BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "ml_models"


def download_translator():
    """
    Helsinki-NLP/opus-mt-ru-en → ml_models/translator/opus-mt-ru-en
    """
    target_dir = MODELS_DIR / "translator" / "opus-mt-ru-en"
    print(f"Downloading Helsinki-NLP/opus-mt-ru-en into {target_dir}")
    snapshot_download(
        repo_id="Helsinki-NLP/opus-mt-ru-en",
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )
    print("Translator ready:", target_dir)


def download_dreamshaper():
    """
    Lykon/dreamshaper-8 → ml_models/dreamshaper-8
    (diffusers-формат Stable Diffusion 1.5)
    """
    target_dir = MODELS_DIR / "dreamshaper-8"
    print(f"Downloading Lykon/dreamshaper-8 into {target_dir}")
    snapshot_download(
        repo_id="Lykon/dreamshaper-8",
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )
    print("DreamShaper ready:", target_dir)


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    download_translator()
    download_dreamshaper()
    print("All done.")


if __name__ == "__main__":
    main()
