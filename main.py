###############################################################################
# Firebird Code Generator
# Copyright (c) 2024 James Stakelum
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
###############################################################################

from datetime import datetime
import os
import sys
import subprocess
import shutil
import configparser
import logging
import re
import configparser
from datetime import datetime
from typing import Optional
from api_caller import *

###############################################################################
# Logging Setup
###############################################################################

# Logging handler
def setup_logging():
    config = configparser.ConfigParser()
    config.read('config.txt')
    
    log_level = config['Logging'].get('level', 'INFO').upper()
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logging.basicConfig(level=numeric_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler("firebird_generator.log"),
                            logging.StreamHandler()
                        ])


###############################################################################
# File Handling and Utility Functions
###############################################################################

def read_params_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    
    params_data = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()

    for line in lines:
        if '=' in line:
            key, value = line.strip().split('=', 1)
            params_data[key.strip()] = value.strip()
        elif ':' in line:
            key, value = line.strip().split(':', 1)
            params_data[key.strip()] = value.strip()

    return params_data


def read_tasks_file(file_path):
    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            pass  # Create an empty tasks.txt file

    with open(file_path, 'r') as file:
        lines = file.readlines()

    new_tasks = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line:
            new_tasks.append(stripped_line)

    archive_path = file_path.replace("tasks.txt", "tasks_archive.txt")
    with open(archive_path, 'a') as archive_file:
        for task in new_tasks:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            archive_file.write(f"{timestamp} - {task}\n")

    return "\n".join(new_tasks)

def create_subfolder(folder_name):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Created subfolder: {folder_name}")
    return

# This removes backticks ```` from files extracted from LLM response.
def clean_content(content):
    """
    Clean the content by removing surrounding and internal backticks,
    as well as language specifiers.
    """
    lines = content.split('\n')
    cleaned_lines = []
    skip_next = False

    for line in lines:
        if skip_next:
            skip_next = False
            continue
        
        # Remove lines that are just backticks
        if line.strip() == '```' or line.strip() == '`':
            continue
        
        # Remove language specifier lines
        if line.strip().startswith('```'):
            skip_next = True
            continue
        
        # Remove leading and trailing backticks from each line
        line = line.strip('`')
        
        cleaned_lines.append(line)

    # Remove any trailing empty lines
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()

    return '\n'.join(cleaned_lines)

def parse_llm_response(response):
    code_blocks = {}
    doc_blocks = {}
    file_blocks = {}
    
    # Regular expression to match the start and end markers, including potential surrounding backticks
    pattern = r'`?<<<(CODE|FILE|DOC) START: (.+?)>>>`?\s*(.*?)\s*`?<<<\1 END: \2>>>`?'
    
    # Find all matches in the response
    matches = re.finditer(pattern, response, re.DOTALL)
    
    for match in matches:
        block_type = match.group(1)
        filename = match.group(2)
        content = match.group(3)
        
        if content:
            # Clean the content
            cleaned_content = clean_content(content)
            
            if block_type == 'CODE':
                code_blocks[filename] = cleaned_content
            elif block_type == 'DOC':
                doc_blocks[filename] = cleaned_content
            elif block_type == 'FILE':
                file_blocks[filename] = cleaned_content
    
    return code_blocks, doc_blocks, file_blocks

###############################################################################
# Project Configuration and Backup Management
###############################################################################

# Read config file
def get_preferred_llm():

    global preferred_llm_name

    config = configparser.ConfigParser()
    config.read('config.txt')

    preferred_llm_name = config['Preferences']['preferred_llm']


