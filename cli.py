import argparse
import util
import os
from os.path import dirname, isfile, abspath, join, basename, isdir, exists
import sys
import tempfile
import shutil
import json


def tailor(args):
  if args.out_dir and exists(args.out_dir):
    if args.overwrite:
      util.info('Clearing existing output directory "%s"...' % (args.out_dir))
      shutil.rmtree(args.out_dir)
    else:
      util.error('Output directory "%s" already exists!' % (args.out_dir))

  with tempfile.TemporaryDirectory(dir='.') as tempdir:
    distpath = None
    if args.dist:
      distpath = args.dist
    else:
      codeqlexec = shutil.which('codeql')
      if codeqlexec:
        rec = util.Recorder()
        util.Executable(codeqlexec)(
          'version',
          '--format', 'json',
          combine_std_out_err=False,
          outconsumer=rec
        )
        j = json.loads(''.join(rec.lines))
        distpath = j['unpackedLocation']

    if distpath:
      codeql = util.CodeQL(
        distpath,
        additional_packs=args.additional_packs,
        search_path=args.search_path,
      )
    else:
      util.error("Please provide the --dist argument or make sure the 'codeql' executable can be found in the PATH environment variable!")


    tailorpack = codeql.download_pack(args.tailor_pack)
    tailorinfo = util.get_tailor_info(tailorpack)

    outpack = shutil.copytree(
      codeql.download_pack(tailorinfo['inpack']),
      join(tempdir, 'pack'),
    )

    outpack_name = tailorinfo['outpack']
    outpack_version = util.add_versions(
      util.get_pack_version(tailorpack),
      util.get_pack_version(outpack),
    )
    util.set_pack_name(outpack, outpack_name)
    util.set_pack_version(
      outpack,
      outpack_version,
    )
    util.pack_add_dep(outpack, util.get_pack_name(tailorpack), '*')

    util.import_module(
      outpack,
      tailorinfo['import']['module'],
      tailorinfo['import']['files'],
    )

    codeql(
      'pack', 'install',
      '--mode', 'update',
      outpack
    )

    codeql(
      'pack', 'create',
      '--threads', '0',
      '-v',
      outpack,
    )

    if args.out_dir:
      shutil.copytree(
        join(
          outpack,
          '.codeql',
          'pack',
          outpack_name,
          outpack_version
        ),
        args.out_dir,
      )

    if args.publish:
      codeql.publish(outpack, ignore_if_exists=args.ignore_if_exists)


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
    'tailor_pack',
    help='The CodeQL pack with the tailor information',
  )

  def print_usage(args):
    print(parser.format_usage())

  args = parser.parse_args()
  tailor(args)


main()
