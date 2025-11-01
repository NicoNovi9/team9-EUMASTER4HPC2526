let MONITORING_COMPUTE_NODE = null;//contains .ip and .node
const GRAFANA_LOCAL_PORT = 3000; 

// Global SSH connection
let sshConnection = null;
let isConnecting = false;
let prometheusServer = null;


module.exports = {
    MONITORING_COMPUTE_NODE,
    GRAFANA_LOCAL_PORT,
    prometheusServer,
    sshConnection,
    isConnecting
};