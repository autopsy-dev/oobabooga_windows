import argparse
import glob
import os
import shutil
import site
import subprocess
import sys

script_dir = os.getcwd()




def run_cmd(cmd, assert_success=False, environment=False, capture_output=False, env=None):
    # Use the conda environment
    if environment:
        conda_env_path = os.path.join(script_dir, "installer_files", "env")
        if sys.platform.startswith("win"):
            conda_bat_path = os.path.join(script_dir, "installer_files", "conda", "condabin", "conda.bat")
            cmd = "\"" + conda_bat_path + "\" activate \"" + conda_env_path + "\" >nul && " + cmd
        else:
            conda_sh_path = os.path.join(script_dir, "installer_files", "conda", "etc", "profile.d", "conda.sh")
            cmd = ". \"" + conda_sh_path + "\" && conda activate \"" + conda_env_path + "\" && " + cmd
    
    # Run shell commands
    result = subprocess.run(cmd, shell=True, capture_output=capture_output, env=env)
    
    # Assert the command ran successfully
    if assert_success and result.returncode != 0:
        print("Command '" + cmd + "' failed with exit status code '" + str(result.returncode) + "'. Exiting...")
        sys.exit()
    return result
def display_models():
    model_dir = "models"
    global model_dirs
    model_dirs = [d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))]
    if len(model_dirs) == 0:
        print("No models found in the 'models' directory!")
    else:
        print("Available models:")
        for i, model in enumerate(model_dirs):
            print(f"{i+1}. {model}")

import os

def select_model():
    models_dir = os.path.join(os.getcwd(), "models")
    if not os.path.exists(models_dir) or not os.path.isdir(models_dir) or len(os.listdir(models_dir)) == 0:
        print("No models available. Please download a model and place it in the models directory.")
        return []
    
    while True:
        display_models()
        if len(model_dirs) > 0:
            model_indices = input("\nSelect a model (enter one or more numbers separated by spaces), or enter 'p' to specify a model path manually: ")
            if model_indices == 'p':
                model_path = input("\nEnter the path to the model directory: ")
                if os.path.exists(model_path) and os.path.isdir(model_path) and len(os.listdir(model_path)) > 0:
                    return [model_path]
                else:
                    print("Invalid model path. Please enter a valid path to a directory with at least one model.")
            elif all([idx.isdigit() and 1 <= int(idx) <= len(model_dirs) for idx in model_indices.split()]):
                return [os.path.join("models", model_dirs[int(idx)-1]) for idx in model_indices.split()]
            else:
                print("Invalid input. Please enter one or more valid numbers separated by spaces, or enter 'p' to specify a model path manually.")
        else:
            print("No models available. Please download a model and place it in the models directory.")
            break


def run_model():
    os.chdir("text-generation-webui")
    global model_dirs
    model_dirs = select_model()
    print("\n")
    if len(model_dirs) > 0:
        for model_dir in model_dirs:
            model_name = os.path.basename(model_dir)
            model_dir_path = os.path.dirname(model_dir)
            run_cmd(f"python server.py --chat --model-menu --wbits 4 --groupsize 128 --gpu-memory 22 --pre_layer 32 --auto-devices --model-dir {model_dir_path} --model {model_name} --model_type llama", environment=True)  # put your flags here!
    else:
        print("No models selected.")


def check_env():
    # If we have access to conda, we are probably in an environment
    conda_exist = run_cmd("conda", environment=True, capture_output=True).returncode == 0
    if not conda_exist:
        print("Conda is not installed. Exiting...")
        sys.exit()
    
    # Ensure this is a new environment and not the base environment
    if os.environ["CONDA_DEFAULT_ENV"] == "base":
        print("Create an environment for this project and activate it. Exiting...")
        sys.exit()


def install_dependencies():
    # Select your GPU or, choose to run in CPU mode
    print("What is your GPU")
    print()
    print("A) NVIDIA")
    print("B) AMD")
    print("C) Apple M Series")
    print("D) None (I want to run in CPU mode)")
    print()
    gpuchoice = input("Input> ").lower()

    # Install the version of PyTorch needed
    if gpuchoice == "a":
        run_cmd("conda install -y -k pytorch[version=2,build=py3.10_cuda11.7*] torchvision torchaudio pytorch-cuda=11.7 cuda-toolkit ninja git -c pytorch -c nvidia/label/cuda-11.7.0 -c nvidia", assert_success=True, environment=True)
    elif gpuchoice == "b":
        print("AMD GPUs are not supported. Exiting...")
        sys.exit()
    elif gpuchoice == "c" or gpuchoice == "d":
        run_cmd("conda install -y -k pytorch torchvision torchaudio cpuonly git -c pytorch", assert_success=True, environment=True)
    else:
        print("Invalid choice. Exiting...")
        sys.exit()

    # Clone webui to our computer
    run_cmd("git clone https://github.com/oobabooga/text-generation-webui.git", assert_success=True, environment=True)
    if sys.platform.startswith("win"):
        # Fix a bitsandbytes compatibility issue with Windows
        run_cmd("python -m pip install https://github.com/jllllll/bitsandbytes-windows-webui/raw/main/bitsandbytes-0.38.1-py3-none-any.whl", assert_success=True, environment=True)
    
    # Install the webui dependencies
    update_dependencies()


