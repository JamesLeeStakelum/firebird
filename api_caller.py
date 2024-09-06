###############################################################################
# Firebird Code Generator
# Copyright (c) 2024 James Stakelum
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
###############################################################################

###############################################################################
# This module handles all the calls to LLMs (eg, OpenAI, Gemini, Perplexity, Groq, Anthropic)
###############################################################################

import re
import os
import configparser
import requests
import time
from datetime import datetime

# Imports for LLMs. Note: anthropic and perplexity don't require special imports as they use requests
from openai import OpenAI
import google.generativeai as genai
from groq import Groq

# Logging handler
import logging
logger = logging.getLogger(__name__)

MAX_RETRIES    = 3
INITIAL_DELAY  = 1
BACKOFF_FACTOR = 2

###############################################################################
# Make requests and get responses using multiple LLMs.
# Each LLM performs several iterations of reflection, after which panel of 
# experts evaluates and scores the final response of each LLM.
###############################################################################
def multi_llm_request(request, logs_folder, include_markers, max_reflection_iterations=3, panel_size=3):

    ###############################################################################
    # Make list of the LLMs available for use. If a key exists, we assume LLM is available.
    ###############################################################################

    global all_llm_list, all_api_keys, all_llm_models

    get_all_llm_info()

    ###############################################################################
    # Make list of LLMs to be used in the panel of experts
    ###############################################################################

    llm_count = 0

    panel_list = []

    for llm_name in all_llm_list:

        if llm_count < panel_size: 
            panel_list.append(llm_name)  
            llm_count += 1

    ###############################################################################
    # Submit request to each LLM, and do several iterations of reflection
    ###############################################################################
    
    response_number = 0
    
    # Dictionary to contain LLM responses
    response_dict = {}

    llm_number = 0
    
    # Iterate through each LLM
    for llm_name in panel_list:
   
        # Do reflection for several iterations on this LLM
        for request_number in range (1, max_reflection_iterations + 1):
    
            print(f"LLM: {llm_name} Request number: {request_number}")

            # For first iteration, use the original request
            if (request_number == 1): this_request = request
    
            # For second request, reflect the previous response and bundle it with the request
            if (request_number > 1):
                reflected_request = "I am trying to find the best possible solution to a task. I have a proposed solution I am considering, but I suspect the solution can be improved upon. And that is why I need your help.\n\n"

                reflected_request += "##################\n\n"
                reflected_request += "Before I show you the proposed solution, I want to first show you the wording of the task for which the proposed solution was created. Here is the original task:\n\n"
                reflected_request += request + "\n\n"
                reflected_request += "##################\n\n"
 
                block_quoted_text = add_blockquote_prefix(response)
                reflected_request += "And now, here is the proposed solution to that task request:\n"
                reflected_request += block_quoted_text + "\n\n"
                reflected_request += "##################\n\n"

                reflected_request += "***Your new task***\n"
                reflected_request += "As mentioned already, I think the proposed solution can be improved upon. " 
                reflected_request += "So, what I need you to do is this: Please reflect upon the original request, and the candidate solution, and try to produce an improved solution that is better that the proposed solution.\n"
    
                this_request = reflected_request
    
            # Make request to the LLM
            response = call_llm_with_logging(this_request, logs_folder, llm_name, include_markers)

            # Sleep to avoid breaking speed limit on the LLM
            time.sleep(0.5)
            
        # Store the response and some metadata about the request in a container
        llm_number += 1
        response_dict[llm_number] = {'llm_name': llm_name, 'response': response, 'reflection_iteration': request_number}
    
    ###############################################################################
    # Bundle the candidate responses from each LLM into a request
    ###############################################################################
    
    # Take reflected output of each LLM, and show them to each LLM and ask for voting/ranking
    voting_request = ""
    voting_request += "I want to find the best possible solution to a task. I gave the same task to multiple LLMs and asked for their proposed solution.\n\n"
    voting_request += "\n\n##################\n\n"
    voting_request += "Here is the original task request:\n"

    block_quoted_task = add_blockquote_prefix(request)
    voting_request += block_quoted_task + "\n\n"
    voting_request += "\n\n##################\n\n"

    voting_request += "As mentioned, I asked multiple LLMs to do that task, and I have several possible solutions. But, I don't know which of the solutions is best. "
    voting_request += "So, I need you to examine each candidate solution, and determine which in your judgement is the best solution from all of them.\n\n"
    voting_request += "Here (below) are the candidate solutions, which I have assigned numbers so you can refer to them by their number:\n"
    voting_request += "\n\n##################\n\n"
    
    for llm_number in range(1, llm_count + 1):
    
        dict_value = response_dict[llm_number]
        response   = dict_value['response']
        block_quoted_response = add_blockquote_prefix(response)

        if response:
            voting_request += f"Here is solution number {llm_number}:\n"
            voting_request += block_quoted_response
            voting_request += "\n\n##################\n\n"    
    
    voting_request += "Now, what I need you to do, is ruminate over the original request and also each of the numbered candidate solutions. Then choose which one of the solutions is the very best. "
    voting_request += "Indicate your preference for which is the best solution by giving me the number for the best solution.\n\n"
    voting_request += "Provide your response in the following format:\n"   
    voting_request += "ANSWER: [number]\n"
    voting_request += "Where [number] is 1, 2, 3, et cetera, corresponding to the correct answer. Do not include any other text or explanation in your response.\n\n"
  
    ###############################################################################
    # Ask each of the LLMs to examine the candidate responses and 
    # choose which is best
    ###############################################################################
    
    # Initialize a dictionary
    votes = {}
    for llm_number in range(1, 10): votes[llm_number] = 0
    
    # Call each LLM and ask it to evaluate the bundle of candidate solutions, and choose which is best
    for llm_name in panel_list:
    
        # Make request to the LLM
        response = call_llm_with_logging(voting_request, logs_folder, llm_name, include_markers)
    
        # Parse the response
        chosen_solution = extract_answer_number(response)
  
        # Increment the vote for the LLM number
        if int(chosen_solution) > 0: 
            votes[chosen_solution] += 1

    ###############################################################################
    # Determine which LLM response has most votes
    ###############################################################################
    
    best_solution_number = 1 # Set a default

    max_votes = -1
    for llm_number in range(1, llm_count + 1):
    
        if (votes[llm_number] > max_votes):
            max_votes = votes[llm_number] 
            best_solution_number = llm_number
    
            print(f"Best: {best_solution_number}")

    dict_value = response_dict[best_solution_number]
    best_response = dict_value['response']
    best_llm_name = dict_value['llm_name']

    print(f"\nSolution with most votes is: {best_solution_number} which has {max_votes} votes.")

    return best_response

