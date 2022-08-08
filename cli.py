import argparse
import util
from util import error, warning, info
import os
from os.path import dirname, isfile, \
                    join, isdir, \
                    exists, abspath, \
                    splitext
import sys
import tempfile
import shutil
import tarfile
import atexit
from subprocess import CalledProcessError
import cliver


def get_codeql(args, location):
  info('Detecting CodeQL distribution...')
  distdir = args.dist or \
            util.codeql_dist_from_path_env() or \
            util.codeql_dist_from_gh_codeql()
  if not distdir:
    error(
      "Please provide the --dist argument or make sure the 'codeql' " +
      "executable can be found via the PATH environment variable or " +
      "install the 'codeql' extension for 'gh' (https://github.com/github/gh-codeql)."
    )

  s = ':'.join(
    filter(
      lambda p: p is not None,
      [util.search_manifest_dir(location), args.search_path]
    )
  )

  codeql = util.CodeQL(
    distdir,
    additional_packs=args.additional_packs,
    search_path=s,
  )
  info(f'CodeQL distribution detected at "{codeql.distdir}".')
  return codeql


def init(args):
  lang = args.language
  if lang is None:
    for l in util.LANGUAGES:
      if args.basename in [f'codeql/{l}-{n}' for n in ['queries', 'all']]:
        lang = l
        break
  if lang is None:
    warning(
      'Could not auto-detect language of resulting pack. ' +
      'Defaulting to "java". Use --language to force the language.'
    )
    lang = 'java'

  util.tailor_template(
    args.outdir,
    lang,
    args.basename,
    args.outname
  )


def download(args):
  codeql = get_codeql(
    args,
    args.outdir if args.outdir else '.'
  )

  pack = codeql.download_pack(
    args.name,
    args.version,
    match_cli=True
  )

  if pack:
    info('Successfully downloaded pack!')
  else:
    error(f'Pack "{args.name}@{args.version}" not found in registry!')

  if args.outdir:
    shutil.copytree(
      pack,
      args.outdir,
    )


def set_pack_meta(args):
  if args.name:
    util.set_pack_name(args.pack, args.name)
  if args.version:
    util.set_pack_version(args.pack, args.version)
  if args.default_suite:
    util.set_pack_defaultsuite(args.pack, args.default_suite)


def set_ql_meta(args):
  if not (args.delete or args.meta):
    error('You must set one of --meta or --delete!')

  for qlf in args.qlfiles:
    for k, v in args.meta:
      util.set_ql_meta(qlf, k, v)
    for k in args.delete:
      util.delete_ql_meta(qlf, k)


def ql_import(args):
  for qlf in args.qlfiles:
    for m in args.modules:
      util.ql_import(qlf, m)


def customize(args):
  util.customize(
    args.pack,
    args.settingsfile,
    args.qlfiles,
    args.priority,
    args.modules
  )


def install(args):
  codeql = get_codeql(args, args.pack)

  info('Updating lock file...')
  codeql.make_lockfile(
    args.pack,
    join(tempdir, 'qlpack.yml.bak'),
    match_cli=True,
    mode=args.mode
  )

  codeql.install(args.pack)


def create(args):
  if not(args.outdir or args.in_place):
    error('No output directory given!')

  codeql = get_codeql(args, args.pack)
  tmppackdir = join(tempdir, 'outpack')

  if args.in_place:
    codeql.create_inplace(args.pack, tmppackdir)
  else:
    codeql.create(args.pack, args.outdir, tmppackdir)


def test(args):
  for tp in args.testpacks:
    codeql = get_codeql(args, tp)
    codeql(
      'test', 'run',
      '--show-extractor-output',
      '--additional-packs', args.pack,
      '--additional-packs', join(args.pack, '.codeql', 'libraries'),
      tp
    )


def autoversion(args):
  codeql = get_codeql(args, args.pack)
  sys.exit(codeql.autoversion(args.pack, args.mode, args.fail))


def publish(args):
  codeql = get_codeql(args, args.pack)
  out = join(tempdir, 'pack.tgz')

  with tarfile.open(out, 'w:gz') as tarf:
    for name in os.listdir(args.pack):
      tarf.add(join(args.pack, name), arcname=name, recursive=True)

  codeql(
    'pack', 'publish',
    '-vv',
    '--file', out
  )


def make_min_db(args):
  codeql = get_codeql(args, args.db)
  codedir = join(tempdir, 'mindb')
  shutil.copytree(
    join(
      util.templatedir(),
      args.language,
      'mindb'
    ),
    codedir,
  )

  codeql(
    'database', 'create',
    '--threads', '0',
    '--language', args.language,
    '--source-root', codedir,
    '--command', join(codedir, 'compile'),
    args.db,
  )


def actions_cli_version(args):
  print(
    cliver.get_latest_version(
      args.repository,
      cliver.ensure_release(
        args.repository,
        args.release,
      )
    )
  )