def create_code_history_backup(project_folder):
    """Create a backup of all files in the project folder before making any changes."""
    
    # Check if there are any code files in the project folder
    code_files_exist = False
    for root, dirs, files in os.walk(project_folder):
        for file in files:
            if file.endswith(('.py', '.java', '.pl', '.php')):  # Add other extensions as needed
                code_files_exist = True
                break
        if code_files_exist:
            break

    # If no code files exist, skip the backup
    if not code_files_exist:
        print("No existing code files found. Skipping backup.")
        return

    # If code files exist, proceed with the backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = os.path.join(project_folder, 'code_history', timestamp)
    os.makedirs(backup_folder, exist_ok=True)

    # Copy all files in the project folder to the backup sub-subfolder
    for root, dirs, files in os.walk(project_folder):
        # Exclude the code_history folder itself from being copied
        if 'code_history' in dirs:
            dirs.remove('code_history')
        
        for file in files:
            source_file = os.path.join(root, file)
            relative_path = os.path.relpath(root, project_folder)
            destination_dir = os.path.join(backup_folder, relative_path)
            os.makedirs(destination_dir, exist_ok=True)
            shutil.copy2(source_file, destination_dir)
    
    print(f"Backup created at {backup_folder}")

###############################################################################
# This reads all the project code and document files and concatenates them into a text bundle
# to put into context for the LLM prompt.
###############################################################################
def create_file_bundle(project_folder, prompt, language):

    code_bundle = ''

    allowed_extensions = ('.txt','.py','.md','.sql','.json','.xml','.csv','.tsv','.pl','.java','.yml','.yaml','.md')

    for root, dirs, files in os.walk(project_folder):
        for file in files:
            if file.lower().endswith(allowed_extensions):
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    relative_path = os.path.relpath(file_path, project_folder)
                    code_bundle += f"\n\n---\n\nFile: {relative_path}\n\n{content}\n\n"
    
    return code_bundle  # Return the code bundle without sending it to LLM yet

###############################################################################
# Code Generation and Compilation
###############################################################################

