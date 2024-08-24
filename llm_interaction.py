# -----------------------------------------------------------------------------
# Firebird Code Generator
# Copyright (c) 2024 James Stakelum
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
# -----------------------------------------------------------------------------

import os
import configparser
from typing import Optional
from api_caller import generate_content_with_retry

# Logging handler
import logging
logger = logging.getLogger(__name__)

class FlexibleConfigParser(configparser.ConfigParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.OPTCRE = configparser.re.compile(
            r'(?P<option>[^:=\s][^:=]*)'
            r'\s*(?P<vi>[:=])\s*'
            r'(?P<value>.*)$'
        )

def read_config(file_path: str) -> FlexibleConfigParser:
    config = FlexibleConfigParser()
    config.read(file_path)
    return config

def get_llm_response(prompt: str, language: str, include_markers: bool = True, max_retries: int = 3) -> Optional[str]:
    """Generate response from LLM, optionally requesting code, documentation, and file markers."""
    if include_markers:

        # Determine the file extension based on the language
        extension = {
            'python': 'py',
            'java': 'java',
            'perl': 'pl'
        }.get(language, 'txt')  # Default to .txt if language is unknown

        prompt += (
            f"\n\nPlease generate the project code, documentation, and any other required text-based files. "
            f"For code, mark the start and end using the format `<<<CODE START: filename.{extension}>>>` and `<<<CODE END: filename.{extension}>>>`. "
            f"For documentation, use `<<<DOC START: filename.{extension}>>>` and `<<<DOC END: filename.{extension}>>>`. "
            f"For other text-based files (e.g., .txt, .csv, .json), use `<<<FILE START: filename.extension>>>` and `<<<FILE END: filename.extension>>>`."
        )
    return get_response_with_retry(prompt, include_markers, max_retries)

def get_response_with_retry(prompt: str, check_for_markers: bool = True, max_retries: int = 3) -> Optional[str]:
    config = read_config('config.txt')
    preferred_llm = config['Preferences']['preferred_llm']
    model = config['Models'][preferred_llm]
    
    api_key = os.environ.get(f"{preferred_llm.upper()}_API_KEY")
    if not api_key:
        raise ValueError(f"{preferred_llm.upper()}_API_KEY environment variable is not set")

    for attempt in range(max_retries):
        try:
            response = generate_content_with_retry(prompt, api_key, model, preferred_llm)
            
            if check_for_markers and response:
                if '<<' not in response or '>>' not in response:
                    logger.warning("Response does not contain expected markers. Retrying...")
                    continue
            
            return response

        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                logger.error("Max retries reached. Failed to get a valid response.")
                return None

    return None


