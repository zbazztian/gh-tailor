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
from distutils import dir_util


LANGUAGES = [
  'java', 'javascript', 'python',
  'ruby', 'csharp', 'cpp', 'go'
]


def searchpath_append(searchpath, appendme):
  return (searchpath + ':' + appendme) if searchpath else appendme


def clear_dir(dirpath):
  for n in os.listdir(dirpath):
    f = join(dirpath, n)
    if isfile(f):
      os.unlink(f)
    elif isdir(f):
      shutil.rmtree(f)


def scriptdir():
  return dirname(__file__)


def templatedir():
  return join(scriptdir(), 'templates')


def tailor_template(
  outdir,
  lang, basename,
  outname,
):

  shutil.copytree(
    join(templatedir(), 'scripts'),
    outdir
  )

  shutil.copyfile(
    join(templatedir(), lang, 'settings.yml'),
    join(outdir, 'settings.yml')
  )

  testpack_template = join(templatedir(), lang, 'tests')
  testpack = join(outdir, 'tests')

  shutil.copytree(
    testpack_template,
    testpack
  )

  shutil.copytree(
    join(templatedir(), lang, 'integration_test_code'),
    join(outdir, 'integration_test_code')
  )

  pack_add_dep(
    testpack,
    outname,
    '*'
  )
  set_pack_name(
    testpack,
    '%s-tests' % outname,
  )

  str2file(
    join(outdir, 'integration-test'),
    file2str(join(outdir, 'integration-test')).format(
      outname=outname,
      language=lang,
    )
  )

  testqlref = lambda num: file2str(join(testpack_template, 'test_%s' % num, 'query.qlref')).strip()
  str2file(
    join(outdir, 'create'),
    file2str(join(outdir, 'create')).format(
      basename=basename,
      outname=outname,
      defaultsuite='codeql-suites/java-code-scanning.qls',
      querypath1=testqlref(1),
      querypath2=testqlref(2),
      securityfolder=lang_security_query_dir(lang),
    )
  )
  return


def lang_security_query_dir(lang):
  if lang == 'csharp':
    return 'Security Features'
  elif lang == 'ruby':
    return 'queries/security'
  elif lang in ['java', 'cpp', 'python', 'javascript', 'go']:
    return 'Security'
  else:
    error('Unsupported language "%s"!' % lang)


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


def is_pack(ppath):
  return isfile(qlpackyml(ppath))


def get_pack_lang(ppath):
  info = get_pack_info(ppath)
  lang = info.get('extractor', None)
  if lang is None:
    for l in LANGUAGES:
      if isdir(
        join(
          ppath,
          '.codeql',
          'libraries',
          'codeql',
          '%s-all' % l
        )
      ):
        lang = l
        break
  return lang


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