def mustbefile(path):
  if not isfile(path):
    error(f'"{path}" is not a file!')
  return path


def mustbeqlorqllfile(path):
  if not (util.is_qlfile(path) or util.is_qllfile(path)):
    error(f'"{path}" is not a CodeQL query or library file!')
  return path


def mustbeqlfile(path):
  if not util.is_qlfile(path):
    error(f'"{path}" is not a CodeQL query file!')
  return path


def mustnotexist(path):
  if exists(path):
    error(f'File or directory "{path}" already exists!')
  return path


def mustbepackname(string):
  if not string or len(string.split('/')) != 2:
    error(f'"{string}" is not a valid package name! It must be of the form "scope/name".')
  return string


def mustbepack(path):
  if not util.is_pack(path):
    error(f'Path "{path}" is not a (Code)QL pack!')
  return path


def mustberepoid(string):
  if not string or len(string.split('/')) != 2:
    error(f'"{string}" is not a valid repository id! It must be of the form "owner/name".')
  return string


def mustbedist(path):
  if not util.is_dist(path):
    error(f'Path "{path}" is not a CodeQL distribution!')
  return path


def main():
  global tempdir
  tempdir = tempfile.mkdtemp()
  atexit.register(cleanup)

  outbase = argparse.ArgumentParser(add_help=False)
  outbase.add_argument(
    '--outdir', '-o',
    type=mustnotexist,
    help='Output directory',
  )

  packbase = argparse.ArgumentParser(add_help=False)
  packbase.add_argument(
    'pack',
    type=mustbepack,
    help='A (Code)QL pack.',
  )

  distbase = argparse.ArgumentParser(add_help=False)
  distbase.add_argument(
    '--dist',
    required=False,
    type=mustbedist,
    help='Path to a CodeQL distribution. If not given, ' +
         'the application will look for a "codeql" ' +
         'executable on PATH or use the "github/gh-codeql" ' +
         'extension, if installed.',
  )
  distbase.add_argument(
    '--search-path',
    required=False,
    default=None,
    help='Additional search path for QL packs',
  )
  distbase.add_argument(
    '--additional-packs',
    required=False,
    default=None,
    help='Additional search path for QL packs. Repeatable.',
  )

  parser = argparse.ArgumentParser(
    prog='tailor',
    description='Customize an existing CodeQL query pack',
  )

  subparsers = parser.add_subparsers()

  sp = subparsers.add_parser(
    'init',
    help='Create a new tailor project',
    description='Create a skeleton for a tailor project in the specified directory',
  )
  sp.add_argument(
    '-l', '--language',
    required=False,
    choices=util.LANGUAGES,
    help='The resulting package\'s desired language.',
  )
  sp.add_argument(
    '-b', '--basename',
    required=True,
    type=mustbepackname,
    help='The name of the packet to be customized.',
  )
  sp.add_argument(
    '-n', '--outname',
    required=True,
    type=mustbepackname,
    help='The name of the resulting package.',
  )
  sp.add_argument(
    'outdir',
    type=mustnotexist,
    help='A directory to create the tailor project in.',
  )
  sp.set_defaults(func=init)

  sp = subparsers.add_parser(
    'download',
    parents=[distbase, outbase],
    help='Download a (Code)QL pack from the registry.',
    description='Download a (Code)QL pack from the registry.',
  )
  sp.add_argument(
    'name',
    type=mustbepackname,
    help='The name of the package to download.',
  )
  sp.add_argument(
    '--version', '-v',
    required=False,
    default='*',
    help='The version of the package to download.',
  )
  sp.set_defaults(func=download)

  sp = subparsers.add_parser(
    'set-pack-meta',
    parents=[packbase],
    help='Modify the metadata values of a pack.',
    description='Modify the metadata values of a pack.',
  )
  sp.add_argument(
    '--name', '-n',
    required=False,
    type=mustbepackname,
    help='The value of the name field.',
  )
  sp.add_argument(
    '--version', '-v',
    required=False,
    help='The value of the version field.',
  )
  sp.add_argument(
    '--default-suite', '-d',
    required=False,
    help='The value of the defaultSuiteFile field.',
  )
  sp.set_defaults(func=set_pack_meta)

  sp = subparsers.add_parser(
    'set-ql-meta',
    help='Modify the metadata values in a CodeQL query.',
    description='Modify the metadata values in a CodeQL query.',
  )
  sp.add_argument(
    '--meta', '-m',
    nargs=2,
    action='append',
    default=[],
    required=False,
    help='The meta key and meta value to set. Repeatable.',
  )
  sp.add_argument(
    '--delete', '-d',
    action='append',
    default=[],
    required=False,
    help='The meta key to delete. Repeatable.',
  )
  sp.add_argument(
    'qlfiles',
    metavar='qlfile',
    nargs='+',
    type=mustbeqlfile,
    help='One or more query files.',
  )
  sp.set_defaults(func=set_ql_meta)

  sp = subparsers.add_parser(
    'ql-import',
    help='Import a module into a CodeQL query or library file.',
    description='Import a module into a CodeQL query or library file.',
  )
  sp.add_argument(
    '--module', '-m',
    action='append',
    dest='modules',
    metavar='module',
    required=True,
    help='The name of the fully-qualified module to import. Repeatable.',
  )
  sp.add_argument(
    'qlfiles',
    metavar='qlfile',
    nargs='+',
    type=mustbeqlorqllfile,
    help='One or more query or library files.',
  )
  sp.set_defaults(func=ql_import)


  sp = subparsers.add_parser(
    'customize',
    parents=[packbase],
    help='Generate and inject CodeQL into an existing pack, based on a settings file.',
    description='Generate and inject CodeQL into an existing pack, based on a settings file.',
  )
  sp.add_argument(
    '--priority', '-p',
    type=int,
    required=False,
    default=0,
    help='The priority of the settings.',
  )
  sp.add_argument(
    '--module', '-m',
    action='append',
    dest='modules',
    required=False,
    help='The name of a fully-qualified module to import into the generated settings qll file. Repeatable.',
  )
  sp.add_argument(
    'settingsfile',
    type=mustbefile,
    help='A yaml file with customization settings.',
  )
  sp.add_argument(
    'qlfiles',
    metavar='qlfile',
    nargs='+',
    type=mustbeqlorqllfile,
    help='One or more query or library files.',
  )
  sp.set_defaults(func=customize)


  sp = subparsers.add_parser(
    'install',
    parents=[distbase, packbase],
    help='Install a (Code)QL pack\'s dependencies.',
    description='Install a (Code)QL pack\'s dependencies.',
  )
  sp.add_argument(
    '--mode', '-m',
    required=False,
    default='merge-update',
    choices=['merge-update', 'update'],
  )
  sp.set_defaults(func=install)


  sp = subparsers.add_parser(
    'create',
    parents=[distbase, packbase, outbase],
    help='Compile a (Code)QL pack.',
    description='Compile a (Code)QL pack.',
  )
  sp.add_argument(
    '--in-place', '-i',
    required=False,
    action='store_true',
    help='Replace the given pack with the result (DESTRUCTIVE OPERATION!).',
  )
  sp.set_defaults(func=create)

  sp = subparsers.add_parser(
    'test',
    parents=[distbase, packbase],
    help='Run one or more test packs against a given pack.',
    description='Run one or more test packs against a given pack.',
  )
  sp.add_argument(
    'testpacks',
    type=mustbepack,
    nargs='+',
    help='One or more CodeQL test packs.',
  )
  sp.set_defaults(func=test)

  sp = subparsers.add_parser(
    'autoversion',
    parents=[distbase, packbase],
    help='Check or automatically bump version numbers of (Code)QL packs.',
    description='Check or automatically bump version numbers of (Code)QL packs.',
  )
  sp.add_argument(
    '--mode', '-m',
    required=False,
    default='new',
    choices=['manual', 'new', 'new-on-collision'],
  )
  sp.add_argument(
    '--fail',
    required=False,
    action='store_true',
    help='Treat warnings as errors.',
  )
  sp.set_defaults(func=autoversion)

  sp = subparsers.add_parser(
    'publish',
    parents=[distbase, packbase],
    help='Publish a compiled CodeQL pack.',
    description='Publish a compiled CodeQL pack.',
  )
  sp.set_defaults(func=publish)

  sp = subparsers.add_parser(
    'make-min-db',
    parents=[distbase],
    help='Create a minimal CodeQL database for test purposes.',
    description='Create a minimal CodeQL database for test purposes.',
  )
  sp.add_argument(
    '-l', '--language',
    required=True,
    choices=util.LANGUAGES,
    help='The database\'s language.',
  )
  sp.add_argument(
    'db',
    type=mustnotexist,
    help='The output directory',
  )
  sp.set_defaults(func=make_min_db)

  sp = subparsers.add_parser(
    'actions-cli-version',
    help='Retrieve the version of the CodeQL CLI currenty installed on GitHub Actions',
    description='Retrieve the version of the CodeQL CLI currenty installed on GitHub Actions',
  )
  sp.add_argument(
    '-r', '--repository',
    required=False,
    type=mustberepoid,
    default='zbazztian/gh-tailor',
    help='The repository ("owner/name") from which to fetch the information.',
  )
  sp.add_argument(
    '-s', '--release',
    default='codeql-versions-on-actions',
    help='The name of the release from which to fetch the information.',
  )
  sp.set_defaults(func=actions_cli_version)

  def print_usage(args):
    print(parser.format_usage())

  parser.set_defaults(func=print_usage)
  args = parser.parse_args()

  args.func(args)


def cleanup():
  shutil.rmtree(tempdir)


try:
  main()
except CalledProcessError as e:
  error(f'Subprocess "{e.cmd}" failed with code "{e.returncode}"!')
