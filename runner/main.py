import argparse
import os
import shutil
import tarfile
import time
from os import path
from subprocess import run
from urllib.error import ContentTooShortError
from urllib.request import urlretrieve

import progressbar
import semver
import yaml

import settings as s


def set_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', type=str, dest='version', default='latest', help='cluster version to deploy')
    parser.add_argument('-d', '--dir', type=str, dest='work_dir', default=s.CLUSTER_WORKDIR,
                        help='optional prefix path for cluster dir')
    parser.add_argument('--region', type=str, dest='region', default='us-east-2', help='AWS region')
    parser.add_argument('--install-config', type=str, dest='install_config',
                        help='path to a fully defined ignition config', required=True)
    return parser.parse_args()


def parse_args_install_config(args=argparse.Namespace()):
    return args.install_config


def prom_top_command(kubeconfig='', version=''):
    cmd = []
    args = [f'--postgres', '--ocp-version', f'{str(version)}', '--range', f'{str(s.MAX_WAIT_SECONDS)}s']
    if s.PROM_TOP_SOURCE == 1:
        cmd = [f'docker', 'run', '--network', 'build_postgres', '--rm', '-v', f'{kubeconfig}:/root/.kube/config',
               '--env-file', f'{s.DOTENV}', '-e', 'PGHOST=postgres', 'quay.io/jcope/prom-top:latest']
    elif s.PROM_TOP_SOURCE == 2:
        cmd = ['prom-top']
    return cmd + args


def parse_args_version(args=argparse.Namespace()):
    v = args.version
    if v == '':
        v = 'latest'
    try:
        if v != 'latest':
            semver.VersionInfo.parse(v)
    except ValueError as e:
        ValueError(f'Expected semver format or "latest", got {v}: {e}')
    return v


def parse_args_region(args=argparse.Namespace()):
    return args.region


def parse_install_config(args=argparse.Namespace()):
    install_config = path.realpath(args.install_config)
    try:
        os.stat(install_config)
    except FileNotFoundError as e:
        print(e)
        quit(1)
    return install_config


def versioned_bin(ocp_binary, version):
    if version == 'latest':
        return f'{ocp_binary}-{s.HOST_PLATFORM}.tar.gz'
    else:
        return f'{ocp_binary}-{s.HOST_PLATFORM}-{version}.tar.gz'


def source(ocp_binary, version):
    return f'https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{version}/{versioned_bin(ocp_binary, version)}'


def mk_work_dir(version):
    d = path.join(s.CLUSTER_WORKDIR, version)
    try:
        os.mkdir(d)
    except FileExistsError:
        # we'll be overwriting the tars and bins here anyway.
        pass
    return d


def live_cluster(deploy_dir):
    meta_file = os.path.join(deploy_dir, 'metadata.json')
    try:
        os.stat(meta_file)
        return True
    except FileNotFoundError:
        pass
    return False


def mk_deploy_dir(parent):
    d = os.path.join(parent, 'deploy')
    try:
        os.mkdir(d)
    except FileExistsError as e:
        pass
        if live_cluster(d):
            pass
            raise FileExistsError(f'{e}\n',
                                  f'found cluster {d}/metadata.json file, which could mean a cluster is still deployed.\n'
                                  f'To avoid orphaning a cluster, first run openshift-install destroy cluster --dir={d}\n'
                                  f'then rerun this program.\n')
        else:
            pass
    return d


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


def fetch_binary(src, dst, name):
    tarball = os.path.join(dst, os.path.basename(src))
    target = os.path.join(dst, f'{name}')
    try:
        os.stat(target)  # short circuit to avoid redownloading tarballs
    except FileNotFoundError:
        pass
    else:
        return target

    try:
        urlretrieve(url=src, filename=tarball, reporthook=show_progress)
    except ContentTooShortError as e:
        raise ContentTooShortError(f"failed to download {src}: {e}")

    with tarfile.open(tarball) as tar:
        tar.extract(member=name, path=dst)
        tar.close()
    return target


