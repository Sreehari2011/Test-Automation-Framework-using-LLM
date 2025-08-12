import os
import logging
import json
import re
from bs4 import BeautifulSoup
from ollama_utils import generate_json_with_ollama
from utils import sanitize_identifier_for_method_name

def generate_pom(driver, class_name, output_dir="pom"):
    """
    Generate a Page Object Model (POM) Python file.
    """
    try:
        # Parse HTML content with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        html_content = str(soup.prettify())
        html_content = re.sub(r'\s+', ' ', html_content).strip()

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
            "  }\n"
            "]\n\n"
            "HTML content:\n"
            f"{html_content[:2000]}"
        )

        # Generate locators using Ollama
        locators = generate_json_with_ollama(prompt)
        if not locators or not isinstance(locators, list):
            logging.error("Ollama failed to generate valid locators.")
            raise RuntimeError("Failed to generate locators for POM using model-based approach.")

        # Validate and clean locators
        unique_locators = []
        seen_raw_identifiers = set()
        if isinstance(locators, list):
            for locator_item in locators:
                if not isinstance(locator_item, dict):
                    logging.warning(f"Skipping non-dictionary item in locators list: {locator_item}")
                    continue
                
                raw_identifier = locator_item.get("identifier")
                
                if not raw_identifier or raw_identifier in seen_raw_identifiers:
                    if raw_identifier in seen_raw_identifiers:
                        logging.debug(f"Skipping duplicate raw_identifier: {raw_identifier}")
                    continue
                
                if not locator_item.get("xpath") and not locator_item.get("css_selector"):
                    logging.debug(f"Skipping locator for '{raw_identifier}' due to missing both xpath and css_selector.")
                    continue
                
                seen_raw_identifiers.add(raw_identifier)
                unique_locators.append(locator_item)
        else:
            logging.error(f"Locators variable is not a list (type: {type(locators)}). Cannot process for POM generation.")
            raise RuntimeError("Invalid locators format for POM generation.")

        # Save locators to JSON file
        project_dir = os.path.dirname(os.path.abspath(__file__))
        locators_output_dir = os.path.join(project_dir, "locators")
        os.makedirs(locators_output_dir, exist_ok=True)
        
        sanitized_class_name_for_file = sanitize_identifier_for_method_name(class_name)
        locators_file_name = f"{sanitized_class_name_for_file}_locators.json"
        locators_file_path = os.path.join(locators_output_dir, locators_file_name)
        try:
            serializable_locators = []
            for loc_item in unique_locators:
                 serializable_locators.append({
                     "identifier": loc_item.get("identifier", "unknown_id"),
                     "category": loc_item.get("category", "unknown_cat"),
                     "xpath": loc_item.get("xpath", ""),
                     "css_selector": loc_item.get("css_selector", "")
                 })
            with open(locators_file_path, "w", encoding="utf-8") as f:
                json.dump(serializable_locators, f, indent=4)
            logging.info(f"Locators (used for POM) saved to: {locators_file_path}")
        except Exception as e_save_loc:
            logging.error(f"Failed to save locators to {locators_file_path}: {e_save_loc}")

        # Generate POM file content
        pom_content_output_dir = os.path.join(project_dir, output_dir)
        os.makedirs(pom_content_output_dir, exist_ok=True)
        
        pascal_case_class_name = ''.join(word.capitalize() for word in str(class_name).split('_'))
        if not pascal_case_class_name:
            pascal_case_class_name = "DefaultPage"

        snake_case_file_name_base = sanitize_identifier_for_method_name(class_name)
        pom_file_name = f"{snake_case_file_name_base}_page.py"
        pom_file_path = os.path.join(pom_content_output_dir, pom_file_name)

        # Fixed POM content with proper string termination
        pom_content = [
            "from selenium.webdriver.common.by import By\n",
            "from selenium.webdriver.support.ui import WebDriverWait\n",
            "from selenium.webdriver.support import expected_conditions as EC\n",
            "from selenium.webdriver.support.ui import Select\n",
            "import logging\n",
            "\n",
            f"class {pascal_case_class_name}Page:\n",
            "    def __init__(self, driver):\n",
            "        self.driver = driver\n",
            "        self.wait = WebDriverWait(driver, 20)\n",
            "\n"
        ]

        generated_method_names = set()

        for locator_item in unique_locators:
            raw_identifier = locator_item.get("identifier")
            category = locator_item.get("category", "other")
            
            method_name_base = sanitize_identifier_for_method_name(raw_identifier, category)
            
            actual_method_name_part = method_name_base
            count = 1
            while actual_method_name_part in generated_method_names:
                actual_method_name_part = f"{method_name_base}_{count}"
                count += 1
            generated_method_names.add(actual_method_name_part)

            xpath = locator_item.get("xpath", "")
            if not xpath:
                logging.warning(f"No XPath locator for identifier '{raw_identifier}' (sanitized: {actual_method_name_part}), skipping POM method.")
                continue

            locator_strategy = "By.XPATH"
            locator_value = xpath
            locator_value_escaped = locator_value.replace("'", "\\'")

            method_added = False
            if category == "input_field":
                pom_content.append(
                    f"    def enter_{actual_method_name_part}(self, value):\n"
                    f"        logging.debug(f\"Entering '{{value}}' into {actual_method_name_part} using XPath: {locator_value_escaped}\")\n"
                    f"        element = self.wait.until(EC.presence_of_element_located(({locator_strategy}, '{locator_value_escaped}')))\n"
                    f"        element.clear()\n"
                    f"        element.send_keys(value)\n"
                    "\n"
                )
                method_added = True
            elif category == "button":
                pom_content.append(
                    f"    def click_{actual_method_name_part}(self):\n"
                    f"        logging.debug(f\"Clicking {actual_method_name_part} using XPath: {locator_value_escaped}\")\n"
                    f"        element = self.wait.until(EC.element_to_be_clickable(({locator_strategy}, '{locator_value_escaped}')))\n"
                    f"        element.click()\n"
                    "\n"
                )
                method_added = True
            elif category == "checkbox":
                pom_content.append(
                    f"    def check_{actual_method_name_part}(self):\n"
                    f"        logging.debug(f\"Checking {actual_method_name_part} using XPath: {locator_value_escaped}\")\n"
                    f"        element = self.wait.until(EC.presence_of_element_located(({locator_strategy}, '{locator_value_escaped}')))\n"
                    f"        if not element.is_selected():\n"
                    f"            element.click()\n"
                    "\n"
                )
                method_added = True
            elif category == "dropdown":
                pom_content.append(
                    f"    def select_option_from_{actual_method_name_part}(self, option_text):\n"
                    f"        logging.debug(f\"Selecting '{{option_text}}' from {actual_method_name_part} using XPath: {locator_value_escaped}\")\n"
                    f"        element = self.wait.until(EC.presence_of_element_located(({locator_strategy}, '{locator_value_escaped}')))\n"
                    f"        select = Select(element)\n"
                    f"        select.select_by_visible_text(option_text)\n"
                    "\n"
                )
                method_added = True
            elif category == "radio":
                pom_content.append(
                    f"    def select_{actual_method_name_part}(self):\n"
                    f"        logging.debug(f\"Selecting radio {actual_method_name_part} using XPath: {locator_value_escaped}\")\n"
                    f"        element = self.wait.until(EC.element_to_be_clickable(({locator_strategy}, '{locator_value_escaped}')))\n"
                    f"        if not element.is_selected():\n"
                    f"            element.click()\n"
                    "\n"
                )
                method_added = True
            
            if not method_added:
                logging.info(f"No specific POM method template for category '{category}' for identifier '{raw_identifier}'.")

        # Write the POM file
        try:
            with open(pom_file_path, "w", encoding="utf-8") as f:
                f.write("".join(pom_content))
            logging.info(f"Generated POM file: {pom_file_path}")
            return pom_file_path
        except Exception as e_write_pom:
            logging.error(f"Failed to write POM file {pom_file_path}: {e_write_pom}")
            return None

    except Exception as e_main_pom:
        logging.error(f"Error in generate_pom function: {e_main_pom}")
        raise