###############################################################################
# We want a section of text to be preceived by the LLM as containing a quote, so we 
# burst the string into lines, prefix each line with the > prefix on each line, 
# then reassemble the lines into a string.
###############################################################################
def add_blockquote_prefix(input_string):

    # Split the input string into a list of lines
    lines = input_string.split('\n')
    
    # Prefix each line with '> '
    prefixed_lines = ['> ' + line for line in lines]
    
    # Reassemble the list of lines into a single string with line feeds
    result_string = '\n'.join(prefixed_lines)
    
    return result_string

###############################################################################
# Given the prompt as input, this logs request, calls function to perform LLM 
# request, gets response, logs response, then returns response
###############################################################################
def call_llm_with_logging(prompt, logs_folder, llm_name, include_markers):

    # Log request
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')  # Microseconds

    request_file_path = os.path.join(logs_folder, f'{timestamp}_request_{llm_name}.txt')  

    with open(request_file_path, 'w', encoding='utf-8') as file: file.write(prompt)

    response = llm_request_with_retry(prompt, logs_folder, llm_name, include_markers)

    # In rare event that we don't have a response, set an empty string
    if response is None: response = '' 

    # Log response
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')  # Microseconds
    log_file_path = os.path.join(logs_folder, f'{timestamp}_response_{llm_name}.txt')
    with open(log_file_path, 'w', encoding='utf-8') as file: file.write(response)

    return response

