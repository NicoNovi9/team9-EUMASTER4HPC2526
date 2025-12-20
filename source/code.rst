Code Documentation
==================

Overview of project files and modules.

Python Modules
--------------

.. automodule:: src.benchmark.main
   :members:
   :undoc-members:

.. automodule:: src.analyzer.stats
   :members:

Bash Scripts
------------

**run_benchmark.sh**
- Launches HPC workloads
- Parameters: `--nodes N --duration T`
- Usage: `./run_benchmark.sh --nodes 4 --duration 300`

Node.js Components
------------------

**dashboard/server.js**
- Serves real-time metrics
- Endpoints: `/metrics`, `/status`

HTML Files
----------

**dashboard/index.html**
- Main visualization page
- Includes D3.js charts for live data
