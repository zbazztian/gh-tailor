import json
import re
import tempfile
import glob
import hashlib
import subprocess
from os.path import isfile, join, relpath, islink, \
                    isdir, exists, basename, abspath, \
                    dirname, expanduser, splitext
import os
import tarfile
from datetime import datetime
import zipfile
import sys
import shutil
import yaml
import threading
import semver


def import_module(ppath, module, filepattern):
  for fpath in glob.iglob(join(ppath, filepattern), recursive=True):
    if isfile(fpath) and splitext(fpath)[1] in ['.ql', '.qll']:
      with open(fpath, 'a') as f:
        f.write('import %s' % (module))


def add_versions(semver1, semver2):
  semver1 = semver.VersionInfo.parse(semver1)
  semver2 = semver.VersionInfo.parse(semver2)
  return str(
    semver.VersionInfo(
      semver1.major + semver2.major,
      semver1.minor + semver2.minor,
      semver1.patch + semver2.patch,
    )
  )

#def emptydir(dirpath):
#  if islink(dirpath) or isfile(dirpath):
#    os.remove(dirpath)
#  elif isdir(dirpath):
#    shutil.rmtree(dirpath)
#  os.makedirs(dirpath)


def error(msg):
  sys.exit('ERROR: ' + msg)


def info(msg):
  print('INFO: ' + msg, flush=True)


def file2str(filepath):
  with open(filepath, 'r') as f:
    return f.read()


def str2file(filepath, string):
  with open(filepath, 'w') as f:
    f.write(string)


def packyml(ppath):
  return join(ppath, 'qlpack.yml')


def is_pack(ppath):
  return isfile(packyml(ppath))


def get_pack_info(ppath):
  with open(packyml(ppath), 'r') as f:
    return yaml.safe_load(f)


def get_tailor_info(ppath):
  with open(join(ppath, 'tailor.yml'), 'r') as f:
    return yaml.safe_load(f)


def set_pack_info(ppath, info):
  with open(packyml(ppath), 'w') as f:
    yaml.dump(info, f)


def get_pack_value(ppath, key):
  return get_pack_info(ppath)[key]


def set_pack_value(ppath, key, value):
  info = get_pack_info(ppath)
  info[key] = value
  set_pack_info(ppath, info)


def get_pack_name(ppath):
  return get_pack_value(ppath, 'name')


def set_pack_name(ppath, name):
  set_pack_value(ppath, 'name', name)


def get_pack_version(ppath):
  return get_pack_value(ppath, 'version')


def set_pack_version(ppath, version):
  return set_pack_value(ppath, 'version', version)


def pack_add_dep(ppath, name, version):
  deps = get_pack_value(ppath, 'dependencies')
  deps[name] = version
  set_pack_value(ppath, 'dependencies', deps)


def print_to_stdout(cmd, stream):
  while True:
    line = stream.readline()
    if line == '':
      break
    print(line, end='', flush=True)
  stream.close()


def close_stdin(cmd, stream):
  stream.close()


class Recorder:
  def __init__(self):
    self.lines = []

  def __call__(self, cmd, stream):
    while True:
      line = stream.readline()
      if line == '':
        break
      self.lines.append(line)
    stream.close()


class Executable:
  def __init__(self, executable):
    self.executable = executable

  def __call__(self,
               *args,
               outconsumer=print_to_stdout,
               errconsumer=print_to_stdout,
               combine_std_out_err=True,
               inprovider=close_stdin,
               cwd='.',
               **kwargs):

    outpipe = subprocess.PIPE
    errpipe = subprocess.PIPE
    if combine_std_out_err:
      errpipe = subprocess.STDOUT
    inpipe = subprocess.PIPE
    command = [self.executable] + list(args)

    with subprocess.Popen(
      command,
      bufsize = 1,
      universal_newlines=True,
      stdout=outpipe,
      stderr=errpipe,
      stdin=inpipe,
      cwd=cwd,
    ) as proc:

      commandstr = ' '.join(command)
      tout = threading.Thread(target=outconsumer, args=(commandstr, proc.stdout))
      tout.start()
      terr = None
      if not combine_std_out_err:
        terr = threading.Thread(target=errconsumer, args=(commandstr, proc.stderr))
        terr.start()
      tin = threading.Thread(target=inprovider, args=(commandstr, proc.stdin))
      tin.start()

      ret = proc.wait()
      tout.join()
      tin.join()
      if terr:
        terr.join()
      if ret != 0:
        raise subprocess.CalledProcessError(cmd=commandstr, returncode=ret)




