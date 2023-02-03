#!/bin/env python3

import signal
import sys
import argparse
import re
import subprocess
import json
import datetime
import time
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
parser.add_argument('-R','--refresh-all', action='store_true', dest='refresh_all',
                    help='Autoupdate renames and additions, but prompt for missing or changed files.')
parser.add_argument('-P','--prompt-all', action='store_true', dest='prompt_all',
                    help='Basically prompt for any situation.')
parser.add_argument('-V','--verify-all', action='store_true', dest='verify_all',
                    help='Verify hashes and show problems, but do not modify any checksum files.')
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

if args.refresh_all:
    mode = { 'renames': 'autoupdate',
             'missing': 'create',
             'new': 'autoupdate',
             'deletes': 'prompt',
             'updates': 'prompt' }

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

# Gracefully handle KeyboardInterrupt
def signal_handler(signal, frame):
    print('Job cancelling due to keyboard interrupt...')
    print_stats()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)


def print_stats():
    exec_time = end_time - start_time - count['waittime']
    try:
        speed = count['bytes'] / exec_time
    except ZeroDivisionError:
        speed = 0.0
    sizestring = '{} bytes'.format(count['bytes'])
    ratestring = '{:.3f} bytes/sec'.format(speed)
    if count['bytes'] > 1024:
        sizestring = '{:.3f} KiB'.format(count['bytes'] / 1024)
        ratestring = '{:.3f} KiB/sec'.format(speed / 1024)
    if count['bytes'] > (1024 * 1024):
        sizestring = '{:.3f} MiB'.format(count['bytes'] / 1024 / 1024)
        ratestring = '{:.3f} MiB/sec ({:.3f} GiB/min; {:.3f} TiB/hr)'.format(speed / 1024 / 1024,
                                                                             speed / 1024 / 1024 / 1024 * 60,
                                                                             speed / 1024 / 1024 / 1024 / 1024 * 60 * 60)
    if count['bytes'] > (1024 * 1024 * 1024):
        sizestring = '{:.3f} GiB'.format(count['bytes'] / 1024 / 1024 / 1024)
    if count['bytes'] > (1024 * 1024 * 1024 * 1024):
        sizestring = '{:.3f} TiB'.format(count['bytes'] / 1024 / 1024 / 1024 / 1024)
    print('Processed {} in {:,} files and {:,} directories in {}'.format(sizestring,count['files'], count['directories'],str(datetime.timedelta(seconds=exec_time))))
    print('Average rate of {}'.format(ratestring))
    if count['waittime'] > 0.0:
        print('Spent {} waiting for user input'.format(str(datetime.timedelta(seconds=count['waittime']))))

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

start_time = time.time()
end_time = start_time
count = {'files':0,'directories':0,'bytes':0,'waittime':0}

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

            end_time = time.time()
            count['directories'] = count['directories'] + 1
            count['files'] = count['files'] + len(ff)
            fz = [(p / x).stat().st_size for x in ff]
            count['bytes'] = count['bytes'] + sum(fz)

            hashdata = md5_to_dict(rawmd5)

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
                    print('  {}UPDATED FILES ({:,}){}'.format(bcolors.WARNING,len(updated_files),bcolors.ENDC))
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
                    print('  {}RENAMED FILES ({:,}){}'.format(bcolors.TEAL,len(renames),bcolors.ENDC))
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
                        print('  {}NEW FILES ({:,}){}'.format(bcolors.OKGREEN,len(added_files),bcolors.ENDC))
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
                    print('  {}MISSING FILES ({:,}){}'.format(bcolors.FAIL,len(missing_files),bcolors.ENDC))
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
                        input_start = time.time()
                        f = input("  Create this checksum file? (y/n)=")
                        input_end = time.time()
                        count['waittime'] = count['waittime'] + (input_end - input_start)
                else:
                    try:
                        mtime = datetime.datetime.fromtimestamp(Path(p / '{}.md5'.format(p.name)).stat().st_mtime) #, tz=timezone.utc)
                        print('  Last Updated: {}'.format(mtime.strftime('%m/%d/%Y %H:%M:%S')))
                    except FileNotFoundError:
                        pass
                    while f not in ('y','n'):
                        input_start = time.time()
                        f = input("  Update this checksum file? (y/n)=")
                        input_end = time.time()
                        count['waittime'] = count['waittime'] + (input_end - input_start)
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

end_time = time.time()
print_stats()
