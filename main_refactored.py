import os
import sys
import logging
import argparse
import subprocess
import spacy
import platform
import datetime
import json
from urllib.parse import urlparse
import py_compile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from locator_extractor_refactored import extract_locators
from gherkin_generator_refactored import generate_gherkin
from pom_generator_refactored import generate_pom
from gherkin_to_test_ai_refactored import convert_gherkin_to_test
from utils import sanitize_identifier_for_method_name

def setup_logging():
    """Set up logging configuration."""

    log_dir = "run_log"
    os.makedirs(log_dir, exist_ok=True)
    current_date=datetime.datetime.now().strftime("%d-%m-%y")
    log_filename=f"{current_date}.log"
    log_filepath=os.path.join(log_dir, log_filename)

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        filename=log_filepath,
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    print(f"Logging setup complete. Log file is at: {log_filepath}")
    logging.debug(f"Logging configured to file: {log_filepath}")

def load_spacy_model():
    """Load spaCy model for error analysis."""
    print("Loading spaCy model")
    try:
        nlp = spacy.load("en_core_web_sm")
        print("spaCy model loaded successfully")
        logging.debug("spaCy model loaded successfully")
        return nlp
    except Exception as e:
        print(f"Failed to load spaCy model: {e}")
        logging.error(f"Failed to load spaCy model: {e}")
        return None

def clear_output_directories(gherkin_file):
    """Clear or create output directories, preserving the specified Gherkin file."""
    print("Clearing output directories")
    directories = ["pom", "tests", "FEATURES", "reports", "LOCATORS"]
    for directory in directories:
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), directory)
        if os.path.exists(dir_path):
            for file in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file)
                if gherkin_file and file_path == os.path.abspath(gherkin_file):
                    continue
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
                    logging.error(f"Error deleting {file_path}: {e}")
        else:
            print(f"Directory {dir_path} does not exist, will be created")
            os.makedirs(dir_path, exist_ok=True)
    logging.debug("Output directories cleared")

def get_chrome_binary_path():
    """Locate the Chrome binary path based on the operating system."""
    print("Locating Chrome binary path")
    logging.debug("Locating Chrome binary path")
    os_type = platform.system()
    print(f"Detected OS: {os_type}")
    logging.debug(f"Detected OS: {os_type}")

    if os_type == "Windows":
        possible_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        ]
    elif os_type == "Darwin":
        possible_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ]
    elif os_type == "Linux":
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/local/bin/google-chrome",
            "/opt/google/chrome/google-chrome"
        ]
    else:
        raise FileNotFoundError(f"Unsupported OS: {os_type}")

    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found Chrome binary at: {path}")
            logging.debug(f"Found Chrome binary at: {path}")
            return path

    raise FileNotFoundError("Chrome binary not found")

def validate_test_file(test_file):
    """Validate the syntax of the generated test file."""
    try:
        py_compile.compile(test_file, doraise=True)
        print(f"Syntax check passed for {test_file}")
        logging.info(f"Syntax check passed for {test_file}")
        return True
    except py_compile.PyCompileError as e:
        print(f"Syntax error in {test_file}: {e}")
        logging.error(f"Syntax error in {test_file}: {e}")
        return False

