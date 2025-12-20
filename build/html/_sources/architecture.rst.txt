Architecture
============

Benchmark workflow explanations.

Benchmark Runs
--------------

**Run Type 1: CPU Baseline**
1. Load configuration from config.yaml
2. Execute benchmark script: `./run_benchmark.sh`
3. Collect metrics via Python analyzer

**Run Type 2: GPU Accelerated**
1. Initialize orchestrator
2. Launch Node.js workload preprocessor
3. Run parallel benchmark with HTML dashboard

Workflow Diagram
----------------

