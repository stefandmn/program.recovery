# -*- coding: utf-8 -*-

import sys
import commons
import urlparse
from resources.lib.SystemRecovery import SystemRecovery


# the program mode
mode = -1
params = {}
if len(sys.argv) > 1:
	for i in sys.argv:
		args = i
		if args.startswith('?'):
			args = args[1:]
		params.update(dict(urlparse.parse_qsl(args)))

if "mode" in params:
	if params['mode'] == 'backup':
		mode = 0
	elif params['mode'] == 'restore':
		mode = 1

if mode == -1:
	mode = commons.SelectDialog(options=[commons.translate(30016), commons.translate(30017)])

# check if program should be run
if mode != -1:
	# run the profile backup
	recovery = SystemRecovery()
	if recovery.isRemote():
		if mode == recovery.Restore:
			# get list of valid restore points
			restorePoints = recovery.listBackups()
			pointNames = []
			folderNames = []
			for aDir in restorePoints:
				pointNames.append(aDir[1])
				folderNames.append(aDir[0])
			selectedRestore = -1
			if "archive" in params:
				# check that the user give archive exists
				if params['archive'] in folderNames:
					# set the index
					selectedRestore = folderNames.index(params['archive'])
					commons.debug(str(selectedRestore) + ": " + params['archive'])
				else:
					commons.DlgNotificationMsg(commons.translate(30045), time=5000)
					commons.debug(params['archive'] + ' is not a valid restore point')
			else:
				# allow user to select the backup to restore from
				mode = commons.SelectDialog(commons.translate(30021), pointNames)
			if selectedRestore != -1:
				recovery.doSelectRestore(restorePoints[selectedRestore][0])
				commons.DlgNotificationMsg(commons.translate(30055), time=5000)
		elif mode == recovery.Backup:
			commons.DlgNotificationMsg(commons.translate(30054), time=5000)
		# execute selected operation (Backup or Restore)
		execute = recovery.run(mode)
		if execute:
			if mode == recovery.Restore:
				commons.DlgNotificationMsg(commons.translate(30057), time=5000)
				commons.sleep(5000)
				if commons.YesNoDialog(commons.translate(30058)):
					commons.restart()
			elif mode == recovery.Backup:
				commons.DlgNotificationMsg(commons.translate(30056), time=5000)
	else:
		# can't go any further
		commons.OkDialog(commons.translate(30045))
		commons.Addon().openSettings()
