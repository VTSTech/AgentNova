import os
import subprocess
import logging

def setup_bitnet(directory, model_name):
    """Handles cloning, compiling, and downloading."""
    if not os.path.exists(directory):
        print(f"Cloning BitNet to {directory}...")
        subprocess.run(["git", "clone", "--recursive", "https://github.com/microsoft/BitNet.git", directory])
    
    os.chdir(directory)
    
    # Check for Clang/LLVM
    print("Checking for Clang compiler...")
    # Trigger the setup_env logic provided by Microsoft
    cmd = [
        "python", "setup_env.py", 
        "--hf-repo", f"microsoft/{model_name}", 
        "--quant-type", "i2_s"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ BitNet Setup and Compilation Successful.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed. Ensure 'C++ Clang tools for Windows' is installed in VS2022. Error: {e}")

if __name__ == "__main__":
    # Example usage
    setup_bitnet("F:/Tools/bitnet-llama", "BitNet-b1.58-2B-4T")