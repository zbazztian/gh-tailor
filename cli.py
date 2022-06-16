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
  info('CodeQL distribution detected at "%s".' % (codeql.distdir))
  return codeql


def init(args):
  if util.is_tailorproject(args.project):
    error('"%s" is already a project!' % (args.project))

  os.makedirs(args.project, exist_ok=True)

  util.str2file(
    util.tailoryml(args.project),
    util.tailor_template(
      args.language,
      base_name=args.base_name,
      out_name=args.out_name
    )
  )

  util.str2file(
    join(args.project, 'TailorCustomizations.qll'),
    util.tailor_customizations_qll(
      args.language,
    )
  )


def set_pack_meta(args):
  if args.name:
    util.set_pack_name(args.pack, args.name)
  if args.version:
    util.set_pack_version(args.pack, args.version)
  if args.default_suite:
    util.set_pack_defaultsuite(args.pack, args.default_suite)


def set_ql_meta(args):
  for qlf in args.qlfiles:
    for k, v in args.meta:
      util.set_ql_meta(qlf, k, v)


def ql_import(args):
  for qlf in args.qlfiles:
    for m in args.module:
      util.ql_import(qlf, m)


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
    error('Pack "%s@%s" not found in registry!' % (args.name, args.version))

  if args.outdir:
    shutil.copytree(
      pack,
      args.outdir,
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


def mustbeqlorqllfile(path):
  if not (util.is_qlfile(path) or util.is_qllfile(path)):
    error('"%s" is not a CodeQL query or library file!' % path)
  return path


def mustbeqlfile(path):
  if not util.is_qlfile(path):
    error('"%s" is not a CodeQL query file!' % path)
  return path


def mustnotexist(path):
  if exists(path):
    error('File or directory "%s" already exists!' % path)
  return path


def mustbepack(path):
  if not util.is_pack(path):
    error('Path "%s" is not a (Code)QL pack!' % path)
  return path


def mustbedist(path):
  if not util.is_dist(path):
    error('Path "%s" is not a CodeQL distribution!' % path)
  return path


def mustbepackname(string):
  if not string or len(string.split('/')) != 2:
    error('"%s" is not a valid package name! It must be of the form "scope/name".' % string)
  return string


def main():
  global tempdir
  tempdir = tempfile.mkdtemp()
  atexit.register(cleanup)

  outbase = argparse.ArgumentParser(add_help=False)
  outbase.add_argument(
    '--outdir', '-o',
    type=mustnotexist,
    help='Directory in which to store the resulting CodeQL pack',
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
    help='Additional search path for QL packs',
  )

  parser = argparse.ArgumentParser(
    prog='tailor',
    description='Customize an existing CodeQL query pack',
  )

  subparsers = parser.add_subparsers()

  initparser = subparsers.add_parser(
    'init',
    parents=[outbase],
    help='Create a new tailor project',
    description='Create a skeleton for a tailor project in the specified directory',
  )
  initparser.add_argument(
    '--language', '-l',
    required=True,
    choices=['java', 'javascript', 'python', 'cpp', 'go', 'ruby', 'csharp'],
    help='Language',
  )
  initparser.add_argument(
    '--base-name',
    required=False,
    default=None,
    type=mustbepackname,
    help='The name of the packet to be customized.',
  )
  initparser.add_argument(
    '--out-name',
    required=False,
    default=None,
    type=mustbepackname,
    help='The name of the resulting package.',
  )
  initparser.set_defaults(func=init)

  downloadparser = subparsers.add_parser(
    'download',
    parents=[distbase, outbase],
    help='Download a (Code)QL pack from the registry.',
    description='Download a (Code)QL pack from the registry.',
  )
  downloadparser.add_argument(
    'name',
    type=mustbepackname,
    help='The name of the package to download.',
  )
  downloadparser.add_argument(
    '--version', '-v',
    required=False,
    default='*',
    help='The version of the package to download.',
  )
  downloadparser.set_defaults(func=download)

  setpackmetaparser = subparsers.add_parser(
    'set-pack-meta',
    parents=[packbase],
    help='Modify the metadata values of a pack.',
    description='Modify the metadata values of a pack.',
  )
  setpackmetaparser.add_argument(
    '--name', '-n',
    required=False,
    type=mustbepackname,
    help='The value of the name field.',
  )
  setpackmetaparser.add_argument(
    '--version', '-v',
    required=False,
    help='The value of the version field.',
  )
  setpackmetaparser.add_argument(
    '--default-suite', '-d',
    required=False,
    help='The value of the defaultSuiteFile field.',
  )
  setpackmetaparser.set_defaults(func=set_pack_meta)

  setqlmetaparser = subparsers.add_parser(
    'set-ql-meta',
    help='Modify the metadata values in a CodeQL query.',
    description='Modify the metadata values in a CodeQL query.',
  )
  setqlmetaparser.add_argument(
    '--meta', '-m',
    nargs=2,
    action='append',
    required=True,
    help='The meta key and meta value to set. Repeatable.',
  )
  setqlmetaparser.add_argument(
    'qlfiles',
    nargs='+',
    type=mustbeqlfile,
    help='One or more query files.',
  )
  setqlmetaparser.set_defaults(func=set_ql_meta)

  qlimportparser = subparsers.add_parser(
    'ql-import',
    help='Import a module into a CodeQL query or library file.',
    description='Import a module into a CodeQL query or library file.',
  )
  qlimportparser.add_argument(
    '--module', '-m',
    action='append',
    required=True,
    help='The name of the fully-qualified module to import. Repeatable.',
  )
  qlimportparser.add_argument(
    'qlfiles',
    nargs='+',
    type=mustbeqlorqllfile,
    help='One or more query or library files.',
  )
  qlimportparser.set_defaults(func=ql_import)

  installparser = subparsers.add_parser(
    'install',
    parents=[distbase, packbase],
    help='Install a (Code)QL pack\'s dependencies.',
    description='Install a (Code)QL pack\'s dependencies.',
  )
  installparser.add_argument(
    '--mode', '-m',
    required=False,
    default='merge-update',
    choices=['merge-update', 'update'],
  )
  installparser.set_defaults(func=install)

  createparser = subparsers.add_parser(
    'create',
    parents=[distbase, packbase, outbase],
    help='Compile a (Code)QL pack.',
    description='Compile a (Code)QL pack.',
  )
  createparser.add_argument(
    '--in-place', '-i',
    required=False,
    action='store_true',
    help='Replace the given pack with the result (DESTRUCTIVE OPERATION!).',
  )
  createparser.set_defaults(func=create)

  autoversionparser = subparsers.add_parser(
    'autoversion',
    parents=[distbase, packbase],
    help='Check or automatically bump version numbers of (Code)QL packs.',
    description='Check or automatically bump version numbers of (Code)QL packs.',
  )
  autoversionparser.add_argument(
    '--mode', '-m',
    required=False,
    default='new',
    choices=['manual', 'new', 'new-on-collision'],
  )
  autoversionparser.add_argument(
    '--fail',
    required=False,
    action='store_true',
    help='Treat warnings as errors.',
  )
  autoversionparser.set_defaults(func=autoversion)

  publishparser = subparsers.add_parser(
    'publish',
    parents=[distbase, packbase],
    help='Publish a compiled CodeQL pack.',
    description='Publish a compiled CodeQL pack.',
  )
  publishparser.set_defaults(func=publish)

  def print_usage(args):
    print(parser.format_usage())

  parser.set_defaults(func=print_usage)
  args = parser.parse_args()

  args.func(args)


def cleanup():
  shutil.rmtree(tempdir)


main()
