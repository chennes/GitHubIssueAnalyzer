# GitHub Issue Analyzer
Use the GraphQL API to download a GitHub Issue list with creation and closure date information

## Use

Set an environment variable called `GITHUB_ACCESS_TOKEN` with a GitHub API key: no extra permissions are required for that key, the script
uses only public information.

Edit the configuration variables at the top of `main.py` to set which repo you intend to analyze,
then run the script using your local python interpreter.

The result is Excel-style CSV data in a file you specify in the configuration variables.
