# RCloneSync
Python 2.7 cloud sync utility using rclone

Rclone provides a programmatic building block interface for transferring files between a cloud service provider and your local filesystem (actually a lot of functionality), but rclone does not provide a turnkey bidirectional sync capability.  RCloneSync.py provides a bidirectional sync solution.

I use RCloneSync on a Centos 7 box to sync both Dropbox and Google Drive to a local disk which is Samba shared on my LAN.   I run it as a Cron job every 30 minutes, or on-demand from the command line.  RCloneSync was developed and debugged for Google Drive and Dropbox (not tested on other services).  
```
	[RCloneSyncWD]$ ./RCloneSync.py --help
	2017-10-29 12:27:06,904/WARNING:  ***** BiDirectional Sync for Cloud Services using RClone *****
	usage: RCloneSync.py [-h] [--Force] [--FirstSync]
						 [--ExcludeListFile EXCLUDELISTFILE] [--Verbose]
						 [--DryRun]
						 {Dropbox:,GDrive:} LocalRoot

	***** BiDirectional Sync for Cloud Services using RClone ***** 

	positional arguments:
	  {Dropbox:,GDrive:}    Name of remote cloud service
	  LocalRoot             Path to local root

	optional arguments:
	  -h, --help            show this help message and exit
	  --Force               Bypass maxDelta (5%) safety check and run the sync
	  --FirstSync           First run setup. WARNING: Local files may overwrite
							Remote versions
	  --ExcludeListFile EXCLUDELISTFILE
							File containing rclone file/path exclusions (Needed
							for Dropbox)
	  --Verbose             Event logging with per-file details (Python INFO level
							- default is WARNING level)
	  --DryRun              Go thru the motions - No files are copied/deleted
```	

Key behaviors / operations
-  Keeps an rclone lsl file list of the Local and Remote systems.  On each run, checks for deltas on Local and Remote.
-  Applies Remote deltas to the Local filesystem, then rclone syncs the Local to the Remote file system.
-  Handles change conflicts nondestructively by creating _LOCAL and _REMOTE file versions.
-  Somewhat fail safe:
	- Lock file prevents multiple simultaneous runs when taking a while
	- File access health check using RCLONE_TEST files
	- Excessive deletes abort - Protects against a failing lsl being interpreted as all the files were deleted.  See --Force switch

Typical run log:
```
/RCloneSync.py Dropbox:  /mnt/raid1/share/public/DBox/Dropbox --ExcludeListFile /home/xxx/RCloneSyncWD/Dropbox_Excludes --Verbose

2017-10-29 13:05:19,556/WARNING:  ***** BiDirectional Sync for Cloud Services using RClone *****
2017-10-29 13:05:19,565/INFO:  >>>>> Checking rclone Local and Remote access health
2017-10-29 13:05:24,001/INFO:  >>>>> Generating Local and Remote lists
2017-10-29 13:05:28,534/INFO:  LOCAL    Checking for Diffs                  - /mnt/raid1/share/public/DBox/Dropbox
2017-10-29 13:05:28,535/INFO:  LOCAL      File is new                       - Public/imagesCASWV071 - Copy.jpg
2017-10-29 13:05:28,535/WARNING:       1 file change(s) on the Local system /mnt/raid1/share/public/DBox/Dropbox
2017-10-29 13:05:28,535/INFO:  REMOTE   Checking for Diffs                  - Dropbox:
2017-10-29 13:05:28,535/INFO:  REMOTE     File was deleted                  - Public/imagesCAB79VH9a.jpg
2017-10-29 13:05:28,536/WARNING:       1 file change(s) on Dropbox:
2017-10-29 13:05:28,536/INFO:  >>>>> Applying changes on Remote to Local
2017-10-29 13:05:28,536/INFO:  LOCAL      Deleting file                     - "/mnt/raid1/share/public/DBox/Dropbox/Public/imagesCAB79VH9a.jpg" 
2017-10-29 13:05:28,542/INFO:  >>>>> Synching Local to Remote
2017/10/29 13:05:28 INFO  : Dropbox root '': Modify window is 1s
2017/10/29 13:05:30 INFO  : Public/imagesCASWV071 - Copy.jpg: Copied (new)
2017/10/29 13:05:32 INFO  : Dropbox root '': Waiting for checks to finish
2017/10/29 13:05:32 INFO  : Dropbox root '': Waiting for transfers to finish
2017/10/29 13:05:32 INFO  : Waiting for deletions to finish
2017/10/29 13:05:32 INFO  : 
Transferred:   7.925 kBytes (1.833 kBytes/s)
Errors:                 0
Checks:               851
Transferred:            1
Elapsed time:        4.3s

2017-10-29 13:05:32,867/INFO:  >>>>> rmdirs Remote
2017-10-29 13:05:36,902/INFO:  >>>>> rmdirs Local
2017-10-29 13:05:36,911/INFO:  >>>>> Refreshing Local and Remote lsl files
2017-10-29 13:05:41,488/WARNING:  >>>>> All done.
```
