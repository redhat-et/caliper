import argparse
import os
import tarfile
import progressbar
import sys
import shutil
import subprocess
from hashlib import sha256
from urllib.parse import urlsplit
from urllib.request import urlretrieve

## TODO ignition files add a hitch into scripting this.  We can't generate them via openshift-install as it requires
##  user input.  Pull secrets, platform config, ssh-keys stand out the most as being problematic.
##  parameterizing the files paths would work, but still runs on some assumptions about platform (aws, gcp, etc) and
##  the presence platforms credentials.
##  Conclusion - automation and caliper are distinct from one-another.  Caliper as is can run against a standard OCP
##  cluster.  If this were to integrate into CI, it's a fair bet that cluster deployment already exists.

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--dir', type=str, dest='work_dir', help='optional prefix path for temp dir', required=True)
parser.add_argument('-c', '--client', type=str, dest='client_loc', help='URL location of OCP client', required=True)
parser.add_argument('-i', '--installer', type=str, dest='installer_loc', help='URL location of OCP installer', required=True)
parser.add_argument("--ignition-config", type=str, dest='ignition_loc', help='path to a fully defined ignition config', required=True)
args = parser.parse_args()

ignition_file = args.ignition_loc
try:
    os.stat(ignition_file)
except FileNotFoundError as e:
    print(e)
    sys.exit(1)

ocp_version = os.path.join(args.work_dir)
try:
    os.stat(ocp_version)
except FileNotFoundError as e:
    print(e)
    sys.exit(1)

oc_tarball = os.path.basename(urlsplit(args.client_loc).path)
inst_tarball = os.path.basename(urlsplit(args.installer_loc).path)

# client's work_dir exists, but we want our own version-relative subdir, so we'll alter work_dir as such.
# all FS ops should be constrained to here
ocp_version = os.path.join(ocp_version, oc_tarball.rstrip('.tar.gz').lstrip('openshift-client-').lstrip('mac').lstrip('linux').lstrip('-'))
print('setting up workspace')
print(f'creating work dir: {ocp_version}')
try:
    os.mkdir(ocp_version)
except FileExistsError:
    # we'll be overwriting the tars and bins here anyway
    print('nevermind, it already exists')
    pass


# if there's a metadata.json file present, there's like a cluster that hasn't been torn down yet.  don't
# orphan the cluster.
installer_work_dir = os.path.join(ocp_version, 'deploy')
print(f'creating installer sub-dir: {installer_work_dir}')
try:
    os.mkdir(installer_work_dir)
except FileExistsError:
    try:
        meta_file = os.path.join(installer_work_dir, "metadata.json")
        f = os.stat(meta_file)
        print(f'found cluster metadata file {meta_file}, which could mean a cluster is still deployed.'
              f'To avoid orphaning a cluster, first run openshift-install destroy cluster --dir={installer_work_dir}'
              f'then rerun this program.')
    except FileNotFoundError:
        pass

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


oc_tarball = os.path.abspath(os.path.join(ocp_version, oc_tarball))
print(f"Downloading file from {args.client_loc} => {oc_tarball}")
try:
    urlretrieve(url=args.client_loc, filename=oc_tarball, reporthook=show_progress)
except Exception as e:
    print(e)
    sys.exit(1)

inst_tarball = os.path.join(ocp_version, inst_tarball)
print(f"Downloading file from {args.installer_loc} => {inst_tarball}")
try:
    urlretrieve(url=args.installer_loc, filename=inst_tarball, reporthook=show_progress)
except Exception as e:
    print(e)
    sys.exit(1)

print("un-tarring openshift client")
with tarfile.open(oc_tarball) as tar:
    tar.extract(member='oc', path=ocp_version)
    oc = os.path.join(ocp_version, "oc")
    tar.close()
print("un-tarring openshift installer")
with tarfile.open(inst_tarball) as tar:
    tar.extract('openshift-install', path=ocp_version)
    openshift_install = os.path.join(ocp_version, "openshift-install")
    tar.close()

print(f"coping ignition config at {ignition_file} to {installer_work_dir}")
try:
    shutil.copy(ignition_file, installer_work_dir)
except Exception as e:
    print(e)

print("openshift client version:")
subprocess.run([f"{oc}", "version"])
print("openshift-install version:")
subprocess.run([f"{openshift_install}", "version"])

print("starting cluster creation")
try:
    subprocess.run([f"{openshift_install}", "create", "cluster", "--dir", f"{installer_work_dir}"], check=True)
except subprocess.CalledProcessError as e:
    print(e)
    sys.exit(1)
