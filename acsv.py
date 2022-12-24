#!/bin/env python3

import sys
import argparse
import re
import subprocess
import json
import datetime
from pathlib import Path

# Parse arguments

behaviors = ['ignore','show','autoupdate','prompt','fail']
behaviors2 = ['skip','show','create','prompt''fail']

parser = argparse.ArgumentParser(description='Advanced Checksum Verifier')
parser.add_argument('directories',metavar='directories',nargs='*',default='',
                    help='Directories to process.')
parser.add_argument('-r','--renames', metavar='BEHAVIOR', dest='renames',
                    default='show',choices=behaviors,
                    help='What to do if we encounter renamed files.')
parser.add_argument('-d','--deletes', metavar='BEHAVIOR', dest='deletes',
                    default='prompt',choices=behaviors,
                    help='What to do if we encounter deleted files.')
parser.add_argument('-n','--new', metavar='BEHAVIOR', dest='new',
                    default='prompt',choices=behaviors,
                    help='What to do if we encounter new files.')
parser.add_argument('-m','--missing', metavar='BEHAVIOR', dest='missing',
                    default='ignore',choices=behaviors2,
                    help='What to do if checksum file is missing.')
parser.add_argument('-u','--updates', metavar='BEHAVIOR', dest='updates',
                    default='prompt',choices=behaviors,
                    help='What to do if file hashes don\'t match.')
parser.add_argument('-A','--autoupdate-all', action='store_true', dest='autoupdate_all',
                    help='Autoupdate for all situations.')
parser.add_argument('-U','--update-all', action='store_true', dest='update_all',
                    help='Prompt/update for checksum files.')
parser.add_argument('-P','--prompt-all', action='store_true', dest='prompt_all',
                    help='Basically prompt for any situation.')
parser.add_argument('-V','--verify-all', action='store_true', dest='verify_all',
                    help='Basically prompt for any situation.')
parser.add_argument('-s','--safe-mode', action='store_true', dest='safe_mode',
                    help='Enable safe mode (do not make any changes to disk).')
#parser.add_argument('-N','--nocolor', action='store_true', dest='nocolor',
#                    help='Do not use terminal colors.')
args = parser.parse_args()

mode = { 'renames': args.renames,
         'missing': args.missing,
         'new': args.new,
         'deletes': args.deletes,
         'updates': args.updates }

if args.autoupdate_all:
    mode = { 'renames': 'autoupdate',
             'missing': 'create',
             'new': 'autoupdate',
             'deletes': 'autoupdate',
             'updates': 'autoupdate' }

if args.verify_all:
    mode = { 'renames': 'show',
             'missing': 'show',
             'new': 'show',
             'deletes': 'show',
             'updates': 'show' }

if args.update_all:
    mode = { 'renames': 'prompt',
             'missing': 'create',
             'new': 'prompt',
             'deletes': 'prompt',
             'updates': 'prompt' }

if args.prompt_all:
    mode = { 'renames': 'prompt',
             'missing': 'prompt',
             'new': 'prompt',
             'deletes': 'prompt',
             'updates': 'prompt' }

print(json.dumps(mode,indent=2))

# Define terminal colors
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    MAG = '\033[35m'
    TEAL = '\033[96m'


# Convert md5sum output to a dict
def md5_to_dict(raw):
    txt = raw.decode('utf-8').split('\n')
    dd = {}
    for t in txt:
        try:
            tt = re.split(r'^([\da-fA-F]{32})\s+(.+)$',t)
            dd[tt[2]] = tt[1]
        except IndexError:
            pass
    return dd


if len(args.directories)==0:
    parser.print_help()

