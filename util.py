import textwrap
import json
import pprint
import queue
import re
import hashlib
from os.path import isfile, join, relpath, islink, \
                    isdir, exists, basename, abspath, \
                    dirname, expanduser, splitext
import os
import sys
import shutil
import yaml
import threading
from semver import VersionInfo
import subprocess
from subprocess import CalledProcessError
import globber


def tailor_template(
  lang, base_name=None,
  out_name=None,
):

  def make_file_pattern():
    if lang == 'csharp':
      return 'Security Features/**/*.ql'
    elif lang == 'ruby':
      return 'queries/security/cwe-*/*.ql'
    elif lang in ['java', 'cpp']:
      return 'Security/CWE/CWE-*/*.ql'
    elif lang in ['python', 'javascript', 'go']:
      return 'Security/CWE-*/*.ql'

  return textwrap.dedent('''
    # base pack: the package you want to tailor
    # this may contain a version range
    base:
      name: "{base_name}"
      version: "{base_version}"

    instructions:
      - type: set-name
        value: "{out_name}"
      - type: set-version
        value: "{out_version}"
      - type: set-default-suite
        value: "{default_suite}"
      - type: append
        value: "import TailorCustomizations"
        dst: "{append_pattern}"
      - type: github-copy
        repository: "zbazztian/gh-tailor"
        revision: main
        src: "bases/java/tailor"
        dst: "/"
      - type: copy
        src: "**/*"
        dst: "/"
  ''').format(
    base_name=base_name or ('codeql/%s-queries' % lang),
    base_version='*',
    out_name=out_name or 'scope/packname',
    out_version='0.0.0',
    default_suite='codeql-suites/%s-code-scanning.qls' % lang,
    append_pattern=make_file_pattern()
  )


def tailor_customizations_qll(lang):
  return textwrap.dedent('''
    import tailor.Customizations

    class MyTailorSettings extends Settings::Provider {{
      MyTailorSettings(){{
        // The priority of these settings. If other settings
        // classes exist, the priority governs which one will
        // take precedence.
        this = 0
      }}

      override predicate assign(string key, string value) {{
        // INSERT YOUR SETTINGS HERE //
        // For example:
        key = "{lang}.local_sources" and value = "true"
        // or
        // key = "{lang}.lenient_taintflow" and value = "false"
      }}
    }}
  ''').format(
    lang=lang
  )


def hashstr(s):
  sha1 = hashlib.sha1()
  sha1.update(s.encode("utf-8"))
  return sha1.hexdigest()


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


def qlpackyml(ppath):
  return join(ppath, 'qlpack.yml')


def tailoryml(ppath):
  return join(ppath, 'tailor.yml')


def is_pack(ppath):
  return isfile(qlpackyml(ppath))


def is_tailorproject(ppath):
  return isfile(tailoryml(ppath))


def get_pack_info(ppath):
  with open(qlpackyml(ppath), 'r') as f:
    return yaml.safe_load(f)


def default_pack_lock_info():
  return {
    'dependencies': {},
    'compiled': False,
    'lockVersion': '1.0.0'
  }


def get_pack_lock_info(ppath, default=None):
  fpath = codeql_pack_lock_yml(ppath)
  if isfile(fpath):
    with open(fpath, 'r') as f:
      return yaml.safe_load(f)
  return default


def set_pack_lock_info(ppath, info):
  with open(codeql_pack_lock_yml(ppath), 'w') as f:
    yaml.dump(info, f)


def get_tailor_info(ppath):
  with open(tailoryml(ppath), 'r') as f:
    return yaml.safe_load(f)


def get_tailor_base(ppath):
  base = get_tailor_info(ppath)['base']
  name, version = base['name'], base.get('version', '*')
  if version[0:2] in ('<=', '>='):
    idx = 2
  elif version[0:1] in '<>=':
    idx = 1
  else:
    idx = 0
  if version == '*' or VersionInfo.isvalid(version[idx:]):
    return name, version
  error(
    ('Invalid tailor base pack version: "%s". ' +
     'Only "*", match expressions or concrete versions ' +
     '(e.g. "1.0.0") are permitted!') % version
  )


def rglob(dirpath, pattern, hidden=False):
  for f in listdir(dirpath, hidden=hidden):
    file2match = relpath(f, dirpath)
    if globber.match(pattern, file2match):
      yield f


def listdir(dirpath, hidden=False):
  dirs = queue.Queue()
  dirs.put(dirpath)
  while not dirs.empty():
    d = dirs.get()
    for f in sorted(os.listdir(d)):
      if (hidden == False and f[0] == '.'):
        continue
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


def pack_hash(ppath):
  return dir_hash(ppath)


def cmp_packs(ppath1, ppath2):
  return pack_hash(ppath1) == pack_hash(ppath2)


def set_pack_info(ppath, info):
  with open(qlpackyml(ppath), 'w') as f:
    yaml.dump(info, f)


def get_pack_value(ppath, key, default=None):
  return get_pack_info(ppath).get(key, default)


