import argparse
import util
from util import error, warning, info
import os
from os.path import dirname, isfile, \
                    join, isdir, \
                    exists, abspath
import sys
import tempfile
import shutil
import tarfile


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


def init_outpack(args):
  if args.outdir:
    if exists(args.outdir):
      error('Output directory "%s" already exists!' % (args.outdir))
    return args.outdir
  else:
    return join(tempdir, 'outpack')


def init(args):
  if util.is_tailorproject(args.project):
    error('"%s" is already a project!' % (args.project))

  os.makedirs(args.project, exist_ok=True)

  util.str2file(
    util.tailoryml(args.project),
    util.tailor_template(
      args.language,
      inName=args.inpack_name,
      outName=args.outpack_name
    )
  )

  util.str2file(
    join(args.project, 'TailorCustomizations.qll'),
    util.tailor_customizations_qll(
      args.language,
    )
  )


def sketch(args):

  if not util.is_tailorproject(args.project):
    error('"%s" is not a valid project!' % (args.project))

  outpack = init_outpack(args)
  codeql = get_codeql(args, args.project)

  info('Downloading inpack...')
  tailor_in_name, tailor_in_version = util.get_tailor_in(args.project)
  inpack = codeql.download_pack(
    tailor_in_name,
    tailor_in_version,
    match_cli=True
  )
  if inpack:
    info('inpack: "%s"' % (inpack))
  else:
    error('inpack "%s" not found in registry!' % (tailor_in_name + '@' + tailor_in_version))

  info('Creating outpack at "%s"...' % (outpack))
  shutil.copytree(
    inpack,
    outpack,
  )

  info('Removing previous pack artifacts from outpack...')
  util.clean_pack(outpack)

  tailor_out_name, tailor_out_version = util.get_tailor_out(args.project)

  info('Setting outpack name to "%s".' % (tailor_out_name))
  util.set_pack_name(outpack, tailor_out_name)

  # set outpack version
  util.set_pack_version(
    outpack,
    codeql.resolve_pack_version(
      tailor_out_name,
      '*', '0.0.0',
      use_search_path=False,
      match_cli=False
    ) \
    if tailor_out_version == '*' else \
    tailor_out_version
  )

  default_suite = util.get_tailor_default_suite(args.project)
  if default_suite:
    info('Setting outpack default suite to "%s".' % (default_suite))
    util.set_pack_defaultsuite(outpack, default_suite)

  info('Copying ql files to outpack...')
  util.sync_qlfiles(args.project, outpack)

  info('Adding dependencies to outpack...')
  for name, version in util.get_tailor_deps(args.project).items():
    util.pack_add_dep(
      outpack,
      name,
      version
    )

  info('Perform imports on outpack...')
  for ti in util.get_tailor_imports(args.project):
    util.import_module(
      outpack,
      ti['module'],
      ti['files'],
    )


def install(args):
  outpack = args.pack

  if not util.is_pack(outpack):
    error('"%s" is not a (Code)QL pack!' % outpack)

  codeql = get_codeql(args, outpack)

  info('Updating lock file...')
  codeql.make_lockfile(
    outpack,
    qlpack_backup_file,
    match_cli=True,
    mode=args.mode
  )

  codeql.install(outpack)


def create(args):

  pack = args.pack
  if not util.is_pack(pack):
    error('"%s" is not a (Code)QL pack!' % pack)

  outdir = args.outdir or args.pack
  if abspath(outdir) != abspath(args.pack) and isdir(outdir):
    error('Output directory "%s" already exists!' % outdir)

  codeql = get_codeql(args, pack)

  info('Building pack...')
  codeql.create(pack, outdir, join(tempdir, 'outpack'))


def autoversion(args):
  pack = args.pack
  if not util.is_pack(pack):
    error('"%s" is not a (Code)QL pack!' % pack)

  codeql = get_codeql(args, pack)

  outdir = args.outdir or args.pack
  if abspath(outdir) != abspath(args.pack) and isdir(outdir):
    error('Output directory "%s" already exists!' % outdir)
  sys.exit(codeql.autoversion(pack, outdir, args.mode, args.fail))


def publish(args):
  pack = args.pack
  if not util.is_pack(pack):
    error('"%s" is not a (Code)QL pack!' % pack)

  codeql = get_codeql(args, pack)

  out = join(tempdir, 'pack.tgz')
  with tarfile.open(out, 'w:gz') as tarf:
    for name in os.listdir(pack):
      tarf.add(join(pack, name), arcname=name, recursive=True)

  codeql(
    'pack', 'publish',
    '-vv',
    '--file', out
  )


def main():
  outbase = argparse.ArgumentParser(add_help=False)
  outbase.add_argument(
    '--outdir',
    help='Directory in which to store the resulting CodeQL pack',
  )

  packbase = argparse.ArgumentParser(add_help=False)
  packbase.add_argument(
    'pack',
    help='A (Code)QL pack.',
  )

  projectbase = argparse.ArgumentParser(add_help=False)
  projectbase.add_argument(
    'project',
    help='A tailor project directory',
  )

  distbase = argparse.ArgumentParser(add_help=False)
  distbase.add_argument(
    '--dist',
    required=False,
    help='Path to a CodeQL distribution',
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
    parents=[projectbase],
    help='Create a new tailor project',
    description='Create a skeleton for a tailor project in the specified directory',
  )
  initparser.add_argument(
    '--language',
    required=True,
    help='Language',
  )
  initparser.add_argument(
    '--inpack-name',
    required=False,
    default=None,
    help='The name of the packet to be customized.',
  )
  initparser.add_argument(
    '--outpack-name',
    required=False,
    default=None,
    help='The name of the resulting package.',
  )
  initparser.set_defaults(func=init)

  sketchparser = subparsers.add_parser(
    'sketch',
    parents=[distbase, projectbase, outbase],
    help='Create a customized package from a tailor project',
    description='Generate a customized package from a tailor project and drop it into a specified directory.',
  )
  sketchparser.set_defaults(func=sketch)

  installparser = subparsers.add_parser(
    'install',
    parents=[distbase, packbase],
    help='Install a (Code)QL pack\'s dependencies.',
    description='Install a (Code)QL pack\'s dependencies.',
  )
  installparser.add_argument(
    '--mode',
    required=False,
    default='merge-update',
    help='One of "merge-update" or "update".',
  )
  installparser.set_defaults(func=install)

  createparser = subparsers.add_parser(
    'create',
    parents=[distbase, packbase, outbase],
    help='Compile a (Code)QL pack.',
    description='Compile a (Code)QL pack.',
  )
  createparser.set_defaults(func=create)

  autoversionparser = subparsers.add_parser(
    'autoversion',
    parents=[distbase, packbase, outbase],
    help='Check or automatically bump version numbers of (Code)QL packs.',
    description='Check or automatically bump version numbers of (Code)QL packs.',
  )
  autoversionparser.add_argument(
    '--mode',
    required=True,
    help='One of: "manual", "bump", "bump-on-collision".',
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

  global tempdir
  with tempfile.TemporaryDirectory(dir='.', prefix='.') as tempdir:
    global qlpack_backup_file
    qlpack_backup_file = join(tempdir, 'qlpack.yml.bak')
    args.func(args)


main()
