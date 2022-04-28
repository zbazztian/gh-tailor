import argparse
import util
from util import error, warning, info
from os.path import dirname, isfile, \
                    join, isdir, \
                    exists, abspath
import sys
import tempfile
import shutil


def get_codeql(args):
  info('Detecting CodeQL distribution...')
  distdir = args.dist or util.codeql_dist_from_path_env()
  if not distdir:
    error(
      "Please provide the --dist argument or make sure the 'codeql' " +
      "executable can be found via the PATH environment variable!"
    )

  codeql = util.CodeQL(
    distdir,
    additional_packs=args.additional_packs,
    search_path=args.search_path,
  )
  info('CodeQL distribution detected at "%s".' % (codeql.distdir))
  return codeql


def check_project(args):
  if not util.is_tailorproject(args.project):
    error('"%s" is not a valid project!' % (args.project))


def init_outpack(args):
  if args.out_dir:
    if exists(args.out_dir):
      if args.overwrite:
        info('Clearing existing output directory "%s"...' % (args.out_dir))
        shutil.rmtree(args.out_dir)
      else:
        error('Output directory "%s" already exists!' % (args.out_dir))
    return args.out_dir
  else:
    return join(tempdir, 'outpack')


def make(args):
  autobump, codeql, outpack, peerpack = tailor(args)

  if peerpack:
    info('Comparing checksums of outpack and peerpack...')
    if util.get_tailor_checksum(outpack) == util.get_tailor_checksum(peerpack):
      warning('Versions and checksums of outpack and peerpack are identical. An upload would not change the functionality.')
    else:
      if not autobump:
        warning('Upload would fail because checksums of outpack and peerpack differ, yet versions are identical!')


def publish(args):
  autobump, codeql, outpack, peerpack = tailor(args)

  if peerpack:
    info('Comparing checksums of outpack and peerpack...')
    if util.get_tailor_checksum(outpack) == util.get_tailor_checksum(peerpack):
      info('Versions and checksums of outpack and peerpack are identical. Nothing left to do.')
      sys.exit(0)
    else:
      if not autobump:
        error('Upload will fail because checksums of outpack and peerpack differ, yet versions are identical!')

  codeql(
    'pack', 'publish',
    '--threads', '0',
    '-vv',
    outpack
  )


def init(args):
  if util.is_tailorproject(args.project):
    error('"%s" is already a project!' % (args.project))

  shutil.copytree(
    join(abspath(dirname(__file__)), 'templates', 'standard'),
    args.project,
    dirs_exist_ok=True,
  )


def tailor(args):
  check_project(args)

  outpack = init_outpack(args)

  codeql = get_codeql(args)

  info('Downloading inpack...')
  tailor_in_name, tailor_in_version = util.get_tailor_in(args.project)
  inpack = codeql.download_pack(tailor_in_name, tailor_in_version)
  if not inpack:
    error('inpack "%s" not found in registry!' % (tailor_in_name + '@' + tailor_in_version))
  info('inpack: "%s"' % (inpack))

  info('Downloading peerpack...')
  tailor_out_name, tailor_out_version = util.get_tailor_out(args.project)
  peerpack = codeql.download_pack(tailor_out_name, tailor_out_version)
  if not peerpack:
    info('No peerpack found.')
  else:
    info('peerpack: "%s"' % (peerpack))


  info('Creating outpack at "%s"...' % (outpack))
  shutil.copytree(
    inpack,
    outpack,
  )

  info('Removing previous pack artifacts from outpack...')
  dotcodeqldir = join(outpack, '.codeql')
  if isdir(dotcodeqldir):
    shutil.rmtree(dotcodeqldir)

  info('Setting outpack name to "%s".' % (tailor_out_name))
  util.set_pack_name(outpack, tailor_out_name)

  # set outpack version
  autobump = tailor_out_version == '*'
  if autobump:
    if peerpack:
      info('Bumping version of outpack...')
      outpack_version = util.add_versions(
        util.get_pack_version(peerpack),
        '0.0.1',
      )
    else:
      outpack_version = '0.0.1'
  else:
    outpack_version = tailor_out_version

  info('outpack version will be "%s".' % (outpack_version))
  util.set_pack_version(
    outpack,
    outpack_version,
  )

  default_suite = util.get_tailor_default_suite(args.project)
  if default_suite:
    info('Setting outpack default suite to "%s".' % (default_suite))
    util.set_pack_defaultsuite(outpack, default_suite)

  info('Copying ql files to outpack...')
  util.sync_qlfiles(args.project, outpack)

  info('Adding dependencies to outpack...')
  for p, v in util.get_tailor_deps(args.project):
    util.pack_add_dep(outpack, p, v)

  info('Perform imports on outpack...')
  for ti in util.get_tailor_imports(args.project):
    util.import_module(
      outpack,
      ti['module'],
      ti['files'],
    )

  info('Installing outpack dependencies...')
  codeql(
    'pack', 'install',
    '--mode', 'update',
    outpack
  )

  info('Writing outpack checksum...')
  util.write_tailor_checksum(
    outpack,
    inpack,
    args.project,
  )

  return autobump, codeql, outpack, peerpack


def main():

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

  makebase = argparse.ArgumentParser(add_help=False)
  makebase.add_argument(
    '--out-dir',
    required=False,
    default=None,
    help='Directory in which to store the resulting CodeQL pack',
  )
  makebase.add_argument(
    '--overwrite',
    required=False,
    action='store_true',
    help='Overwrite any existing directory specified by --out-dir',
  )

  parser = argparse.ArgumentParser(
    prog='tailor',
    #help='Customize an existing CodeQL query pack',
    description='Customize an existing CodeQL query pack',
  )

  subparsers = parser.add_subparsers()

  initparser = subparsers.add_parser(
    'init',
    parents=[projectbase],
    help='Create a new tailor project',
    description='Create a skeleton for a tailor project in the specified directory',
  )
  initparser.set_defaults(func=init)

  makeparser = subparsers.add_parser(
    'make',
    parents=[makebase, distbase, projectbase],
    help='Create a customized package',
    description='Create a customized package and drop it into a specified directory.',
  )
  makeparser.set_defaults(func=make)

  publishparser = subparsers.add_parser(
    'publish',
    parents=[makebase, distbase, projectbase],
    help='Create a customized package and publish it',
    description='Create a customized package and publish it.',
  )
  publishparser.set_defaults(func=publish)

  def print_usage(args):
    print(parser.format_usage())

  parser.set_defaults(func=print_usage)
  args = parser.parse_args()

  global tempdir
  with tempfile.TemporaryDirectory(dir='.', prefix='.') as tempdir:
    args.func(args)


main()
