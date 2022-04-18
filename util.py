import re
import tempfile
import glob
import hashlib
import subprocess
from os.path import isfile, join, relpath, islink, isdir, exists, basename, abspath, dirname
import os
import tarfile
from datetime import datetime
import zipfile
import sys
import shutil

REQUEST_TIMEOUT = 100


def error(msg):
  sys.exit('ERROR: ' + msg)


def info(msg):
  print('INFO: ' + msg, flush=True)


def make_date():
  return datetime.today().strftime('%Y%m%d')


def parse_date(datestr):
  return datetime.strptime(datestr, '%Y-%m-%dT%H:%M:%SZ')


def write_str(filepath, string):
  with open(filepath, 'w') as f:
    f.write(string)


def hashstr(s):
  sha1 = hashlib.sha1()
  sha1.update(s.encode("utf-8"))
  return sha1.hexdigest()


def file2str(filepath):
  with open(filepath, 'r') as f:
    return f.read()


def str2file(filepath, string):
  with open(filepath, 'w') as f:
    f.write(string)


QLPACK_DEPENDENCIES_PATTERN = re.compile('^(dependencies:\s*)$', re.MULTILINE)

def add_dependency_to_pack(packdir, dependency):
  qlpackyml = join(packdir, 'qlpack.yml')
  str2file(qlpackyml, re.sub(QLPACK_DEPENDENCIES_PATTERN, '\g<1>\n  %s' % (dependency), file2str(qlpackyml)))


QLPACK_VERSION_PATTERN = re.compile('^(version:\s+)(\S+)(.*)$', re.MULTILINE)

def get_pack_version(packdir):
  vmatch = QLPACK_VERSION_PATTERN.search(file2str(join(packdir, 'qlpack.yml')))
  return vmatch.group(2) if vmatch else None


QLPACK_NAME_PATTERN = re.compile('^(name:\s+)(\S+)(.*)$', re.MULTILINE)

def get_pack_name(packdir):
  nmatch = QLPACK_NAME_PATTERN.search(file2str(join(packdir, 'qlpack.yml')))
  return nmatch.group(2) if nmatch else None


class Git:
  def __init__(self, checkout_dir):
    self.checkout_dir = checkout_dir

  def __call__(self, *args):
    command = ['git'] + list(args)
    try:
      return subprocess.run(
        command,
        capture_output=True,
        check=True,
        cwd=self.checkout_dir,
      ).stdout.decode().strip()
    except subprocess.CalledProcessError as cpe:
      print('Command "%s" failed with exit code %d' % (' '.join(command), cpe.returncode))
      print('stdout:')
      print(cpe.output.decode())
      print('stderr:')
      print(cpe.stderr.decode(), flush=True)
      raise

  def branch(self):
    return self('branch', '--show-current')


  def revision(self, branch):
    return self('rev-parse', branch)


def is_dist(directory):
  return (
    isfile(join(directory, 'codeql')) and
    isdir(join(directory, 'tools'))
  )


def extract_dist(dirorarchive):
  if isdir(dirorarchive):
    d = dirorarchive
  elif isfile(dirorarchive):
    if basename(dirorarchive) in ['codeql', 'codeql.exe'] and is_dist(dirname(dirorarchive)):
      d = dirname(dirorarchive)
    else:
      d = abspath('codeql-input-distribution')
      if exists(d):
        info('Deleting "%s"...' % (d))
        shutil.rmtree(d)
      if tarfile.is_tarfile(dirorarchive):
        info('Extracting .tar.gz archive "%s"...' % (dirorarchive))
        tar_xf(dirorarchive, d)
      elif zipfile.is_zipfile(dirorarchive):
        info('Extracting .zip archive "%s"...' % (dirorarchive))
        unzip(dirorarchive, d)
      else:
        error('"%s": unsupported input format!' % (dirorarchive))
      d = join(d, 'codeql')
  else:
    error('File "%s" does not exist!' % (dirorarchive))

  if not is_dist(d):
    error('"%s" is not a CodeQL distribution' % (dirorarchive))

  return d


def tar_czf(directory, outfile):
  with tarfile.open(outfile, 'w:gz') as f:
    f.add(directory, arcname='codeql')


def tar_xf(tarpath, outdir):
  with tarfile.open(tarpath, 'r:gz') as f:
    f.extractall(path=outdir)


def tar_member2str(tarpath, member):
  with tarfile.open(tarpath, 'r:gz') as f:
    try:
      with f.extractfile(member) as fo:
        return fo.read().decode('utf-8')
    except KeyError as ke:
      return ''


def zip_member2str(zippath, member):
  with zipfile.ZipFile(zippath, 'r') as z:
    try:
      with z.open(member) as f:
        return f.read().decode('utf-8')
    except KeyError as ke:
      return ''


def unzip(zippath, outdir):
  with zipfile.ZipFile(zippath, 'r') as z:
    z.extractall(path=outdir)


