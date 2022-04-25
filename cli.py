import argparse
import util
from util import error, info
import os
from os.path import dirname, isfile, abspath, \
                    join, basename, isdir, \
                    exists
import sys
import tempfile
import shutil
import json


def tailor(args):

  if not util.is_tailorproject(args.project):
    error('"%s" is not a valid project!' % (args.project))

  if args.out_dir and exists(args.out_dir):
    if args.overwrite:
      info('Clearing existing output directory "%s"...' % (args.out_dir))
      shutil.rmtree(args.out_dir)
    else:
      error('Output directory "%s" already exists!' % (args.out_dir))

  with util.TempDir(parentdir='.', keep=args.keep_tmp) as tempdir:
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

    info('Downloading in pack...')
    tailor_in_name, tailor_in_version = util.get_tailor_in(args.project)
    inpack = codeql.download_pack(tailor_in_name, tailor_in_version)
    if not inpack:
      error('In pack "%s" not found in registry!' % (tailor_in_name + '@' + tailor_in_version))
    info('in pack: "%s"' % (inpack))

    info('Downloading peer pack...')
    tailor_out_name, tailor_out_version = util.get_tailor_out(args.project)
    peerpack = codeql.download_pack(tailor_out_name, tailor_out_version)
    if not peerpack:
      info('No peer pack found.')
    else:
      info('peer pack: "%s"' % (peerpack))

    info('Creating out pack...')
    outpack = shutil.copytree(
      inpack,
      args.out_dir,
    )
    info('out pack: "%s"' % (outpack))

    info('Removing previous pack artifacts from out pack...')
    dotcodeqldir = join(outpack, '.codeql')
    if isdir(dotcodeqldir):
      shutil.rmtree(dotcodeqldir)

    info('Setting out pack name to "%s".' % (tailor_out_name))
    util.set_pack_name(outpack, tailor_out_name)

    # set out pack version
    if tailor_out_version == '*':
      if peerpack:
        info('Bumping version of out pack...')
        outpack_version = util.add_versions(
          util.get_pack_version(peerpack),
          '0.0.1',
        )
      else:
        outpack_version = '0.0.1'
    else:
      outpack_version = tailor_out_version

    info('out pack version will be "%s".' % (outpack_version))
    util.set_pack_version(
      outpack,
      outpack_version,
    )

    info('Copying ql files to out pack...')
    util.sync_qlfiles(args.project, outpack)

    info('Adding dependencies to out pack...')
    for p, v in util.get_tailor_deps(args.project):
      util.pack_add_dep(outpack, p, v)

    info('Perform imports on out pack...')
    for ti in util.get_tailor_imports(args.project):
      util.import_module(
        outpack,
        ti['module'],
        ti['files'],
      )

    info('Installing out pack dependencies...')
    codeql(
      'pack', 'install',
      '--mode', 'update',
      outpack
    )

    info('Writing out pack checksum...')
    util.write_tailor_checksum(
      outpack,
      inpack,
      args.project,
    )

    if peerpack:
      info('Comparing checksums of out pack and peer pack...')
      if util.get_tailor_checksum(outpack) == util.get_tailor_checksum(peerpack):
        info('Versions and checksums of out pack and peer pack are identical. Nothing left to do.')
        os.exit(0)
      else:
        if tailor_out_version != '*':
          error('Checksums of out pack and peer pack differ, but versions are identical!')



def main():
  parser = argparse.ArgumentParser(
    prog='tailor',
    #help='Customize an existing CodeQL query pack',
    description='Customize an existing CodeQL query pack',
  )

  parser.add_argument(
    '--dist',
    required=False,
    help='Path to a CodeQL distribution',
  )
  parser.add_argument(
    '--publish',
    required=False,
    action='store_true',
    help='Emit the GitHub Actions "skipped" output',
  )
  parser.add_argument(
    '--out-dir',
    required=False,
    default=None,
    help='Directory in which to store the resulting CodeQL pack',
  )
  parser.add_argument(
    '--search-path',
    required=False,
    default=None,
    help='Additional search path for QL packs',
  )
  parser.add_argument(
    '--additional-packs',
    required=False,
    default=None,
    help='Additional search path for QL packs',
  )
  parser.add_argument(
    '--overwrite',
    required=False,
    action='store_true',
    help='Overwrite any existing directory specified by --out-dir',
  )
  parser.add_argument(
    '--ignore-if-exists',
    required=False,
    action='store_true',
    help='Do not fail if a package with the same name and version already exists in the package registry.',
  )
  parser.add_argument(
    '--keep-tmp',
    required=False,
    action='store_true',
    help='Do not delete the temporary directory after program termination.',
  )
  parser.add_argument(
    'project',
    help='A directory containing tailor.yml file',
  )

  def print_usage(args):
    print(parser.format_usage())

  args = parser.parse_args()
  tailor(args)


main()