def parse_version(vstr):
  if vstr[0:2] in ('<=', '>='):
    idx = 2
  elif vstr[0:1] in '<>=':
    idx = 1
  else:
    idx = 0
  if vstr == '*' or VersionInfo.isvalid(vstr[idx:]):
    return vstr
  error(
    ('Invalid pack version: "%s". ' +
     'Only "*", match expressions or concrete versions ' +
     '(e.g. "1.0.0") are permitted!') % vstr
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


def hash_dir(dirpath):
  def hash_file(path, h):
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
          y.pop('version', None)
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
    hash_file(f, h)
    h.update(relpath(f, dirpath).encode('utf-8'))
  return h.hexdigest()


def hash_pack(ppath):
  return hash_dir(ppath)


def cmp_packs(ppath1, ppath2):
  return hash_pack(ppath1) == hash_pack(ppath2)


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
  deps = get_pack_value(ppath, 'dependencies', {})
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


  def autoversion(self, ppath, mode, fail):

    # set version and check uploadability
    packname = get_pack_name(ppath)
    packversion = get_pack_version(ppath)

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
        identical = cmp_packs(ppath, latestpeer)
        if identical:
          warning('This pack and its latest version in the registry are identical!')
          if fail:
            return 2
        else:
          info('This pack and its latest version in the registry differ!')

        newv = set_pack_version(
          ppath,
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
        return self.autoversion(ppath, 'new', fail)

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


  def create_inplace(self, ppath, tmppath):
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

    clear_dir(ppath)
    dir_util.copy_tree(tmppack, ppath)
    shutil.rmtree(tmppath)


  def create(self, ppath, outdir, tmppath):
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

    shutil.copytree(tmppack, outdir)
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


def set_ql_meta(qlfile, key, value):
  before, metadata, after = dissect_query(file2str(qlfile))
  modified = False
  for i, (k, v) in enumerate(metadata):
    if k == key:
      metadata[i] = (key, value)
      modified = True
      break
  if not modified:
    metadata.append((key, value))
  str2file(qlfile, assemble_query(before, metadata, after))
  info('Set metadata key "%s" to value "%s" in "%s".' % (key, value, qlfile))


def dissect_query(qlstr):
  PATTERN_METADATA = re.compile('^(.*?)/\*\*(.*?)\*/(.*)$', flags=re.DOTALL)
  PATTERN_METADATA_LINE_SEP = re.compile('^\s*\*?\s*@', flags=re.MULTILINE)
  PATTERN_LEADING_STAR = re.compile('^\s*\*?\s*', flags=re.MULTILINE)
  result = []

  # extract metadata section
  m = PATTERN_METADATA.match(qlstr)
  if not m:
    return result
  before, metadata_section, after = m.group(1), m.group(2), m.group(3)

  lines = PATTERN_METADATA_LINE_SEP.split(metadata_section)[1:]

  for l in lines:
    key, value = re.split('\s', l, maxsplit=1)
    value = PATTERN_LEADING_STAR.sub('', value)
    value = re.sub('\s+', ' ', value).strip()
    result.append((key, value))

  return before, result, after


def assemble_query(before, metadata, after):
  md_section = '/**'
  for k,v in metadata:
    md_section = md_section + ('\n * @%s %s' % (k, v))
  md_section = md_section + '\n */'
  return before + md_section + after


def is_qlfile(path):
  return isfile(path) and splitext(path)[1] == '.ql'


def is_qllfile(path):
  return isfile(path) and splitext(path)[1] == '.qll'


def has_import(qlfile, module):
  PATTERN_IMPORT = re.compile('^\s*import\s+(%s).*$' % module, flags=re.MULTILINE)
  m = PATTERN_IMPORT.search(file2str(qlfile))
  return True if m else False


def ql_import(qlfile, module):
  if not has_import(qlfile, module):
    with open(qlfile, 'a') as f:
      f.write('\nimport %s' % module)


def normalize_settings(settings):
  if type(settings) != dict:
    error('The settings must be presented as a dictionary!')
  for k in settings.keys():
    if type(k) != str:
      error('Settings keys must be strings! "%s" isn\'t.' % str(k))
    v = settings[k]
    if type(v) == str:
      settings[k] = [v]
    elif type(v) == list:
      for i in v:
        if type(i) != str:
          error('Settings values must either be strings or arrays of strings! "%s" is neither.' % str(v))
    else:
      error('Settings values must either be strings or arrays of strings! "%s" is neither.' % str(v))
  return settings


def hash_settings(settings):
  h = hashlib.sha1()
  for k in sorted(settings.keys()):
    h.update(k.encode('utf-8'))
    for i in sorted(settings[k]):
      h.update(i.encode('utf-8'))
  return h.hexdigest()


def customize(ppath, settingsfile, qlfiles, priority, modules):
  with open(settingsfile, 'r') as f:
    settings = normalize_settings(yaml.safe_load(f))

  shutil.copytree(
    join(dirname(__file__), 'ql', 'common', 'tailor'),
    join(ppath, 'tailor'),
    dirs_exist_ok=True
  )

  if modules is None:
    modules = ['tailor.Customizations']
    shutil.copytree(
      join(dirname(__file__), 'ql', get_pack_lang(ppath), 'tailor'),
      join(ppath, 'tailor'),
      dirs_exist_ok=True
    )

  modules.append('tailor.Settings')

  usmod = 'UserSettings_%s' % hash_settings(settings)

  str2file(
    join(ppath, 'tailor', '%s.qll' % usmod),
    generate_settings_ql(settings, priority, usmod, modules)
  )

  for qlf in qlfiles:
    ql_import(qlf, 'tailor.%s' % usmod)


def generate_settings_ql(settings, priority, name, modules):
  keyvalues = ' or'.join(
    '\n    k = "{k}" and v = [{values}\n    ]'.format(
      k=k,
      values=','.join('\n      "%s"' % v for v in vs)
    ) for k, vs in settings.items()
  )

  return textwrap.dedent('''
    {modules}

    class {classname} extends Tailor::Settings {{
      {classname}(){{ this = {priority} }}
      override predicate assign(string k, string v) {{{keyvalues}
      }}
    }}
  ''').format(
    modules='\n'.join('import %s' % m for m in modules),
    priority=priority,
    classname=name,
    keyvalues=keyvalues,
  )