def get_customization_hash(path):
  info('Calculating customization hash of "%s"...' % (path))
  if isdir(path):
    hashfile = join(path, 'customization_hash')
    if isfile(hashfile):
      with open(hashfile, 'r') as f:
        return f.read().decode('utf-8')
  elif isfile(path):
    if zipfile.is_zipfile(path):
      return zip_member2str(path, 'codeql/customization_hash')
    if tarfile.is_tarfile(path):
      return tar_member2str(path, 'codeql/customization_hash')
  return ''


def sha1suml(filepath):
  sha1 = hashlib.sha1()
  sha1.update(os.readlink(filepath).encode('utf-8'))
  return sha1.hexdigest()


def sha1sumf(filepath):
  sha1 = hashlib.sha1()
  with open(filepath, 'rb') as f:
    while True:
      bs = f.read(4096)
      if bs == b'':
        break
      sha1.update(bs)
  return sha1.hexdigest()


def sha1sumd(directory):
  info('Calculating sha1sum of directory "%s"...' % (directory))
  def traverse():
    for dirpath, dirs, files in os.walk(directory):
      yield relpath(dirpath, directory)
      for f in files:
        fpath = join(dirpath, f)
        yield relpath(fpath, directory)
        yield sha1sum(fpath)
  return hashstr('\n'.join(traverse()))


def sha1sum(path):
  if islink(path):
    return sha1suml(path)
  elif isfile(path):
    return sha1sumf(path)
  elif isdir(path):
    return sha1sumd(path)
  else:
    raise Exception('Path "%s" does not exist!' % (path))


class ScriptUtils:

  def __init__(self, distdir):
    self.distdir = distdir


  def codeql(self, *args):
    command = [join(self.distdir, 'codeql')] + list(args)
    commandstr = ' '.join(command)
    self.info('Running "%s"' % (commandstr))
    outpipe = subprocess.PIPE
    with subprocess.Popen(
      command,
      bufsize = 1,
      universal_newlines=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      #cwd=checkout_dir,
    ) as proc:

      while True:
        line = proc.stdout.readline()
        if line == '':
          break
        print(line, end='', flush=True)

      if proc.wait() != 0:
        raise subprocess.CalledProcessError('Command "%s" failed with exit code %d' % (commandstr, proc.returncode), command)


  def run_tests(self, testdir):
    self.codeql(
      'test', 'run',
      testdir
    )


  def add_dependency_to_packs(self, packdirpattern, dependency):
    for packdir in [p for p in glob.iglob(join(self.distdir, packdirpattern), recursive=True)]:
      add_dependency_to_pack(packdir, dependency)


  def pack_name(self, packdir):
    return get_pack_name(packdir)


  def pack_version(self, packdir):
    return get_pack_version(packdir)


  def rebuild_packs(self, packpattern):
    executed = False
    for path in [p for p in glob.iglob(join(self.distdir, packpattern), recursive=True)]:
      if not (isdir(path) and isfile(join(path, 'qlpack.yml'))):
        self.error('"%s" is not a CodeQL Pack!' % (path))
      lockyml = join(path, 'codeql-pack.lock.yml')
      if isfile(lockyml):
        os.remove(lockyml)
      with tempfile.TemporaryDirectory(dir='.') as tempdir:
        executed = True
        tmppack = join(tempdir, 'tmppack')
        shutil.move(path, tmppack)
        self.codeql(
          'pack', 'create',
          '--threads', '0',
          '--output', join(path, '../../..'),
          tmppack
        )

    if not executed:
      self.error('rebuild_packs(codeql, "%s") had no effect!' % (packpattern))


  def error(self, msg):
    error(msg)


  def info(self, msg):
    info(msg)


  def makedirs(self, dstpath):
    os.makedirs(join(self.distdir, dstpath), exist_ok=True)


  def copy2dir(self, srcpattern, dstdirpattern):
    executed = False
    for srcfile in [s for s in glob.iglob(srcpattern, recursive=True)]:
      for dstdir in [d for d in glob.iglob(join(self.distdir, dstdirpattern), recursive=True)]:
        if not isdir(dstdir):
          self.error('"%s" is not a directory!' % (dstdir))
        dstpath = join(dstdir, basename(srcfile))
        if isfile(srcfile) or islink(srcfile):
          shutil.copyfile(srcfile, dstpath, follow_symlinks=False)
        else:
          shutil.copytree(srcfile, dstpath, symlinks=True, dirs_exist_ok=True)
        executed = True

    if not executed:
      self.error('copy2dir("%s", "%s") had no effect!' % (srcpattern, dstdirpattern))


  def append(self, srcfile, dstfilepattern):
    executed = False
    for dstfile in [d for d in glob.iglob(join(self.distdir, dstfilepattern), recursive=True)]:
      if not isfile(dstfile):
        self.error('"%s" is not a file!' % (dstfile))
      executed = True
      with open(dstfile, 'ab') as fdst:
        with open(srcfile, 'rb') as fsrc:
          fdst.write(fsrc.read())

    if not executed:
      self.error('append("%s", "%s") had no effect!' % (srcfile, dstfilepattern))
