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
import configparser

# Logging handler
import logging
logger = logging.getLogger(__name__)

# Function to read config
def get_preferred_llm():
    config = configparser.ConfigParser()
    config.read('config.txt')
    return config['Preferences']['preferred_llm']

def ensure_logs_subfolder_exists():
    logs_folder = os.path.join(os.getcwd(), 'llm_logs')
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
    return logs_folder

def log_request(logs_folder, request_text):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')[:-3]  # Include milliseconds
    preferred_llm = get_preferred_llm()
    request_file_path = os.path.join(logs_folder, f'{timestamp}_request_{preferred_llm}.txt')
    
    with open(request_file_path, 'w', encoding='utf-8') as file:
        file.write(request_text)
    
    return request_file_path

def log_response(logs_folder, response_text):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')[:-3]  # Include milliseconds
    preferred_llm = get_preferred_llm()
    log_file_path = os.path.join(logs_folder, f'{timestamp}_response_{preferred_llm}.txt')
    
    with open(log_file_path, 'w', encoding='utf-8') as file:
        file.write(response_text)
    
    return log_file_path

def upload_project_code_and_docs(project_folder, prompt, language):
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
