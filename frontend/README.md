# Meluxina SLURM Job Submitter with Node.js

This project is a Node.js script that connects via SSH to the Meluxina HPC cluster and submits SLURM batch jobs to run Python scripts remotely.

## Features

- Connects securely to Meluxina using SSH key authentication.
- Uploads SLURM batch scripts to the remote cluster via SFTP.
- Submits jobs using `sbatch` with resource requests.
- Supports passing JSON parameters to Python scripts on Meluxina.
- Fetches and logs SLURM job submission outputs.

## Requirements

- **Node.js** (v14+ recommended): runtime for JavaScript.
- **npm**: Node.js package manager.
- **SSH key configured** for passwordless login to Meluxina.
- Installed Node.js dependencies:
  - `ssh2`

## Installation

1. Clone this repository or download the script.

2. Install npm dependencies:


## Configuration

Edit the script to:

- Set your Meluxina username, hostname, and SSH key path.
- Adjust SLURM resource requests in the batch script portion.
- Specify the path to your Python script on Meluxina.
- Customize any JSON parameters to pass to the Python script.

## Usage
commands:

npm install

node conn_melux.js