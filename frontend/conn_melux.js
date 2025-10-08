const { Client } = require('ssh2');
const express = require('express');
const fs = require('fs');
const path = require('path');

// Global SSH connection
let sshConnection = null;
let isConnecting = false;

function getContextParams() {
  const params = {};

  if (__dirname.includes('ivanalkhayat')) {
    params.privateKey = '/Users/ivanalkhayat/.ssh/id_ed25519_mlux';
    params.username = 'u103038';
  }

  if (__dirname.includes('nicola')) {
    params.privateKey = 'nicola path';
    params.username = 'u10xxxx';
  }
  
  if (__dirname.includes('moa')) {
    params.privateKey = 'moa path';
    params.username = 'u10xxxx';
  }
  
  if (__dirname.includes('daniele')) {
    params.privateKey = 'daniele path';
    params.username = 'u10xxxx';
  }

  return params;
}

const contextParams = getContextParams();

const envParams = {
  'privateKeyPath': contextParams.privateKey,
  'username': contextParams.username,
  'host': 'login.lxp.lu',
  'port': 8822
};

const sshConfig = {
  host: 'login.lxp.lu',
  port: envParams.port,
  username: envParams.username,
  privateKey: fs.readFileSync(envParams.privateKeyPath),
};

// Get or create SSH connection
async function getSSHConnection() {
  return new Promise((resolve, reject) => {
    // If connection exists and is ready, return it
    if (sshConnection && sshConnection._sock && sshConnection._sock.readable) {
      return resolve(sshConnection);
    }

    // If already connecting, wait for it
    if (isConnecting) {
      const checkInterval = setInterval(() => {
        if (sshConnection && sshConnection._sock && sshConnection._sock.readable) {
          clearInterval(checkInterval);
          resolve(sshConnection);
        }
      }, 100);
      setTimeout(() => {
        clearInterval(checkInterval);
        reject(new Error('Connection timeout'));
      }, 10000);
      return;
    }

    // Create new connection
    isConnecting = true;
    sshConnection = new Client();

    sshConnection.on('ready', () => {
      console.log('SSH connection to Meluxina established!');
      isConnecting = false;
      resolve(sshConnection);
    });

    sshConnection.on('error', (err) => {
      console.error('SSH connection error:', err);
      isConnecting = false;
      sshConnection = null;
      reject(err);
    });

    sshConnection.on('close', () => {
      console.log('SSH connection closed');
      sshConnection = null;
      isConnecting = false;
    });

    sshConnection.connect(sshConfig);
  });
}

// Upload files helper
async function uploadFiles(sftp, files) {
  for (const file of files) {
    await new Promise((resolve, reject) => {
      sftp.fastPut(file.local, file.remote, (err) => {
        if (err) {
          console.error(`Failed to upload ${file.local}:`, err);
          reject(err);
        } else {
          console.log(`${file.remote} uploaded successfully.`);
          resolve();
        }
      });
    });
  }
}

// Execute command helper
async function execCommand(conn, command) {
  return new Promise((resolve, reject) => {
    conn.exec(command, (err, stream) => {
      if (err) return reject(err);

      let output = '';
      let errorOutput = '';

      stream.on('close', () => {
        if (errorOutput) {
          console.error('Command error:', errorOutput);
        }
        resolve(output);
      }).on('data', (data) => {
        output += data.toString();
        console.log('Output:', data.toString());
      }).stderr.on('data', (data) => {
        errorOutput += data.toString();
        console.error('STDERR:', data.toString());
      });
    });
  });
}

