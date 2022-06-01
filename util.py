import json
import pprint
import queue
import re
from glob import iglob
import hashlib
import subprocess
import itertools
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
from semver import VersionInfo


def hashstr(s):
  sha1 = hashlib.sha1()
  sha1.update(s.encode("utf-8"))
  return sha1.hexdigest()


def searchpath_prepend(searchpath, prependme):
  return (prependme + ':' + searchpath) if searchpath else prependme


def import_module(ppath, module, filepattern):
  for fpath in iglob(join(ppath, filepattern), recursive=True):
    if isfile(fpath) and splitext(fpath)[1] in ['.ql', '.qll']:
      with open(fpath, 'a') as f:
        f.write('\nimport %s' % (module))


def add_versions(v1str, v2str):
  semver1 = VersionInfo.parse(v1str)
  semver2 = VersionInfo.parse(v2str)
  return str(
    VersionInfo(
      semver1.major + semver2.major,
      semver1.minor + semver2.minor,
      semver1.patch + semver2.patch,
    )
  )


def match_version(versionstr, matchstr):
  def adjust_matchstr(matchstr):
    if matchstr == '*':
      return '>=0.0.0'
    elif matchstr[0].isdigit():
      return '==' + matchstr
    elif matchstr[0] == '=' and matchstr[1].isdigit():
      return '=' + matchstr
    else:
      return matchstr
  return VersionInfo.parse(versionstr).match(adjust_matchstr(matchstr))


def compare_version(v1, v2):
  return VersionInfo.parse(v1).compare(VersionInfo.parse(v2))


def error(msg):
  sys.exit('ERROR: ' + msg)


def info(msg):
  print('INFO: ' + msg, flush=True)


def warning(msg):
  print('WARNING: ' + msg, flush=True)


def file2str(filepath):
  with open(filepath, 'r') as f:
    return f.read()


def str2file(filepath, string):
  with open(filepath, 'w') as f:
    f.write(string)


def codeql_pack_lock_yml(ppath):
  return join(ppath, 'codeql-pack.lock.yml')


def packyml(ppath):
  return join(ppath, 'qlpack.yml')


def tailoryml(ppath):
  return join(ppath, 'tailor.yml')


def is_pack(ppath):
  return isfile(packyml(ppath))


def is_tailorproject(ppath):
  return isfile(tailoryml(ppath))


def get_pack_info(ppath):
  with open(packyml(ppath), 'r') as f:
    return yaml.safe_load(f)


def get_pack_lock_info(ppath):
  with open(codeql_pack_lock_yml(ppath), 'r') as f:
    return yaml.safe_load(f)


def get_tailor_info(ppath):
  with open(tailoryml(ppath), 'r') as f:
    return yaml.safe_load(f)


def get_tailor_in_or_out_pack(ppath, inorout):
  packs = list((get_tailor_info(ppath).get(inorout) or {}).items())
  kind = '%spack' % (inorout)
  if len(packs) == 0:
    error('No %s specified!' % (kind))
  if len(packs) > 1:
    error('Only one %s is allowed!' % (kind))
  return packs[0]


def get_tailor_in(ppath):
  name, version = get_tailor_in_or_out_pack(ppath, 'in')
  if version[0:2] in ('<=', '>='):
    idx = 2
  elif version[0:1] in '<>=':
    idx = 1
  else:
    idx = 0
  if version == '*' or VersionInfo.isvalid(version[idx:]):
    return name, version
  error(
    ('Invalid tailor inpack version: "%s". ' +
     'Only "*", match expressions or concrete versions ' +
     '(e.g. "1.0.0") are permitted!') % (version)
  )


def get_tailor_cli_compat(ppath):
  return get_tailor_info(ppath).get('cliCompatibility', True)


def get_tailor_out(ppath):
  name, version = get_tailor_in_or_out_pack(ppath, 'out')
  if version == '*' or VersionInfo.isvalid(version):
    return name, version
  error(
    ('Invalid tailor outpack version: "%s". ' +
      'Only "*" or concrete versions ' +
      '(e.g. "1.0.0") are permitted!') % (version)
  )


def get_tailor_deps(ppath):
  return get_tailor_info(ppath).get('dependencies') or {}


def get_tailor_imports(ppath):
  return get_tailor_info(ppath).get('imports') or []


def get_tailor_default_suite(ppath):
  return get_tailor_info(ppath).get('defaultSuiteFile', None)


def sync_qlfiles(srcdir, dstdir, clobber=False):
  for f in qlfiles(srcdir):
    targetf = join(dstdir, relpath(f, srcdir))
    os.makedirs(dirname(targetf), exist_ok=True)
    if exists(targetf) and not clobber:
      error('File "%s" overwrites file "%s"!' % (f, targetf))
    shutil.copy(f, targetf)