def fetch_oc_bin(src, dst):
    try:
        return fetch_binary(src, dst, 'oc')
    except Exception as e:
        raise Exception(f"failed to download openshift-client: {e}")


def fetch_openshift_install_bin(src, dst):
    try:
        return fetch_binary(src, dst, 'openshift-install')
    except Exception as e:
        raise Exception(f"failed to download openshift-install: {e}")


def prepare_install_config(src, dst, version, region):
    try:
        shutil.copy(src=src, dst=dst)
    except shutil.SameFileError as e:
        pass
    cfg = dst
    if path.isdir(cfg):
        cfg = path.join(dst, path.basename(src))
    try:
        with open(cfg, mode='r') as file:
            installer_data = yaml.load(file, Loader=yaml.FullLoader)

        installer_data['metadata']['name'] = 'caliper-ocp-' + version
        installer_data['platform']["aws"]['region'] = region

        with open(cfg, mode='w') as file:
            yaml.dump(installer_data, file, yaml.Dumper)
    finally:
        file.close()

    return cfg


def get_cluster_passwd(deploy_dir):
    pw_file = os.path.realpath(os.path.join(deploy_dir, 'auth/kubeadmin-password'))
    print(f"getting password file: {pw_file}")
    try:
        with open(pw_file) as file:
            password = file.read()
            file.close()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"password file {pw_file} not found: {e}")
    return password


oc = ''


def main():
    args = set_args()
    version = parse_args_version(args)
    region = parse_args_region(args)
    install_config = parse_install_config(args)
    installer_link = source('openshift-install', version)
    client_link = source('openshift-client', version)

    work_dir = mk_work_dir(version)

    print(
        'Deployment Params:\n'
        f'\tVersion: {version}\n'
        f'\tClient: {client_link}\n'
        f'\tInstaller: {installer_link}\n'
        f'\tWorking Dir: {work_dir}\n'
    )
    time.sleep(3)

    try:
        deploy_dir = mk_deploy_dir(work_dir)
    except FileExistsError as e:
        raise e
    prepare_install_config(src=install_config, dst=deploy_dir, version=version, region=region)

    global oc
    try:
        oc = fetch_oc_bin(client_link, work_dir)
        openshift_install = fetch_openshift_install_bin(installer_link, work_dir)
    except Exception as e:
        print(e)
        quit(1)

    print('starting cluster creation')
    output = run([openshift_install, 'create', 'cluster', '--dir', f'{deploy_dir}'], check=False, text=True)
    if output.returncode > 0:
        print(f'error creating cluster:\ncmd: {output.args}\nerr:{output.stderr}')
        quit(1)

    time.sleep(s.MAX_WAIT_SECONDS)

    password = ''
    try:
        password = get_cluster_passwd(deploy_dir)
    except FileNotFoundError as e:
        print(f"failed to get cluster password: {e}")
        quit(1)

    kubeconfig = path.join(deploy_dir, 'auth/kubeconfig')
    os.putenv('KUBECONFIG', kubeconfig)
    output = run([oc, 'login', '-u', 'kubeadmin', '-p', password, '--kubeconfig', kubeconfig], check=False, text=True)
    if output.returncode > 0:
        print(f'failed to login to cluster')
        quit(0)

    prom_top = prom_top_command(kubeconfig, version)
    if len(prom_top) == 0:
        print('prom-top image or binary not found')
        quit(1)
    output = run(prom_top, text=True, check=False)
    if output.returncode > 0:
        print('prom-top failed')
        quit(1)

    output = run([openshift_install, 'destroy', 'cluster', '--dir', deploy_dir], check=False, text=True)
    if output.returncode > 0:
        print(f'cluster teardown failed: {output.stderr}')
        quit(1)
    print('cluster destroyed, job complete')

    quit(0)


if __name__ == '__main__':
    main()
