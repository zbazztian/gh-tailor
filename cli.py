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



def get_codeql(args):
  info('Detecting CodeQL distribution...')
  distdir = args.dist or \
            util.codeql_dist_from_path_env() or \
            util.codeql_dist_from_gh_codeql()
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


def check_uploadability(codeql, outpack, autobump, strict):
  if not codeql.can_upload(outpack, autobump):
    warning('Upload would fail!')
    if strict:
      sys.exit(2)


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

  shutil.copytree(
    join(abspath(dirname(__file__)), 'templates', 'java'),
    args.project,
    dirs_exist_ok=True,
  )


def compile(args):
  codeql = get_codeql(args)

  if not util.is_pack(args.pack):
    error('"%s" is not a (Code)QL pack!' % args.pack)

  outpack = args.pack

  info('Removing previous pack artifacts from outpack...')
  util.clean_pack(outpack)

  autobump = args.autobump
  if autobump:
    codeql.autobump(outpack)

  info('Installing pack dependencies...')
  codeql.install(outpack)

  info('Building pack...')
  codeql.create(outpack)

  check_uploadability(codeql, outpack, autobump, args.strict)


def publish(args):
  codeql = get_codeql(args)

  if not util.is_pack(args.pack):
    error('"%s" is not a (Code)QL pack!' % args.pack)

  outpack = args.pack

  subpack = util.subpack(outpack)
  if not subpack:
    error('"%s" was not compiled!' % outpack)

  out = join(tempdir, 'pack.tgz')
  with tarfile.open(out, 'w:gz') as tarf:
    for name in os.listdir(subpack):
      tarf.add(join(subpack, name), arcname=name, recursive=True)

  codeql(
    'pack', 'publish',
    '-vv',
    '--file', out
  )


def create(args):
  check_project(args)

  outpack = init_outpack(args)

  codeql = get_codeql(args)

  info('Downloading inpack...')
  tailor_in_name, tailor_in_version = util.get_tailor_in(args.project)
  inpack = codeql.download_pack(tailor_in_name, tailor_in_version)
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
  autobump = tailor_out_version == '*'
  if autobump:
    codeql.autobump(outpack)
  else:
    util.set_pack_version(
      outpack,
      tailor_out_version,
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
  codeql.install(outpack)

  info('Building outpack...')
  codeql.create(outpack)

  check_uploadability(codeql, outpack, autobump, args.strict)


def main():
  #print(util.dir_hash('customized/.codeql/pack/zbazztian/customized-java-queries/0.0.5/'))
  #print(util.dir_hash('/home/sebastian/.codeql/packages/zbazztian/customized-java-queries/0.0.4/'))
  #return

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

  strictbase = argparse.ArgumentParser(add_help=False)
  strictbase.add_argument(
    '--strict',
    required=False,
    action='store_true',
    help='Treat warnings as errors.',
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
  initparser.set_defaults(func=init)

  createparser = subparsers.add_parser(
    'create',
    parents=[strictbase, distbase, projectbase],
    help='Create a customized, compiled package from a tailor project',
    description='Generate a customized, compiled package from a tailor project and drop it into a specified directory.',
  )
  createparser.add_argument(
    '--outdir',
    required=False,
    default=None,
    help='Directory in which to store the resulting CodeQL pack',
  )
  createparser.set_defaults(func=create)

  compileparser = subparsers.add_parser(
    'compile',
    parents=[strictbase, distbase, packbase],
    help='Compile a (Code)QL pack.',
    description='Compile a (Code)QL pack.',
  )
  compileparser.add_argument(
    '--autobump',
    required=False,
    action='store_true',
    help='Bump the version of the pack before compilation.',
  )
  compileparser.set_defaults(func=compile)

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
    args.func(args)


main()
