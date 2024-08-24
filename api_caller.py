# -----------------------------------------------------------------------------
# Firebird Code Generator
# Copyright (c) 2024 James Stakelum
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
# -----------------------------------------------------------------------------

import os
import configparser
import requests
import time

# Logging handler
import logging
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
INITIAL_DELAY = 1
BACKOFF_FACTOR = 2

# API URLs and Versions
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Read config.txt
config = configparser.ConfigParser()
config.read('config.txt')
preferred_llm = config['Preferences']['preferred_llm']

# Conditional imports based on preferred_llm
if preferred_llm == 'openai':
    from openai import OpenAI
elif preferred_llm == 'gemini':
    import google.generativeai as genai
elif preferred_llm == 'groq':
    from groq import Groq
# Note: anthropic and perplexity don't require special imports as they use requests

def send_to_llm(prompt, api_key, model, llm_provider):
    if llm_provider == "openai":
        return send_to_openai(prompt, api_key, model)
    elif llm_provider == "gemini":
        return send_to_gemini(prompt, api_key, model)
    elif llm_provider == "anthropic":
        return send_to_anthropic(prompt, api_key, model)
    elif llm_provider == "perplexity":
        return send_to_perplexity(prompt, api_key, model)
    elif llm_provider == "groq":
        return send_to_groq(prompt, api_key, model)
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

def send_to_openai(prompt, api_key, model):
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model,
    )
    return completion.choices[0].message.content

def send_to_gemini(prompt, api_key, model):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model)
    response = model.generate_content(prompt)
    return response.text

def send_to_anthropic(prompt, api_key, model):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION
    }
    data = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(ANTHROPIC_API_URL, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    return result['content'][0]['text'].strip()


def send_to_groq(prompt, api_key, model):
    client = Groq(api_key=api_key)
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model,
    )
    return chat_completion.choices[0].message.content

def send_to_perplexity(prompt, api_key, model):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 20000  # Adjust as needed
    }
    response = requests.post(PERPLEXITY_API_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def generate_content_with_retry(prompt, api_key, model, llm_provider):
    retry_count = 0
    delay = INITIAL_DELAY

    while retry_count < MAX_RETRIES:
        try:
            response_text = send_to_llm(prompt, api_key, model, llm_provider)

            if not response_text.strip():
                raise ValueError("Empty response returned. Retrying...")

            if retry_count > 0:
                logger.info("Success on retry!")

            return response_text

        except Exception as e:
            logger.error(f"Error: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
            retry_count += 1
            delay *= BACKOFF_FACTOR

    logger.error(f"Failed after {MAX_RETRIES} attempts. Exiting.")
    return None