def qlfiles(directory):
  for ext in ['ql', 'qll']:
    for f in iglob(join(directory, '**/*' + ext), recursive=True):
      if isfile(f):
        yield f


def listdir(dirpath):
  dirs = queue.Queue()
  dirs.put(dirpath)
  while not dirs.empty():
    d = dirs.get()
    for f in sorted(os.listdir(d)):
      absf = join(d, f)
      if isdir(absf):
        dirs.put(absf)
      yield absf


def dir_hash(dirpath):
  def file_hash(path, h):
    if islink(path):
      h.update(b'link')
      h.update(
        os.readlink(path).encode('utf-8')
      )
    elif isfile(path):
      h.update(b'file')

      if basename(path) == 'qlpack.yml':
        with open(path, 'r') as f:
          y = yaml.safe_load(f) or {}
          y.get('buildMetadata', {}) \
           .pop('creationTime', None)
          h.update(
            pprint.pformat(
              y,
              sort_dicts=True,
              indent=1
            ).encode('utf-8')
          )
      else:
        with open(path, 'rb') as f:
          while True:
            bs = f.read(4096)
            if bs == b'':
              break
            h.update(bs)
    elif isdir(path):
      h.update(b'directory')
    else:
      error('Unexpected file type for "%s"!' % (path))

  h = hashlib.sha1()
  for f in listdir(dirpath):
    file_hash(f, h)
    h.update(relpath(f, dirpath).encode('utf-8'))
  return h.hexdigest()


def subpack_path(ppath):
  return join(
    ppath,
    '.codeql',
    'pack',
    get_pack_name(ppath),
    get_pack_version(ppath)
  )


def subpack(ppath):
  res = subpack_path(ppath)
  if isdir(res):
    return res
  return None


def pack_hash(ppath):
  sp = subpack(ppath)
  if sp:
    return dir_hash(sp)
  return dir_hash(ppath)


def cmp_packs(ppath1, ppath2):
  return pack_hash(ppath1) == pack_hash(ppath2)


def set_pack_info(ppath, info):
  with open(packyml(ppath), 'w') as f:
    yaml.dump(info, f)


def get_pack_value(ppath, key, default=None):
  return get_pack_info(ppath).get(key, default)


def set_pack_value(ppath, key, value):
  info = get_pack_info(ppath)
  info[key] = value
  set_pack_info(ppath, info)


def get_pack_name(ppath):
  return get_pack_value(ppath, 'name')


def set_pack_name(ppath, name):
  set_pack_value(ppath, 'name', name)


def get_pack_version(ppath):
  return get_pack_value(ppath, 'version', '0.0.0')


def get_pack_cli_version(ppath, default='0.0.0'):
  return get_pack_info(ppath) \
           .get('buildMetadata', {}) \
           .get('cliVersion', default)


def set_pack_version(ppath, version):
  return set_pack_value(ppath, 'version', version)


def set_pack_defaultsuite(ppath, value):
  set_pack_value(ppath, 'defaultSuiteFile', value)


def pack_add_dep(ppath, name, version):
  deps = get_pack_value(ppath, 'dependencies')
  deps[name] = version
  set_pack_value(ppath, 'dependencies', deps)


def push_lock_versions(ppath):
  cply = codeql_pack_lock_yml(ppath)
  if isfile(cply):
    lock_info = get_pack_lock_info(ppath)
    for name, properties in (lock_info.get('dependencies') or {}).items():
      pack_add_dep(ppath, name, properties['version'])
    os.remove(cply)


def clean_pack(ppath):
  dotcodeqldir = join(ppath, '.codeql')
  if isdir(dotcodeqldir):
    shutil.rmtree(dotcodeqldir)


def search_manifest(path):
  current = path
  while True:
    res = join(current, '.codeqlmanifest.yml')
    if isfile(res):
      return res
    parent = abspath(join(current, os.pardir))
    if parent == abspath(current)
      return None
    current = parent


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


def codeql_dist_from_path_env():
  codeqlexec = shutil.which('codeql')
  if codeqlexec:
    rec = Recorder()
    Executable(codeqlexec)(
      'version',
      '--format', 'json',
      combine_std_out_err=False,
      outconsumer=rec
    )
    return json.loads(''.join(rec.lines))['unpackedLocation']
  else:
    return None


def codeql_dist_from_gh_codeql():
  ghexec = shutil.which('gh')
  if ghexec:
    rec = Recorder()
    Executable(ghexec)(
      'codeql',
      'version',
      '--format', 'json',
      combine_std_out_err=False,
      outconsumer=rec
    )
    return json.loads(''.join(rec.lines))['unpackedLocation']
  else:
    return None


