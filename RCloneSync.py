#!/usr/bin/env python
#========================================================= 
#
#  Basic BiDirectional Sync using RClone 
#
#  Usage
#   Configure rclone, including authentication before using this tool.  rclone must be in the search path.
#
#  Chris Nelson, November 2017
#
# 171112  Revamped error handling to be effective.  See Readme.md.
#       Added --CheckAccess switch to make filesystems access test optional.  Default is False (no check).
# 171015  Moved tooManyLocalDeletes error message down below the remote check to provide both local and remote change lists to the stdout
# 170917  Added --Force switch - required when the the % changes on local or remote system are grater than maxDelta.  Safeguard for
#       local or remote not online.
#       Added --ignore-times to the copy of changed file on remote to local.  Was not copying files with matching sizes.
# 170805  Added --Verbose command line switch 
# 170730  Horrible bug - remote lsl failing results in deleting all local files, and then iteratively replicating _LOCAL and _REMOTE files.
#       Added connection test/checking files to abort if the basic connection is down.  RCLONE_TEST files on the local system
#       must match the remote system (and be unchanged), else abort.
#       Added lockfile so that a second run aborts if a first run is still in process, or failed and left the lockfile in place.
#       Added python logging, sorted processing
# 170716  New
#
# Known bugs:
#   
#
#==========================================================

import argparse
import sys
import re
import os.path, subprocess
from datetime import datetime
import time
import shlex
import logging
import inspect                              # for getting the line number for error messages
import collections                          # dictionary sorting 


# Configurations
localWD =    "/home/cjn/RCloneSyncWD/"      # File lists for the local and remote trees as of last sync, etc.
maxDelta = 50                               # % deleted allowed, else abort.  Use --Force to override.


logging.basicConfig(format='%(asctime)s/%(levelname)s:  %(message)s')   # /%(module)s/%(funcName)s

localListFile = remoteListFile = ""         # On critical error, these files are deleted, requiring a --FirstSync to recover.
RTN_ABORT = 1                               # Tokens for return codes based on criticality.
RTN_CRITICAL = 2                            # Aborts allow rerunning.  Criticals block further runs.  See Readme.md.


