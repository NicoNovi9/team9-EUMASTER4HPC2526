const { Client } = require('ssh2');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const fs = require('fs');
const path = require('path');
const net = require('net');
const { get } = require('http');

// Global SSH connection
let sshConnection = null;
let isConnecting = false;

// Prometheus tunnel state
let prometheusStream = null;
let prometheusServer = null;
const GRAFANA_LOCAL_PORT = 3000; 
// the monitoring compute node where prometheus AND grafana are running
let MONITORING_COMPUTE_NODE = null; // Update this with your compute node
let IP_COMPUTE_NODE = null; //IP of the compute node running prometheus, MAYBE USELESS
let OLLAMA_SERVICE_IP = null; // IP of the compute node running ollama_service
let OLLAMA_JOB_ID;
let OLLAMA_NODE;


async function waitForPrometheus(retries = 30, delay = 2000) {
  const conn = await getSSHConnection();
  
  attempts=0;
  if (!MONITORING_COMPUTE_NODE) {
    MONITORING_COMPUTE_NODE = await getPrometheusNode();    //todo decouple getting prometheus node and ollama info!! too messy
  }
  
  for (let i = 0; i < retries; i++) {
  
    console.log(`[${i+1}/${retries}] Checking Prometheus...`);
    
    try {
      const output = await execCommand(
        conn, 
        `curl -s http://${MONITORING_COMPUTE_NODE}:9090/-/healthy --connect-timeout 2`
      );
      
      if (output.includes('Prometheus')) {
        console.log('✓ Prometheus is ready!');
        return true;
      }else{
        console.log('Prometheus not ready yet, retrying...');
      }
    } catch (err) {
      // Ignore errors, keep trying
      console.log('catch error-> Prometheus not ready yet, retrying...');
      sleep(500);
    }
    
    // Wait before next attempt
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  
  throw new Error('Prometheus did not become ready in time');
}

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
      // Clean up Prometheus tunnel if connection closes
      if (prometheusServer) {
        prometheusServer.close();
        prometheusServer = null;
      }
    });

    sshConnection.connect(sshConfig);
  });
}

// Setup SSH tunnel to Grafana on compute node
async function setupGrafanaTunnel() {
  return new Promise(async (resolve, reject) => {
    try {
      // Get SSH connection
      const conn = await getSSHConnection();

      // If tunnel already exists, return success
      if (prometheusServer && prometheusServer.listening) {
        console.log('Prometheus tunnel already active');
        return resolve(true);
      }

      // Create local server that will forward to remote Prometheus
      prometheusServer = net.createServer((localSocket) => {
        console.log('Local connection received for Prometheus');

        // Forward the connection through SSH to the compute node
        conn.forwardOut(
          '127.0.0.1',              // Source address (local on Meluxina)
          0,                         // Source port (let SSH choose)
          MONITORING_COMPUTE_NODE,   // Destination host (compute node)
          GRAFANA_LOCAL_PORT,                      // Destination port (Grafana)
          (err, remoteStream) => {
            if (err) {
              console.error('SSH forward error:', err);
              localSocket.end();
              return;
            }

            console.log('SSH tunnel to grafana established');

            // Pipe data bidirectionally between local socket and remote stream
            localSocket.pipe(remoteStream).pipe(localSocket);

            // Handle errors
            localSocket.on('error', (err) => {
              console.error('Local socket error:', err);
              remoteStream.end();
            });

            remoteStream.on('error', (err) => {
              console.error('Remote stream error:', err);
              localSocket.end();
            });
          }
        );
      });

      // Listen on local port
      prometheusServer.listen(GRAFANA_LOCAL_PORT, '127.0.0.1', () => {
        console.log(`✓ Prometheus tunnel active on localhost:${GRAFANA_LOCAL_PORT}`);
        resolve(true);
      });

      prometheusServer.on('error', (err) => {
        console.error('Prometheus tunnel server error:', err);
        reject(err);
      });

    } catch (error) {
      console.error('Failed to setup Prometheus tunnel:', error);
      reject(error);
    }
  });
}

// Upload files helper
async function uploadFiles(sftp, files) {
//CREATE FIRST THE DIRECTORIES

const remoteDir = '/home/users/' + envParams.username + '/client';
const dirExists = await sftp.exists(remoteDir);

if (!dirExists) {
    await sftp.mkdir(remoteDir, true);
}
//THEN UPLOAD THE FILES
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
        console.error('the command was->'+command);
      });
    });
  });
}