###############################################################################
# Wrapper around LLM calls
###############################################################################
def llm_request_with_retry(prompt, logs_folder, llm_name, include_markers):

    retry_count = 0
    delay = INITIAL_DELAY
    last_valid_response = None

    while retry_count < MAX_RETRIES:
        try:
            response = call_llm(prompt, llm_name)

            if not response or not response.strip():
                raise ValueError("Empty response returned. Retrying...")

            last_valid_response = response  # Store the last valid response

            if include_markers and ('<<' not in response or '>>' not in response):
                logger.warning("Response does not contain expected markers. Retrying...")
                retry_count += 1
                time.sleep(delay)
                delay *= BACKOFF_FACTOR
                continue

            if retry_count > 0:
                logger.info("Success on retry!")

            return response

        except Exception as e:
            logger.error(f"Error: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
            retry_count += 1
            delay *= BACKOFF_FACTOR

    logger.error(f"Failed to find markers after {MAX_RETRIES} attempts.")
    return last_valid_response  # Return the last valid response, even without markers

###############################################################################
# Gets API key and model for the LLM, then calls function specific for the LLM.
###############################################################################
def call_llm(prompt, llm_name):

    global all_llm_list, all_api_keys, all_llm_models

    get_all_llm_info()

    api_key = all_api_keys[llm_name]
    model   = all_llm_models[llm_name]

    if llm_name == "openai":
        return send_to_openai(prompt, api_key, model)

    elif llm_name == "gemini":
        return send_to_gemini(prompt, api_key, model)

    elif llm_name == "anthropic":
        return send_to_anthropic(prompt, api_key, model)

    elif llm_name == "perplexity":
        return send_to_perplexity(prompt, api_key, model)

    elif llm_name == "groq":
        return send_to_groq(prompt, api_key, model)

    else:
        raise ValueError(f"Unsupported LLM provider: {llm_name}")

###############################################################################
# Get LLM model and API key for all LLMs. Populates values for
# all_llm_list, all_api_keys, all_llm_models
###############################################################################
def get_all_llm_info():

    global all_llm_list, all_api_keys, all_llm_models    

    # Read models from config file
    config = configparser.ConfigParser()
    config.read('config.txt')  

    # Make a list of LLMs which are available for use
    all_llm_list = []

    if os.getenv("GEMINI_API_KEY"):     all_llm_list.append('gemini')
    if os.getenv("OPENAI_API_KEY"):     all_llm_list.append('openai')
    if os.getenv("PERPLEXITY_API_KEY"): all_llm_list.append('perplexity')
    if os.getenv("ANTHROPIC_API_KEY"):  all_llm_list.append('anthropic')
    if os.getenv("GROQ_API_KEY"):       all_llm_list.append('groq')

    # Get models for each LLM service
    all_llm_models = {}
    for llm in all_llm_list:
        all_llm_models[llm] = ''
        if llm in config['Models']: all_llm_models[llm] = config['Models'][llm]
 
    # Get API keys from environment
    all_api_keys = {}
    for llm in all_llm_list: all_api_keys[llm] = ''

    if os.getenv("OPENAI_API_KEY"):     all_api_keys['openai']     = os.getenv("OPENAI_API_KEY")
    if os.getenv("GEMINI_API_KEY"):     all_api_keys['gemini']     = os.getenv("GEMINI_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):  all_api_keys['anthropic']  = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("GROQ_API_KEY"):       all_api_keys['groq']       = os.getenv("GROQ_API_KEY")
    if os.getenv("PERPLEXITY_API_KEY"): all_api_keys['perplexity'] = os.getenv("PERPLEXITY_API_KEY")

    return

###############################################################################
# OpenAI
###############################################################################
def send_to_openai(prompt, api_key, model):

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model,
    )
    return completion.choices[0].message.content

###############################################################################
# Google Gemini
###############################################################################
def send_to_gemini(prompt, api_key, model):

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model)
    response = model.generate_content(prompt)
    return response.text

###############################################################################
# Anthropic
###############################################################################
def send_to_anthropic(prompt, api_key, model):

    api_url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"  # Or the latest version you prefer
    }
    data = {
        "model": model,
        "max_tokens": 4096,  # Adjust as needed
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(api_url, headers=headers, json=data)
    response.raise_for_status()  # Check for HTTP errors
    result = response.json()
    response_text = result['content'][0]['text'].strip()
    return response_text

###############################################################################
# Groq
###############################################################################
def send_to_groq(prompt, api_key, model):

    client = Groq(api_key=api_key)
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model,
    )
    return chat_completion.choices[0].message.content

###############################################################################
# Perplexity
###############################################################################
def send_to_perplexity(prompt, api_key, model):

    PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

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

###############################################################################
# Extracting answer number
###############################################################################
def extract_answer_number(response):

    # Try to find the exact format first
    exact_match = re.search(r'^ANSWER:\s*(\d+)\s*$', response, re.MULTILINE)
    if exact_match:
        return int(exact_match.group(1))

    # If exact format not found, try more lenient patterns
    number_patterns = [
        r'ANSWER:\s*(\d+)',  # ANSWER: followed by number
        r'(\d+)\s*$',        # Number at the end of the string
        r'(\d+)',            # Any number in the string
    ]

    for pattern in number_patterns:
        match = re.search(pattern, response)
        if match:
            return int(match.group(1))

    # If no number found, look for number words
    number_words = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
    for i, word in enumerate(number_words, 1):
        if word in response.lower():
            return i

    # If still no match, return 0 and log a warning
    logger.warning("No valid answer number found in the response. Returning 0.")
    return 0