def set_pack_value(ppath, key, value):
  info = get_pack_info(ppath)
  info[key] = value
  set_pack_info(ppath, info)
  return value


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


def search_manifest_dir(path):
  current = abspath(path)
  while True:
    manifest = join(current, '.codeqlmanifest.json')
    if isfile(manifest):
      return current
    parent = abspath(join(current, os.pardir))
    if parent == abspath(current):
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
        raise CalledProcessError(cmd=commandstr, returncode=ret)


def exec_from_path_env(execname):
  e = shutil.which(execname)
  return Executable(e) if e else None


def codeql_dist_from_path_env():
  codeql = exec_from_path_env('codeql')
  if codeql:
    rec = Recorder()
    codeql(
      'version',
      '--format', 'json',
      combine_std_out_err=False,
      outconsumer=rec
    )
    return json.loads(''.join(rec.lines))['unpackedLocation']
  else:
    return None


def codeql_dist_from_gh_codeql():
  gh = exec_from_path_env('gh')
  if gh:
    try:
      rec = Recorder()
      gh(
        'codeql',
        'version',
        '--format', 'json',
        combine_std_out_err=False,
        outconsumer=rec
      )
      return json.loads(''.join(rec.lines))['unpackedLocation']
    except CalledProcessError:
      return None
  else:
    return None


def perform_instructions(tpath, ppath, tmpdir):
  ops = get_tailor_info(tpath).get('instructions', [])
  m = {
    'set-name': ins_set_name,
    'set-version': ins_set_version,
    'append': ins_append,
    'set-default-suite': ins_set_default_suite,
    'copy': ins_copy,
    'github-copy': ins_github_copy,
  }
  for n, op in enumerate(ops):
    t = op.get('type', None)
    op['description'] = op.get('description', str(n))
    info('Executing instruction "%s"...' % op['description'])
    if not t:
      error('Instruction is missing "type" key!')
    m[t](tpath, ppath, op, tmpdir)


def value_or_fail(o, k):
  if not k in o:
    error('Instruction is missing a "%s" key!' % k)
  return o[k]


def ins_set_name(tpath, ppath, o, tmpdir):
  set_pack_name(ppath, value_or_fail(o, 'value'))


def ins_set_version(tpath, ppath, o, tmpdir):
  set_pack_version(ppath, value_or_fail(o, 'value'))


def ins_append(tpath, ppath, o, tmpdir):
  value = value_or_fail(o, 'value')
  dst = value_or_fail(o, 'dst').strip('/')

  for fpath in rglob(ppath, dst):
    if isfile(fpath):
      with open(fpath, 'a') as f:
        f.write('\n%s' % value)


def ins_set_default_suite(tpath, ppath, o, tmpdir):
  value = value_or_fail(o, 'value').strip('/')
  suitepath = join(ppath, value)
  if not isfile(suitepath):
    error('"%s" does not exist!' % suitepath)
  set_pack_defaultsuite(ppath, value)


def ins_copy(tpath, ppath, o, tmpdir):
  src = value_or_fail(o, 'src').strip('/')
  dst = value_or_fail(o, 'dst').strip('/')
  if not copy2dir(tpath, src, ppath, dst):
    warning('No file was copied!')