async function doBenchmarking(res) {
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

    conn.sftp

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
      { local: '../backend/client/clientService.py', remote: 'client/clientService.py' },
      { local: '../backend/client/clientServiceHandler.py', remote: 'client/clientServiceHandler.py' },
      { local: '../backend/client/testClientService.py', remote: 'client/testClientService.py' },
      { local: '../backend/ollamaService.py', remote: 'ollamaService.py' },
      { local: '../backend/qdrantService.py', remote: 'qdrantService.py' },
      { local: 'recipe.json', remote: 'recipe.json' },
      { local: '../backend/pushgateway_service.sh', remote: 'pushgateway_service.sh' },
      { local: '../backend/client/client_service.def', remote: 'client/client_service.def' },
      { local: '../backend/monitoring_stack.sh', remote: 'monitoring_stack.sh' }
    ];

    // Upload all files
    await uploadFiles(sftp, filesToUpload);

    // Submit the job with --parsable flag
    const output = await execCommand(conn, 'sbatch --parsable job.sh');
    const jobId = output.trim();
    console.log('SLURM job submission finished. Job ID:', jobId);

    //TODO CHECK IF PROMETHEUS IS RUNNING
    await waitForPrometheus();
    ({ jobID: OLLAMA_JOB_ID, ip: OLLAMA_SERVICE_IP, node: OLLAMA_NODE } = await getOllamaServiceInfo(conn, envParams.username));

    setupGrafanaTunnel()

    return { success: true, output: output.trim(), jobId: jobId };

  } catch (error) {
    console.error('doBenchmarking-Benchmarking failed:', error);
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

  // Prometheus monitoring endpoint
  app.get('/monitor', async (req, res) => {
    try {
      // Ensure tunnel is active
      await setupGrafanaTunnel();
      
      // Serve HTML page with embedded Prometheus
      res.send(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Prometheus Monitoring - MeluXina</title>
          <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
              font-family: Arial, sans-serif;
              overflow: hidden;
            }
            .header {
              background: #2c3e50;
              color: white;
              padding: 15px 20px;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .header h1 {
              font-size: 20px;
              font-weight: normal;
            }
            .status {
              display: inline-block;
              margin-left: 20px;
              padding: 4px 12px;
              background: #27ae60;
              border-radius: 12px;
              font-size: 12px;
            }
            iframe { 
              position: absolute;
              top: 50px;
              left: 0;
              width: 100%; 
              height: calc(100% - 50px);
              border: none; 
            }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>
              Prometheus Monitoring
              <span class="status">🟢 Connected to ${MONITORING_COMPUTE_NODE}</span>
            </h1>
          </div>
          <iframe src="/prometheus/" sandbox="allow-same-origin allow-scripts allow-forms"></iframe>
        </body>
        </html>
      `);
    } catch (error) {
      res.status(500).send(`
        <h1>Error</h1>
        <p>Failed to setup Prometheus tunnel: ${error.message}</p>
        <p>Make sure Prometheus is running on ${MONITORING_COMPUTE_NODE}:9090</p>
      `);
    }
  });

  // Setup Prometheus tunnel endpoint
  app.post('/setup-tunnel', async (req, res) => {
    try {
      await setupGrafanaTunnel();
      res.json({ success: true, message: 'Prometheus tunnel established' });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  // Benchmark endpoints USED BY THE WIZARD!!!
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
      const result = await doBenchmarking(res);

      res.json({
        success: result.success,
        message: result.success ? 'Benchmark job submitted successfully' : 'Failed to submit benchmark',
        path: filePath,
        fileName: fileName,
        jobId: result.output || result.error,
        grafanaAddress: `http://localhost:${GRAFANA_LOCAL_PORT}`,
        ipComputeNodeService: OLLAMA_SERVICE_IP,
        ollamaComputeNode: OLLAMA_NODE,
        ollamaJobID: OLLAMA_JOB_ID
      });


    } catch (error) {
      console.error('Error in /startbenchmark:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  });

  // Get queue status
  app.get('/squeue', async (req, res) => {
    try {
      const result = await submitSqueue();
      res.json(result);
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  // Cancel job
  app.post('/scancel/:jobId', async (req, res) => {
    try {
      const result = await submitCancel(req.params.jobId);
      res.json(result);
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  // Prometheus proxy - THIS MUST BE LAST
  // Only proxy if tunnel is active
  /*app.use('/prometheus', async (req, res, next) => {
    // Check if tunnel exists, if not try to create it
    if (!prometheusServer || !prometheusServer.listening) {
      try {
        await setupGrafanaTunnel();
      } catch (error) {
        return res.status(503).send('Prometheus tunnel not available: ' + error.message);
      }
    }
    next();
  }, createProxyMiddleware({
    target: `http://localhost:${GRAFANA_LOCAL_PORT}`,
    changeOrigin: true,
    ws: true,
    pathRewrite: {
      '^/prometheus': '',
    },
    onError: (err, req, res) => {
      console.error('Proxy error:', err);
      res.status(500).send('Prometheus connection error. Tunnel may be down.');
    },
    onProxyReq: (proxyReq, req, res) => {
      console.log(`Proxying ${req.method} ${req.url} -> ${GRAFANA_LOCAL_PORT}`);
    }
  }));*/

  //kills any process using the port before starting the server
  require('child_process').execSync(`lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true`);

  app.listen(PORT, () => {
    console.log(`🚀 Server running at http://localhost:${PORT}`);
    console.log(`📄 Open http://localhost:${PORT} to access the wizard`);
    console.log(`📊 Open http://localhost:${PORT}/monitor to view Prometheus USELESS`);
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
  console.log('\nClosing connections...');
  if (prometheusServer) {
    prometheusServer.close();
  }
  if (sshConnection) {
    sshConnection.end();
  }
  process.exit();
});

// Get prometheus_service compute node from squeue
async function getPrometheusNode(maxAttempts = 100, delayMs = 2000) {
  console.log("prometheus getting node info");
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(`[${attempt}/${maxAttempts}] Checking for prometheus_service...`);
    
    try {
      const conn = await getSSHConnection();
      
      // Use your helper function to run squeue command
      const squeueCmd = `squeue -u ${envParams.username} -n monitoring_stack -h -o '%N'`;
      const output = await execCommand(conn, squeueCmd);
      
      const node = output.trim();
      if (node) {
        console.log(`✓ Found monitoring_stack running on node: ${node}`);
        
        // Call the 'host' command here using helper function
        const hostCmd = `host ${node}`;
        const hostResult = await execCommand(conn, hostCmd);
        console.log("Host command output:", hostResult.trim());

         // Extract IP using regex
        const ipRegex = /has address (\d{1,3}(?:\.\d{1,3}){3})/;
        const match = hostResult.match(ipRegex);
        IP_COMPUTE_NODE = match ? match[1] : null;

      if (IP_COMPUTE_NODE) {
        console.log(`Resolved IP for ${node}: ${IP_COMPUTE_NODE}`);
      } else {
        console.warn(`No IP address found in output:\n${hostResult}`);
      }      
        
        return node;  // Node name still returned as before
      }

      // Retry logic
      if (attempt < maxAttempts) {
        console.log(`monitoring_stack not found, retrying in ${delayMs}ms...`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }

    } catch (error) {
      console.error(`Error on attempt ${attempt}:`, error.message);
      
      // Retry if possible
      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      } else {
        throw error;
      }
    }
  }
  
  throw new Error(`No monitoring_stack job found after ${maxAttempts} attempts. Please submit the job first.`);
}
async function getOllamaServiceInfo(conn, username, options = {}) {
  const {
    maxRetries = 10,
    initialDelay = 20000,
    maxDelay = 60000,
    backoffMultiplier = 1.5
  } = options;

  async function attemptGetServiceInfo(attemptNumber) {
    try {
      const jobName = 'ollama_service';
      const squeueCmd = `squeue -u ${username} -n ${jobName} -h -o '%i %N %S' --sort=-S | head -n 1`;
      const squeueResult = (await execCommand(conn, squeueCmd)).trim();
      console.log(`squeue result for ${jobName}:`, squeueResult);

      if (!squeueResult) {
        throw new Error(`No job found with name: ${jobName}`);
      }

      // Parse job ID and node name
      const [jobID, nodeName] = squeueResult.split(/\s+/);
      
      if (!jobID || !nodeName) {
        throw new Error(`Could not parse job info from squeue result: ${squeueResult}`);
      }

      console.log(`Job '${jobName}' (ID: ${jobID}) is running on node: ${nodeName}`);

      // Step 2: Run host command to get IP address of the node
      const hostCmd = `host ${nodeName}`;
      const hostResult = await execCommand(conn, hostCmd);

      // Step 3: Extract IP from host command output
      const ipRegex = /has address (\d{1,3}(?:\.\d{1,3}){3})/;
      const match = hostResult.match(ipRegex);
      const ollamaIP = match ? match[1] : null;

      if (!ollamaIP) {
        throw new Error(`Could not parse IP from host result:\n${hostResult}`);
      }

      console.log(`Ollama service details - Job ID: ${jobID}, Node: ${nodeName}, IP: ${ollamaIP}`);
      
      return {
        jobID: jobID,
        ip: ollamaIP,
        node: nodeName
      };

    } catch (err) {
      if (attemptNumber >= maxRetries) {
        console.error(`Failed after ${maxRetries} attempts:`, err.message);
        throw err;
      }

      const delay = Math.min(
        initialDelay * Math.pow(backoffMultiplier, attemptNumber),
        maxDelay
      );

      console.log(
        `Attempt ${attemptNumber + 1}/${maxRetries} failed: ${err.message}. ` +
        `Retrying in ${delay}ms...`
      );

      await new Promise(resolve => setTimeout(resolve, delay));

      return attemptGetServiceInfo(attemptNumber + 1);
    }
  }

  // 👇 Wait before first attempt
  console.log(`Waiting ${initialDelay}ms before first attempt...`);
  await new Promise(resolve => setTimeout(resolve, initialDelay));

  return attemptGetServiceInfo(0);
}
