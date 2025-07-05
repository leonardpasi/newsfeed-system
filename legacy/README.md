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
  - [EC2 instance setup](#ec2-instance-setup)
  - [Cron Job Setup](#cron-job-setup)
  - [Flask Server setup](#flask-server-setup)
  - [Tests](#tests)


## Architecture

### Overview
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ RSS Feeds   │───▶│  Ingestion   │───▶│ LLM Filter  │───▶│ DynamoDB    │
│ Reddit API  │    │  (Python)    │    │ (OpenAI)    │    │ Storage     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
                                                                    │
┌─────────────┐    ┌──────────────┐    ┌─────────────┐              │
│ Static Web  │◀───│ S3 Bucket    │◀───│ JSON Export │◀─────────────┘
│ Dashboard   │    │ (hosting)    │    │ Generator   │
└─────────────┘    └──────────────┘    └─────────────┘

┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ Test        │───▶│ Mock API     │───▶│ LLM Filter  │───▶│ In-Memory   │
│ Harness     │    │ (Flask)      │    │ (OpenAI)    │    │ Storage     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
```
- **Core Technologies**: Python, Amazon EC2, DynamoDB, S3, OpenAI API, Flask  
- **Key Principles**: Modular design, automated operations, monitoring
- **Web Dashboard**: available **[here](https://newsfeed-static-web-interface.s3.eu-north-1.amazonaws.com/dashboard.html)**

### Ingestion

- **RSS Sources**: Tom's Hardware, Ars Technica using `feedparser` with retry logic
- **Reddit Source**: r/InfoSecNews via PRAW API with rate limiting
- **Modular Design**: New sources added via `configs/sources_urls.yaml`
- **Efficiency**: Filters out existing articles before processing
- **Automation**: Cron jobs for continuous ingestion every x minutes

### Filtering

- **LLM Scoring**: OpenAI GPT-4.1-nano rates relevance on 1-5 scale for IT managers
  - **1**: Consumer tech, general business
  - **3**: Software releases, industry trends  
  - **5**: Security breaches, critical outages
- **Threshold**: Default minimum score of 3.0 (moderately relevant)
- **Cost Optimization**: Truncated prompts, consistent low-temperature scoring

### Storage

- **DynamoDB Table**: `news-items` with composite key `(source, published_at_id)`
- **GSI**: `published_at-index` for cross-source time-based queries
- **Schema**: Supports relevance scores, synthetic flags, links, timestamps
- **Operations**: Batch writes with duplicate prevention

### Mock NewsFeed API
The GitHub repo is kept private as sharing the following is a security risk:

- **Elastic public IP address**: http://56.228.68.56:5000/api/v1/
- **Endpoints**:
  - `POST /ingest` - Accept synthetic test events
  - `GET /retrieve` - Return filtered events (score ≥ 3.0) sorted by relevance × recency
  - `GET /health` - System status
- **Processing**: Same LLM filter as production, deterministic ranking
- **Storage**: Memory-only for synthetic data (not persisted to DynamoDB)
- See `tests/test_api.sh` for ready-to-run examples

### Bonus question
*How would you evaluate the efficiency and correctness of your news retrieval and filtering process?*

- **Filtering accuracy**: Manual annotation of a (small) set of news items for each source
- **Time efficiency**: Measuring publication-to-upload latency
- **Cost efficiency**: track OpenAI and AWS costs (right now, the system is set up such that there are no costs associated with AWS)

### Ideas for future development

- Only include news items title (and description) in LLM prompt, leaving out the body, to reduce number of tokens
- Use RSS `lastBuildDate` to avoid reprocessing unchanged feeds
- Implement fall back filter(s) to take over if OpenAI API is down
- Improve monitoring of the application, set up alarms
- Apache Airflow or other orchestration tools
- IaC (Terraform) for automated deployment of the infrastructure



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

### EC2 instance setup
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

To run the application on the EC2, the instance needs proper permissions to the DynamoDB `news-items` table and the S3 `newsfeed-static-web-interface` bucket. These are granted by creating a policy, creating a IAM role with the policy, and then attributing the role to the EC2 instance. The policies are available at `configs/IAM_policies`.

To setup the S3 bucket, run the `scripts/setup_web_interface.py` script.

Additionally, the firewall needs to be configured to allow inbound http traffic on port 5000 (for the Mock NewsFeed API).

### Cron Job Setup
The crontab can be modified with the ```crontab -e``` command.
```bash
# Add to crontab for automated ingestion
# E.g: run every 2 hours with a 20 minute offset
0 */2 * * * /path/to/scripts/run_ingestion.sh tomshardware
20 */2 * * * /path/to/scripts/run_ingestion.sh arstechnica  
40 */2 * * * /path/to/scripts/run_ingestion.sh r-infosecnews
```

### Flask Server setup
```bash
# Run in foreground
poetry run python -m scripts.simple_api

# Run in background so it persists
nohup poetry run python -m scripts.simple_api > api.log 2>&1 &
```

### Tests
The `./tests` directory contains some basic functionality tests. At this point, there are no automated tests, just some simple python and bash scripts.
