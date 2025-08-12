import os
import sys
import subprocess
import shutil
import platform
import logging
from packaging import version
import importlib.metadata
import venv

# Define project directory and virtual environment paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_DIR, 'setup.log')),
        logging.StreamHandler()
    ]
)

def check_python_version():
    """Check if Python version is 3.8 or higher."""
    if sys.version_info < (3, 8):
        logging.error("Python 3.8 or higher is required.")
        sys.exit(1)
    logging.info(f"Python version {sys.version_info.major}.{sys.version_info.minor} is sufficient.")

def create_virtualenv():
    """Create a virtual environment if it doesn't exist."""
    if os.path.exists(VENV_DIR):
        logging.info(f"Virtual environment already exists at {VENV_DIR}.")
    else:
        logging.info(f"Creating virtual environment at {VENV_DIR}...")
        venv.create(VENV_DIR, with_pip=True)

def get_executables():
    """Determine paths to Python and pip executables in the virtual environment."""
    if platform.system() == "Windows":
        python_exec = os.path.join(VENV_DIR, "Scripts", "python.exe")
        pip_exec = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        python_exec = os.path.join(VENV_DIR, "bin", "python")
        pip_exec = os.path.join(VENV_DIR, "bin", "pip")
    return python_exec, pip_exec

def upgrade_pip(pip_exec):
    """Check and upgrade pip if needed."""
    PIP_REQUIRED = "21.0"
    logging.info("Checking pip version...")
    try:
        pip_version = subprocess.check_output([pip_exec, "--version"]).decode().split()[1]
        if version.parse(pip_version) >= version.parse(PIP_REQUIRED):
            logging.info(f"pip version {pip_version} is sufficient.")
        else:
            logging.info(f"Upgrading pip (current version: {pip_version}, required: >= {PIP_REQUIRED})...")
            subprocess.check_call([pip_exec, "install", "--upgrade", "pip"])
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to check or upgrade pip: {e}")
        sys.exit(1)

def install_requirements(pip_exec):
    """Check and install dependencies from requirements.txt."""
    requirements_path = os.path.join(PROJECT_DIR, "requirements.txt")
    if not os.path.exists(requirements_path):
        logging.error(f"requirements.txt not found at {requirements_path}")
        sys.exit(1)

    logging.info("Checking dependencies from requirements.txt...")
    installed_packages = {dist.metadata['Name'].lower(): dist.version for dist in importlib.metadata.distributions()}
    required_packages = {}
    with open(requirements_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("==")
            if len(parts) != 2:
                logging.warning(f"Skipping invalid line in requirements.txt: {line}")
                continue
            package = parts[0].strip()
            pkg_version = parts[1].split("#")[0].strip()
            required_packages[package.lower()] = pkg_version

    all_deps_met = True
    for package, pkg_version in required_packages.items():
        if package not in installed_packages:
            logging.info(f"{package} is not installed. Will install {package}=={pkg_version}.")
            all_deps_met = False
        elif version.parse(installed_packages[package]) != version.parse(pkg_version):
            logging.info(f"{package} version {installed_packages[package]} is installed, but {pkg_version} is required. Will reinstall.")
            all_deps_met = False
        else:
            logging.info(f"{package}=={pkg_version} is already installed.")

    if not all_deps_met:
        logging.info(f"Installing dependencies from {requirements_path}...")
        try:
            subprocess.check_call([pip_exec, "install", "-r", requirements_path, "--no-cache-dir"])
            logging.info("Successfully installed dependencies.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install dependencies: {e}")
            sys.exit(1)
    else:
        logging.info("All dependencies from requirements.txt are already satisfied.")

def verify_key_dependencies(python_exec):
    """Verify installation of critical dependencies."""
    dependencies = ['selenium', 'pytest', 'transformers', 'torch', 'spacy']
    logging.info("Verifying key dependencies...")
    for dep in dependencies:
        try:
            subprocess.check_call([python_exec, "-c", f"import {dep}; print(f'{dep} version: ', {dep}.__version__)"])
            logging.info(f"{dep} is installed correctly.")
        except subprocess.CalledProcessError as e:
            error_output = e.output.decode() if e.output is not None else "No output available"
            logging.error(f"{dep} is not installed correctly: {error_output}")
            sys.exit(1)

def install_spacy_model(python_exec):
    """Check and install spaCy model en_core_web_sm if not present."""
    logging.info("Checking spaCy model en_core_web_sm...")
    try:
        subprocess.check_call([python_exec, "-c", "import spacy; nlp = spacy.load('en_core_web_sm'); print('spaCy model loaded successfully')"])
        logging.info("spaCy model en_core_web_sm is already installed.")
    except subprocess.CalledProcessError:
        logging.info("Installing spaCy model en_core_web_sm...")
        try:
            subprocess.check_call([python_exec, "-m", "spacy", "download", "en_core_web_sm"])
            logging.info("Successfully installed spaCy model en_core_web_sm.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install spaCy model en_core_web_sm: {e}")
            sys.exit(1)

def install_chromedriver(pip_exec):
    """Check and install ChromeDriver if not present."""
    logging.info("Checking ChromeDriver installation...")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        chrome_driver_path = ChromeDriverManager().install()
        if os.path.exists(chrome_driver_path):
            logging.info(f"ChromeDriver is already installed at {chrome_driver_path}.")
        else:
            raise FileNotFoundError("ChromeDriver path not found.")
    except (ImportError, FileNotFoundError):
        logging.info("Installing ChromeDriver...")
        try:
            subprocess.check_call([pip_exec, "install", "--upgrade", "webdriver-manager"])
            from webdriver_manager.chrome import ChromeDriverManager
            chrome_driver_path = ChromeDriverManager().install()
            logging.info(f"ChromeDriver installed at {chrome_driver_path}.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install ChromeDriver: {e}")
            sys.exit(1)

def verify_check_packages(python_exec):
    """Run check_packages.py to verify all dependencies."""
    check_packages_path = os.path.join(PROJECT_DIR, "check_packages.py")
    if os.path.exists(check_packages_path):
        logging.info("Running check_packages.py to verify dependencies...")
        try:
            subprocess.check_call([python_exec, check_packages_path])
            logging.info("All dependencies verified by check_packages.py.")
        except subprocess.CalledProcessError as e:
            logging.error(f"check_packages.py failed: {e}")
            sys.exit(1)
    else:
        logging.warning(f"check_packages.py not found at {check_packages_path}. Skipping verification.")

def main():
    """Main function to set up the framework."""
    logging.info(f"Setting up test automation framework in {PROJECT_DIR}...")
    check_python_version()
    create_virtualenv()
    python_exec, pip_exec = get_executables()
    upgrade_pip(pip_exec)
    install_requirements(pip_exec)
    verify_key_dependencies(python_exec)
    install_spacy_model(python_exec)
    install_chromedriver(pip_exec)
    verify_check_packages(python_exec)

    logging.info("Setup complete! To activate the virtual environment:")
    if platform.system() == "Windows":
        logging.info(f"{os.path.join(VENV_DIR, 'Scripts', 'activate.bat')}")
    else:
        logging.info(f"source {os.path.join(VENV_DIR, 'bin', 'activate')}")
    logging.info("To run the framework, use:")
    logging.info(f"python {os.path.join(PROJECT_DIR, 'main.py')} --url <your-target-url>")
    logging.info("Replace <your-target-url> with the URL you want to test.")

if __name__ == "__main__":
    main()