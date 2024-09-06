
# Project Documentation

## Overview
This project automates the creation of other apps using a Language Learning Model (LLM). It follows a structured process to take user-defined tasks and project parameters, interact with an LLM to generate code and supporting files, and then save these files into a designated project subfolder. The app also generates documentation for the created app and supports iterative updates based on user feedback.

## Project Name
The project is named **Firebird** after the famous ballet by Igor Stravinsky. The ballet features some of the greatest music ever written, especially the finale, which is both powerful and uplifting. The story of the Firebird is a mythical tale set in an enchanted castle, where a powerful spell holds the inhabitants captive. Through the courage and perseverance of the hero, the spell is eventually broken, bringing freedom and renewal.

Just as the Firebird brings new life through its magical power, this project aims to empower developers to create innovative applications effortlessly, breaking barriers and opening new possibilities.

## Licensing
This project is open-source, allowing others to modify and distribute the software under the terms of the Apache License Version 2.0. As per the license terms, retain the original author's name in any distributions or derivatives.

## Installation and Setup
1. Ensure Python is installed on your machine.
2. Install any required dependencies using `pip install -r requirements.txt` if a `requirements.txt` file is provided.
3. Configure the `config.txt` file:
   - Set your LLM preferences such as model type, temperature, and other relevant parameters.
   - Set logging preferences, including whether to log LLM responses and the location of log files.
4. Set your LLM API keys in the environment variables. Setting API keys in environment variables is recommended for security reasons, as it helps to keep sensitive information out of the source code. Only set the keys for the LLMs you intend to use. For example:
    ```
    set OPENAI_API_KEY=your-gemini-api-key
    set GEMINI_API_KEY=your-gemini-api-key
    set ANTHROPIC_API_KEY=your-anthropic-api-key
    set GROQ_API_KEY=your-groq-api-key
    set PERPLEXITY_API_KEY=your-perplexity-api-key
    ```

## Usage

### Initial Setup
1. Write a description of the desired app in the `tasks.txt` file.
2. Set the project subfolder name and programming language in `project_params.txt`.
3. Run the `main.py` script to initiate the app creation process.

### Example:
- `tasks.txt`: "Create a word guessing game."
- `project_params.txt`: 
    ```
    project_name:word_game
    language:python
    ```

### Iterative Updates
1. After generating the initial code, the user can make changes or add new requirements by updating `tasks.txt`.
2. Run `main.py` again to send the updated request to the LLM. The LLM will incorporate the new instructions and modify the existing code as needed.
3. LLM responses and updates are logged in the `llm_logs` subfolder, allowing users to review the interactions.

## Modules and Functions

### `main.py`
- **Description**: The primary script to run the application.
- **Key Functions**:
  - `main()`: Initiates the process by reading `tasks.txt`, sending requests to the LLM, and coordinating the overall flow. It handles both initial code generation and iterative updates.

### `api_caller.py`
- **Description**: Manages API calls to the LLM.
- **Key Functions**:
  - `call_llm(prompt)`: Sends a request to the LLM and returns the response. It also handles retries and error management based on the preferences set in `config.txt`.

### Configuration Files
- `project_params.txt`: Contains the project subfolder name and programming language.
- `tasks.txt`: Contains the description of the app to be created. It can be updated for iterative requests.
- `config.txt`: Stores configuration details, including:
   - LLM preferences (model, temperature, etc.)
   - Logging preferences (whether to log responses, log file locations, etc.)

### Logging
- **LLM Responses**: All LLM interactions are logged in the `llm_logs` subfolder, providing a trace of the responses and the evolution of the generated code.

## Multi-Language Support
The project can generate code in multiple programming languages, including Python and Java. Most testing so far has been conducted with Python. The project also supports additional languages based on user specifications.

## EXE Compilation
For Python projects, the app can compile the generated code into an executable (EXE) file. This allows the user to distribute the software without requiring Python to be installed on the target machine.

## GUI Creation
If the user specifies that the generated app should include a Graphical User Interface (GUI), the LLM will create the necessary code to build a GUI, tailored to the project's requirements.

## Process Flow
1. **Input Tasks**: The user provides a description of the desired app in `tasks.txt`.
2. **Set Parameters**: The user sets the project name and programming language in `project_params.txt`.
3. **Run Main Script**: The user runs `main.py`, which reads the inputs, interacts with the LLM, and manages the flow of the process.
4. **LLM Interaction**:
    - The LLM first confirms its understanding of the request.
    - After confirmation, the LLM generates the necessary code and supporting files.
    - The user can make iterative updates by modifying `tasks.txt` and rerunning the script.
5. **File Management**: The generated files are saved in the designated subfolder.
6. **Documentation**: The app requests the LLM to generate documentation, which is saved as `documentation.md` in the project subfolder.
7. **Logging**: All interactions with the LLM are logged for review and traceability.

## Example Use Case
### Word Guessing Game
- **Task**: Create a simple word guessing game.
- **Project Parameters**: 
    ```
    project_name:word_game
    language:python
    ```
- **Outcome**: The generated code, supporting files, and documentation are saved in the `word_game` subfolder, with all LLM interactions logged in `llm_logs`.

## Contributing Guidelines
Contributions to this project are welcome. To contribute, please follow these guidelines:

### Coding Standards
- Follow PEP 8 for Python code.
- Ensure code is well-commented and easy to understand.
- Write meaningful commit messages and document changes in the changelog.

### Contribution Expectations
- **Alignment with Project Vision**: Contributions should align with the overall direction and goals of the project. If you're considering a significant change or new feature, please open an issue first to discuss it with the project maintainer (James Lee Stakelum) before starting work on it.
- **Approval Process**: All pull requests will be reviewed by the project maintainer. Contributions that deviate from the project's vision or introduce breaking changes may be rejected or require revisions.
- **Roadmap Consideration**: Please review the project roadmap before suggesting major changes. If your contribution is in line with upcoming planned features, it is more likely to be accepted.

### Submitting a Pull Request
1. Fork the repository.
2. Create a new branch with a descriptive name (e.g., `feature/add-gui-support`).
3. Make your changes in the new branch.
4. Ensure that your changes do not break existing functionality by running tests.
5. Submit a pull request to the main repository, describing the changes you made and why they are necessary.

## About the Author
**James Lee Stakelum**  
James is an AI developer with a passion for technology, chess, and classical music. He has developed this project to help streamline the process of creating applications using AI-driven tools.

- **Contact Information:** JamesLeeStakelum@proton.me
- **LinkedIn:** [James Lee Stakelum](https://www.linkedin.com/in/james-lee-stakelum-38440122/)