def bidirSync():

    global localListFile, remoteListFile

    def printMsg (locale, msg, key=''):
        return "{:9}{:35} - {}".format(locale, msg, key)

    excludes = ' '
    if exclusions:
        if not os.path.exists(exclusions):
            logging.error ("Specified Exclusions file does not exist:  " + exclusions)
            return RTN_ABORT
        excludes = " --exclude-from " + exclusions + ' '

    localListFile  = localWD + remoteName[0:-1] + '_localLSL'          # Delete the ':' on the end
    remoteListFile = localWD + remoteName[0:-1] + '_remoteLSL'

    _dryRun = ' '
    if dryRun:
        _dryRun = '--dry-run'       # string used on rclone invocations
        if os.path.exists (localListFile):
            subprocess.call (['cp', localListFile, localListFile + 'DRYRUN'])
            localListFile  += 'DRYRUN'
        if os.path.exists (remoteListFile):
            subprocess.call (['cp', remoteListFile, remoteListFile + 'DRYRUN'])
            remoteListFile += 'DRYRUN'


    # ***** FIRSTSYNC generate local and remote file lists, and copy any unique Remote files to Local *****
    if firstSync:
        logging.info (">>>>> Generating --FirstSync Local and Remote lists")
        with open(localListFile, "w") as of:
            if subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of):
                logging.error (printMsg ("*****", "Failed rclone lsl.  Specified --LocalRoot invalid?  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), localRoot)); return RTN_CRITICAL

        with open(remoteListFile, "w") as of:
            if subprocess.call(shlex.split("rclone lsl " + remoteNameSP + excludes), stdout=of):
                logging.error (printMsg ("*****", "Failed rclone lsl.  Specified --Cloud invalid?  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), remoteName)); return RTN_CRITICAL

        status, localNow  = loadList (localListFile)
        if status:  logging.error (printMsg ("*****", "Failed loading local list file <{}>".format(localListFile))); return RTN_CRITICAL

        status, remoteNow = loadList (remoteListFile)
        if status:  logging.error (printMsg ("*****", "Failed loading remote list file <{}>".format(remoteListFile))); return RTN_CRITICAL

        for key in remoteNow:
            if key not in localNow:
                src  = '"' + remoteName + key + '" '            # Extra space for shlex.split
                dest = '"' + localRoot + '/' + key + '" '
                logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                if subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun)):
                    logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL

        with open(localListFile, "w") as of:                    # Update local list file, then fall into regular sync
            if subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of):
                logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), localRoot)); return RTN_CRITICAL


    # ***** Check for existance of prior local and remote lsl files *****
    if not os.path.exists (localListFile) or not os.path.exists (remoteListFile):
        logging.error ("***** Cannot find prior local or remote lsl files."); return RTN_CRITICAL


    # ***** Check basic health of access to the local and remote filesystems *****
    if checkAccess:
        logging.info (">>>>> Checking rclone Local and Remote filesystems access health")
        localChkListFile  = localWD + remoteName[0:-1] + '_localChkLSL'          # Delete the ':' on the end
        remoteChkListFile = localWD + remoteName[0:-1] + '_remoteChkLSL'
        chkFile = 'RCLONE_TEST'

        with open(localChkListFile, "w") as of:
            if subprocess.call(shlex.split("rclone lsl " + localRootSP + '--include ' + chkFile), stdout=of):
                logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), localRoot)); return RTN_CRITICAL

        with open(remoteChkListFile, "w") as of:
            if subprocess.call(shlex.split("rclone lsl " + remoteNameSP + '--include ' + chkFile), stdout=of):
                logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), remoteName)); return RTN_CRITICAL

        status, localCheck  = loadList (localChkListFile)
        if status:  logging.error (printMsg ("*****", "Failed loading local check list file <{}>".format(localChkListFile))); return RTN_CRITICAL

        status, remoteCheck = loadList (remoteChkListFile)
        if status:  logging.error (printMsg ("*****", "Failed loading remote check list file <{}>".format(remoteChkListFile))); return RTN_CRITICAL

        if len(localCheck) < 1 or len(localCheck) != len(remoteCheck):
            logging.error (printMsg ("*****", "Failed access health test:  <{}> local count {}, remote count {}"
                                     .format(chkFile, len(localCheck), len(remoteCheck)), "")); return RTN_CRITICAL
        else:
            for key in localCheck:
                logging.debug ("Check key <{}>".format(key))
                if key not in remoteCheck:
                    logging.error (printMsg ("*****", "Failed access health test:  Local key <{}> not found in remote".format(key), "")); return RTN_CRITICAL

        os.remove(localChkListFile)
        os.remove(remoteChkListFile)


    # ***** Get current listings of the local and remote trees *****
    logging.info (">>>>> Generating Local and Remote lists")

    localListFileNew = localWD + remoteName[0:-1] + '_localLSL_new'
    with open(localListFileNew, "w") as of:
        if subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of):
            logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), localRoot)); return RTN_CRITICAL

    remoteListFileNew = localWD + remoteName[0:-1] + '_remoteLSL_new'
    with open(remoteListFileNew, "w") as of:
        if subprocess.call(shlex.split("rclone lsl " + remoteNameSP + excludes), stdout=of):
            logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), remoteName)); return RTN_CRITICAL


    # ***** Load Current and Prior listings of both Local and Remote trees *****
    status, localPrior = loadList (localListFile)                    # Successful load of the file return status = 0
    if status:                  logging.error (printMsg ("*****", "Failed loading prior local list file <{}>".format(localListFile))); return RTN_CRITICAL
    if len(localPrior) == 0:    logging.error (printMsg ("*****", "Zero length in prior local list file <{}>".format(localListFile))); return RTN_CRITICAL

    status, remotePrior = loadList (remoteListFile)
    if status:                  logging.error (printMsg ("*****", "Failed loading prior remote list file <{}>".format(remoteListFile))); return RTN_CRITICAL
    if len(remotePrior) == 0:   logging.error (printMsg ("*****", "Zero length in prior remote list file <{}>".format(remoteListFile))); return RTN_CRITICAL

    status, localNow = loadList (localListFileNew)
    if status:                  logging.error (printMsg ("*****", "Failed loading current local list file <{}>".format(localListFileNew))); return RTN_ABORT
    if len(localNow) == 0:      logging.error (printMsg ("*****", "Zero length in current local list file <{}>".format(localListFileNew))); return RTN_ABORT

    status, remoteNow = loadList (remoteListFileNew)
    if status:                  logging.error (printMsg ("*****", "Failed loading current remote list file <{}>".format(remoteListFileNew))); return RTN_ABORT
    if len(remoteNow) == 0:     logging.error (printMsg ("*****", "Zero length in current remote list file <{}>".format(remoteListFileNew))); return RTN_ABORT


    # ***** Check for LOCAL deltas relative to the prior sync
    logging.info (printMsg ("LOCAL", "Checking for Diffs", localRoot))
    localDeltas = {}
    localDeleted = 0
    for key in localPrior:
        _newer=False; _older=False; _size=False; _deleted=False
        if key not in localNow:
            logging.info (printMsg ("LOCAL", "  File was deleted", key))
            localDeleted += 1
            _deleted=True            
        else:
            if localPrior[key]['datetime'] != localNow[key]['datetime']:
                if localPrior[key]['datetime'] < localNow[key]['datetime']:
                    logging.info (printMsg ("LOCAL", "  File is newer", key))
                    _newer=True
                else:               # Now local version is older than prior sync
                    logging.info (printMsg ("LOCAL", "  File is OLDER", key))
                    _older=True
            if localPrior[key]['size'] != localNow[key]['size']:
                logging.info (printMsg ("LOCAL", "  File size is different", key))
                _size=True

        if _newer or _older or _size or _deleted:
            localDeltas[key] = {'new':False, 'newer':_newer, 'older':_older, 'size':_size, 'deleted':_deleted}

    for key in localNow:
        if key not in localPrior:
            logging.info (printMsg ("LOCAL", "  File is new", key))
            localDeltas[key] = {'new':True, 'newer':False, 'older':False, 'size':False, 'deleted':False}

    localDeltas = collections.OrderedDict(sorted(localDeltas.items()))      # sort the deltas list
    if len(localDeltas) > 0:
        logging.warning ("  {:4} file change(s) on the Local system {}".format(len(localDeltas), localRoot))


    # ***** Check for REMOTE deltas relative to the last sync
    logging.info (printMsg ("REMOTE", "Checking for Diffs", remoteName))
    remoteDeltas = {}
    remoteDeleted = 0
    for key in remotePrior:
        _newer=False; _older=False; _size=False; _deleted=False
        if key not in remoteNow:
            logging.info (printMsg ("REMOTE", "  File was deleted", key))
            remoteDeleted += 1
            _deleted=True            
        else:
            if remotePrior[key]['datetime'] != remoteNow[key]['datetime']:
                if remotePrior[key]['datetime'] < remoteNow[key]['datetime']:
                    logging.info (printMsg ("REMOTE", "  File is newer", key))
                    _newer=True
                else:               # Now remote version is older than prior sync 
                    logging.info (printMsg ("REMOTE", "  File is OLDER", key))
                    _older=True
            if remotePrior[key]['size'] != remoteNow[key]['size']:
                logging.info (printMsg ("REMOTE", "  File size is different", key))
                _size=True

        if _newer or _older or _size or _deleted:
            remoteDeltas[key] = {'new':False, 'newer':_newer, 'older':_older, 'size':_size, 'deleted':_deleted}

    for key in remoteNow:
        if key not in remotePrior:
            logging.info (printMsg ("REMOTE", "  File is new", key))
            remoteDeltas[key] = {'new':True, 'newer':False, 'older':False, 'size':False, 'deleted':False}

    remoteDeltas = collections.OrderedDict(sorted(remoteDeltas.items()))    # sort the deltas list
    if len(remoteDeltas) > 0:
        logging.warning ("  {:4} file change(s) on {}".format(len(remoteDeltas), remoteName))


    # ***** Check for too many deleted files - possible error condition and don't want to start deleting on the other side !!!
    tooManyLocalDeletes = False
    if not force and float(localDeleted)/len(localPrior) > float(maxDelta)/100:
        logging.error ("Excessive number of deletes (>{}%, {} of {}) found on the Local system {} - Aborting.  Run with --Force if desired."
                       .format (maxDelta, localDeleted, len(localPrior), localRoot))
        tooManyLocalDeletes = True

    tooManyRemoteDeletes = False    # Local error message placed here so that it is at the end of the listed changes for both
    if not force and float(remoteDeleted)/len(remotePrior) > float(maxDelta)/100:
        logging.error ("Excessive number of deletes (>{}%, {} of {}) found on the Remote system {} - Aborting.  Run with --Force if desired."
                       .format (maxDelta, remoteDeleted, len(remotePrior), remoteName))
        tooManyRemoteDeletes = True

    if tooManyLocalDeletes or tooManyRemoteDeletes: return RTN_ABORT


    # ***** Update LOCAL with all the changes on REMOTE *****
    if len(remoteDeltas) == 0:
        logging.info (">>>>> No changes on Remote - Skipping ahead")
    else:
        logging.info (">>>>> Applying changes on Remote to Local")

    for key in remoteDeltas:

        if remoteDeltas[key]['new']:
            #logging.info (printMsg ("REMOTE", "  New file", key))
            if key not in localNow:
                # File is new on remote, does not exist on local
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '" '
                logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                if subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun)):
                    logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL
            else:
                # File is new on remote AND new on local
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '_REMOTE' + '" '
                logging.warning (printMsg ("*****", "  Changed in both local and remote", key))
                logging.warning (printMsg ("REMOTE", "  Copying to local", dest))
                if subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun)):
                    logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL
                # Rename local
                src  = '"' + localRoot + '/' + key + '" '
                dest = '"' + localRoot + '/' + key + '_LOCAL' + '" '
                logging.warning (printMsg ("LOCAL", "  Renaming local copy", dest))
                if subprocess.call(shlex.split("rclone moveto " + src + dest + _dryRun)):
                    logging.error (printMsg ("*****", "Failed rclone moveto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL


        if remoteDeltas[key]['newer']:
            if key not in localDeltas:
                # File is newer on remote, unchanged on local
                src  = '"' + remoteName + key + '" '
                dest = '"' + localRoot + '/' + key + '" '
                logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                if subprocess.call(shlex.split("rclone copyto " + src + dest + "--ignore-times " + _dryRun)):
                    logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL
            else:
                if key in localNow:
                    # File is newer on remote AND also changed (newer/older/size) on local
                    src  = '"' + remoteName + key + '" '
                    dest = '"' + localRoot + '/' + key + '_REMOTE' + '" '
                    logging.warning (printMsg ("*****", "  Changed in both local and remote", key))
                    logging.warning (printMsg ("REMOTE", "  Copying to local", dest))
                    if subprocess.call(shlex.split("rclone copyto " + src + dest + "--ignore-times " + _dryRun)):
                        logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL
                    # Rename local
                    src  = '"' + localRoot + '/' + key + '" '
                    dest = '"' + localRoot + '/' + key + '_LOCAL' + '" '
                    logging.warning (printMsg ("LOCAL", "  Renaming local copy", dest))
                    if subprocess.call(shlex.split("rclone moveto " + src + dest + _dryRun)):
                        logging.error (printMsg ("*****", "Failed rclone moveto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL
                else:
                    # File is newer on remote AND also deleted locally
                    src  = '"' + remoteName + key + '" '
                    dest = '"' + localRoot + '/' + key + '" '
                    logging.info (printMsg ("REMOTE", "  Copying to local", dest))
                    if subprocess.call(shlex.split("rclone copyto " + src + dest + "--ignore-times " + _dryRun)):
                        logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL
                    

        if remoteDeltas[key]['deleted']:
            #logging.info (printMsg ("REMOTE", "  File was deleted", key))
            if key not in localDeltas:
                if key in localNow:
                    # File is deleted on remote, unchanged locally
                    src  = '"' + localRoot + '/' + key + '" '
                    logging.info (printMsg ("LOCAL", "  Deleting file", src))
                    if subprocess.call(shlex.split("rclone delete " + src + _dryRun)):
                        logging.error (printMsg ("*****", "Failed rclone delete.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL

                    # File is deleted on remote AND changed (newer/older/size) on local
                    # Local version survives
##            else:
##                if key in localNow:
##                    src  = '"' + localRoot + '/' + key + '" '
##                    dest = '"' + localRoot + '/' + key + '_LOCAL' + '" '
##                    logging.warning (printMsg ("*****", "  Also changed locally", key))
##                    logging.warning (printMsg ("LOCAL", "  Renaming local", dest))
##                    if subprocess.call(shlex.split("rclone moveto " + src + dest + _dryRun)):
##                        logging.error (printMsg ("*****", "Failed rclone moveto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL

    for key in localDeltas:
        if localDeltas[key]['deleted']:
            if (key in remoteDeltas) and (key in remoteNow):
                # File is deleted on local AND changed (newer/older/size) on remote
                src  = '"' + remoteName + key + '"'
#                dest = '"' + localRoot + '/' + key + '_REMOTE' + '"'
                dest = '"' + localRoot + '/' + key + '"'
                logging.warning (printMsg ("*****", "  Deleted locally and also changed remotely", key))
                logging.warning (printMsg ("REMOTE", "  Copying to local", dest))
                if subprocess.call(shlex.split("rclone copyto " + src + dest + _dryRun)):
                    logging.error (printMsg ("*****", "Failed rclone copyto.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), src)); return RTN_CRITICAL


    # ***** Sync LOCAL changes to REMOTE ***** 
    if len(remoteDeltas) == 0 and len(localDeltas) == 0 and not firstSync:
        logging.info (">>>>> No changes on Local - Skipping sync from Local to Remote")
    else:
        logging.info (">>>>> Synching Local to Remote")
        if verbose:  syncVerbosity = '--verbose '
        else:        syncVerbosity = ' '
        switches = ' ' #'--ignore-size '

        if subprocess.call(shlex.split("rclone sync " + localRootSP + remoteNameSP + syncVerbosity + switches + excludes + _dryRun)):
            logging.error (printMsg ("*****", "Failed rclone sync.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), "")); return RTN_CRITICAL

        logging.info (">>>>> rmdirs Remote")
        if subprocess.call(shlex.split("rclone rmdirs " + remoteNameSP + _dryRun)):
            logging.error (printMsg ("*****", "Failed rclone rmdirs.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), remoteName)); return RTN_CRITICAL

        logging.info (">>>>> rmdirs Local")
        if subprocess.call(shlex.split("rclone rmdirs " + localRootSP + _dryRun)):
            logging.error (printMsg ("*****", "Failed rclone rmdirs.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), localRoot)); return RTN_CRITICAL


    # ***** Clean up *****
    logging.info (">>>>> Refreshing Local and Remote lsl files")
    os.remove(remoteListFileNew)
    os.remove(localListFileNew)
    with open(localListFile, "w") as of:
        if subprocess.call(shlex.split("rclone lsl " + localRootSP + excludes), stdout=of):
            logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), localRoot)); return RTN_CRITICAL
    with open(remoteListFile, "w") as of:
        if subprocess.call(shlex.split("rclone lsl " + remoteNameSP + excludes), stdout=of):
            logging.error (printMsg ("*****", "Failed rclone lsl.  (Line {})".format(inspect.getframeinfo(inspect.currentframe()).lineno-1), remoteName)); return RTN_CRITICAL




lineFormat = re.compile('\s*([0-9]+) ([\d\-]+) ([\d:]+).([\d]+) (.*)')

def loadList (infile):
    # Format ex:
    #  3009805 2013-09-16 04:13:50.000000000 12 - Wait.mp3
    #   541087 2017-06-19 21:23:28.610000000 DSC02478.JPG
    #    size  <----- datetime (epoch) ----> key

    d = {}
    try:
        with open(infile, 'r') as f:
            for line in f:
                out = lineFormat.match(line)
                if out:
                    size = out.group(1)
                    date = out.group(2)
                    _time = out.group(3)
                    microsec = out.group(4)
                    date_time = time.mktime(datetime.strptime(date + ' ' + _time, '%Y-%m-%d %H:%M:%S').timetuple()) + float('.'+ microsec)
                    filename = out.group(5)
                    d[filename] = {'size': size, 'datetime': date_time}
                else:
                    logging.warning ("Something wrong with this line (ignored) in {}:\n   <{}>".format(infile, line))

        return 0, collections.OrderedDict(sorted(d.items()))        # return Success and a sorted list
    except:
        logging.error ("Exception in loadList loading <{}>:  <{}>".format(infile, sys.exc_info()))
        return 1, ""                                                # return False


lockfile = "/tmp/RCloneSync_LOCK"
def requestLock (caller):
    for xx in range(5):
        if os.path.exists(lockfile):
            with open(lockfile) as fd:
                lockedBy = fd.read()
                logging.debug ("{}.  Waiting a sec.".format(lockedBy[:-1]))   # remove the \n
            time.sleep (1)
        else:  
            with open(lockfile, 'w') as fd:
                fd.write("Locked by {} at {}\n".format(caller, time.asctime(time.localtime())))
                logging.debug ("LOCKed by {} at {}.".format(caller, time.asctime(time.localtime())))
            return 0
    logging.warning ("Timed out waiting for LOCK file to be cleared.  {}".format(lockedBy))
    return -1

def releaseLock (caller):
    if os.path.exists(lockfile):
        with open(lockfile) as fd:
            lockedBy = fd.read()
            logging.debug ("Removed lock file:  {}.".format(lockedBy))
        os.remove(lockfile)
        return 0
    else:
        logging.warning ("<{}> attempted to remove /tmp/LOCK but the file does not exist.".format(caller))
        return -1
        


if __name__ == '__main__':

    logging.warning ("***** BiDirectional Sync for Cloud Services using RClone *****")

    try:
        clouds = subprocess.check_output(['rclone', 'listremotes'])
    except subprocess.CalledProcessError, e:
        logging.error ("ERROR***** Can't get list of known remotes.  Have you run rclone config?")
        exit()
    except:
        logging.error ("ERROR***** rclone not installed?\nError message: {}\n".format(sys.exc_info()[1]))
        exit()
    clouds = clouds.split()

    parser = argparse.ArgumentParser(description="***** BiDirectional Sync for Cloud Services using RClone *****")
    parser.add_argument('Cloud',        help="Name of remote cloud service", choices=clouds)
    parser.add_argument('LocalRoot',    help="Path to local root", default=None)
    parser.add_argument('--FirstSync',  help="First run setup.  WARNING: Local files may overwrite Remote versions.  Also asserts --Verbose.", action='store_true')
    parser.add_argument('--CheckAccess',help="Ensure expected RCLONE_TEST files are found on both Local and Remote filesystems, else abort.", action='store_true')
    parser.add_argument('--Force',      help="Bypass maxDelta ({}%%) safety check and run the sync.  Also asserts --Verbose.".format(maxDelta), action='store_true')
    parser.add_argument('--ExcludeListFile', help="File containing rclone file/path exclusions (Needed for Dropbox)", default=None)
    parser.add_argument('--Verbose',    help="Event logging with per-file details (Python INFO level - default is WARNING level)", action='store_true')
    parser.add_argument('--DryRun',     help="Go thru the motions - No files are copied/deleted.  Also asserts --Verbose.", action='store_true')
    args = parser.parse_args()

    remoteName   = args.Cloud
    remoteNameSP = remoteName + ' '           # Space on end added to keep the subprocess call code clean
    localRoot    = args.LocalRoot
    localRootSP  = args.LocalRoot + ' '
    firstSync    = args.FirstSync
    checkAccess  = args.CheckAccess
    verbose      = args.Verbose
    exclusions   = args.ExcludeListFile
    dryRun       = args.DryRun
    force        = args.Force

    if verbose or force or firstSync or dryRun:
        logging.getLogger().setLevel(logging.INFO)      # Log each file transaction
    else:
        logging.getLogger().setLevel(logging.WARNING)   # Log only unusual events

    if requestLock (sys.argv) == 0:
        status = bidirSync()
        if status == RTN_CRITICAL:
            logging.error ('***** Critical Error Abort - Must run --FirstSync to recover.  See Readme.md *****')
            if os.path.exists (localListFile):   subprocess.call (['mv', localListFile, localListFile + '_ERROR'])
            if os.path.exists (remoteListFile):  subprocess.call (['mv', remoteListFile, remoteListFile + '_ERROR'])
        if status == RTN_ABORT:            
            logging.error ('***** Error abort.  Try running the sync again. *****')
        releaseLock (sys.argv)
    else:  logging.warning ("Prior lock file in place.  Aborting.")
    logging.warning (">>>>> All done.\n\n")
