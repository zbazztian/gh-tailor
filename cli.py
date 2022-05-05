import argparse
import util
from util import error, warning, info
from os.path import dirname, isfile, \
                    join, isdir, \
                    exists, abspath
import sys
import tempfile
import shutil


UPLOAD_WILL_SUCCEED = 0
UPLOAD_NOT_NECESSARY = 2
UPLOAD_WILL_FAIL = 3


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
  if args.outdir:
    if exists(args.outdir):
      if args.overwrite:
        info('Clearing existing output directory "%s"...' % (args.outdir))
        shutil.rmtree(args.outdir)
      else:
        error('Output directory "%s" already exists!' % (args.outdir))
    return args.outdir
  else:
    return join(tempdir, 'outpack')


def create(args):
  state, codeql, outpack, peerpack = sketch(args)

  codeql(
    'pack', 'create',
    '--threads', '0',
    '-vv',
    outpack
  )


def publish(args):
  state, codeql, outpack, peerpack = sketch(args)

  if state != UPLOAD_NOT_NECESSARY:
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
    join(abspath(dirname(__file__)), 'templates', 'java'),
    args.project,
    dirs_exist_ok=True,
  )


def sketch(args):
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
  for name, version in util.get_tailor_deps(args.project).items():
    util.pack_add_dep(outpack, name, version)

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

  state = UPLOAD_WILL_SUCCEED
  if peerpack:
    info('Comparing checksums of outpack and peerpack...')
    if util.get_tailor_checksum(outpack) == util.get_tailor_checksum(peerpack):
      info('Checksums are identical.')
      state = UPLOAD_NOT_NECESSARY
    else:
      info('Checksums differ.')
      if not autobump:
        warning('Upload will fail because checksums of outpack and peerpack differ, yet versions are identical!')
        state = UPLOAD_WILL_FAIL

  if args.strict and state != UPLOAD_WILL_SUCCEED:
    sys.exit(state)

  return state, codeql, outpack, peerpack


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

  strictbase = argparse.ArgumentParser(add_help=False)
  strictbase.add_argument(
    '--strict',
    required=False,
    action='store_true',
    help='Treat warnings as errors.',
  )

  sketchbase = argparse.ArgumentParser(add_help=False)
  sketchbase.add_argument(
    '--outdir',
    required=False,
    default=None,
    help='Directory in which to store the resulting CodeQL pack',
  )
  sketchbase.add_argument(
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

  sketchparser = subparsers.add_parser(
    'sketch',
    parents=[strictbase, sketchbase, distbase, projectbase],
    help='Generate a customized, uncompiled package',
    description='Generate a customized, uncompiled package and drop it into a specified directory.',
  )
  sketchparser.set_defaults(func=sketch)

  createparser = subparsers.add_parser(
    'create',
    parents=[strictbase, sketchbase, distbase, projectbase],
    help='Create a customized, compiled package',
    description='Generate a customized, compiled package and drop it into a specified directory.',
  )
  createparser.set_defaults(func=create)

  publishparser = subparsers.add_parser(
    'publish',
    parents=[strictbase, sketchbase, distbase, projectbase],
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