def ins_github_copy(tpath, ppath, o, tmpdir):
  src = value_or_fail(o, 'src').strip('/')
  dst = value_or_fail(o, 'dst').strip('/')
  repo = value_or_fail(o, 'repository')
  revision = value_or_fail(o, 'revision')
  gh = exec_from_path_env('gh')
  checkout = join(tmpdir, 'github-copy-repo')
  gh(
    'repo', 'clone',
    repo,
    checkout,
  )
  git = exec_from_path_env('git')
  git(
    '--git-dir', join(checkout, '.git'),
    '--work-tree', checkout,
    'reset', '--hard', revision,
  )
  if not copy2dir(checkout, src, ppath, dst):
    warning('No file was copied!')


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


  def make_lockfile(
    self, ppath,
    qlpackyml_backup_file,
    match_cli=True, mode='merge-update'
  ):

    if mode == 'update':
      if isfile(codeql_pack_lock_yml(ppath)):
        os.remove(codeql_pack_lock_yml(ppath))

    li = get_pack_lock_info(ppath, default_pack_lock_info())
    pi = get_pack_info(ppath)

    lideps = li.get('dependencies') or {}
    pideps = pi.get('dependencies') or {}
    pi['dependencies'] = pideps

    for d, v in pideps.items():
      if d in lideps:
        pideps[d] = lideps[d]['version']
      else:
        resolvedv = self.resolve_pack_version(
          d,
          v,
          match_cli=match_cli
        )
        if resolvedv is None:
          error('Could not resolve %s@%s!' % (d, v))
        pideps[d] = resolvedv

    shutil.copyfile(qlpackyml(ppath), qlpackyml_backup_file)
    try:
      set_pack_info(ppath, pi)
      self.install(ppath, mode='update')
    finally:
      shutil.copyfile(qlpackyml_backup_file, qlpackyml(ppath))


  def autoversion(self, ppath, outdir, mode, fail):

    if abspath(ppath) != abspath(outdir):
      shutil.copytree(ppath, outdir, dirs_exist_ok=False)

    # set version and check uploadability
    packname = get_pack_name(outdir)
    packversion = get_pack_version(outdir)

    def success():
      info('Package does not exist yet, upload will succeed.')

    if mode == 'manual':

      if self.download_pack(
        packname,
        packversion,
        use_search_path=False,
        match_cli=False
      ):
        warning('Package %s@%s already exists!' % (packname, packversion))
        if fail:
          return 2
      else:
        success()

    elif mode == 'new':

      latestpeer = self.download_pack(
        packname,
        '*',
        use_search_path=False,
        match_cli=False
      )

      if latestpeer:
        identical = cmp_packs(outdir, latestpeer)
        if identical:
          warning('This pack and its latest version in the registry are identical!')
          if fail:
            return 2
        else:
          info('This pack and its latest version in the registry differ!')

        newv = set_pack_version(
          outdir,
          add_versions(
            get_pack_version(latestpeer),
            '0.0.1',
          )
        )
        info('Bumped version to "%s".' % newv)
      else:
        success()

    elif mode == 'new-on-collision':

      if self.download_pack(
        packname,
        packversion,
        use_search_path=False,
        match_cli=False
      ):
        info('Package %s@%s already exists.' % (packname, packversion))
        return self.autoversion(outdir, outdir, 'new', fail)

      else:
        success()

    else:
      error('Unknown mode "%s"!' % mode)

    return 0


  def install(self, ppath, mode='use-lock'):
    self(
      'pack', 'install',
      '--mode', mode,
      ppath
    )


  def create(self, ppath, output, tmppath):
    self(
      'pack', 'create',
      '--threads', '0',
      '--output', tmppath,
      '-vv',
      ppath
    )

    tmppack = join(
      tmppath,
      get_pack_name(ppath),
      get_pack_version(ppath),
    )

    if isdir(output):
      shutil.rmtree(output)
    shutil.move(tmppack, output)
    shutil.rmtree(tmppath)


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
      packcache = expanduser('~/.codeql/packages')
      for p in rglob(packcache, '**'):
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


  def download_pack(
    self,
    pname,
    matchstr,
    match_cli=True,
    use_search_path=True
  ):
    cli_version = self.get_version()

    info('Downloading %s@%s...' % (pname, matchstr))
    p = self.download_pack_impl(
      pname,
      matchstr,
      use_search_path=use_search_path
    )
    while True:
      if not(p and match_cli):
        return p
      pv = get_pack_version(p)
      if not match_version(pv, matchstr):
        return None
      if compare_version(
        get_pack_cli_version(p, cli_version),
        cli_version
      ) <= 0:
        return p

      pred = '<' + pv
      info('Previous pack was incompatible with this CLI, downloading %s@%s instead...' % (pname, pred))
      p = self.download_pack_impl(
        pname,
        pred,
        use_search_path=use_search_path
      )


  def resolve_pack_version(
    self, pname, matchstr,
    default=None, match_cli=True,
    use_search_path=True
  ):
    pack = self.download_pack(
      pname,
      matchstr,
      match_cli=match_cli,
      use_search_path=use_search_path
    )
    return get_pack_version(pack) if pack else default


  def download_pack_impl(self, packname, matchstr, use_search_path=True):
    not_found = set()

    def errgobbler(cmd, stream):
      while True:
        line = stream.readline()
        if line == '':
          break
        if re.match(
          ".*A fatal error occurred: '.*' not found in the registry .*",
          line,
        ):
          not_found.add(1)
        else:
          print(line, end='', flush=True)
      stream.close()

    try:
      rec = Recorder()
      search_path = self.make_search_path_args() if use_search_path else []
      self(
        'pack', 'download',
        '--format', 'json',
        *search_path,
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

    except CalledProcessError as e:
      if not_found:
        return None
      else:
        raise


def is_dist(directory):
  return (
    isfile(join(directory, 'codeql')) and
    isdir(join(directory, 'tools'))
  )


def copy2dir(srcroot, srcpattern, dstroot, dstdirpattern, hidden=False):
  executed = False
  dstdirs = list(rglob(dstroot, dstdirpattern, hidden=hidden))
  if dstdirpattern in ['', '.']:
    dstdirs.append(dstroot)
  for srcfile in rglob(srcroot, srcpattern, hidden=hidden):
    for dstdir in dstdirs:
      if not isdir(dstdir):
        error('"%s" is not a directory!' % dstdir)
      dstpath = join(dstdir, basename(srcfile))
      if isfile(srcfile):
        shutil.copyfile(srcfile, dstpath)
      else:
        shutil.copytree(srcfile, dstpath, dirs_exist_ok=True)
      executed = True
  return executed
