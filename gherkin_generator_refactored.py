import os
import logging
import json
from ollama_utils import query_ollama
from utils import sanitize_identifier_for_method_name

class LocatorMap:
    def __init__(self):
        self._map = {}

    def add_locator(self, identifier, element_info, gherkin_step):
        self._map[identifier] = {
            "element_info": element_info,
            "gherkin_step": gherkin_step
        }

    def get_all_mappings(self):
        return self._map

def generate_gherkin(class_name, locators, output_dir="FEATURES"):
    """
    Generate a Gherkin feature file with positive, negative, and edge case scenarios
    based on the class name and locators using model.
    Returns the path to the generated feature file and a LocatorMap instance.
    """
    project_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(project_dir, "FEATURES")
    os.makedirs(output_dir, exist_ok=True)
    safe_class_name = ''.join(word.capitalize() for word in class_name.split('_'))
    feature_file_name = f"{safe_class_name}.feature"
    feature_file_path = os.path.join(output_dir, feature_file_name)

    locator_map = LocatorMap()

    # Craft prompt for Model to generate Gherkin
    locators_json = json.dumps(locators, indent=2)
    prompt = (
        "You are an expert test automation engineer specializing in complex web applications. Your task is to write a Gherkin feature file based on a list of locators extracted from a webpage.\n\n"
    "Follow this process:\n"
    "1. **Analyze the Locators**: Examine the `identifier` and `category` of each locator to infer the primary user interactions available on the page.\n"
    "2. **Determine Page Type**: Based on the available interactions, classify the page's purpose. For example, is it a data entry form, an analytical dashboard, a simple content page, or something else?\n"
    "3. **Generate a mix of scenarios:**:"
    "a. **Positive Scenarios**: Test the happy path and successful submissions. "
    "b. **Negative Scenarios**: Test for explicit validation errors with invalid data (e.g., incorrect email format, phone number with letters). "
    "c. **Edge Case Scenarios**: Test boundary values, empty submissions, and unusually long inputs. "
    "**For data entry forms, use 'Scenario Outline' with 'Examples' tables to test multiple data variations for a single scenario.** "
    "The goal is to test the page's core functionality.\n\n"
    "**Guidance for Different Page Types:**\n"
    "- **For a Data Form**: Scenarios should test successful submission, validation errors with missing/invalid data, and boundary values.\n"
    "- **For an Analytical Dashboard**: Scenarios might include verifying the default data state, interacting with controls (like date pickers, search fields, or dropdown filters), testing data updates after applying a filter, checking for tooltips on charts, and verifying data export functionality if present.\n\n"
    "The output must be only a valid Gherkin feature file string, without any markdown or extra text.\n"
    "Use the identifiers from the locators in your Gherkin steps.\n\n"
    "Locators:\n"
    f"{locators_json}\n\n"
    "Feature name: {safe_class_name} Feature"
    )

    # Generate Gherkin content using Ollama
    gherkin_content = query_ollama(prompt)
    if not gherkin_content:
        logging.error("Ollama failed to generate Gherkin content.")
        raise RuntimeError("Failed to generate Gherkin content using model-based approach.")

    # Parse Gherkin content to populate locator_map
    for line in gherkin_content.splitlines():
        line = line.strip()
        if line.startswith(("Given ", "When ", "And ", "Then ")):
            for locator in locators:
                identifier = locator.get("identifier", "").replace("_", " ")
                if identifier.lower() in line.lower():
                    locator_map.add_locator(identifier, locator, line)
                    break

    # Write feature file
    try:
        with open(feature_file_path, "w", encoding="utf-8") as f:
            f.write(gherkin_content)
        logging.info(f"Gherkin feature file generated: {feature_file_path}")
    except Exception as e:
        logging.error(f"Failed to write Gherkin feature file {feature_file_path}: {e}")
        return None, None

    return feature_file_path, locator_map



# "You are an expert test automation engineer specializing in complex web applications. Your task is to write a Gherkin feature file based on a list of locators extracted from a webpage.\n\n"
#     "Follow this process:\n"
#     "1. **Analyze the Locators**: Examine the `identifier` and `category` of each locator to infer the primary user interactions available on the page.\n"
#     "2. **Determine Page Type**: Based on the available interactions, classify the page's purpose. For example, is it a data entry form, an analytical dashboard, a simple content page, or something else?\n"
#     "3. **Generate a mix of scenarios:**: Create meaningful positive, negative, and edge case scenarios that are appropriate for the identified page type. The goal is to test the page's core functionality.\n\n"
#     "**Guidance for Different Page Types:**\n"
#     "- **For a Data Form**: Scenarios should test successful submission, validation errors with missing/invalid data, and boundary values.\n"
#     "- **For an Analytical Dashboard**: Scenarios might include verifying the default data state, interacting with controls (like date pickers, search fields, or dropdown filters), testing data updates after applying a filter, checking for tooltips on charts, and verifying data export functionality if present.\n\n"
#     "The output must be only a valid Gherkin feature file string, without any markdown or extra text.\n"
#     "Use the identifiers from the locators in your Gherkin steps.\n\n"
#     "Locators:\n"
#     f"{locators_json}\n\n"
#     "Feature name: {safe_class_name} Feature"