# Newsfeed-system <!-- omit from toc -->
*A real-time newsfeed system that aggregates IT-related news from selected public sourcers, filters them for relevance, and provides a simple web dashboard to display the latest updates. Dashboard available [here](https://newsfeed-static-web-interface.s3.eu-north-1.amazonaws.com/dashboard.html).*

## Table of contents <!-- omit from toc -->
- [Architecture](#architecture)
  - [Overview](#overview)
  - [Ingestion](#ingestion)
  - [Filtering](#filtering)
  - [Storage](#storage)
  - [Mock NewsFeed API](#mock-newsfeed-api)
  - [Bonus question](#bonus-question)
  - [Ideas for future development](#ideas-for-future-development)
- [Installation](#installation)
  - [Install Poetry](#install-poetry)
  - [Create virtual environment](#create-virtual-environment)
  - [Configuring environment variables](#configuring-environment-variables)
  - [Running Scripts](#running-scripts)
  - [Install pre-commit hooks](#install-pre-commit-hooks)
  - [Setup on EC2 instance](#setup-on-ec2-instance)


## Architecture

### Overview
### Ingestion
### Filtering
### Storage
### Mock NewsFeed API
### Bonus question


### Ideas for future development
- Leverage the ```lastBuildDate``` field in RSS feed to avoid processing the feed if it hasn't changed since the last fetch
- Use ```is_synthetic``` as a partition key, or just have different table for synthetic items.

## Installation

This project uses **Poetry** for dependency management and environment setup.
Follow the instructions below to set up the environment and run the project.

### Install Poetry

If you don't have **Poetry** installed, a nice way to do so is using [pipx](https://github.com/pypa/pipx).

```
pipx install poetry
```


### Create virtual environment

Once you've cloned the repo, from the project's root directory, install dependencies using Poetry:
```bash
poetry install
```
This will create a virtual environment and install all dependencies listed in the `poetry.lock` file.

### Configuring environment variables

To use the LLM filter, a valid OpenAI API key is need. Furthermore, a valid Reddit app id and secret are required to make API calls to Reddit (and ingest data from subreddits)

1. Create a `.env` file in the root directory of the project:
```bash
touch .env
```

1. Add your OpenAI API key and Reddit app id & secret to the `.env` file:
```
OPENAI_API_KEY=your_api_key_here
REDDIT_APP_ID=
REDDIT_APP_SECRET=
```

**Note**: Make sure to keep your `.env` file private and not to commit it to version control.
It's included in `.gitignore` to prevent accidental commits.

### Running Scripts

To run scripts using Poetry:

```bash
poetry run python -m scripts.main --src tomshardware --store --filter --generate-json --upload-s3
```


### Install pre-commit hooks
I use `ruff` for formatting, import sorting, and linting. These
are run automatically at every commit through the installation of pre-commit hooks.
You can install `ruff` and `pre-commit` with pipx.
```bash
pipx install ruff pre-commit
```
And then, from the project directory:
```bash
poetry run pre-commit install
```

### Setup on EC2 instance
To run the application on a new EC2 instance with Amazon Linux, the following set up is required:

```bash
sudo yum update -y

# install pip
sudo yum install -y python3-pip

# install pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# install poetry
pipx install poetry

# install and set up git
sudo dnf install -y git
git --version
git config --global user.name "YOUR_NAME"
git config --global user.email "YOUR_EMAIL"

# generate ssh key pair
ssh-keygen -t ed25519 -C "YOUR_EMAIL"
cat ~/.ssh/id_ed25519.pub
# Then add the public key to github account

git clone git@github.com:leonardpasi/newsfeed-system.git

# --- Install python3.12 with pyenv -----
# Install dependencies
sudo yum groupinstall -y "Development Tools"
sudo yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel

# Install pyenv
curl https://pyenv.run | bash

# Add to PATH
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Install Python 3.12
pyenv install 3.12.7
pyenv global 3.12.7

# Verify
python --version
# ---------------------------------------


cd newsfeed-system
poetry install
```

To run the application on the EC2, it needs to have proper permissions to the DynamoDB table and the S3 bucket. These are granted by creating a policy, creating a IAM role with the policy, and then attributing the role to the EC2 instance.

Additionally, the firewall needs to be configured to allow inbound http traffic on port 5000 (for the Mock NewsFeed API).