# Build prompts and call LLMs
def generate_code_for_project(app_folder, prompt, language, main_file):

    # Reads all existing project code and bundles into a string for inclusion in LLM context
    create_code_history_backup(app_folder)
    code_bundle = create_file_bundle(app_folder, prompt, language)

    ###############################################################################
    # Get LLM's understanding of the task
    ###############################################################################

    llm_explanation = ""
    while True:

        # Create a prompt to ask LLM if it understands the task
        blockquoted_prompt = add_blockquote_prefix(prompt)
        understanding_prompt = ""
        understanding_prompt += f"**Specific task assignment**\n"
        understanding_prompt += f"I am preparing to code a program using the {language} programming language\n"
        understanding_prompt += f"However, before beginning any actual coding, is it important to first clarify the specifics of the intended programming task.\n"
        understanding_prompt += f"Therefore, please summarize your understanding of the requested programming task described below:\n\n"
        understanding_prompt += f"{blockquoted_prompt}\n\n"
        understanding_prompt += f"#########################\n\n"
        understanding_prompt += f"Just to clarify: I do not want code or code snippets at this point. The focus at this point must be on describing the functional features of the program, not actual code.\n"

        # If code bundle exists, add it to context
        if code_bundle:

            understanding_prompt += f'Any changes you make must be made to the existing code files and any supporting files as the starting baseline for subsequent changes. '
            understanding_prompt += f"For context, here is a bundle of all the source code and all supporting files as they currently exist:\n"
            understanding_prompt += f"{code_bundle}\n"
            understanding_prompt += f"#########################\n\n"

        # Instruction to not include additional remarks/comments
        understanding_prompt += f"I prefer to have only your description of the task, and no other preliminary or concluding remarks/comments.\n\n"

        response = multi_llm_request(understanding_prompt, logs_folder, include_markers=False)

        llm_explanation = response

        print("Response received from LLM.")
        print(f"LLM's understanding:\n{llm_explanation}\n")

        user_input = input("If the LLM's understanding aligns with your expectations, press [Y]es to confirm, or [N]o to cancel: ").strip().upper()

        if user_input == 'Y':
            # Clear the tasks.txt file only after the user confirms
            with open('tasks.txt', 'w') as file:
                pass  # This will create an empty tasks.txt file
            break
        else:
            sys.exit(0)

    # Determine file extension for the language
    extension = {'python': 'py', 'java': 'java', 'perl': 'pl', 'php': '.php'}.get(language, 'txt')

    ###############################################################################
    # Request LLM to create a detailed architecture document
    ###############################################################################

    blockquoted_prompt = add_blockquote_prefix(prompt)
    blockquoted_llm_explanation = add_blockquote_prefix(llm_explanation)
    architecture_prompt = ""
    architecture_prompt += f"I am preparing to do some computer programming with your assistance, using the {language} programming language.\n"
    architecture_prompt += f"#########################\n"
    architecture_prompt += f"However, I don't want to start performing any coding tasks yet. First, we need to prepare an architecture document, so I can examine your proposed architecture. But, for your awareness, here is the task that was requested:\n\n"
    architecture_prompt += f"{blockquoted_prompt}\n"
    architecture_prompt += f"#########################\n\n"
    architecture_prompt += f"As a reminder, here is how you described the current task assignment, in your own words, in our previous chat response in a conversation we are having:\n"
    architecture_prompt += f"{blockquoted_llm_explanation}\n"
    architecture_prompt += f"#########################\n\n"

    # Request LLM to use highly decomposed coding
    architecture_prompt += f"**Coding Style Preference: Modular and Highly Decomposed**\n"
    architecture_prompt += f"\n"
    architecture_prompt += f"I prefer a coding style that breaks down tasks into very small, focused functions. Here's what I expect:\n"
    architecture_prompt += f"\n"
    architecture_prompt += f"- **Single-Purpose Functions:** Each function should perform only one task. If a task involves multiple steps, break it down into separate functions, each handling one step.\n"
    architecture_prompt += f"- **Modularity:** Functions should be small, self-contained, and easy to understand.\n"
    architecture_prompt += f"- **Clear Structure:** Avoid long, complex functions. Instead, use sequences of short functions to accomplish complex tasks.\n"
    architecture_prompt += f"\n"
    architecture_prompt += f"The benefits of this approach include:\n"
    architecture_prompt += f"- **Fewer Errors:** Smaller functions are easier for the LLM to generate correctly.\n"
    architecture_prompt += f"- **Simpler Debugging:** Isolated functions make it easier to find and fix issues.\n"
    architecture_prompt += f"- **Better Documentation:** Clear, focused functions are easier to describe and understand.\n"
    architecture_prompt += f"- **Flexible Code:** Modular code is easier to modify and extend.\n"
    architecture_prompt += f"\n"
    architecture_prompt += f"Please ensure the code you generate follows this highly modular and functionally decomposed approach.\n"
    architecture_prompt += f"#########################\n"

    # Request for technical architecture document
    architecture_prompt += f"**Architectural document**\n"
    architecture_prompt += f"Before any actual coding is performed, first, it is necessary to create a highly detailed techical architecture document that describes a technical solution for accomplishing the task.\n"
    architecture_prompt += f"So, based on the requested task, please generate a highly detailed technical architecture document.\n"
    architecture_prompt += f"The document will contain the following:\n"
    architecture_prompt += f"For all code modules, the name of the module, the purpose of the module, and list of all functions inside the module.\n"
    architecture_prompt += f"For all functions, the name of the function, the purpose of the function, and the parameters for the function, what the function returns, and a step-by-step description of what the function does.\n"
    architecture_prompt += f"List all function-to-function relationships that show which functions call what.\n"
    architecture_prompt += f"List any supporting files.\n"
    architecture_prompt += f"Save the technical architecture document in a file named technical_architecture.txt\n"
    architecture_prompt += f"\n"
    architecture_prompt += f"When designing the technical architecture, please remember that it is intended for a highly modular and functionally decomposed approach as previously mentioned.\n"
    architecture_prompt += f"#########################\n\n"

    # Prompt regarding indicators of file boundaries
    architecture_prompt += f"**File delimiters**\n"
    architecture_prompt += f"When generating the technical architecture file, use these markers in your response to indicate beginning and end of the file contents:\n"
    architecture_prompt += f"<<<FILE START: technical_architecture.txt>>> and <<<FILE END: technical_architecture.txt>>>.\n"
    architecture_prompt += f"#########################\n\n"

    # Clarify again the specific current task
    architecture_prompt += f"**Specific task assignment**\n"
    architecture_prompt += f"So, what I need you to do now is create the technical architecture document.\n"

    # Call LLM and request architecture document
    response = multi_llm_request(architecture_prompt, logs_folder, include_markers=False)

    architecture_text = response.strip()

    ###############################################################################
    # Extract architecture document from the LLM response, and write to file
    ###############################################################################

    code_blocks, doc_blocks, file_blocks = parse_llm_response(architecture_text)

    if file_blocks:
        for filename, file_content in file_blocks.items():
            file_path = os.path.join(app_folder, filename)
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(file_content)
            print(f"Saved file to {file_path}")  # Debugging line

            architecture_plan = ''
            if (filename == 'technical_architecture.txt'): architecture_plan = file_content

    ###############################################################################
    # Request LLM to generate the code
    ###############################################################################

    while True:
        code_prompt = "";

        # Role prompt
        code_prompt += f"You are an expert professional computer programmer with experience in the {language} language. You follow best practices.\n"
        code_prompt += f"#########################\n"

        code_prompt += f"I need you to generate the code.\n"
        code_prompt += f"#########################\n"
        code_prompt += f"But before you begin coding, there are several important details I need to clarify.\n"
        code_prompt += f"#########################\n"
        code_prompt += f"Here are some guidelines for the program code:\n"
        code_prompt += f"Code must be in the {language} programming language.\n"
        code_prompt += f"The main script must be named '{main_file}'. \n"
        code_prompt += f"#########################\n"

        code_prompt += f"**File encoding preference**\n"
        code_prompt += f"Regarding file encodings, I prefer ASCII, although UTF8 is okay if necessary to have some special characters. But always avoid Unicode.\n"
        code_prompt += f"#########################\n"

        # Request LLM to use highly decomposed coding
        code_prompt += f"**Coding Style Preference: Modular and Highly Decomposed**\n"
        code_prompt += f"\n"
        code_prompt += f"I prefer a coding style that breaks down tasks into very small, focused functions. Here's what I expect:\n"
        code_prompt += f"\n"
        code_prompt += f"- **Single-Purpose Functions:** Each function should perform only one task. If a task involves multiple steps, break it down into separate functions, each handling one step.\n"
        code_prompt += f"- **Modularity:** Functions should be small, self-contained, and easy to understand.\n"
        code_prompt += f"- **Clear Structure:** Avoid long, complex functions. Instead, use sequences of short functions to accomplish complex tasks.\n"
        code_prompt += f"\n"
        code_prompt += f"The benefits of this approach include:\n"
        code_prompt += f"- **Fewer Errors:** Smaller functions are easier for the LLM to generate correctly.\n"
        code_prompt += f"- **Simpler Debugging:** Isolated functions make it easier to find and fix issues.\n"
        code_prompt += f"- **Better Documentation:** Clear, focused functions are easier to describe and understand.\n"
        code_prompt += f"- **Flexible Code:** Modular code is easier to modify and extend.\n"
        code_prompt += f"\n"
        code_prompt += f"Please ensure the code you generate follows this highly modular and functionally decomposed approach.\n"
        code_prompt += f"#########################\n"

        # Request for extensive comments in code
        code_prompt += f"**Comments in the code**\n"
        code_prompt += f"Include extensive comments in the code. Use the # symbol to preceed single-line comments. Use docstrings for multi-line comments\n"
        code_prompt += f"Comments are extremely helpful. They assist the LLM to understand the purpose of the code when I ask the LLM to review the code to either make improvements or fix problems. I like having comments on three levels: 1. for each module, describing the purpose of the module; 2. for each function, describing the purpose of the function; 3. for each operation inside a function, which is normally ever few lines of code, describing the operation.\n"
        code_prompt += f"#########################\n"

        # Avoid backticks in code or any other files
        code_prompt += f"**Avoid backticks in the code and other files**\n"
        code_prompt += f"Backticks almost always cause serious problems when they appear in code and other files. It is best to avoid them altogether. Please don't include backticks in code or any other files.\n"

        # No stubbing
        code_prompt += f"**Provide complete code, not partial code excerpts**\n"
        code_prompt += f"Please provide the complete code module, not just a partial code snippet. Avoid showing only the relevant part; I need the entire code with the changes. Do not provide stubs or partial code. Show the full code after applying the changes.\n"
        code_prompt += f"#########################\n"

        # Don't just focus on the lines of code to be changed. Consider impact on other related parts of the complete solution
        code_prompt += f"**Reflect on all relationships and aspects of the code**\n"
        code_prompt += f"When making code changes such as improving existing code or fixing a bug, a common type of mistake I want to avoid is just focusing on the specific affected lines of code without considering impacts the code change that is being contemplated might have elsewhere in related parts of the system, which can sometimes be very remote.\n"
        code_prompt += f"Therefore, when making changes to existing code, always reflect on all aspects of the code. Consider relationships between functions, and parameters, and external files.\n"
        code_prompt += f"#########################\n"

        # Things to do or check to prevent errors when code executes
        code_prompt += f"**Some things to do and check in the code to prevent possible problems**\n"
        code_prompt += f"Verify the correct usage of data structures and their methods.\n"
        code_prompt += f"Double-check all loop conditions and array indexing.\n"
        code_prompt += f"Ensure all necessary imports are included and correctly specified.\n"
        code_prompt += f"Implement robust input validation for all function parameters.\n"
        code_prompt += f"Include comprehensive error handling with try-except blocks.\n"
        code_prompt += f"Ensure proper type checking.\n"
        code_prompt += f"Include checks for input types, ranges, and validity before processing data, particularly for function parameters and user inputs.\n"
        code_prompt += f"When making REST API calls, ensure the response is checked for validity and completeness before processing.\n"
        code_prompt += f"Use type hints and include runtime type checks can prevent many type-related errors.\n"
        code_prompt += f"When working with lists and dictionaries, include checks to ensure indices or keys exist before accessing them.\n"
        code_prompt += f"Include checks for None or null values before accessing object properties or calling methods, especially when dealing with API responses or database queries.\n"
        code_prompt += f"Implement comprehensive try-except blocks, especially around API calls, file operations, and any code that interacts with external resources.\n"

        # Prompt regarding indicators of file boundaries
        code_prompt += f"**File delimiters in your response**\n"
        code_prompt += f"Generate the project code, documentation, and any other required text-based files, always using markers in your response to indicate beginning and ending of the file contents thusly:\n"
        code_prompt += f"For code, mark the start and end using the format <<<CODE START: filename.{extension}>>> and <<<CODE END: filename.{extension}>>>.\n"
        code_prompt += f"For documentation, use <<<DOC START: filename.md>>> and <<<DOC END: filename.md>>>`.\n"
        code_prompt += f"For other text-based files (e.g., .txt, .csv, .json, .xml, .sql, .tsv, et cetera), use <<<FILE START: filename.extension>>> and <<<FILE END: filename.extension>>>.\n"
        code_prompt += f"#########################\n\n"

        # Inform LLM to use existing code as baseline for any subsequent code changes
        code_prompt += f"**Refer to existing code as baseline for any changes**\n"
        code_prompt += f"Any changes you make must be made to the existing code files and any supporting files as the starting baseline for subsequent changes.\n"

        # Show code bundle, if it exists
        if code_bundle:
            code_prompt += f"Here is all the source code and all supporting files in the form as they currently exist prior to any subsequents changes you may make:\n"
            code_prompt += f"{code_bundle}\n"
            code_prompt += f"#########################\n"

        # Request for requirements.txt, if Python
        if (language == 'python'):
           code_prompt += f"**Installing Python libraries**\n"
           code_prompt += "If libraries are needed that are not part of the standard Python libraries, please create a requirements.txt file, using the pip command with syntax for installing the libraries.\n"
           code_prompt += f"#########################\n"

        # Task assignment in original wording
        blockquoted_prompt = add_blockquote_prefix(prompt)
        blockquoted_llm_explanation = add_blockquote_prefix(prompt)
        code_prompt += f"**Details about the specific task assignment**\n"
        code_prompt += f"Previously, in our chat, I shared the task assignment worded in my own words, and I asked you to reword it in your words, so I could ascertain if our understanding is aligned.\n"
        code_prompt += f"Thank you for confirming your understanding. It is aligned with my own understanding and expectations.\n\n"
        code_prompt += f"**My wording of the task**\n"
        code_prompt += f"Here is the specific task assignment as worded using my words:\n\n"
        code_prompt += f"{blockquoted_prompt}\n\n"

        # Task assignment wording by LLM
        code_prompt += f"**Your wording of the task**\n"
        code_prompt += f"Now, as a reminder, here (below) is how you described the current task assignment, in your own words, in our previous chat response in a conversation we are having:\n"
        code_prompt += f"{blockquoted_llm_explanation}\n"
        code_prompt += f"#########################\n"

        # Technical architecture
        code_prompt += f"**Technical architecture for the task**\n"
        code_prompt += f"To guide you in specifics of the solution, here is the detailed technical architecture for the code solution, which represents the coding plan for the task assignment:\n"
        code_prompt += f"{architecture_plan}\n"
        code_prompt += f"#########################\n\n"

        # Imports
        code_prompt += f"**Instructions for imports to functions from modules**\n"
        code_prompt += f"Always include complete and correct import statements at the beginning of each script.\n"
        code_prompt += f"When referencing functions from other modules, use fully qualified names (module_name.function_name) or ensure proper imports are in place.\n"
        code_prompt += f"#########################\n\n"

        # Get response from LLM. This response contains the code.
        response = multi_llm_request(code_prompt, logs_folder, include_markers=True)

        code_blocks, doc_blocks, file_blocks = parse_llm_response(response)

        if code_blocks:
            for filename, code in code_blocks.items():
                code_file_path = os.path.join(app_folder, filename)
                with open(code_file_path, 'w', encoding='utf-8') as file:
                    file.write(code)

        if doc_blocks:
            for filename, doc in doc_blocks.items():
                doc_file_path = os.path.join(app_folder, filename)
                with open(doc_file_path, 'w', encoding='utf-8') as file:
                    file.write(doc)

        if file_blocks:
            for filename, file_content in file_blocks.items():
                file_path = os.path.join(app_folder, filename)
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(file_content)
                print(f"Saved file to {file_path}")  # Debugging line

        break

    ###############################################################################
    # Request LLM to review code
    ###############################################################################

    # Fetch code bundle
    code_bundle = create_file_bundle(app_folder, prompt, language)

    while True:
        code_prompt = "";

        # Role prompt
        code_prompt += f"You are an expert professional computer programmer with experience in the {language} language. You follow best practices.\n"
        code_prompt += f"#########################\n"

        code_prompt += f"I need you to review some existing code.\n"
        code_prompt += f"#########################\n"
        code_prompt += f"But before you begin coding, there are some details I need to clarify.\n"
        code_prompt += f"#########################\n"
        code_prompt += f"Here are some guidelines for the program code:\n"
        code_prompt += f"Code must be in the {language} programming language.\n"
        code_prompt += f"#########################\n"


        # Prompt regarding indicators of file boundaries
        code_prompt += f"**File delimiters in your response**\n"
        code_prompt += f"When generating file output, use markers in your response to indicate beginning and ending of the file contents thusly:\n"
        code_prompt += f"For code, mark the start and end using the format <<<CODE START: filename.{extension}>>> and <<<CODE END: filename.{extension}>>>.\n"
        code_prompt += f"For documentation, use <<<DOC START: filename.md>>> and <<<DOC END: filename.md>>>`.\n"
        code_prompt += f"For other text-based files (e.g., .txt, .csv, .json, .xml, .sql, .tsv, et cetera), use <<<FILE START: filename.extension>>> and <<<FILE END: filename.extension>>>.\n"
        code_prompt += f"#########################\n\n"

        # Inform LLM to use existing code as baseline for any subsequent code changes
        code_prompt += f"**Refer to existing code as baseline for any changes**\n"
        code_prompt += f"Any changes you make must be made to the existing code files and any supporting files as the starting baseline for subsequent changes.\n"

        # Show code bundle
        if code_bundle:
            code_prompt += f"Here is all the source code and all supporting files in the form as they currently exist prior to any subsequents changes you may make:\n"
            code_prompt += f"{code_bundle}\n"
            code_prompt += f"#########################\n"

        # Request for requirements.txt, if Python
        if (language == 'python'):
           code_prompt += f"**Installing Python libraries**\n"
           code_prompt += "If libraries are needed that are not part of the standard Python libraries, please create a requirements.txt file, using the pip command with syntax for installing the libraries.\n"
           code_prompt += f"#########################\n"

        # Task assignment in original wording
        blockquoted_prompt = add_blockquote_prefix(prompt)
        blockquoted_llm_explanation = add_blockquote_prefix(prompt)
        code_prompt += f"**Details about the specific task assignment**\n"
        code_prompt += f"Previously, in our chat, I shared the task assignment worded in my own words, and I asked you to reword it in your words, so I could ascertain if our understanding is aligned.\n"
        code_prompt += f"Thank you for confirming your understanding. It is aligned with my own understanding and expectations.\n\n"
        code_prompt += f"**My wording of the task**\n"
        code_prompt += f"Here is the specific task assignment as worded using my words:\n\n"
        code_prompt += f"{blockquoted_prompt}\n\n"