class CodeQL(Executable):

  def __init__(self, distdir, additional_packs=None, search_path=None):
    Executable.__init__(self, join(distdir, 'codeql'))
    self.distdir = distdir
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


  def bump_version(self, ppath):
    new_version = add_versions(
      get_pack_version(ppath),
      '0.0.1',
    )
    self.set_version(ppath, new_version)
    return new_version


  def set_version(self, ppath, version):
    old_version = get_pack_version(ppath)
    new_version = version

    if old_version == new_version:
      return old_version

    old_sp = subpack(ppath)
    if old_sp:
      set_pack_version(old_sp, new_version)

    set_pack_version(
      ppath,
      new_version
    )

    new_sp = subpack_path(ppath)
    if isdir(new_sp):
      shutil.rmtree(new_sp)

    if old_sp:
      shutil.move(old_sp, new_sp)

    return new_version


  def install(self, ppath):
    self(
      'pack', 'install',
      '--mode', 'use-lock',
      ppath
    )


  def create(self, ppath):
    self(
      'pack', 'create',
      '--threads', '0',
      '-vv',
      ppath
    )


  def list_packs(self, use_search_path=True, use_pack_cache=True):
    if use_search_path:
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

    if use_pack_cache:
      packcache = expanduser('~/.codeql/packages/**')
      for p in iglob(packcache, recursive=True):
        if is_pack(p):
          yield p


  def get_pack(self, packname, matchstr, use_search_path=True, use_pack_cache=True):
    latestp = None
    latestv = '0.0.0'
    for p in self.list_packs(
      use_search_path=use_search_path,
      use_pack_cache=use_pack_cache,
    ):
      if get_pack_name(p) == packname:
        v = get_pack_version(p)
        if match_version(v, matchstr) and compare_version(v, latestv) >= 0:
          latestv = v
          latestp = p
    return latestp


  def get_version(self):
    rec = Recorder()
    self(
      'version',
      '--format', 'json',
      combine_std_out_err=False,
      outconsumer=rec,
    )
    return json.loads(''.join(rec.lines))['version']


  def download_pack(self, pname, matchstr, match_cli=True):
    cli_version = self.get_version()
    p = self.download_pack_impl(pname, matchstr)
    while True:
      if not(p and match_cli):
        return p
      pv = get_pack_version(p)
      if not match_version(pv, matchstr):
        return None
      if get_pack_cli_version(p, cli_version) == cli_version:
        return p
      p = self.download_pack_impl(pname, '<' + pv)


  def resolve_pack_version(self, pname, matchstr, default=None, match_cli=True):
    pack = self.download_pack(
      pname,
      matchstr,
      match_cli=match_cli
    )
    return get_pack_version(pack) if pack else default


  def download_pack_impl(self, packname, matchstr):
    not_found = set()

    def errgobbler(cmd, stream):
      while True:
        line = stream.readline()
        if line == '':
          break
        print(line, end='', flush=True)
        if re.match(
          ".*A fatal error occurred: '.*' not found in the registry .*",
          line,
        ):
          not_found.add(1)
      stream.close()

    try:
      rec = Recorder()
      self(
        'pack', 'download',
        '--format', 'json',
        *self.make_search_path_args(),
        packname + '@' + matchstr,
        combine_std_out_err=False,
        errconsumer=errgobbler,
        outconsumer=rec
      )
      j = json.loads(''.join(rec.lines))
      latestv = None
      for p in j.get('packs', {}):
        pv = p['version']
        if not(
          p['name'] == packname and \
          match_version(pv, matchstr)
        ):
          return None
        if latestv is None or compare_version(pv, latestv) >= 0:
          latestv = pv

      # TODO: Remove this once 'codeql download' always returns json
      # data with information about the downloaded packages
      # for now this is necessary, unfortunately.
      if latestv:
        return self.get_pack(
          packname,
          latestv,
          use_search_path=True,
          use_pack_cache=True
        )
      else:
        return self.get_pack(
          packname,
          matchstr,
          use_search_path=True,
          use_pack_cache=False
        )

    except subprocess.CalledProcessError as e:
      if not_found:
        return None
      else:
        raise


def is_dist(directory):
  return (
    isfile(join(directory, 'codeql')) and
    isdir(join(directory, 'tools'))
  )


def copy2dir(srcpattern, dstdirpattern):
  executed = False
  for srcfile in [s for s in iglob(srcpattern, recursive=True)]:
    for dstdir in [d for d in iglob(join(self.distdir, dstdirpattern), recursive=True)]:
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
  for dstfile in [d for d in iglob(join(self.distdir, dstfilepattern), recursive=True)]:
    if not isfile(dstfile):
      error('"%s" is not a file!' % (dstfile))
    executed = True
    with open(dstfile, 'ab') as fdst:
      with open(srcfile, 'rb') as fsrc:
        fdst.write(fsrc.read())

  if not executed:
    error('append("%s", "%s") had no effect!' % (srcfile, dstfilepattern))