for cdir in args.directories:
    for p in Path(cdir).rglob("."):

        ckfiles = ['{}.md5'.format(p.name),'.md5']

        ff = [str(f.name) for f in p.glob('*') if f.is_file() and not f.is_symlink() and f.name not in ckfiles]
        ff.sort()
        if len(ff)==0:
            print('{}[EMPTY ] {}{}'.format(bcolors.OKBLUE,p.resolve(),bcolors.ENDC))
        elif len(ff)>0:

            if Path(p / '{}.md5'.format(p.name)).is_file():
                nohashfile = False
                print('{}[VERIFY] {}{}'.format(bcolors.OKBLUE,p.resolve(),bcolors.ENDC))
                with open(Path(p / '{}.md5'.format(p.name)),'rb') as ckfile:
                    ckdata = md5_to_dict(ckfile.read())
                #print(json.dumps(md5_to_dict(ckdata),indent=2))
            else:
                nohashfile = True
                if mode['missing'] in ('prompt','fail'):
                    print('{}[NOFILE] {}{}'.format(bcolors.HEADER,p.resolve(),bcolors.ENDC))
                    if mode['missing'] == 'fail':
                        raise Exception("ERROR: Missing checksum file.")
                elif mode['missing'] in ('create'):
                    print('{}[CREATE] {}{}'.format(bcolors.HEADER,p.resolve(),bcolors.ENDC))
                elif mode['missing'] == 'skip':
                    print('{}[NOFILE] {}{}'.format(bcolors.OKBLUE,p.resolve(),bcolors.ENDC))
                    continue
                elif mode['missing'] == 'show':
                    print('{}[NOFILE] {}{}'.format(bcolors.HEADER,p.resolve(),bcolors.ENDC))
                    continue
                else:
                    print('{}[CREATE] {}{}'.format(bcolors.OKBLUE,p.resolve(),bcolors.ENDC))
                ckdata = {}
            
            cmd = ['md5sum','--']
            cmd.extend(ff)
            rawmd5 = subprocess.run(cmd,capture_output=True,check=True,cwd=p).stdout
            hashdata = md5_to_dict(rawmd5)
            #print(json.dumps(md5_to_dict(hashdata.stdout),indent=2))

            hash_matches = {k: ckdata[k] for k in ckdata if k in hashdata and ckdata[k] == hashdata[k]}
            updated_files = {k: hashdata[k] for k in hashdata if k in ckdata and ckdata[k] != hashdata[k]}
            missing_files = {k: ckdata[k] for k in ckdata if k not in hashdata}
            added_files = {k: hashdata[k] for k in hashdata if k not in ckdata}

            renames = {}

            if len(missing_files)>0 and len(added_files)>0:
                jj = list(missing_files)
                jj.sort()
                kk = list(added_files)
                kk.sort()
                for j in jj:
                    for k in kk:
                        try:
                            if missing_files[j] == added_files[k]:
                                renames[j] = k
                                missing_files.pop(j)
                                added_files.pop(k)
                        except KeyError:
                            continue

            update = False
            prompt = False

            if len(updated_files)>0:
                if mode['updates'] != 'ignore':
                    print(f'  {bcolors.WARNING}UPDATED FILES{bcolors.ENDC}')
                    for k in updated_files.keys():
                        print('  {}{} -> {} {}{}'.format(bcolors.WARNING,ckdata[k],hashdata[k],k,bcolors.ENDC))
                if mode['updates'] in ('autoupdate','prompt'):
                    update = True
                if mode['updates'] == 'prompt':
                    prompt = True
                if mode['updates'] == 'fail':
                    raise Exception('ERROR: Updated files were found.  The hashes don\'t match.')

            if len(renames)>0:
                if mode['renames'] != 'ignore':
                    print(f'  {bcolors.TEAL}RENAMED FILES{bcolors.ENDC}')
                    for k in renames.keys():
                        print('  {}{} "{}" -> "{}"{}'.format(bcolors.TEAL,ckdata[k],k,renames[k],bcolors.ENDC))
                if mode['renames'] in ('autoupdate','prompt'):
                    update = True
                if mode['renames'] == 'prompt':
                    prompt = True
                if mode['renames'] == 'fail':
                    raise Exception('ERROR: Renamed files were found. The file names aren\'t consistent with the hash file.')

            if len(added_files)>0:
                if nohashfile:
                    if mode['missing'] != 'create':
                        prompt = True
                else:
                    if mode['new'] != 'ignore':
                        print(f'  {bcolors.OKGREEN}NEW FILES{bcolors.ENDC}')
                        for k in added_files.keys():
                            print('  {}{} {}{}'.format(bcolors.OKGREEN,added_files[k],k,bcolors.ENDC))
                    if mode['new'] in ('autoupdate','prompt'):
                        update = True
                    if mode['new'] == 'prompt':
                        prompt = True
                    if mode['new'] == 'fail':
                        raise Exception('ERROR: New files were found. The files aren\'t in the hash file.')

            if len(missing_files)>0:
                if mode['deletes'] != 'ignore':
                    print(f'  {bcolors.FAIL}MISSING FILES{bcolors.ENDC}')
                    for k in missing_files.keys():
                        print('  {}{} {}{}'.format(bcolors.FAIL,missing_files[k],k,bcolors.ENDC))
                if mode['deletes'] in ('autoupdate','prompt'):
                    update = True
                if mode['deletes'] == 'prompt':
                    prompt = True
                if mode['deletes'] == 'fail':
                    raise Exception('ERROR: Some files were deleted.')


            f = ''
            if prompt:
                if nohashfile:
                    while f not in ('y','n'):
                        f = input("  Create this checksum file? (y/n)=")
                else:
                    try:
                        mtime = datetime.datetime.fromtimestamp(Path(p / '{}.md5'.format(p.name)).stat().st_mtime) #, tz=timezone.utc)
                        print('  Last Updated: {}'.format(mtime.strftime('%m/%d/%Y %H:%M:%S')))
                    except FileNotFoundError:
                        pass
                    while f not in ('y','n'):
                        f = input("  Update this checksum file? (y/n)=")
            if update or nohashfile:
                if f != 'n':
                    if nohashfile:
                        if mode['missing'] == 'prompt':
                            print('  Creating checksum file {}.md5...'.format(p.name))
                    else:
                        print('  Updating checksum file {}.md5...'.format(p.name))
                    # Write out updated checksum file
                    if args.safe_mode:
                        print('{}Safe mode prevented write to file {}{}'.format(bcolors.WARNING,p / '{}.md5'.format(p.name),bcolors.ENDC))
                    else:
                        with open(p / '{}.md5'.format(p.name),'wb') as h:
                            h.write(rawmd5)





