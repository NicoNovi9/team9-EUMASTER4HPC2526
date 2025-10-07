const { Client } = require('ssh2');
const fs = require('fs');

const conn = new Client();

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


const envParams={
    'privateKeyPath':contextParams.privateKey,
    'username':contextParams.username,
    'host':'login.lxp.lu',
    'port':8822
}
const sshConfig = {
  host: 'login.lxp.lu',
  port: envParams.port,
  username: envParams.username,
  privateKey: fs.readFileSync(envParams.privateKeyPath),
};

const myJson = {
  key1: "value1",
  key2: 42,
};

const recipe = fs.readFileSync('./recipe.json');
const recipeJson = JSON.parse(recipe);
recipeJson.username = envParams.username; // add username to the recipe
const jsonString = JSON.stringify(recipeJson).replace(/"/g, '\\"'); // just escape quotes

const jobScript = `#!/bin/bash -l

#SBATCH --time=00:05:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --ntasks-per-node=32

module load Python
python /home/users/${envParams.username}/orch.py "${jsonString}"
`;


// Save job script locally
fs.writeFileSync('job.sh', jobScript);

conn.on('ready', () => {
  console.log('SSH connection to Meluxina established!');

  // Upload the job script via SFTP and python files
  conn.sftp((err, sftp) => {
    if (err) throw err;

    sftp.fastPut('job.sh', 'job.sh', (err) => {
      if (err) throw err;
      console.log('Job script uploaded successfully.');
// uploading all python files so we don't have to manually upload them to meluxina
//--------------------------------upload orch.py
      sftp.fastPut('../backend/orch.py', 'orch.py', (err) => {
        if (err) throw err;
        console.log('orch.py uploaded successfully.');
      });
//--------------------------------upload clientsHandler.py
      sftp.fastPut('../backend/clientsHandler.py', 'clientsHandler.py', (err) => {
        if (err) throw err;
        console.log('clientsHandler.py uploaded successfully.');
      });
//--------------------------------upload llmClient.py
      sftp.fastPut('../backend/llmClient.py', 'llmClient.py', (err) => {
        if (err) throw err;
        console.log('llmClient.py uploaded successfully.');
      });
//--------------------------------upload retrievalClient.py
   //TODO: daniele will develop this file

      // Submit the job
      conn.exec('sbatch job.sh', (err, stream) => {
        if (err) throw err;

        stream.on('close', () => {
          console.log('SLURM job submission finished.');
          conn.end();
        }).on('data', (data) => {
          console.log('SLURM output:', data.toString());
        }).stderr.on('data', (data) => {
          console.error('SLURM error:', data.toString());
        });
      });
    });
  });
}).connect(sshConfig);