class CodeQL(Executable):

  def __init__(self, distdir, additional_packs=None, search_path=None):
    Executable.__init__(self, join(distdir, 'codeql'))
    self.additional_packs = additional_packs
    self.search_path = search_path


  def make_search_path_args(self):
    args = []
    if self.additional_packs:
      args.append('--additional-packs')
      args.append(self.additional_packs)
    if self.search_path:
      args.append('--search-path')
      args.append(self.search_path)
    return args


  def publish(self, ppath, ignore_if_exists=False):
    already_exists = set()

    def errgobbler(cmd, stream):
      while True:
        line = stream.readline()
        if line == '':
          break
        print(line, end='', flush=True)
        if re.match(
          ".*A fatal error occurred: Package '.*' already exists\..*",
          line,
        ):
          already_exists.add(1)
      stream.close()

    try:
      self(
        'pack', 'publish',
        '--threads', '0',
        '-v',
        *self.make_search_path_args(),
        ppath,
        combine_std_out_err=False,
        errconsumer=errgobbler,
      )
    except subprocess.CalledProcessError as e:
      if already_exists:
        msg = 'Package already exists with the given version!'
        if ignore_if_exists:
          info(msg)
        else:
          error(msg)
      else:
        raise e


  def list_packs(self):
    rec = Recorder()
    self(
      'resolve', 'qlpacks',
      '--format', 'json',
      *self.make_search_path_args(),
      combine_std_out_err=False,
      outconsumer=rec,
    )
    j = json.loads(''.join(rec.lines))

    for k in j:
      for v in j[k]:
        yield v

    packcache = expanduser('~/.codeql/packages/**')
    for p in glob.iglob(packcache, recursive=True):
      if is_pack(p):
        yield p


  def get_latest_pack(self, packname):
    latestp = None
    latestv = None
    for p in self.list_packs():
      if get_pack_name(p) == packname:
        v = semver.VersionInfo.parse(get_pack_version(p))
        if latestv is None or v.compare(latestv) > 0:
          latestv = v
          latestp = p
    return latestp


  def download_pack(self, packname):
    rec = Recorder()
    self(
      'pack', 'download',
      '--format', 'json',
      *self.make_search_path_args(),
      packname,
      combine_std_out_err=False,
      outconsumer=rec,
    )
    j = json.loads(''.join(rec.lines))
    return self.get_latest_pack(packname)


def is_dist(directory):
  return (
    isfile(join(directory, 'codeql')) and
    isdir(join(directory, 'tools'))
  )


def copy2dir(srcpattern, dstdirpattern):
  executed = False
  for srcfile in [s for s in glob.iglob(srcpattern, recursive=True)]:
    for dstdir in [d for d in glob.iglob(join(self.distdir, dstdirpattern), recursive=True)]:
      if not isdir(dstdir):
        error('"%s" is not a directory!' % (dstdir))
      dstpath = join(dstdir, basename(srcfile))
      if isfile(srcfile) or islink(srcfile):
        shutil.copyfile(srcfile, dstpath, follow_symlinks=False)
      else:
        shutil.copytree(srcfile, dstpath, symlinks=True, dirs_exist_ok=True)
      executed = True

  if not executed:
    error('copy2dir("%s", "%s") had no effect!' % (srcpattern, dstdirpattern))


def append(srcfile, dstfilepattern):
  executed = False
  for dstfile in [d for d in glob.iglob(join(self.distdir, dstfilepattern), recursive=True)]:
    if not isfile(dstfile):
      error('"%s" is not a file!' % (dstfile))
    executed = True
    with open(dstfile, 'ab') as fdst:
      with open(srcfile, 'rb') as fsrc:
        fdst.write(fsrc.read())

  if not executed:
    error('append("%s", "%s") had no effect!' % (srcfile, dstfilepattern))
