from urllib.request import (
  Request,
  HTTPRedirectHandler,
  HTTPDefaultErrorHandler,
  OpenerDirector,
  HTTPSHandler,
  HTTPErrorProcessor,
  UnknownHandler,
)
import os
import json
from fnmatch import fnmatch
from datetime import datetime


RESULTS_PER_PAGE = 100
API_URL = 'https://api.github.com'
REPO_ID = 'zbazztian/commons-io-public'
RELEASE_ID = 'codeql-versions-for-actions'


def parse_link_header(value):
  result = {}
  if not value:
    return result
  for l in value.split(', '):
    urlval, relval = l.split('; ')
    rel = relval.split('=')[1].strip('"')
    url = urlval.lstrip('<').rstrip('>')
    result[rel] = url
  return result


def request(
  url: str,
  method: str = "GET",
  headers: dict = {},
  data: bytes = None,
):

  method = method.upper()

  opener = OpenerDirector()
  add = opener.add_handler
  add(HTTPRedirectHandler())
  add(HTTPSHandler())
  add(HTTPDefaultErrorHandler())
  add(HTTPErrorProcessor())
  add(UnknownHandler())

  req = Request(
    url,
    data=data,
    headers=headers,
    method=method,
  )

  with opener.open(req) as resp:
    return (
      resp.status,
      resp.headers,
      resp.read().decode(resp.headers.get_content_charset('utf-8')),
    )


def error(msg):
  sys.exit('ERROR: ' + msg)


def info(msg):
  print('INFO: ' + msg, flush=True)


def now():
  return datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%SZ')


def parse_date(datestr):
  return datetime.strptime(datestr, '%Y-%m-%dT%H:%M:%SZ')


def sort_by_created_at(releasesorassets):
  return sorted(
    releasesorassets,
    key=lambda e: parse_date(e['created_at']),
    reverse=True
  )


def default_headers():
  return {
    'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
    'Accept': 'application/vnd.github.v3+json',
  }


def latest_asset(release: str, assetfilter: str):
  for a in sort_by_created_at(release['assets']):
    if fnmatch(a['name'], assetfilter):
      return a
  return None


def latest_version(release):
  a = latest_asset(
    release,
    'version-*'
  )
  return read_asset(a) if a else None


def read_asset(asset: str) -> str:
  return request(
    f'{API_URL}/repos/{REPO_ID}/releases/assets/{asset["id"]}',
    headers={
      **default_headers(),
      'Accept': 'application/octet-stream',
    },
    method='get',
  )[2]


def list_releases():
  url = f'{API_URL}/repos/{REPO_ID}/releases?per_page={RESULTS_PER_PAGE}'

  while True:
    _, headers, body = request(
      url,
      method='get',
      headers=default_headers()
    )
    body = json.loads(body)
    for r in body:
      yield r

    url = parse_link_header(headers.get('link')).get('next', None)
    if not url:
      break


def get_release(releasefilter):
  for r in sort_by_created_at(list_releases()):
    if fnmatch(r['tag_name'], releasefilter):
      return r
  return None


def ensure_release(rid: str) -> str:
  return get_release(rid) or create_release(rid, 'main')


def create_release(tag, revision):
  return json.loads(
    request(
      f'{API_URL}/repos/{REPO_ID}/releases',
      data=json.dumps({
        'tag_name': tag,
        'target_commitish': revision,
      }).encode('utf-8'),
      headers=default_headers(),
      method='post',
    )[2]
  )


def upload_asset(release, assetname, data):
  return json.loads(
    request(
      release['upload_url'].replace('{?name,label}', '') + f'?name={assetname}&label={assetname}',
      data=data,
      headers={
        **default_headers(),
        'Content-Type': 'application/text',
      },
      method='post',
    )[2]
  )


def upload_latest_version(version: str) -> None:
  r = ensure_release(RELEASE_ID)
  assetname = f'version-{now()}'
  for a in r['assets']:
    if assetname == a['name']:
      info(f'"{assetname}" was previously uploaded. Nothing left to do.')
      return
  if latest_version(r) == version:
    info(f'Latest version did not change ({version}). Nothing left to do.')
    return
  info(f'Setting newest version to "{version}".')
  upload_asset(r, assetname, version.encode('utf-8'))


upload_latest_version('1.2.25')
