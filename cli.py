import argparse
import util
import os
from os.path import dirname, isfile, abspath, join, basename
import sys
import tempfile


def tailor(args):
  with tempfile.TemporaryDirectory(dir='.') as tempdir:
    if args.out_dir is None:
      args.out_dir = join(tempdir, 'pack')

    codeql = util.CodeQL('/home/sebastian/apps/codeql/2.8.5/')
    tailorinfo = util.get_tailor_info(
      codeql.download_pack(
        args.tailor_pack,
        additional_packs=args.additional_packs,
        search_path=args.search_path
      )
    )
    print(tailorinfo)


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
    '--fail-if-exists',
    required=False,
    action='store_true',
    help='Fail the pack upload if a pack with the same name and version already exists',
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
    'tailor-pack',
    required=True,
    help='The CodeQL pack with the tailor information',
  )

  def print_usage(args):
    print(parser.format_usage())

  args = parser.parse_args()
  tailor(args)


main()