#        # Task assignment wording by LLM
#        code_prompt += f"**Your wording of the task**\n"
#        code_prompt += f"Now, as a reminder, here (below) is how you described the current task assignment, in your own words, in our previous chat response in a conversation we are having:\n"
#        code_prompt += f"{blockquoted_llm_explanation}\n"
#        code_prompt += f"#########################\n"

        # Technical architecture
        code_prompt += f"**Technical architecture for the task**\n"
        code_prompt += f"To guide you in specifics of the solution, here is the detailed technical architecture for the code solution, which represents the coding plan for the task assignment:\n"
        code_prompt += f"{architecture_plan}\n"
        code_prompt += f"#########################\n\n"

        # Instructions
        code_prompt += f"**Instructions for code review**\n"
        code_prompt += f"Check the code for bugs. Often, it's simple things that cause problems. So, check all the obvious things, such as:\n"
        code_prompt += f"When referencing functions from other modules, use fully qualified names (module_name.function_name) or ensure proper imports are in place.\n"
        code_prompt += f"Always include complete and correct import statements at the beginning of each script.\n"
        code_prompt += f"Verify the correct usage of data structures and their methods.\n"
        code_prompt += f"Double-check all loop conditions and array indexing.\n"

        code_prompt += f"#########################\n\n"


        code_prompt += f"**Task clarification**\n"
        code_prompt += f"So, just to clarify what I need you to do: I suspect there are one or more bugs in the code. The code is very close to being correct, but I am worried there may be some minor errors. Please ruminate on the code, and consider every possible bug, and fix them.\n"
        code_prompt += f"#########################\n\n"

        print("Performing code review")

        # Get response from LLM. This response contains the code.
        response = multi_llm_request(code_prompt, logs_folder, include_markers=True)

        code_blocks, doc_blocks, file_blocks = parse_llm_response(response)

        if code_blocks:
            for filename, code in code_blocks.items():
                code_file_path = os.path.join(app_folder, filename)
                with open(code_file_path, 'w', encoding='utf-8') as file:
                    file.write(code)

        if doc_blocks:
            for filename, doc in doc_blocks.items():
                doc_file_path = os.path.join(app_folder, filename)
                with open(doc_file_path, 'w', encoding='utf-8') as file:
                    file.write(doc)

        if file_blocks:
            for filename, file_content in file_blocks.items():
                file_path = os.path.join(app_folder, filename)
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(file_content)
                print(f"Saved file to {file_path}")  # Debugging line

        break


    ###############################################################################
    # Create documentation
    ###############################################################################

    create_documentation = 0

    if (create_documentation == 1):

        # Request comprehensive project documentation
        full_context_prompt = create_file_bundle(app_folder, "Comprehensive project documentation request", language)

        while True:
            doc_prompt = (
                f"Please generate comprehensive documentation based on the provided context. Use markdown format. Name the file 'documentation.md'.\n\n"
                f"Context:\n{full_context_prompt}\n\n"
            )
    
            response = multi_llm_request(doc_prompt, logs_folder, include_markers=False)
    
            documentation = response.strip()
    
            if documentation:
                doc_file_path = os.path.join(app_folder, 'documentation.md')
                with open(doc_file_path, 'w', encoding='utf-8') as file:
                    file.write(documentation)
                break
            else:
                print("No documentation was generated.")

