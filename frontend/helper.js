const fs = require('fs');
const path = require('path');
const consts = require('./constants.js');
const net = require('net');
const pLimit = require('p-limit');


const { Client } = require('ssh2');

let envParams = {};

function init() {
    contextParams=getContextParams();
   envParams = {
  'privateKeyPath': contextParams.privateKey,
  'username': contextParams.username,
  'host': 'login.lxp.lu',
  'port': 8822};
  
}

init();//called outside via require!

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



const sshConfig = {
  host: 'login.lxp.lu',
  port: envParams.port,
  username: envParams.username,
  privateKey: fs.readFileSync(envParams.privateKeyPath),
};

//get or create ssh connection
async function getSSHConnection() {
  return new Promise((resolve, reject) => {
    // If connection exists and is ready, return it
    if (consts.sshConnection && consts.sshConnection._sock && consts.sshConnection._sock.readable) {
      return resolve(consts.sshConnection);
    }

    // If already connecting, wait for it
    if (consts.isConnecting) {
      const checkInterval = setInterval(() => {
        if (consts.sshConnection && consts.sshConnection._sock && consts.sshConnection._sock.readable) {
          clearInterval(checkInterval);
          resolve(consts.sshConnection);
        }
      }, 100);
      setTimeout(() => {
        clearInterval(checkInterval);
        reject(new Error('Connection timeout'));
      }, 10000);
      return;
    }

    // Create new connection
    consts.isConnecting = true;
    consts.sshConnection = new Client();

    consts.sshConnection.on('ready', () => {
      console.log('SSH connection to Meluxina established!');
      consts.isConnecting = false;
      resolve(consts.sshConnection);
    });

    consts.sshConnection.on('error', (err) => {
      console.error('SSH connection error:', err);
      consts.isConnecting = false;
      consts.sshConnection = null;
      reject(err);
    });

    consts.sshConnection.on('close', () => {
      console.log('SSH connection closed');
      consts.sshConnection = null;
      consts.isConnecting = false;
      // Clean up Prometheus tunnel if connection closes
      if (consts.prometheusServer) {
        consts.prometheusServer.close();
        consts.prometheusServer = null;
      }
    });

    consts.sshConnection.connect(sshConfig);
  });
}

/**
 * Wait for Prometheus to become ready
 */
async function waitForPrometheus(retries = 30, delay = 2000) {
  const conn = await getSSHConnection();
  
  attempts=0;
  if (!consts.MONITORING_COMPUTE_NODE) {
    consts.MONITORING_COMPUTE_NODE = await getPrometheusNode(conn, envParams.username, );    //todo decouple getting prometheus node and ollama info!! too messy
    console.log("Prometheus compute node IP:", consts.MONITORING_COMPUTE_NODE.ip);
}
  
  for (let i = 0; i < retries; i++) {
  
    console.log(`[${i+1}/${retries}] Checking Prometheus...`);
    
    try {
        console.log(`doing: curl -s http://${consts.MONITORING_COMPUTE_NODE.ip}:9090/-/healthy --connect-timeout 2`);
      const output = await execCommand(
        conn, 
        `curl -s http://${consts.MONITORING_COMPUTE_NODE.ip}:9090/-/healthy --connect-timeout 2`
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




/**
 * Get context-specific parameters based on user directory
 */
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

/**
 * Execute SSH command
 */
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
        console.error('the command was->' + command);
      });
    });
  });
}

/**
 * Upload multiple files via SFTP
 */
async function uploadFiles(sftp, files) {
  const remoteDir = '/home/users/' + envParams.username + '/client';
  const dirExists = await sftp.exists(remoteDir);

  if (!dirExists) {
    await sftp.mkdir(remoteDir, true);
  }

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

//Get Prometheus compute node from squeue
async function getPrometheusNode(conn, username, maxAttempts = 100, delayMs = 2000) {
  console.log("Getting prometheus node info");
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(`[${attempt}/${maxAttempts}] Checking for monitoring_stack...`);
    
    try {
      const squeueCmd = `squeue -u ${username} -n monitoring_stack -h -o '%N'`;
      const output = await execCommand(conn, squeueCmd);
      
      const node = output.trim();
      if (node) {
        console.log(`✓ Found monitoring_stack running on node: ${node}`);
        
        const hostCmd = `host ${node}`;
        const hostResult = await execCommand(conn, hostCmd);
        console.log("Host command output:", hostResult.trim());

        const ipRegex = /has address (\d{1,3}(?:\.\d{1,3}){3})/;
        const match = hostResult.match(ipRegex);
        const ipComputeNode = match ? match[1] : null;

        if (ipComputeNode) {
          console.log(`Resolved IP for ${node}: ${ipComputeNode}`);
        } else {
          console.warn(`No IP address found in output:\n${hostResult}`);
        }      
        
        return { node, ip: ipComputeNode };
      }

      if (attempt < maxAttempts) {
        console.log(`monitoring_stack not found, retrying in ${delayMs}ms...`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }

    } catch (error) {
      console.error(`Error on attempt ${attempt}:`, error.message);
      
      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      } else {
        throw error;
      }
    }
  }
  
  throw new Error(`No monitoring_stack job found after ${maxAttempts} attempts.`);
}

