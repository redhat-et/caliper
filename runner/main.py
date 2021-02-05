import argparse
import os
import sys
import progressbar
import gzip
import tarfile
from urllib.request import urlretrieve
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--dir', type=str, dest='work_dir', help='optional prefix path for temp dir', required=True)
parser.add_argument('-c', '--client', type=str, dest='client_loc', help='URL location of OCP client', required=True)
parser.add_argument('-i', '--installer', type=str, dest='installer_loc', help='URL location of OCP installer', required=True)
args = parser.parse_args()

work_dir = os.path.join(args.work_dir)

try:
    os.stat(work_dir)
except FileNotFoundError as e:
        print(e)
        sys.exit(1)

c_file = os.path.basename(urlsplit(args.client_loc).path)
i_file = os.path.basename(urlsplit(args.installer_loc).path)

pbar = None


def show_progress(block_num, block_size, total_size):
    global pbar
    if pbar is None:
        pbar = progressbar.ProgressBar(maxval=total_size, term_width=120, widgets=[progressbar.widgets.ETA(), progressbar.widgets.Bar()]).start()

    downloaded = block_num * block_size
    if downloaded < total_size:
        pbar.update(downloaded)
    else:
        pbar.finish()
        pbar = None


c_file_loc = os.path.join(work_dir, c_file)
print(f"Downloading file from {args.client_loc} => {c_file_loc}")
try:
    urlretrieve(url=args.client_loc, filename=c_file_loc, reporthook=show_progress)
except Exception as e:
    print(e)
    sys.exit(1)

i_file_loc = os.path.join(work_dir, i_file)
print(f"Downloading file from {args.installer_loc} => {i_file_loc}")
try:
    urlretrieve(url=args.installer_loc, filename=i_file_loc, reporthook=show_progress)
except Exception as e:
    print(e)
    sys.exit(1)


with tarfile.open(c_file_loc) as tar:
    tar.extract(member='oc', path=work_dir)
    tar.close()
with tarfile.open(i_file_loc) as tar:
    tar.extract('openshift-install', path=work_dir)
    tar.close()
