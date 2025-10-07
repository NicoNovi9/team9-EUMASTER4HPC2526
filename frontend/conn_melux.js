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


const recipe = fs.readFileSync('./recipe.json');
const recipeJson = JSON.parse(recipe);
recipeJson.username = envParams.username; // add username to the recipe
const jsonString = JSON.stringify(recipeJson).replace(/"/g, '\\"'); // just escape quotes

const operation = process.argv[2];
const job_to_cancel = process.argv[3];


if(!operation){
  console.log("submitting benchmarking job by default");
  doBenchmarking();
}
if(operation == "squeue"){
  console.log("submitting squeue command");
  submitSqueue();
}

if(operation == "scancel" && job_to_cancel){
  console.log("submitting cancel command"); 
  submitCancel(job_to_cancel);
}





function doBenchmarking(){
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
     // sftp.fastPut('../backend/clientsHandler.py', 'clientsHandler.py', (err) => {
     //   if (err) throw err;
     //   console.log('clientsHandler.py uploaded successfully.');
     // });
//--------------------------------upload llmClient.py
      sftp.fastPut('../backend/ollamaClient.py', 'ollamaClient.py', (err) => {
        if (err) throw err;
        console.log('ollamaClient.py uploaded successfully.');
      });
//--------------------------------upload serviceHandler.py
   sftp.fastPut('../backend/servicesHandler.py', 'servicesHandler.py', (err) => {
        if (err) throw err;
        console.log('serviceHandler.py uploaded successfully.');
      });
//--------------------------------upload ollamaService.py
   sftp.fastPut('../backend/ollamaService.py', 'ollamaService.py', (err) => {
        if (err) throw err;
        console.log('ollamaService.py uploaded successfully.');
      });
//--------------------------------upload qdrantService.py
   sftp.fastPut('../backend/qdrantService.py', 'qdrantService.py', (err) => {
        if (err) throw err;
        console.log('qdrantService.py uploaded successfully.');
      });
      //--------------------------------upload recipe.js
   sftp.fastPut('recipe.json', 'recipe.json', (err) => {
        if (err) throw err;
        console.log('recipe.json uploaded successfully.');
      });

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
}

function submitSqueue(){
  
  conn.on('ready', () => {
  console.log('Connected to Meluxina for squeue!');
  conn.exec('squeue', (err, stream) => {
    if (err) throw err;

    let output = '';
    stream.on('close', (code, signal) => {
      console.log('squeue output:\n' + output);
      conn.end();
    }).on('data', (data) => {
      output += data.toString();
    }).stderr.on('data', (data) => {
      console.error('STDERR: ' + data.toString());
    });
  });
}).connect(sshConfig);
}
function submitCancel(jobId){
  
  conn.on('ready', () => {
  console.log('Connected to Meluxina for squeue!');
  conn.exec('scancel '+jobId, (err, stream) => {
    if (err) throw err;

    let output = '';
    stream.on('close', (code, signal) => {
      console.log('scancel output:\n' + output);
      conn.end();
    }).on('data', (data) => {
      output += data.toString();
    }).stderr.on('data', (data) => {
      console.error('STDERR: ' + data.toString());
    });
  });
}).connect(sshConfig);

}