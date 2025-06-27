The backend uses Poetry for package management, please install it.
###How to start
1. poetry install
2. I would recommend using vscode: launch.json
```
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Uvicorn with Debugpy",
            "type": "debugpy",
            "request": "launch",
            "module": "uvicorn",  // Run Uvicorn as a module
            "args": [
                "spos_service.main:app",  // Your app entry point
                "--reload"
            ],
            "console": "integratedTerminal",
            "justMyCode": false,  // Optional: Allows debugging of library code
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}

```
3. Under ```Run and Debug``` hit run
