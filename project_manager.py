# -----------------------------------------------------------------------------
# Firebird Code Generator
# Copyright (c) 2024 James Stakelum
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
# -----------------------------------------------------------------------------

from llm_interaction import get_llm_response
import shutil
import os
from datetime import datetime

# Logging handler
import logging
logger = logging.getLogger(__name__)

def ensure_logs_subfolder_exists():
    logs_folder = os.path.join(os.getcwd(), 'llm_logs')
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
    return logs_folder

def log_request(logs_folder, request_text):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    request_file_path = os.path.join(logs_folder, f'{timestamp}_request.txt')
    
    with open(request_file_path, 'w', encoding='utf-8') as file:  # Specify utf-8 encoding
        file.write(request_text)
    
    return request_file_path

def log_response(logs_folder, response_text):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(logs_folder, f"{timestamp}_response.txt")

    with open(log_file_path, 'w', encoding='utf-8') as file:  # Specify utf-8 encoding
        file.write(response_text)

def upload_project_code_and_docs(project_folder, prompt, language):
    code_bundle = ''

    for file in os.listdir(project_folder):
        if file.endswith(('.py', '.java', '.pl', '.txt')):  # Include relevant file extensions
            file_path = os.path.join(project_folder, file)
            if os.path.isfile(file_path):  # Ensure it's a file, not a directory
                with open(file_path, 'r') as f:
                    content = f.read()
                    code_bundle += f"\n\n---\n\nFile: {file}\n\n{content}\n\n"

    return code_bundle  # Return the code bundle without sending it to LLM yet

#def save_code_and_specs(project_folder, llm_response, prompt):
#    retries = 0
#    max_retries = 3
#    requirements_found = False
#    
#    while retries < max_retries and not requirements_found:
#        if isinstance(llm_response, str):
#            # Handle multiple code blocks
#            code_blocks, doc_blocks = parse_llm_response(llm_response)
#
#            for filename, code in code_blocks.items():
#                code_file_path = os.path.join(project_folder, filename)
#                with open(code_file_path, 'w') as file:
#                    file.write(code)
#                print(f"Saved code to {code_file_path}")
#
#            for filename, documentation in doc_blocks.items():
#                doc_file_path = os.path.join(project_folder, filename)
#                with open(doc_file_path, 'w') as file:
#                    file.write(documentation)
#                print(f"Saved documentation to {doc_file_path}")
#
#            if '<<<REQ START>>>' in llm_response and '<<<REQ END>>>' in llm_response:
#                requirements = llm_response.split('<<<REQ START>>>')[1].split('<<<REQ END>>>')[0].strip()
#                requirements_file_path = os.path.join(project_folder, 'requirements.txt')
#                with open(requirements_file_path, 'w') as file:
#                    file.write(requirements)
#                requirements_found = True
#                print(f"Saved requirements to {requirements_file_path}")
#
#        retries += 1
#        if not requirements_found and retries < max_retries:
#            print("Requirements not found, retrying...")
#            llm_response = upload_project_code_and_docs(project_folder, prompt)
#    
#    if not requirements_found:
#        raise ValueError("Failed to save requirements after multiple retries.")

#def read_files_from_subfolder(subfolder_name):
#    """Reads all files in the subfolder into memory as strings."""
#    file_contents = {}
#    for root, dirs, files in os.walk(subfolder_name):
#        for file in files:
#            file_path = os.path.join(root, file)
#            with open(file_path, 'r') as f:
#                file_contents[file] = f.read()
#    return file_contents

def create_code_history_backup(project_folder):
    """Create a backup of all files in the project folder before making any changes."""
    
    # Check if there are any code files in the project folder
    code_files_exist = False
    for root, dirs, files in os.walk(project_folder):
        for file in files:
            if file.endswith(('.py', '.java', '.pl')):  # Add other extensions as needed
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
