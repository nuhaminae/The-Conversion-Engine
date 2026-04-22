# Run this from PowerShell: .\format.ps1
# Black
.\.venv\Scripts\black . --exclude .venv
# isort
.\.venv\Scripts\isort . --skip .venv
# flake8
.\.venv\Scripts\python.exe -m flake8 . --exclude=.venv