/**
 * Get Ollama service information
 */
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
// ===============SSH LOGS HELPERS================ //


const limit = pLimit(3); // max 3 concurrent SFTP operations
let cachedSftp = null;

/**
 * Reuse a single SFTP session
 */
async function getSftp(conn) {
  if (cachedSftp) return cachedSftp;
  cachedSftp = await new Promise((resolve, reject) => {
    conn.sftp((err, sftp) => {
      if (err) reject(err);
      else resolve(sftp);
    });
  });
  return cachedSftp;
}

/**
 * Generic retry wrapper with exponential backoff
 */
async function withRetry(fn, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (err) {
      if (err.message.includes('Channel open failure') && i < retries - 1) {
        const delay = 1000 * (i + 1);
        console.warn(`⚠️ SFTP channel failed, retrying in ${delay}ms...`);
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw err;
    }
  }
}

/**
 * List files and directories in a given path (reusing SFTP session)
 */
async function listLogsDirectory(conn, remotePath, relativePath = '') {
  return limit(async () =>
    withRetry(async () => {
      const sftp = await getSftp(conn);

      const items = await new Promise((resolve, reject) => {
        sftp.readdir(remotePath, (err, list) => {
          if (err) reject(err);
          else resolve(list);
        });
      });

      const result = { files: [], directories: [] };

      for (const item of items) {
        const relPath = relativePath ? `${relativePath}/${item.filename}` : item.filename;
        const entry = {
          name: item.filename,
          path: relPath,
          size: item.attrs.size,
          modified: new Date(item.attrs.mtime * 1000).toISOString()
        };

        if (item.attrs.isDirectory()) result.directories.push(entry);
        else result.files.push({ ...entry, extension: path.extname(item.filename) });
      }

      result.directories.sort((a, b) => a.name.localeCompare(b.name));
      result.files.sort((a, b) => a.name.localeCompare(b.name));
      return result;
    })
  );
}

/**
 * Read the content of a remote log file (reusing SFTP)
 */
async function readLogFile(conn, remotePath) {
  return limit(async () =>
    withRetry(async () => {
      const sftp = await getSftp(conn);
      return new Promise((resolve, reject) => {
        const readStream = sftp.createReadStream(remotePath);
        let content = '';

        readStream.on('data', (chunk) => (content += chunk.toString('utf8')));
        readStream.on('end', () => resolve(content));
        readStream.on('error', (err) => reject(err));
      });
    })
  );
}

/**
 * Get metadata about a file or directory (reusing SFTP)
 */
async function getFileInfo(conn, remotePath) {
  return limit(async () =>
    withRetry(async () => {
      const sftp = await getSftp(conn);

      return new Promise((resolve, reject) => {
        sftp.stat(remotePath, (err, stats) => {
          if (err) reject(err);
          else
            resolve({
              size: stats.size,
              modified: new Date(stats.mtime * 1000).toISOString(),
              isDirectory: stats.isDirectory(),
              isFile: stats.isFile()
            });
        });
      });
    })
  );
}


/// --------------HTML HELPERS ---------------  //

/**
 * Simple template rendering function
 * Replaces {{PLACEHOLDER}} with actual values
 */
function renderTemplate(templatePath, data) {
  try {
    let template = fs.readFileSync(templatePath, 'utf8');
    
    // Replace all placeholders with actual data
    for (const [key, value] of Object.entries(data)) {
      const placeholder = new RegExp(`{{${key}}}`, 'g');
      template = template.replace(placeholder, value || '');
    }
    
    return template;
  } catch (error) {
    console.error('Error rendering template:', error);
    throw error;
  }
}


/**
 * Generate directory item HTML
 */
function generateDirectoryItem(dir) {
  return `
    <div class="item">
      <div class="item-left">
        <div class="icon">📁</div>
        <div class="item-info">
          <div class="item-name">${dir.name}</div>
          <div class="item-meta">Modified: ${new Date(dir.modified).toLocaleString()}</div>
        </div>
      </div>
      <div class="item-actions">
        <a href="/logs?path=${encodeURIComponent(dir.path)}" class="btn btn-view">Open</a>
      </div>
    </div>
  `;
}