def update_dependencies():
    os.chdir("text-generation-webui")
    run_cmd("git pull", assert_success=True, environment=True)

    # Installs/Updates dependencies from all requirements.txt
    run_cmd("python -m pip install -r requirements.txt --upgrade", assert_success=True, environment=True)
    extensions = next(os.walk("extensions"))[1]
    for extension in extensions:
        extension_req_path = os.path.join("extensions", extension, "requirements.txt")
        if os.path.exists(extension_req_path):
            run_cmd("python -m pip install -r " + extension_req_path + " --upgrade", assert_success=True, environment=True)

    # The following dependencies are for CUDA, not CPU
    # Check if the package cpuonly exists to determine if torch uses CUDA or not
    cpuonly_exist = run_cmd("conda list cpuonly | grep cpuonly", environment=True, capture_output=True).returncode == 0
    if cpuonly_exist:
        return

    # Finds the path to your dependencies
    for sitedir in site.getsitepackages():
        if "site-packages" in sitedir:
            site_packages_path = sitedir
            break

    # This path is critical to installing the following dependencies
    if site_packages_path is None:
        print("Could not find the path to your Python packages. Exiting...")
        sys.exit()

    # Fix a bitsandbytes compatibility issue with Linux
    if sys.platform.startswith("linux"):
        shutil.copy(os.path.join(site_packages_path, "bitsandbytes", "libbitsandbytes_cuda117.so"), os.path.join(site_packages_path, "bitsandbytes", "libbitsandbytes_cpu.so"))

    if not os.path.exists("repositories/"):
        os.mkdir("repositories")
    
    # Install GPTQ-for-LLaMa which enables 4bit CUDA quantization
    os.chdir("repositories")
    if not os.path.exists("GPTQ-for-LLaMa/"):
        run_cmd("git clone https://github.com/oobabooga/GPTQ-for-LLaMa.git -b cuda", assert_success=True, environment=True)
    
    # Install GPTQ-for-LLaMa dependencies
    os.chdir("GPTQ-for-LLaMa")
    run_cmd("git pull", assert_success=True, environment=True)
    run_cmd("python -m pip install -r requirements.txt", assert_success=True, environment=True)
    
    # On some Linux distributions, g++ may not exist or be the wrong version to compile GPTQ-for-LLaMa
    if sys.platform.startswith("linux"):
        gxx_output = run_cmd("g++ --version", environment=True, capture_output=True)
        if gxx_output.returncode != 0 or b"g++ (GCC) 12" in gxx_output.stdout:
            # Install the correct version of g++
            run_cmd("conda install -y -k gxx_linux-64=11.2.0", environment=True)

    # Compile and install GPTQ-for-LLaMa
    os.rename("setup_cuda.py", "setup.py")
    run_cmd("python -m pip install .", environment=True)
    
    # Wheel installation can fail while in the build directory of a package with the same name
    os.chdir("..")
    
    # If the path does not exist, then the install failed
    quant_cuda_path_regex = os.path.join(site_packages_path, "quant_cuda*/")
    if not glob.glob(quant_cuda_path_regex):
        print("ERROR: GPTQ CUDA kernel compilation failed.")
        # Attempt installation via alternative, Windows-specific method
        if sys.platform.startswith("win"):
            print("Attempting installation with wheel.")
            result = run_cmd("python -m pip install https://github.com/jllllll/GPTQ-for-LLaMa-Wheels/raw/main/quant_cuda-0.0.0-cp310-cp310-win_amd64.whl", environment=True)
            if result.returncode == 0:
                print("Wheel installation success!")
            else:
                print("ERROR: GPTQ wheel installation failed. You will not be able to use GPTQ-based models.")
        else:
            print("You will not be able to use GPTQ-based models.")
        print("Continuing with install..")


def download_model():
    os.chdir("text-generation-webui")
    run_cmd("python download-model.py", environment=True)




if __name__ == "__main__":
    # Verifies we are in a conda environment
    check_env()

    parser = argparse.ArgumentParser()
    parser.add_argument('--update', action='store_true', help='Update the web UI.')
    args = parser.parse_args()

    if args.update:
        update_dependencies()
    else:
        # If webui has already been installed, skip and run
        if not os.path.exists("text-generation-webui/"):
            install_dependencies()
            os.chdir(script_dir)

        # Check if a model has been downloaded yet
        if len(glob.glob("text-generation-webui/models/*/")) == 0:
            download_model()
            os.chdir(script_dir)

        # Run the model with webui
        run_model()
