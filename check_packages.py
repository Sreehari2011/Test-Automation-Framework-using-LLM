import importlib.metadata
import sys
import spacy

required_packages = {
    'numpy': '1.26.4',
    'selenium': '4.15.2',
    'beautifulsoup4': '4.12.2',
    'pytest': '7.4.3',
    'pytest-bdd': '6.1.1',
    'pytest-rerunfailures': '10.3',
    'pytest-xdist': '3.3.1',
    'allure-pytest': '2.13.2',
    'webdriver-manager': '4.0.0',
    'spacy': '3.7.2',
    'requests': '2.31.0'
}

def check_package(package_name, required_version):
    try:
        installed_version = importlib.metadata.version(package_name)
        if installed_version == required_version:
            print(f"{package_name}: Installed (Version {installed_version})")
        else:
            print(f"{package_name}: Installed (Version {installed_version}) but required {required_version}")
    except importlib.metadata.PackageNotFoundError:
        print(f"{package_name}: Not installed")

def check_spacy_model():
    try:
        nlp = spacy.load("en_core_web_sm")
        model_version = nlp.meta["version"]
        print(f"spaCy model en_core_web_sm: Installed (Version {model_version})")
    except Exception as e:
        print(f"spaCy model en_core_web_sm: Not installed or failed to load: {e}")

def main():
    print("Checking package installations...")
    for package, version in required_packages.items():
        check_package(package, version)
    check_spacy_model()

if __name__ == "__main__":
    main()