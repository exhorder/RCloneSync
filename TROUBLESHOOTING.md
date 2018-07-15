# Troubleshoot notes 
 
## Reading rclone and RCloneSync logs
RCloneSync's log messages have dashes in the dates, such as `2018-05-26`, and rclone's log messages have slashes in the dates, 
such as `2018/05/26`. This will give you a clue on which layer is complaining.  

Here are two normal runs.  The first has one newer file on the remote.  The second has not deltas between local and remote.  

```
2018-06-12 16:00:01,618/:  ***** BiDirectional Sync for Cloud Services using RClone *****
2018-06-12 16:00:01,627/:  Synching Remote path  <Dropbox:>  with Local path  </path to local tree base/>
2018-06-12 16:00:17,000/:       1 file change(s) on REMOTE:    1 new,    0 newer,    0 older,    0 deleted
2018-06-12 16:00:34,291/:  >>>>> All done.


2018-06-12 18:00:01,095/:  ***** BiDirectional Sync for Cloud Services using RClone *****
2018-06-12 18:00:01,106/:  Synching Remote path  <Dropbox:>  with Local path  </path to local tree base/>
2018-06-12 18:00:20,189/:  >>>>> All done.
```

This run shows an intermittant fail.  Lines 3 and 4 are rlone messages.  Line 5 is a bubbled-up _warning_ message from RCloneSync, conveying
the rclone error.  RCloneSync retries each rclone command up to three times.  Since there are no more error/warning messages, 
the rlone failure recovered on the second try, and the overall sync was successful.

```
2018-06-12 18:30:02,055/:  ***** BiDirectional Sync for Cloud Services using RClone *****
2018-06-12 18:30:02,064/:  Synching Remote path  <Dropbox:>  with Local path  </path to local tree base/>
2018/06/12 18:30:11 ERROR : SW1/GitHub/funcs3/.git/objects/af: error listing: unexpected end of JSON input
2018/06/12 18:30:11 Failed to lsl: unexpected end of JSON input
2018-06-12 18:30:11,723/:    WARNING  rclone lsl try 0 failed.            - Dropbox:
2018-06-12 18:30:22,119/:  >>>>> All done.
```

Rclone also has built in 3x retries.  If you run with `--rcVerbose` you'll see error and retry messages from rclone, such as shown below.
This is normal, not a bug. **If at the end of the run there is no _final_ message indicating an abort or critical (as shown below)
then the overall RCloneSync run was 
successful and any messages can be considered noise, as shown above.**  This log shows a Critical failure which requries a --FirstSync 
to recover from - see the README.md Runtime Error Handling bullet.
```
...
2018/05/26 20:49:40 Google drive root '': Waiting for checks to finish
2018/05/26 20:49:40 Google drive root '': Waiting for transfers to finish
2018/05/26 20:49:40 Google drive root '': not deleting files as there were IO errors
2018/05/26 20:49:40 Attempt 3/3 failed with 3 errors and: not deleting files as there were IO errors
2018/05/26 20:49:40 Failed to sync: not deleting files as there were IO errors
2018-05-26 20:49:40,853/:    WARNING  rclone sync try 2 failed.           - /path to local tree base/
2018-05-26 20:49:40,853/:    ERROR    rclone sync failed.  (Line 384)     - /path to local tree base/
2018-05-26 20:49:40,879/:  ***** Critical Error Abort - Must run --FirstSync to recover.  See README.md *****
2018-05-26 20:49:40,886/:  >>>>> All done.
```

## Run rclone commands manually 
RCloneSync uses rclone lsl, copyto, moveto, delete, sync, and rmdir commands.  To solve a problem, try the operation 
manually from the console, with the rclone's --verbose switch.  Any error messages come right back to you without the big wrapper 
of RCloneSync dealing with the entire sync process.  Learning what rclone is actually doing will aid you greatly in problem solving.

## Rclone bugs?
Rclone gets updated frequently.  Most revs are Beta.  Check the rclone forum (https://github.com/ncw/rclone/issues) for discussion, 
and open issues in the rclone github issues, as appropriate.  Try installing a later or older rclone rev.  A few issues have been
rclone bugs, so it does happen, and I can't do anything about it.


## Illegal filenames
Some cloud services allow characters in filenames thata are not legal on the local filesystem, such as '/', ':'.  RCloneSync will fail 
when attempting to copy these files to the localfilesystem.  See 

## Running from cron
If you run RCloneSync as a cron job, redirect stdout and stderr to a file.  This setup runs a sync to Dropbox
every half hour, and logs all stdout (via the `>>`) and stderr (via `2>&1`) to a log file.  

```
0,30  *  *  *  *   /<path to script>/RCloneSync.py Dropbox: /<path to local>/Dropbox --CheckAccess --ExcludeListFile /<path to user home>/.RCloneSyncWD/Dropbox_Excludes >> /<path to logdir>/Dropbox_runlog 2>&1
```

## Denied downloads of "infected" or "abusive" files 
Google Drive (only?) has a filter for certain file types (.exe, .apk, and ??) that by default cannot be copied from the Remote to the Local. 
Mother is trying to protect you from evil and dirty things (The Wall reference).
See (https://github.com/ncw/rclone/issues/2317).  If you are having problems, run with --Verbose or with --rcVerbose to see
specifically which files are generating complaints.  If the error is `This file has been identified as malware or spam and 
cannot be downloaded.` then you **_may_** wish to add the RCLONE_DRIVE_ACKNOWLEDGE_ABUSE switch for GDrive rclone runs.
See Environment Variables and Config file (https://rclone.org/docs/) for where to find your rclone config file, and adding such switches to 
the config for a specific Remote, or by setting an environment var.  **_Note_** that RCloneSync does not (currently) support random rclone switches
on the RCloneSync command line.  Also **_Note_** that maybe there's a real problem with one of your files.  User beware.

## Running Python version 2.6?

If RCloneSync crashes as follows, you are probably running an unsupported version of python (seen on a CentOS 6 running Python 2.6.6). 
Do a secondary Python install of Python 2.7.x.  See... Google `Python altinstall` on Linux machines (https://docs.python.org/2/using/unix.html) 
and (https://danieleriksson.net/2017/02/08/how-to-install-latest-python-on-centos/). 
**_Note_** that RCloneSync does not (currently) support Python 3.x, but @hildogjr has a fork you may be interested in.  In the bin list 
is 3.x support and version enforcement for graceful failure, rather than this crap:

```
2018-06-12 17:39:44,137/:  ***** BiDirectional Sync for Cloud Services using RClone *****
Traceback (most recent call last):
  File "./RCloneSync.py", line 472, in <module>
    logging.error ("ERROR  rclone not installed?\nError message: {}\n".format(sys.exc_info()[1])); exit()
ValueError: zero length field name in format
```

