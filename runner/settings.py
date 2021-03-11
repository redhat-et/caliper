import dotenv
from dotenv import load_dotenv
from subprocess import run, DEVNULL
from os import path
import platform

def get_platform():
    host_os = ''
    if platform.system() == 'Darwin':
        host_os = 'mac'
    elif platform.system().lower() == 'Linux':
        host_os = 'linux'
    else:
        print('unsupported OS (sorry Windows)')
        quit(0)
    return host_os


# Return 0 if none found, 1 if docker image, 2 if local PATH binary
def verify_prom_top():
    output = run(['docker', 'inspect', 'quay.io/jcope/prom-top:latest'], check=False, text=True, stdout=DEVNULL)
    if output.returncode > 0:
        output = run(['which', 'prom-top'], check=False, text=True, stdout=DEVNULL)
        if output.returncode > 0:
            return 0
        else:
            return 2
    return 1


_env_file = dotenv.find_dotenv()
if _env_file == '':
    print('cannot find .env file')
    quit(1)

CLUSTER_INIT_BUFFER_SECONDS = 20 * 60
TEST_RANGE_SECONDS = 10 * 60  # time to allow the cluster to stabilize before gather metrics
MAX_WAIT_SECONDS = CLUSTER_INIT_BUFFER_SECONDS + TEST_RANGE_SECONDS
REPO_ROOT = path.realpath(path.join(path.dirname(__file__), path.pardir))
CLUSTER_WORKDIR = path.join(REPO_ROOT, '_clusters')
HOST_PLATFORM = get_platform()
PROM_TOP_SOURCE = verify_prom_top()
DOTENV = path.realpath(_env_file)

load_dotenv(DOTENV)