/**
 * Generate file item HTML
 */
function generateFileItem(file) {
  const icon = file.extension === '.err' ? '❌' : file.extension === '.out' ? '✅' : '📄';
  
  return `
    <div class="item">
      <div class="item-left">
        <div class="icon">${icon}</div>
        <div class="item-info">
          <div class="item-name">${file.name}</div>
          <div class="item-meta">
            Size: ${(file.size / 1024).toFixed(2)} KB | 
            Modified: ${new Date(file.modified).toLocaleString()}
          </div>
        </div>
      </div>
      <div class="item-actions">
        <a href="/logs/view?file=${encodeURIComponent(file.path)}" class="btn btn-view" target="_blank">View</a>
        <a href="/logs/download?file=${encodeURIComponent(file.path)}" class="btn btn-download">Download</a>
      </div>
    </div>
  `;
}



/**
 * Utility sleep function
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Setup SSH tunnel to Grafana on compute node
async function setupGrafanaTunnel() {
  return new Promise(async (resolve, reject) => {
    try {
      // Get SSH connection
      const conn = await getSSHConnection();

      // If tunnel already exists, return success
      if (consts.prometheusServer && consts.prometheusServer.listening) {
        console.log('Prometheus tunnel already active');
        return resolve(true);
      }

      // Create local server that will forward to remote Prometheus
      consts.prometheusServer = net.createServer((localSocket) => {
        console.log('Local connection received for Prometheus');

        // Forward the connection through SSH to the compute node
        conn.forwardOut(
          '127.0.0.1',              // Source address (local on Meluxina)
          0,                         // Source port (let SSH choose)
          consts.MONITORING_COMPUTE_NODE.ip,   // Destination host (compute node)
          consts.GRAFANA_LOCAL_PORT,                      // Destination port (Grafana)
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
      consts.prometheusServer.listen(consts.GRAFANA_LOCAL_PORT, '127.0.0.1', () => {
        console.log(`✓ Prometheus tunnel active on localhost:${consts.GRAFANA_LOCAL_PORT}`);
        resolve(true);
      });

      consts.prometheusServer.on('error', (err) => {
        console.error('Prometheus tunnel server error:', err);
        reject(err);
      });

    } catch (error) {
      console.error('Failed to setup Prometheus tunnel:', error);
      reject(error);
    }
  });
}



/**
 * Generate breadcrumb HTML for logs browser
 */
function generateBreadcrumb(subPath) {
  let breadcrumb = '<a href="/logs">output/logs</a>';
  
  if (subPath) {
    const parts = subPath.split('/');
    breadcrumb += ' / ' + parts.map((part, idx) => {
      const partialPath = parts.slice(0, idx + 1).join('/');
      return `<a href="/logs?path=${encodeURIComponent(partialPath)}">${part}</a>`;
    }).join(' / ');
  }
  
  return breadcrumb;
}



/**
 * Generate content for logs browser
 */
function generateLogsContent(logsList) {
  if (logsList.directories.length === 0 && logsList.files.length === 0) {
    return `
      <div class="empty">
        <div class="empty-icon">📂</div>
        <h2>No logs found</h2>
        <p>This directory is empty</p>
      </div>
    `;
  }
  
  let content = '';
  
  // Add directories
  content += logsList.directories.map(dir => generateDirectoryItem(dir)).join('');
  
  // Add files
  content += logsList.files.map(file => generateFileItem(file)).join('');
  
  return content;
}

function generateJobSH(username){
  const jobScript = `#!/bin/bash -l

#SBATCH --time=00:45:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --output=/home/users/${username}/output/logs/%x_%j.out
#SBATCH --error=/home/users/${username}/output/logs/%x_%j.err

mkdir -p /home/users/${username}/output/logs

module load Python
python /home/users/u103038/orch.py /home/users/${username}/recipe.json 
`;
// writing to file in local

try {
  fs.writeFileSync('job.sh', jobScript);
  // file written successfully
} catch (err) {
  console.error(err);
}
}

module.exports = {
    init,
  waitForPrometheus,
  getSSHConnection,
  getContextParams,
    sshConfig,
    envParams,
    setupGrafanaTunnel,
      renderTemplate,           
  generateBreadcrumb,       
  generateLogsContent,  
  execCommand,
  uploadFiles,
  getOllamaServiceInfo,
  listLogsDirectory,
  readLogFile,
  getFileInfo,
  generateJobSH
};