###############################################################################
# This handles the compile to an EXE file
###############################################################################
def compile_to_exe(app_folder, main_file):

    try:
        # Run PyInstaller
        subprocess.run(['pyinstaller', '--onefile', '--console', main_file], cwd=app_folder, check=True)
        print(f"Successfully compiled {main_file} to executable.")

        # Move the executable from the 'dist' folder to the project folder
        exe_name = os.path.splitext(main_file)[0] + '.exe'
        dist_path = os.path.join(app_folder, 'dist', exe_name)
        project_path = os.path.join(app_folder, exe_name)
        
        shutil.move(dist_path, project_path)
        print(f"Moved executable to {project_path}")

        # Remove the 'dist' and 'build' folders
        shutil.rmtree(os.path.join(app_folder, 'dist'))
        shutil.rmtree(os.path.join(app_folder, 'build'))
        os.remove(os.path.join(app_folder, f"{os.path.splitext(main_file)[0]}.spec"))
        print("Cleaned up PyInstaller artifacts.")

    except subprocess.CalledProcessError as e:
        print(f"Error compiling to executable: {e}")
    except FileNotFoundError:
        print("PyInstaller not found. Please install it using 'pip install pyinstaller'.")
    except Exception as e:
        print(f"An error occurred during compilation or file moving: {e}")

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

