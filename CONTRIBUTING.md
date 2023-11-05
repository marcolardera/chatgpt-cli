## How to contribute to ChatGPT CLI

External contributes to this project are welcome! :heart: :heart:

### Philosophy

The philosophy behind this tool is to keep things simple, while at the same time to provide all the features that really matters for users who need to interact with ChatGPT models from the command line in a quick and efficient way.
Regarding the code, the original idea was to have a single, well structured, Python script. Since then, many new features and improvements had been added and it may be necessary at some point to refactor it in a mode modular way...

### Development

Check out the repository:

`git clone https://github.com/marcolardera/chatgpt-cli.git`

Create and activate a Virtual Environment:

`python3 -m venv venv` or `python -m venv venv`

`source venv/bin/activate` (Linux/MacOS) or `.\venv\Scripts\activate` (Windows)

Install the requirements:

`pip install -r requirements.txt`

Run the code during development:

`python src/chatgpt.py`

After the changes are done don't forget to:

- update `requirements.txt` and `setup.cfg` if necessary
- update `README.md` if necessary
- update `pyproject.toml` with a new version number
- test if the installation as a package still works as expected using `pip install .` and running `chatgpt-cli`

### Formatting

This project uses Black (https://github.com/psf/black) as a code formatter (Most IDE have an extension that makes straightforward to use it). Please format the code using this tool before submitting a PR.