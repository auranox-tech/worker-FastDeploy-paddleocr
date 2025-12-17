import os
import tarfile
import subprocess
from pathlib import Path
from urllib.parse import urlparse  # Import urlparse

BUILD_FOR_OFFLINE = os.getenv("BUILD_FOR_OFFLINE", "true").lower() == "true"

PADDLEX_MODEL_HOME = Path(os.getenv("PADDLEX_MODEL_HOME", "/models"))
PADDLEX_HOME = Path(os.getenv("PADDLEX_HOME", "/opt/paddlex"))

MODELS = {
    "UVDoc": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/UVDoc_infer.tar",
    "PP-LCNet_x1_0_doc_ori": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_doc_ori_infer.tar",
    "PP-DocLayoutV2": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-DocLayoutV2_infer.tar",
    "PaddleOCR-VL-0.9B": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PaddleOCR-VL_infer.tar",
}

FONT_URL = "https://paddle-model-ecology.bj.bcebos.com/paddlex/PaddleX3.0/fonts/PingFang-SC-Regular.ttf"


def run(cmd):
    print("▶", " ".join(cmd))
    subprocess.check_call(cmd)


def download(url, dst):
    run(["wget", "-q", url, "-O", str(dst)])


def extract(tar_path: Path, target_dir: Path, model_url: str):  # Changed model_name to model_url
    with tarfile.open(tar_path) as tar:
        tar.extractall(path=tar_path.parent)

    # Derive the expected extracted folder name from the URL's filename
    parsed_url = urlparse(model_url)
    filename_from_url = Path(parsed_url.path).name  # e.g., "PaddleOCR-VL_infer.tar"
    extracted_folder_name = filename_from_url.replace(".tar", "")  # e.g., "PaddleOCR-VL_infer"

    extracted_source_dir = tar_path.parent / extracted_folder_name

    if not extracted_source_dir.exists():
        # As a fallback, try inspecting the tar file contents to find the root directory
        try:
            with tarfile.open(tar_path) as tar:
                members = tar.getnames()
                if members:
                    # Assume the first member or its parent directory is the root
                    first_member_path = Path(members[0])
                    # If the first member is a directory or a file nested in a directory
                    if "/" in str(first_member_path) or first_member_path.is_dir():
                        root_dir_name = str(first_member_path).split("/")[0]
                        extracted_source_dir = tar_path.parent / root_dir_name
        except Exception as e:
            print(f"Warning: Could not inspect tar file contents: {e}")

    if not extracted_source_dir.exists():
        raise FileNotFoundError(
            f"Could not find the extracted directory for the model. "
            f"Expected '{tar_path.parent / extracted_folder_name}'. "
            f"Please check the tar file's internal structure from URL '{model_url}'."
        )

    extracted_source_dir.rename(target_dir)


def main():
    if not BUILD_FOR_OFFLINE:
        print("Offline build disabled, skipping.")
        return

    PADDLEX_MODEL_HOME.mkdir(parents=True, exist_ok=True)

    for model_name, url in MODELS.items():
        tar_path = PADDLEX_MODEL_HOME / f"{model_name}.tar"
        model_dir = PADDLEX_MODEL_HOME / model_name

        if model_dir.exists():
            print(f"✓ {model_name} already exists, skipping.")
            continue

        download(url, tar_path)
        # Pass the original URL to the extract function to determine the extracted folder name
        extract(tar_path, model_dir, url)  # Pass model_url here
        tar_path.unlink()

    # Fonts
    fonts_dir = PADDLEX_HOME / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    font_path = fonts_dir / "PingFang-SC-Regular.ttf"
    if not font_path.exists():
        download(FONT_URL, font_path)

    print("✅ Offline PaddleOCR-VL models ready.")


if __name__ == "__main__":
    main()
