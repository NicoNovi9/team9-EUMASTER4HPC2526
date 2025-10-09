#!/bin/bash
set -e

echo "Starting Ollama server in container..."

# Configure Ollama to ignore TLS certificate verification
export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_INSECURE=true
export CURL_CA_BUNDLE=""
export SSL_VERIFY=false

# Start Ollama server
ollama serve &
OLLAMA_PID=$!
echo "Started ollama serve (PID: $OLLAMA_PID)"

# Wait for Ollama to initialize
echo "Waiting for Ollama to initialize..."
sleep 10

# Pull model if specified with TLS bypass
echo "Pulling model: llama2"
if [ -n "llama2" ]; then
    echo "Attempting to pull model: llama2 (ignoring TLS certificates)"
    
    # Try with curl bypass for TLS issues
    export GODEBUG=x509ignoreCN=0,x509sha1=1
    export CURL_INSECURE=1
    
    if ! ollama pull "llama2"; then
        echo "⚠ ollama pull failed, trying alternative method..."
        
        # Alternative: try to bypass TLS completely
        if ! GODEBUG=x509ignoreCN=0 ollama pull "llama2"; then
            echo "⚠ Both pull attempts failed - model may already be present or network issue"
            echo "Continuing anyway..."
        else
            echo "✓ Model llama2 pulled successfully with alternative method"
        fi
    else
        echo "✓ Model llama2 pulled successfully"
    fi
else
    echo "⚠ No model specified, skipping pull"
fi

echo "Ollama is ready - keeping container alive"
echo "Ollama API available at: http://$(hostname -i):11434"
echo "Available models:"
ollama list || echo "Could not list models"

# Keep the container running
wait $OLLAMA_PID
