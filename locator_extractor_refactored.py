from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import logging
import json
import os
import re
from ollama_utils import generate_json_with_ollama
from utils import sanitize_identifier_for_method_name

def extract_locators(driver):
    """Extract locators from the page using Code Llama via Ollama and save as JSON."""
    try:
        # Parse HTML content with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Store HTML content in a temporary variable, minified for Code Llama
        html_content = str(soup.prettify())
        # Remove excessive whitespace and newlines for efficient processing
        html_content = re.sub(r'\s+', ' ', html_content).strip()
        logging.debug(f"HTML sent to Ollama: {html_content}")
        # Save the HTML content to file for inspection
        with open("debug_html.txt", "w", encoding="utf-8") as f:
            f.write(html_content)

        # Craft prompt for Code Llama
        prompt = (
            "You are an expert in web automation. Given the HTML content of a webpage, identify all interactable elements (e.g., input fields, buttons, checkboxes, radio buttons, dropdowns) and provide their identifiers, categories, XPaths, and CSS selectors in JSON format. "
            "Focus only on elements that can be interacted with (e.g., <input>, <button>, <select>). "
            "The output must be a JSON array of objects, each with the following fields: "
            "- identifier: A meaningful name for the element (e.g., 'username', 'submit_button'). Use id, name, placeholder, or label text if available. "
            "- category: The type of element (e.g., 'input_field', 'button', 'checkbox', 'radio', 'dropdown'). "
            "- xpath: The XPath to locate the element. "
            "- css_selector: The CSS selector to locate the element. "
            "Ensure XPaths and CSS selectors are precise and unique. Avoid non-interactable elements like <div>, <span>, or static text. "
            "Return only the JSON array, without any additional text or markdown. "
            "Example output:\n"
            "[\n"
            "  {\n"
            "    \"identifier\": \"username\",\n"
            "    \"category\": \"input_field\",\n"
            "    \"xpath\": \"//input[@id='username' or @name='username']\",\n"
            "    \"css_selector\": \"input#username\"\n"
            "  },\n"
            "  {\n"
            "    \"identifier\": \"submit_button\",\n"
            "    \"category\": \"button\",\n"
            "    \"xpath\": \"//button[@type='submit']\",\n"
            "    \"css_selector\": \"button[type='submit']\"\n"
            "  }\n"
            "]\n\n"
            "HTML content:\n"
            f"{html_content}"
        )

        # Generate locators using Ollama
        locators = generate_json_with_ollama(prompt)
        if not locators or not isinstance(locators, list):
            logging.error("Ollama failed to generate valid locators.")
            raise RuntimeError("Failed to generate locators using model-based approach.")

        # Validate and clean locators
        unique_locators = []
        seen = set()
        for locator in locators:
            identifier = locator.get("identifier")
            if not identifier or identifier in seen:
                continue
            if not locator.get("xpath") or not locator.get("css_selector"):
                logging.debug(f"Skipping locator with missing xpath or css_selector: {identifier}")
                continue
            seen.add(identifier)
            unique_locators.append(locator)

        # Save locators to JSON file
        project_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(project_dir, "LOCATORS")
        os.makedirs(output_dir, exist_ok=True)
        class_name = sanitize_identifier_for_method_name(driver.current_url.split("/")[-1].replace(".php", "").replace("-", "_"))
        file_name = f"{class_name}_locators.json"
        file_path = os.path.join(output_dir, file_name)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(unique_locators, f, indent=4)
            logging.info(f"Locators saved to: {file_path}")
        except Exception as e:
            logging.error(f"Failed to save locators to {file_path}: {e}")

        logging.info(f"Extracted {len(unique_locators)} locators")
        return unique_locators

    except Exception as e:
        logging.error(f"Error extracting locators: {e}")
        raise