async function doBenchmarking() {
  const jobScript = `#!/bin/bash -l

#SBATCH --time=00:05:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --ntasks-per-node=32

module load Python
python /home/users/${envParams.username}/orch.py /home/users/${envParams.username}/recipe.json 
`;

  // Save job script locally
  fs.writeFileSync('job.sh', jobScript);

  try {
    const conn = await getSSHConnection();

    // Get SFTP session
    const sftp = await new Promise((resolve, reject) => {
      conn.sftp((err, sftpSession) => {
        if (err) reject(err);
        else resolve(sftpSession);
      });
    });

    // Define files to upload
    const filesToUpload = [
      { local: 'job.sh', remote: 'job.sh' },
      { local: '../backend/orch.py', remote: 'orch.py' },
      { local: '../backend/ollamaClient.py', remote: 'ollamaClient.py' },
      { local: '../backend/servicesHandler.py', remote: 'servicesHandler.py' },
      { local: '../backend/ollamaService.py', remote: 'ollamaService.py' },
      { local: '../backend/qdrantService.py', remote: 'qdrantService.py' },
      { local: 'recipe.json', remote: 'recipe.json' }
    ];

    // Upload all files
    await uploadFiles(sftp, filesToUpload);

    // Submit the job with --parsable flag
const output = await execCommand(conn, 'sbatch --parsable job.sh');
const jobId = output.trim();
console.log('SLURM job submission finished. Job ID:', jobId);

return { success: true, output: output.trim(), jobId: jobId };


  } catch (error) {
    console.error('Benchmarking failed:', error);
    return { success: false, error: error.message };
  }
}

async function submitSqueue() {
  try {
    const conn = await getSSHConnection();
    const output = await execCommand(conn, 'squeue');
    console.log('squeue output:\n' + output);
    return { success: true, output: output };
  } catch (error) {
    console.error('squeue failed:', error);
    return { success: false, error: error.message };
  }
}

async function submitCancel(jobId) {
  try {
    const conn = await getSSHConnection();
    const output = await execCommand(conn, `scancel ${jobId}`);
    console.log('scancel output:\n' + output);
    return { success: true, output: output };
  } catch (error) {
    console.error('scancel failed:', error);
    return { success: false, error: error.message };
  }
}

function setupWebApp() {
  const PORT = 8000;
  const app = express();

  // Middleware
  app.use(express.json());
  app.use(express.static(__dirname));

  // Serve the HTML wizard page
  app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'wizard.html'));
  });

  app.post('/startbenchmark', async (req, res) => {
    try {
      console.log("Received request to start benchmark", req.body);
      const jsonData = req.body;
      const fileName = 'recipe.json';
      const filePath = path.join(__dirname, fileName);

      // Save JSON to local filesystem
      fs.writeFileSync(filePath, JSON.stringify(jsonData, null, 2));
      console.log(`✓ JSON saved locally: ${filePath}`);

      // Start the benchmarking job
      const result = await doBenchmarking();

      res.json({
        success: result.success,
        message: result.success ? 'Benchmark job submitted successfully' : 'Failed to submit benchmark',
        path: filePath,
        fileName: fileName,
        jobId: result.output || result.error
      });

    } catch (error) {
      console.error('Error in /startbenchmark:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  });

  // Optional: Add endpoints for squeue and scancel
  app.get('/squeue', async (req, res) => {
    try {
      const result = await submitSqueue();
      res.json(result);
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  app.post('/scancel/:jobId', async (req, res) => {
    try {
      const result = await submitCancel(req.params.jobId);
      res.json(result);
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  app.listen(PORT, () => {
    console.log(`🚀 Server running at http://localhost:${PORT}`);
    console.log(`📄 Open http://localhost:${PORT} to access the wizard`);
  });
}

// Handle command line operations
const operation = process.argv[2];
const job_to_cancel = process.argv[3];

(async () => {
  if (!operation) {
    console.log("Submitting benchmarking job by default");
    await doBenchmarking();
    process.exit(0);
  }
  
  if (operation == "squeue") {
    console.log("Submitting squeue command");
    await submitSqueue();
    process.exit(0);
  }

  if (operation == "scancel" && job_to_cancel) {
    console.log("Submitting cancel command");
    await submitCancel(job_to_cancel);
    process.exit(0);
  }
  
  if (operation == "webapp") {
    console.log("Setting up web app");
    setupWebApp();
  }
})();

// Graceful shutdown on ctrl+c
process.on('SIGINT', () => {
  console.log('\nClosing SSH connection...');
  if (sshConnection) {
    sshConnection.end();
  }
  process.exit();
});
