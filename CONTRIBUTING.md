# How to contribute to ChatGPT CLI

External contributes to this project are welcome! :heart: :heart:

## Philosophy

The philosophy behind this tool is to maintain simplicity while providing essential features for users who need to interact with ChatGPT models from the command line efficiently. As explained in the README.md, we have undergone a significant refactor to improve modularity and maintainability.

Our current approach emphasizes organizing code into logical directories, with each script ideally not exceeding 200-300 lines. This structure allows for better code organization, easier maintenance, and improved readability. Contributors are encouraged to follow this modular approach when adding new features or making improvements.

We wanna to balance simplicity with functionality, ensuring that the tool remains user-friendly while accommodating the growing feature set. When contributing, please consider how your changes fit into this modular structure and maintain the tool's core philosophy of simplicity and efficiency.

## Development

Check out the repository:

`git clone https://github.com/marcolardera/chatgpt-cli.git`

Create and activate a Virtual Environment:

`python3 -m venv venv` or `python -m venv venv`

`source venv/bin/activate` (Linux/MacOS) or `.\venv\Scripts\activate` (Windows)

Install the requirements:

`pip install -r requirements.txt`

Run the code during development:

`python src/chatgpt_cli.py`

After the changes are done don't forget to:

- update `requirements.txt` and `setup.cfg` if necessary
- update `README.md` if necessary
- update `pyproject.toml` with a new version number
- test if the installation as a package still works as expected using `pip install .` and running `chatgpt-cli`

### Formatting

This project uses [Ruff](https://github.com/astral-sh/ruff) as a code formatter (Most IDE have an extension that makes straightforward to use it). Please format the code using this tool before submitting a PR.
