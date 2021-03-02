import argparse
import os
import tarfile
import progressbar
import sys
import shutil
import subprocess
import yaml
import semver
import platform
from dotenv import load_dotenv
from urllib.request import urlretrieve


## TODO ignition files add a hitch into scripting this.  We can't generate them via openshift-install as it requires
##  user input.  Pull secrets, platform config, ssh-keys stand out the most as being problematic.
##  parameterizing the files paths would work, but still runs on some assumptions about platform (aws, gcp, etc) and
##  the presence platforms credentials.
##  Conclusion - automation and caliper are distinct from one-another.  Caliper as is can run against a standard OCP
##  cluster.  If this were to integrate into CI, it's a fair bet that cluster deployment already exists.

default_workdir = os.path.join(os.path.realpath(os.path.join(os.path.dirname(__file__), os.pardir)), "_clusters")

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--version', type=str, dest='version', default='latest', help='cluster version to deploy')
parser.add_argument('-d', '--dir', type=str, dest='work_dir', default=default_workdir,
                    help='optional prefix path for temp dir')
parser.add_argument('--region', type=str, dest='region', default='us-east-2', help='AWS region')
parser.add_argument('--install-config', type=str, dest='install_config_loc',
                    help='path to a fully defined ignition config', required=True)
parser.add_argument('--prom-top', type=str, dest='prom_top', help='path to the prom-top binary', default='prom-top')
parser.add_argument('--prom-top-config', type=str, default='prom_top_config', help='path the .env file containing DB config')
args = parser.parse_args()

load_dotenv()

version = args.version
try:
    if version != 'latest':
        semver.VersionInfo.parse(version)
except ValueError as e:
    print(f'Expected semver format, got {version}')
    quit(1)

host_os = ''
if platform.system() == 'Darwin':
    host_os = 'mac'
elif platform.system().lower() == 'Linux':
    host_os = 'linux'
else:
    print('unsupported OS (sorry Windows)')
    quit(0)

installer_link = f'openshift-install-{host_os}'
client_link = f'openshift-client-{host_os}'
if version == 'latest':
    installer_link = installer_link + '.tar.gz'
    client_link = client_link + '.tar.gz'
else:
    installer_link = installer_link + f'-{version}.tar.gz'
    client_link = client_link + f'-{version}.tar.gz'

installer_link = f'https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{version}/{installer_link}'
client_link = f'https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{version}/{client_link}'

install_config = os.path.realpath(args.install_config_loc)
try:
    os.stat(install_config)
except FileNotFoundError as e:
    print(e)

    quit(1)

work_dir = os.path.join(args.work_dir, version)
print('setting up workspace')
try:
    print(f'creating work dir: {work_dir}')
    os.mkdir(work_dir)
except FileExistsError:
    # we'll be overwriting the tars and bins here anyway
    pass

print(
    'Deployment Params:\n'
    f'\tVersion: {version}\n'
    f'\tClient: {client_link}\n'
    f'\tInstaller: {installer_link}\n'
    f'\tWorking Dir: {work_dir}\n'
)


pbar = None


def show_progress(block_num, block_size, total_size):
    global pbar
    if pbar is None:
        pbar = progressbar.ProgressBar(maxval=total_size, term_width=120,
                                       widgets=[progressbar.widgets.ETA(), progressbar.widgets.Bar()]).start()

    downloaded = block_num * block_size
    if downloaded < total_size:
        pbar.update(downloaded)
    else:
        pbar.finish()
        pbar = None


tarball = os.path.join(work_dir, os.path.basename(client_link))
print(f'Downloading file from {client_link} => {tarball}')
try:
    urlretrieve(url=client_link, filename=tarball, reporthook=show_progress)
except Exception as e:
    print(e)
    quit(1)
print('un-tarring openshift client')
with tarfile.open(tarball) as tar:
    tar.extract(member='oc', path=work_dir)
    tar.close()
oc = os.path.join(work_dir, 'oc')


tarball = os.path.join(work_dir, os.path.basename(installer_link))
print(f'Downloading file from {installer_link} => {tarball}')
try:
    urlretrieve(url=installer_link, filename=tarball, reporthook=show_progress)
except Exception as e:
    print(e)
    quit(1)
print('un-tarring openshift installer')
with tarfile.open(tarball) as tar:
    tar.extract('openshift-install', path=work_dir)
    tar.close()
openshift_install = os.path.join(work_dir, 'openshift-install')
#
# if there's a metadata.json file present, there's like a cluster that hasn't been torn down yet.  don't
# orphan the cluster.
config_dir = os.path.join(work_dir, 'deploy')
print(f'creating installer sub-dir: {config_dir}')
try:
    os.mkdir(config_dir)
except FileExistsError:
    try:
        meta_file = os.path.join(config_dir, 'metadata.json')
        f = os.stat(meta_file)
        print(f'found cluster metadata file {meta_file}, which could mean a cluster is still deployed.'
              f'To avoid orphaning a cluster, first run openshift-install destroy cluster --dir={config_dir}'
              f'then rerun this program.')
    except FileNotFoundError:
        pass

print(f'coping ignition config at {install_config} to {config_dir}')
try:
    config_dest = os.path.join(config_dir, 'install-config.yaml')
    shutil.copy(install_config, config_dest)

    with open(config_dest, mode='r') as file:
        installer_data = yaml.load(file, Loader=yaml.FullLoader)
        file.close()

    installer_data['metadata']['name'] = 'caliper-ocp-' + version
    installer_data['platform']["aws"]['region'] = args.region
    with open(config_dest, mode='w') as file:
        yaml.dump(installer_data, file, yaml.Dumper)
        file.close()
except Exception as e:
    print(e)
    quit(1)


print('starting cluster creation')
try:
    subprocess.run([f'{openshift_install}', 'create', 'cluster', '--dir', f'{config_dir}'], check=True)
except subprocess.CalledProcessError as e:
    print(e)
    sys.exit(1)

print('logging into cluster')
kubeconfig = os.path.realpath(os.path.join(config_dir, 'auth/kubeconfig'))
os.putenv('KUBECONFIG', kubeconfig)

password = ''
try:
    with open(os.path.realpath(os.path.join(config_dir, 'auth/kubeadmin-password'))) as file:
        password = file.read()
        file.close()
except FileNotFoundError as e:
    print(f'could not find password file {os.path.realpath(os.path.join(config_dir, "auth/kubeadmin-password"))}')
    quit(1)

try:
    subprocess.run([oc, 'login', '-u', 'kubeadmin', '-p', password], check=True)
    measurements = subprocess.run([args.prom_top, '--range', '30m', '-v', version, '--postgres'], text=True)
except subprocess.CalledProcessError as e:
    print(e)
    quit(1)
