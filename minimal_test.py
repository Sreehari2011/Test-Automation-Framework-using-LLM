from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time

print("--- Starting Minimal WebDriver Test ---")

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--remote-debugging-pipe")

# Use an explicit Service object to get detailed logs
service = Service(log_output="chromedriver_minimal.log")

driver = None
try:
    print("Initializing WebDriver...")
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver initialized successfully.")

    print("Setting page load timeout to 30 seconds...")
    driver.set_page_load_timeout(30)

    target_url = "https://the-internet.herokuapp.com/add_remove_elements/"
    print(f"Navigating to {target_url}...")
    driver.get(target_url)

    # If it succeeds, it will print the following
    print("\n--- TEST SUCCEEDED! ---")
    print(f"Successfully loaded page. Title: {driver.title}")

except Exception as e:
    print("\n--- TEST FAILED ---")
    print(f"An error occurred: {e}")
    print("\nPlease check the 'chromedriver_minimal.log' file for detailed error messages from the driver.")

finally:
    if driver:
        print("Closing WebDriver.")
        driver.quit()
    print("--- Minimal Test Finished ---")