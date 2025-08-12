import requests
import json
import logging

def query_ollama(prompt, model="qwen2.5-coder:32b", endpoint="http://10.31.5.112:5353/api/generate"):
    """
    Send a prompt to the Ollama API and return the response.
    
    Args:
        prompt (str): The prompt to send to the model.
        model (str): The model name (default: 'qwen2.5-coder:32b').
        endpoint (str): The Ollama API endpoint.
    
    Returns:
        str: The model's response, or None if the request fails.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        logging.info(f"Sending prompt to Ollama: {model} | Payload size : {len(json.dumps(payload))} | prompt : {prompt}")
        response = requests.post(endpoint, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        model_response=result.get("response", "")
        if not model_response.strip():
            logging.warning("Ollama API returned successfull status but the response content is empty")
            return None
        
        return model_response
    
    except requests.exceptions.Timeout as e:
        logging.error(f"Ollama API request timedout : {e}")
        return None
    except requests.exceptions.HTTPError as e:
        logging.error(f"Ollama API request failed with HTTP status : {e.response.status_code} - {e.response.text}")
        return None
    except requests.RequestException as e:
        logging.error(f"Ollama API request failed with a network error : {e}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from Ollama API response. Response text : {response.text}")
        return None

def generate_json_with_ollama(prompt, max_retries=3):
    """
    Generate JSON output using Ollama, with retries for invalid JSON.
    
    Args:
        prompt (str): The prompt to generate JSON output.
        max_retries (int): Number of retries for invalid JSON.
    
    Returns:
        list or dict: Parsed JSON output, or None if parsing fails.
    """
    for attempt in range(max_retries):
        response = query_ollama(prompt)
        if not response:
            logging.warning(f"Ollama returned empty response on attempt {attempt + 1}")
            continue
        
        try:
            parsed = json.loads(response.strip())
            return parsed
        except json.JSONDecodeError as e:
            logging.warning(f"Failed to parse JSON on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logging.info("Retrying with refined prompt...")
                prompt += "\n\nCRITICAL: The output MUST be a valid JSON array. Do not include any text, explanations, or markdown syntax before or after the JSON content."
    
    logging.error("Failed to generate valid JSON after multipleretries")
    return None