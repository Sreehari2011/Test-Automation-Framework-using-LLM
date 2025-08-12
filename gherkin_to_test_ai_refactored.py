import os
import re
import logging
import json
from ollama_utils import query_ollama
from gherkin_generator_refactored import LocatorMap
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from utils import sanitize_identifier_for_method_name

def sanitize_xpath(xpath):
    """Ensure proper quotation in XPath expressions."""
    corrected_xpath = re.sub(r"='([^']*)'", r'="\1"', xpath)
    if not re.match(r'^//[\w\[\]@=*\(\)|"\'\s]+$', corrected_xpath):
        logging.warning(f"Potentially invalid XPath: {corrected_xpath}")
    return corrected_xpath

def validate_locator(driver, locator_strategy, locator_value):
    """Validate a locator by checking if it finds an element on the page."""
    try:
        driver.find_element(locator_strategy, locator_value)
        logging.debug(f"Validated locator: {locator_strategy}={locator_value}")
        return True
    except Exception as e:
        logging.warning(f"Invalid locator {locator_strategy}={locator_value}: {e}")
        return False

def convert_gherkin_to_test(gherkin_content, class_name, url, locator_map=None, output_dir="tests"):
    """Convert Gherkin content to pytest test scripts using Code Llama."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(project_dir, output_dir)
    os.makedirs(output_dir, exist_ok=True)

    open(os.path.join(output_dir, "__init__.py"), 'a').close()

    safe_class_name = ''.join(word.capitalize() for word in class_name.split('_'))
    test_file_name = f"test_{sanitize_identifier_for_method_name(class_name)}.py"
    test_file_path = os.path.join(output_dir, test_file_name)

    # Initialize locator map with validated locators
    driver = None
    if locator_map is None:
        locator_map = LocatorMap()
        step_mappings = {
            "name field": ("name", "input_field", '//input[@id="name" or @name="name"]', "input#name"),
            "email field": ("email", "input_field", '//input[@id="email" or @name="email"]', "input#email"),
            "male gender radio button": ("gender", "radio", '//input[@id="gender" and @name="gender"]', "input#gender"),
            "mobile field": ("mobile", "input_field", '//input[@id="mobile" or @name="mobile"]', "input#mobile"),
            "date_of_birth dropdown": ("date_of_birth", "input_field", '//input[@id="dob" or @name="dob"]', "input#dob"),
            "subjects field": ("subjects", "input_field", '//input[@id="subjects" or @name="subjects"]', "input#subjects"),
            "sports hobby checkbox": ("hobbies_sports", "checkbox", '//input[@id="hobbies" and following-sibling::label[text()="Sports"]]', "input#hobbies"),
            "address field": ("address", "input_field", '//textarea[@id="address" or @name="address"]', "textarea#address"),
            "submit button": ("submit", "button", '//input[@type="submit"]', "input[type='submit']"),
            "form submission confirmation": ("confirmation", "text", '//div[contains(text(), "Form submitted") or contains(text(), "Submission successful")]', "div.alert-success")
        }
        logging.info("Building locator map from Gherkin content...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(url)
        for line in gherkin_content.splitlines():
            line = line.strip()
            if line.startswith(("Given ", "When ", "And ", "Then ")):
                for step_key, (identifier, category, xpath, css_selector) in step_mappings.items():
                    if step_key.lower() in line.lower():
                        sanitized_xpath = sanitize_xpath(xpath)
                        if validate_locator(driver, By.XPATH, sanitized_xpath):
                            locator_map.add_locator(identifier, {"category": category, "xpath": sanitized_xpath, "css_selector": css_selector}, line)
                            logging.debug(f"Mapped step '{line}' to locator '{identifier}'")
                        else:
                            logging.error(f"Skipping invalid locator for step '{line}': {sanitized_xpath}")
                        break
                else:
                    logging.warning(f"No locator mapping found for step: {line}")
        driver.quit()

    # Parse Gherkin content
    steps = []
    current_scenario = None
    logging.info("Parsing Gherkin content...")
    for line in gherkin_content.splitlines():
        line = line.strip()
        if line.startswith("Scenario:"):
            current_scenario = sanitize_identifier_for_method_name(line.split(":", 1)[1].strip())
            logging.debug(f"Found scenario: {current_scenario}")
        elif line.startswith(("Given ", "When ", "Then ", "And ")):
            steps.append((current_scenario, line))
    if not steps:
        logging.error("No valid Gherkin steps found in content")
        return None

    # Craft prompt for Code Llama to generate pytest code
    prompt = f"""
        You are an expert in web automation and pytest. Given a Gherkin feature file content and a locator map, generate a pytest test script in Python. 
        For each 'Then' step in the Gherkin content, generate a corresponding 'assert' statement in the pytest test function. Use the POM to interact with elements and then assert on their state (e.g., visibility, text content). 
        The script should use Selenium WebDriver with a Page Object Model (POM) class named '{safe_class_name}Page'. 
        Use the provided URL and locator map to map Gherkin steps to POM methods. 
        The output must be valid Python code as a string, without markdown or additional text. 
        Include necessary imports, a pytest fixture for the driver, and test functions for each scenario. 
        Use WebDriverWait and expected_conditions for robust element interactions. 
        Ensure all Python syntax is valid and executable. 
        Example output:
        import pytest
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        from pom.example_page import ExamplePage

        @pytest.fixture
        def driver():
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            driver.get('http://example.com')
            yield driver
            driver.quit()

        def test_example_scenario(driver):
            page = ExamplePage(driver)
            page.enter_username('test_user')
            page.click_submit_button()
            element = page.wait.until(EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "Success")]')))
            assert element.is_displayed(), 'Confirmation not displayed'

        Gherkin content:
        {gherkin_content}

        Locator map:
        {json.dumps(locator_map.get_all_mappings(), indent=2)}

        URL: {url}
        POM class name: {safe_class_name}Page
    """

    # Generate test code using Ollama
    test_content = query_ollama(prompt)
    if not test_content:
        logging.error("Ollama failed to generate test code.")
        raise RuntimeError("Failed to generate test code using model-based approach.")
    
    # Sanitize the AI's response by removing Markdown code fences
    if test_content.strip().startswith("```python"):
        logging.debug("Stripping Markdown fences from AI response.")
         # Find the content between the first newline and the last '```'
        try:
            first_newline = test_content.index('\n')
            last_fence = test_content.rindex('```')
            test_content = test_content[first_newline + 1:last_fence].strip()
        except ValueError:
            logging.warning("Could not properly strip Markdown fences. Writing raw content.")

    # Write test file
    try:
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_content)
        logging.info(f"Generated test file: {test_file_path}")
        return test_file_path
    except Exception as e:
        logging.error(f"Failed to write test file {test_file_path}: {e}")
        return None