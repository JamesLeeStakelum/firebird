# -----------------------------------------------------------------------------
# Firebird Code Generator
# Copyright (c) 2024 James Stakelum
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
# -----------------------------------------------------------------------------

from datetime import datetime
import os
import sys
import subprocess
import shutil
from project_manager import ensure_logs_subfolder_exists, log_request, log_response, upload_project_code_and_docs, create_code_history_backup
from llm_interaction import get_llm_response
import configparser
import re

# Logging handler
import logging
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

def create_app_subfolder(folder_name):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Created subfolder: {folder_name}")
    return folder_name

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

def parse_llm_response(response, language):
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


def generate_code_for_project(app_folder, prompt, language, main_file):

    # Bundles all existing project code into a string for placement in LLM context
    create_code_history_backup(app_folder)
    code_bundle = upload_project_code_and_docs(app_folder, prompt, language)

    # Get LLM's understanding of the task
    llm_explanation = ""
    while True:
        understanding_prompt = (
            f"Please summarize your understanding of the task described below.\n\n"
            f"Task:\n{prompt}\n\n"
            f"#########################\n\n"
        )

        # Add code bundle for context if it exists
        if code_bundle:
            understanding_prompt += (
                f'Any changes you make must be made to the existing code files and any supporting files as the starting baseline for subsequent changes. '
                f"For context, here is a bundle of all the source code and all supporting files as they currently exist:\n"
                f"{code_bundle}\n"
            )    

        logs_folder = ensure_logs_subfolder_exists()
        log_request(logs_folder, understanding_prompt)

        response = get_llm_response(understanding_prompt, language, include_markers=False)

        log_response(logs_folder, response)

        llm_explanation = response.strip()

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

    extension = {
        'python': 'py',
        'java': 'java',
        'perl': 'pl'
    }.get(language, 'txt')

    # Request LLM to create a detailed architecture document
    architecture_prompt = ""
    architecture_prompt += f"#########################\n"
    architecture_prompt += f"We are not yet ready to perform the coding task. But, for your awareness, here is the task that was requested:\n"
    architecture_prompt += f"{prompt}\n"
    architecture_prompt += f"#########################\n\n"
    architecture_prompt += f"As a reminder, here is how you described the current task assignment, in your own words, in our previous chat response in a conversation we are having:\n"
    architecture_prompt += f"{llm_explanation}\n"
    architecture_prompt += f"#########################\n\n"
    architecture_prompt += f"Before any actual coding is performed, first, it is necessary to create a highly detailed techical architecture document that describes a technical solution for accomplishing the task.\n"
    architecture_prompt += f"So, based on the requested task, please generate a highly detailed technical architecture document.\n"
    architecture_prompt += f"The document will contain the following:\n"
    architecture_prompt += f"For all code modules, the name of the module, the purpose of the module, and list of all functions inside the module.\n"
    architecture_prompt += f"For all functions, the name of the function, the purpose of the function, and the parameters for the function, what the function returns, and a step-by-step description of what the function does.\n"
    architecture_prompt += f"List all function-to-function relationships that show which functions call what.\n"
    architecture_prompt += f"List any supporting files.\n"
    architecture_prompt += f"Save the technical archicture document in a file named technical_architecture.txt\n"
    architecture_prompt += f""#########################\n"

    # Prompt regarding indicators of file boundaries
    architecture_prompt += f"When generating the technical architecture file, use these markers in your response to indicate beginning and end of the file contents:\n"
    architecture_prompt += f"<<<FILE START: technical_architecture.txt>>> and <<<FILE END: technical_architecture.txt>>>."
    architecture_prompt += f"#########################\n\n"

    # Call LLM and request architecture document
    log_request(logs_folder, architecture_prompt)
    response = get_llm_response(architecture_prompt, language, include_markers=False)
    log_response(logs_folder, response)
    architecture_text = response.strip()

    # Extract architecture document from the LLM response, and write to file
    code_blocks, doc_blocks, file_blocks = parse_llm_response(architecture_text, language)
    if file_blocks:
        for filename, file_content in file_blocks.items():
            file_path = os.path.join(app_folder, filename)
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(file_content)
            print(f"Saved file to {file_path}")  # Debugging line

            architecture_plan = ''
            if (filename == 'technical_architecture.txt'): architecture_plan = file_content


    # Request LLM to generate the code
    while True:
        code_prompt = "";

        # Role prompt
        code_prompt += f"You are an expert professional computer programmer with experience in the {language} language. You follow best practices.\n"

        code_prompt += f"Thank you for confirming your understanding.\n"
        code_prompt += f"Now, please generate the code.\n"
        code_prompt += f"Here are some guidelines for the program code:\n"
        code_prompt += f"Code must be in the {language} programming language.\n"
        code_prompt += f"The main script must be named '{main_file}'. \n"
        code_prompt += f"When making changes to existing code, always show the complete code; never stub out sections.\n"
        code_prompt += f"Regarding file encodings, I prefer ASCII, although UTF8 is okay if necessary to have some special characters. But always avoid Unicode.\n"

        # Request for comments in code
        code_prompt += f"Include comments in the code. Use the # symbol to preceed single-line comments. Use docstrings for multi-line comments\n"
        code_prompt += f"Comments are extremely helpful. The assist the LLM to understand the purpose of the code when I ask the LLM to review the code to either make improvements or fix problems. I like having comments on three levels: 1. for each module, describing the purpose of the module; 2. for each function, describing the purpose of the function; 3. for each operation inside a function, which is normally ever few lines of code, describing the operation.\n\n"

        code_prompt += f"Don't include backticks in code or other files. Backticks cause serious problems.\n"
        code_prompt += f"When making changes to existing code, always reflect on all aspects of the code. Consider relationships between functions, and parameters, and external files.\n"
        code_prompt += f"#########################\n"

        # Prompt regarding indicators of file boundaries
        code_prompt += f"\n\nPlease generate the project code, documentation, and any other required text-based files, use markers in your response.\n"
        code_prompt += f"For code, mark the start and end using the format <<<CODE START: filename.{extension}>>> and <<<CODE END: filename.{extension}>>>. "
        code_prompt += f"For documentation, use <<<DOC START: filename.md>>> and <<<DOC END: filename.md>>>`. "
        code_prompt += f"For other text-based files (e.g., .txt, .csv, .json, .xml, .sql, .tsv, et cetera), use <<<FILE START: filename.extension>>> and <<<FILE END: filename.extension>>>."
        code_prompt += f"#########################\n\n"

        # Inform LLM to use existing code as baseline for any subsequent code changes
        code_prompt += f"Any changes you make must be made to the existing code files and any supporting files as the starting baseline for subsequent changes. "
        code_prompt += f"Here is all the source code and all supporting files as they currently exists:\n"
        code_prompt += f"{code_bundle}\n"
        code_prompt += f"#########################\n"

        # Request for requirements.txt, if Python
        if (language == 'python'):
           code_prompt += "If libraries are needed that are not part of the standard Python libraries, please create a requirements.txt file, using the pip command with syntax for installing the libraries.\n"

        # Task assignment
        code_prompt += f"#########################\n"
        code_prompt += f"Here is the specific task assignment:\n"
        code_prompt += f"{prompt}\n"
        code_prompt += f"#########################\n\n"
        code_prompt += f"As a reminder, here is how you described the current task assignment, in your own words, in our previous chat response in a conversation we are having:\n"
        code_prompt += f"{llm_explanation}\n"

        # Technical architecutre
        code_prompt += f"Here is the detailed technical architecture for this task:\n"
        code_prompt += f"architecture_plan\n"
        code_prompt += f"#########################\n\n"

        log_request(logs_folder, code_prompt)

        # Get response from LLM. This response contains the code.
        response = get_llm_response(code_prompt, language, include_markers=True)
        log_response(logs_folder, response)

        code_blocks, doc_blocks, file_blocks = parse_llm_response(response, language)

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

    # Request comprehensive project documentation
    full_context_prompt = upload_project_code_and_docs(app_folder, "Comprehensive project documentation request", language)
    while True:
        doc_prompt = (
            f"Please generate comprehensive documentation based on the provided context. Use markdown format. Name the file 'documentation.md'.\n\n"
            f"Context:\n{full_context_prompt}\n\n"
        )

        log_request(logs_folder, doc_prompt)

        response = get_llm_response(doc_prompt, language, include_markers=False)
        log_response(logs_folder, response)

        documentation = response.strip()

        if documentation:
            doc_file_path = os.path.join(app_folder, 'documentation.md')
            with open(doc_file_path, 'w', encoding='utf-8') as file:
                file.write(documentation)
            break
        else:
            print("No documentation was generated.")

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

def main():
    params = read_params_file('project_params.txt')
    project_name = params.get('project_name')
    language = params.get('language', 'python').lower()
    main_file = params.get('main_file', 'main.py')
    compile_option = params.get('compile', 'no').lower()

    if not project_name:
        raise ValueError("Project name not found in project_params.txt.")

    task = read_tasks_file('tasks.txt')
    if not task:
        print("No new tasks found or all tasks are already processed in tasks.txt.")
        return

    app_folder = create_app_subfolder(project_name)
    generate_code_for_project(app_folder, task, language, main_file)

    if compile_option in ['yes', '1']:
        main_file_path = os.path.join(app_folder, main_file)
        if os.path.exists(main_file_path):
            compile_to_exe(app_folder, main_file)
        else:
            print(f"Main file {main_file_path} not found. Skipping compilation.")



if __name__ == "__main__":

    setup_logging()

    main()
