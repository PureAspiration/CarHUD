import subprocess
import sys

python_executable = sys.executable  # This is the Python interpreter running run_all.py

print("Running compress_nslr.py...")
subprocess.run([python_executable, "compress_nslr.py"], check=True)

print("Running divide_nslr_to_grid.py...")
subprocess.run([python_executable, "divide_nslr_to_grid.py"], check=True)

print("All scripts completed successfully.")
