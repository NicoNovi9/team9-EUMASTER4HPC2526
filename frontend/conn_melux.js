const { Client } = require('ssh2');
const express = require('express');
const fs = require('fs');
const path = require('path');
const net = require('net');
const { get } = require('http');

const consts = require('./constants.js');
const helper = require('./helper.js');


// Prometheus tunnel state
// the monitoring compute node where prometheus AND grafana are running
let IP_COMPUTE_NODE = null; //IP of the compute node running prometheus, MAYBE USELESS
let OLLAMA_SERVICE_IP = null; // IP of the compute node running ollama_service
let OLLAMA_JOB_ID;
let OLLAMA_NODE;




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
python /home/users/${helper.envParams.username}/orch.py /home/users/${helper.envParams.username}/recipe.json 
`;

  // Save job script locally
  fs.writeFileSync('job.sh', jobScript);

  try {
    const conn = await helper.getSSHConnection();

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
      { local: '../backend/requirements.txt', remote: 'requirements.txt' },
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
    await helper.uploadFiles(sftp, filesToUpload);

    // Submit the job with --parsable flag
    const output = await helper.execCommand(conn, 'sbatch --parsable job.sh');
    const jobId = output.trim();
    console.log('SLURM job submission finished. Job ID:', jobId);

    //TODO CHECK IF PROMETHEUS IS RUNNING
    await helper.waitForPrometheus();
    ({ jobID: OLLAMA_JOB_ID, ip: OLLAMA_SERVICE_IP, node: OLLAMA_NODE } = await helper.getOllamaServiceInfo(conn, helper.envParams.username));

    helper.setupGrafanaTunnel()

    return { success: true, output: output.trim(), jobId: jobId };

  } catch (error) {
    console.error('doBenchmarking-Benchmarking failed:', error);
    return { success: false, error: error.message };
  }

  
}

async function submitSqueue() {
  try {
    const conn = await helper.getSSHConnection();
    const output = await helper.execCommand(conn, 'squeue');
    console.log('squeue output:\n' + output);
    return { success: true, output: output };
  } catch (error) {
    console.error('squeue failed:', error);
    return { success: false, error: error.message };
  }
}

async function submitCancel(jobId) {
  try {
    const conn = await helper.getSSHConnection();
    const output = await helper.execCommand(conn, `scancel ${jobId}`);
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

  // ========================================
  // LOGS ENDPOINTS
  // ========================================

  // Get list of log files/directories
  app.get('/logs', async (req, res) => {
  try {
    const conn = await helper.getSSHConnection();
    const subPath = req.query.path || '';
    const baseLogsPath = `/home/users/${helper.envParams.username}/output/logs`;
    const fullPath = subPath ? `${baseLogsPath}/${subPath}` : baseLogsPath;

    // Ottieni la lista dei file
    const logsList = await helper.listLogsDirectory(conn, fullPath, subPath);
    
    // Renderizza il template HTML
    const html = helper.renderTemplate(
      path.join(__dirname, 'templates', 'log-browser.html'),
      {
        BREADCRUMB: helper.generateBreadcrumb(subPath),
        CONTENT: helper.generateLogsContent(logsList)
      }
    );
    
    res.send(html);
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// View log file content
app.get('/logs/view', async (req, res) => {
  try {
    const conn = await helper.getSSHConnection();
    const filePath = req.query.file;
    
    if (!filePath) {
      return res.status(400).send('File path required');
    }

    const baseLogsPath = `/home/users/${helper.envParams.username}/output/logs`;
    const fullPath = `${baseLogsPath}/${filePath}`;
    
    const content = await helper.readLogFile(conn, fullPath);
    const fileInfo = await helper.getFileInfo(conn, fullPath);

    // Renderizza il template HTML
    const html = helper.renderTemplate(
      path.join(__dirname, 'templates', 'log-viewer.html'),
      {
        FILE_NAME: path.basename(filePath),
        FILE_META: `Size: ${(fileInfo.size / 1024).toFixed(2)} KB | Modified: ${new Date(fileInfo.modified).toLocaleString()}`,
        BACK_LINK: `/logs?path=${encodeURIComponent(path.dirname(filePath))}`,
        FILE_CONTENT: content || '<em style="color: #888;">File is empty</em>'
      }
    );
    
    res.send(html);
  } catch (error) {
    res.status(500).send(`<h1>Error</h1><p>${error.message}</p>`);
  }
});


  // Download log file
  app.get('/logs/download', async (req, res) => {
    try {
      const conn = await helper.getSSHConnection();
      const filePath = req.query.file;
      
      if (!filePath) {
        return res.status(400).send('File path required');
      }

      const baseLogsPath = `/home/users/${helper.envParams.username}/output/logs`;
      const fullPath = `${baseLogsPath}/${filePath}`;
      
      const content = await helper.readLogFile(conn, fullPath);
      
      res.setHeader('Content-Disposition', `attachment; filename="${path.basename(filePath)}"`);
      res.setHeader('Content-Type', 'text/plain');
      res.send(content);
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });


  // Setup Prometheus tunnel endpoint
  app.post('/setup-tunnel', async (req, res) => {
    try {
      await helper.setupGrafanaTunnel();
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
        grafanaAddress: `http://localhost:${consts.GRAFANA_LOCAL_PORT}`,
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


  //kills any process using the port before starting the server
  require('child_process').execSync(`lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true`);

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
  console.log('\nClosing connections...');
  if (consts.prometheusServer) {
    consts.prometheusServer.close();
  }
  if (consts.sshConnection) {
    consts.sshConnection.end();
  }
  process.exit();
});






