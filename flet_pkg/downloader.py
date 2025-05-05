import os
import requests
import tarfile
import tempfile
import shutil
from pathlib import Path


def download_package_from_pubdev(package_name: str, output_dir: Path) -> Path:
    """
    Downloads and extracts a Flutter package from pub.dev to the specified directory.

    Args:
        package_name: Name of the package (e.g., "url_launcher")
        output_dir: Directory where the package should be extracted

    Returns:
        Path to the extracted package directory
    """

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get package metadata
    api_url = f"https://pub.dev/api/packages/{package_name}"
    response = requests.get(api_url)
    response.raise_for_status()

    data = response.json()
    latest_version = data["latest"]["version"]
    tarball_url = f"https://pub.dev/packages/{package_name}/versions/{latest_version}.tar.gz"

    print(f"📦 Downloading {package_name} v{latest_version}...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Download the package
        tarball_path = Path(tmp_dir) / f"{package_name}.tar.gz"
        with requests.get(tarball_url, stream=True) as r:
            r.raise_for_status()
            with open(tarball_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Extract the package
        with tarfile.open(tarball_path, "r:gz") as tar:
            # Extract to temporary directory
            temp_extract_dir = Path(tmp_dir) / "extracted"
            tar.extractall(path=temp_extract_dir, filter='data')

            # Find the actual package content (handles different package structures)
            package_content = None
            possible_paths = [
                temp_extract_dir / f"{package_name}-{latest_version}",
                temp_extract_dir / package_name,
                temp_extract_dir
            ]

            for path in possible_paths:
                if path.exists():
                    package_content = path
                    break

            if not package_content:
                raise FileNotFoundError("Could not find package content in extracted files")

            # Move content to output directory
            for item in package_content.glob("*"):
                dest = output_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        os.remove(dest)

                shutil.move(str(item), str(dest))

    print(f"✅ Package successfully extracted to: {output_dir}")
    print("📦 Package contents:")
    for item in output_dir.glob("*"):
        print(f" - {item.name}")

    return output_dir


if __name__ == "__main__":
    package_name = "flame"
    output_dir = Path("package/flutter")
    download_package_from_pubdev(package_name, output_dir)
