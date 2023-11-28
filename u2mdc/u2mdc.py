#!/usr/bin/env python3

import os
import sys
import json
import yaml
import argparse
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder


### a config file named u2mdc.conf alongside the executable must contain the following
### values as generated from mixcloud API tools at https://www.mixcloud.com/developers/
# client_id:
# client_secret:
# code:
def authenticate():
    # get secret config values to build URL from config file, so maybe i can share this if i want to
    configpath = os.path.dirname(os.path.abspath(__file__))
    config = p(open(f'{ configpath }/u2mdc.conf'))
    client_id = config.get('client_id')
    client_secret = config.get('client_secret')
    code = config.get('code')
    url = f'https://www.mixcloud.com/oauth/access_token?client_id={ client_id }&redirect_uri=google.com&client_secret={ client_secret }&code={ code }'
    # get an access token to use in authentication headers
    access_token_response = requests.post( url )
    access_token = access_token_response.json().get('access_token')
    return access_token


def getargs():
    parser = argparse.ArgumentParser(description='upload to Mixcloud using a YAML file')
    parser.add_argument('-u', '--update', action='store_true', help='update entry; not new')
    parser.add_argument('files', action='store', nargs='+', help='YAML files to read')
    return parser.parse_args()


def getdesc(y):
    desc = ''
    for d in y.get('description'):
        desc += f'{ d.get("line") }\n\n'
    desc = desc[:-1]
    return desc


def getmp3(y):
    mp3file = y.get('mp3')
    mp3 = f"/default/45678/{ mp3file }"
    mp3maxlen = 4294967296
    try:
        mp3size = os.path.getsize(mp3)
        if mp3size > mp3maxlen:
            raise SystemExit(f'{ mp3 } too large (length: { mp3size }, maxlen: { mp3maxlen })')
    except FileNotFoundError:
        raise SystemExit(f'{ mp3 } file not found')
    return mp3, mp3file


def getpic(y):
    picfile = y.get("img")
    pic = f'/default/djrobyay.freelancer/img/sets/{ picfile }'
    pictype = os.path.splitext(pic)[1][1:]
    if pictype.lower() == 'jpg':
        pictype = 'jpeg'
    picmaxlen = 10485760
    try:
        picsize = os.path.getsize(pic)
        if picsize > picmaxlen:
            raise SystemExit(f'{ pic } too large (length: { picsize }, maxlen: { picmaxlen })')
    except FileNotFoundError:
        raise SystemExit(f'{ pic } file not found')
    return pic, picfile, pictype


def gettags(y):
    tags = y.get('tags').split(',')
    if len(tags) > 5:
        raise SystemExit('too many tags (max tags: 5)')
    return tags


def init():
    # authenticate and get an access token - might as well be new each time
    args = getargs()
    for yamlfile in args.files:
        run(yamlfile=yamlfile, update=args.update, access_token=authenticate())


def makefields(description, name, pic, picfile, pictype, publish_date, tags, tracks):
    # compile the fields into a dictionary
    fields = {'name': name,
              'picture': (picfile, open(pic, 'rb'), f'image/{ pictype }'),
              'description': description
             }
    if publish_date:
        fields['publish_date'] = publish_date
    # compile tags into the fields dictionary
    for idx, tag in enumerate(tags):
        fields[f'tags-{ idx }-tag'] = tag
    # compile track details into the fields dictionary
    for idx, track in enumerate(tracks):
        fields[f'sections-{ idx+1 }-song'] = track.get('title')
        fields[f'sections-{ idx+1 }-artist'] = track.get('artist')
    return fields


def p(content):
    return list(yaml.load_all(content, Loader=yaml.BaseLoader))[0]


def postcontent(fields, url):
    m = MultipartEncoder( fields )
    return requests.post(url, data=m, headers={'Content-Type': m.content_type})


def run(access_token, update, yamlfile):
    # read, load, and parse the yaml
    y = p(open(yamlfile))
    # compile collected values into a dictionary
    pic, picfile, pictype = getpic(y)
    name = y.get('title')
    fields = makefields( description=getdesc(y),
                         name=name,
                         pic=pic,
                         picfile=picfile,
                         pictype=pictype,
                         publish_date=y.get('publish-date'),
                         tags=gettags(y),
                         tracks=y.get('tracks') )
    # if we have a mixcloud key already, we need to update
    mixcloudkey = y.get('mixcloud')
    if mixcloudkey:
        if not update:
            sys.stderr.write(f'changing to update - exists on mixcloud as { mixcloudkey }\n')
            update = True
    # set the API endpoint URL, and add mp3 field to the dictionary if we are NOT updating
    if update:
        url = f'https://api.mixcloud.com/upload/djrobyay/{ mixcloudkey }/edit/?access_token={ access_token }'
    else:
        mp3, mp3file = getmp3(y)
        fields['mp3'] = (mp3file, open(mp3, 'rb'), 'audio/mp3')
        url = f'https://api.mixcloud.com/upload/?access_token={ access_token }'
    # do it
    sys.stdout.write(f'## now uploading {name} to Mixcloud\n')
    r = postcontent(fields=fields, url=url)
    # and, vaguely report on it. :)
    if r.status_code == 200:
        key = json.loads(r.content).get('result').get('key')
        sys.stdout.write(f'{name}: OK - mixcloud key: {key}\n')
    else:
        sys.stdout.write(f'{name}: FAIL (response code: {r.status_code})\n')
        result = json.loads(r.content).get('error')
        for bit in result:
            sys.stdout.write(f'error {bit}: {result[bit]}\n')
        sys.stdout.write('\n')
        sys.exit(1)


if __name__ == '__main__':
    init()