def process_url_and_gherkin(url, gherkin_file=None):
    """Process URL to generate POM, Gherkin, and tests."""
    print(f"Processing URL: {url}, Gherkin file: {gherkin_file}")
    logging.debug(f"Processing URL: {url}, Gherkin file: {gherkin_file}")

    print("Calling clear_output_directories")
    clear_output_directories(gherkin_file)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--no-proxy-server")
    options.add_argument("--disable-gpu")
    options.add_argument("--proxy-server='direct://'")
    options.add_argument("--proxy-bypass-list=*")
    options.add_argument("--disable-blink-features=AutomationControlled")
    print("Chrome options configured")
    logging.debug("Chrome options configured")

    try:
        print("Getting Chrome binary path")
        options.binary_location = get_chrome_binary_path()
    except FileNotFoundError as e:
        print(f"Chrome binary error: {e}")
        logging.error(f"Chrome binary error: {e}")
        return

    try:
        print("Initializing ChromeDriver with webdriver-manager")
        logging.info("Initializing ChromeDriver with webdriver-manager")
        chrome_driver_manager = ChromeDriverManager()
        base_path = chrome_driver_manager.install()
        if os.path.isfile(base_path):
            base_path = os.path.dirname(base_path)
        chrome_driver_path = os.path.join(base_path, "chromedriver")

        os.chmod(chrome_driver_path, 0o755)
        print(f"Using ChromeDriver at: {chrome_driver_path}")
        logging.debug(f"Using ChromeDriver at: {chrome_driver_path}")
        driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)
        print("ChromeDriver initialized successfully")
        logging.debug("ChromeDriver initialized successfully")
    except Exception as e:
        print(f"WebDriver initialization error: {e}")
        logging.error(f"WebDriver initialization error: {e}")
        return

    try:
        class_name = sanitize_identifier_for_method_name(url.split("/")[-1].replace(".php", "").replace("-", "_"))
        print(f"Derived class name: {class_name}")
        logging.debug(f"Derived class name: {class_name}")

        driver.set_page_load_timeout(60)
        print(f"Navigating to {url}")
        logging.debug(f"Navigating to {url}")
        driver.get(url)

        print("Extracting locators")
        locators = extract_locators(driver)
        logging.debug(f"Extracted {len(locators)} locators")

        print("Generating POM")
        pom_file = generate_pom(driver, class_name)
        if not pom_file:
            print("POM generation failed")
            logging.error("POM generation failed")
            driver.quit()
            return
        print(f"POM file generated: {pom_file}")
        logging.debug(f"POM file generated: {pom_file}")

        print("Generating or using Gherkin file")
        if gherkin_file and os.path.exists(gherkin_file):
            print(f"Using provided Gherkin file: {gherkin_file}")
            logging.debug(f"Using provided Gherkin file: {gherkin_file}")
            with open(gherkin_file, "r", encoding="utf-8") as f:
                gherkin_content = f.read()
            locator_map = None
        else:
            print("Generating Gherkin with positive, negative, and edge cases")
            feature_path, locator_map = generate_gherkin(class_name, locators)
            if not feature_path:
                print("Gherkin generation failed")
                logging.error("Gherkin generation failed")
                driver.quit()
                return
            print(f"Gherkin file generated: {feature_path}")
            logging.debug(f"Gherkin file generated: {feature_path}")
            with open(feature_path, "r", encoding="utf-8") as f:
                gherkin_content = f.read()

        print("Converting Gherkin to test")
        test_file = convert_gherkin_to_test(gherkin_content, class_name, url, locator_map)
        if not test_file:
            print("Test generation failed")
            logging.error("Test generation failed")
            driver.quit()
            return
        print(f"Test file generated: {test_file}")
        logging.debug(f"Test file generated: {test_file}")

        print("Validating test file syntax")
        if not validate_test_file(test_file):
            print("Aborting pytest execution due to syntax error")
            logging.error("Aborting pytest execution due to syntax error")
            driver.quit()
            return
        
        print("Running tests with pytest")
        logging.info("Running tests with pytest")
        cmd = [
            sys.executable, "-m", "pytest", test_file,
            "--alluredir=reports",
            "--reruns", "2",
            "--reruns-delay", "1",
            "-v"
        ]

        os.makedirs("reports", exist_ok=True)
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Tests executed successfully")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            logging.info("Tests executed successfully")
            logging.debug(f"STDOUT: {result.stdout}")
            logging.debug(f"STDERR: {result.stderr}")
        except subprocess.CalledProcessError as e:
            print("Test execution failed")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            logging.error("Test execution failed")
            logging.error(f"STDOUT: {e.stdout}")
            logging.error(f"STDERR: {e.stderr}")

            nlp = load_spacy_model()
            if nlp:
                print("Analyzing error with spaCy")
                doc = nlp(e.stderr)
                for sent in doc.sents:
                    print(f"Error sentence: {sent.text}")
                    logging.debug(f"Error sentence: {sent.text}")

                suggestions = []
                if "NoSuchElementException" in e.stderr:
                    suggestions.append("Verify locators generated by the model")
                    suggestions.append(f"Check if elements are present on {url} using browser developer tools")
                if "TimeoutException" in e.stderr:
                    suggestions.append("Increase page load timeout in main.py (driver.set_page_load_timeout)")
                    suggestions.append(f"Verify {url} is accessible with 'curl -k {url}'")
                if "SyntaxError" in e.stderr:
                    suggestions.append("Check the generated test file for syntax errors")
                    suggestions.append(f"Run 'python3 -m py_compile {test_file}' to validate")
                if suggestions:
                    print("Suggestions for resolution:")
                    for suggestion in suggestions:
                        print(f"- {suggestion}")
                        logging.info(f"Suggestion: {suggestion}")
        except Exception as e:
            print(f"Unexpected error during test execution: {e}")
            logging.error(f"Unexpected error during test execution: {e}")

    except Exception as e:
        print(f"Error during processing: {e}")
        logging.error(f"Error during processing: {e}")
    finally:
        driver.quit()
        print("WebDriver closed")
        logging.debug("WebDriver closed")

def main():
    """Main function to parse arguments and execute the framework."""
    print("Script execution started")
    setup_logging()
    nlp = load_spacy_model()

    print("Parsing command-line arguments")
    parser = argparse.ArgumentParser(description="Test Automation Framework")
    parser.add_argument("--url", help="Target URL. Can also be set via environment variable TEST_URL")
    parser.add_argument("--gherkin", help="Path to Gherkin feature file")
    args = parser.parse_args()

    # Read URL from environment variable if not provided as argument
    url = args.url or os.getenv("TEST_URL")
    if not url:
        print("Error: Target URL must be provided via --url argument or TEST_URL environment variable.")
        logging.error("Target URL not provided")
        sys.exit(1)

    print(f"Arguments parsed: URL={url}, Gherkin={args.gherkin}")
    logging.debug(f"Arguments parsed: URL={url}, Gherkin={args.gherkin}")

    print("Starting main execution")
    process_url_and_gherkin(url, args.gherkin)
    print("Main execution completed")

if __name__ == "__main__":
    main()