# Get project name from command line param. If no param, app exits.
def get_project_name():

    global project_name
    if len(sys.argv) < 2:
        print("Error: Please provide a project name as a command line argument.")
        sys.exit(1)

    project_name = sys.argv[1]

    project_name = project_name.lower().replace(" ", "") # Remove spaces. Convert to lower case.

    print(f"Project: {project_name}")

def main():

    # What LLM do we normally prefer to use
    get_preferred_llm()

    # Determine project name
    get_project_name()

    # Define folder paths
    global app_folder, config_folder, logs_folder
    app_folder    = os.path.join(os.getcwd(), 'projects', project_name, 'files')
    config_folder = os.path.join(os.getcwd(), 'projects', project_name, 'config')
    logs_folder   = os.path.join(os.getcwd(), 'projects', project_name, 'llm_logs')

    # Create subfolders if they do not exist
    create_subfolder(app_folder)
    create_subfolder(config_folder)
    create_subfolder(logs_folder)

    # Create project parameter file if it does not exit
    parameters_file = os.path.join(config_folder, 'project_params.txt')
    if not os.path.exists(parameters_file):
        file_content = f"project_name:{project_name}\nlanguage:python\nmain_file=main.py\ncompile:no\n"
        with open(parameters_file, "w") as file: file.write(file_content)

    # Read parameters from project parameters file
    params          = read_params_file(parameters_file)
    language        = params.get('language', 'python').lower()
    main_file       = params.get('main_file', 'main.py')
    compile_option  = params.get('compile', 'no').lower()

    # Read task file
    task_file = os.path.join(config_folder, 'tasks.txt')
    task = read_tasks_file(task_file)

    print(f"Task file: {task_file}")
    print(f"Parameters file: {parameters_file}")
    print(f"Language: {language}")
    print(f"Compile: {compile_option}")
    print(f"Main file: {main_file}")

    # If no tasks, then exit
    if not task:
        print("No new tasks found or all tasks are already processed in tasks.txt.")
        exit(0)

    main_file_path = os.path.join(app_folder, main_file)

    # Generate code
    generate_code_for_project(app_folder, task, language, main_file_path)

    # Compile code (if indicated in project parameter file)
    if compile_option in ['yes', '1']:

        if os.path.exists(main_file_path):
            compile_to_exe(app_folder, main_file)
        else:
            print(f"Main file {main_file_path} not found. Skipping compilation.")



if __name__ == "__main__":

    setup_logging()

    main()






