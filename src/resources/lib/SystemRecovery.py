# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import common
from resources.lib.SettingsManager import SettingsManager
from resources.lib.FileSystem import LocalFileSystem, ZipFileSystem, FileManager

if hasattr(sys.modules["__main__"], "xbmc"):
	xbmc = sys.modules["__main__"].xbmc
else:
	import xbmc

if hasattr(sys.modules["__main__"], "xbmcgui"):
	xbmcgui = sys.modules["__main__"].xbmcgui
else:
	import xbmcgui

if hasattr(sys.modules["__main__"], "xbmcvfs"):
	xbmcvfs = sys.modules["__main__"].xbmcvfs
else:
	import xbmcvfs



class SystemRecovery:
	Backup = 0
	Restore = 1

	def __init__(self):
		self.status = 0
		self.localFS = None
		self.remoteFS = None
		self.restoreFile = None
		self.savedRemoteFS = None
		self.remoteBasePath = None
		self.fileManager = None
		self.restorePoint = None
		self.localFS = LocalFileSystem(common.path('special://home'))
		if common.setting('remote_selection') == 1:
			self.remoteBasePath = common.setting('remote_path_2')
			self.remoteFS = LocalFileSystem(common.setting('remote_path_2'))
			common.setAddonSetting("remote_path", "")
		elif common.setting('remote_selection') == 0:
			self.remoteBasePath = common.setting('remote_path')
			self.remoteFS = LocalFileSystem(common.setting("remote_path"))


	def isRemote(self):
		return not (self.remoteBasePath is None or self.remoteBasePath == "")


	def listBackups(self):
		result = []
		# get all the folders in the current root path
		dirs,files = self.remoteFS.listdir(self.remoteBasePath)
		for aDir in dirs:
			if self.remoteFS.exists(self.remoteBasePath + aDir + "/backup.bvf"):
				# folder may or may not contain time, older versions didn't include this
				if len(aDir) > 8:
					folderName = aDir[6:8] + '-' + aDir[4:6] + '-' + aDir[0:4] + " " + aDir[8:10] + ":" + aDir[10:12]
				else:
					folderName = aDir[6:8] + '-' + aDir[4:6] + '-' + aDir[0:4]
				result.append((aDir,folderName))
		for aFile in files:
			file_ext = aFile.split('.')[-1]
			folderName = str(aFile.split('.')[0]).encode('UTF-8', 'replace')
			if file_ext == 'zip' and (len(folderName) == 12 or len(folderName) == 8) and str(folderName).isdigit():
				# folder may or may not contain time, older versions didn't include this
				if len(aFile ) > 8:
					folderName = aFile [6:8] + '-' + aFile [4:6] + '-' + aFile [0:4] + " " + aFile [8:10] + ":" + aFile [10:12]
				else:
					folderName = aFile [6:8] + '-' + aFile [4:6] + '-' + aFile [0:4]
				result.append((aFile, folderName))
		result.sort(key=self.getFolderSortKey)
		return result


	def getFolderSortKey(self, aKey):
		result = aKey[0]
		if len(result) < 8:
			result += "0000"
		return result


	def doSelectRestore(self, restorePoint):
		self.restorePoint = restorePoint


	def backup(self):
		self.status = 0
		# check if remote path exists
		if self.remoteFS.exists(self.remoteFS.RootPath):
			# may be data in here already
			common.debug("Remote path exists - may have old files in it", "SystemRecovery")
		else:
			# make the remote directory
			self.remoteFS.mkdir(self.remoteFS.RootPath)
		# create a validation file for backup rotation
		if not self._createValidationFile():
			# we may not be able to write to this destination for some reason
			common.error("Validation file can not be created, backup process skipped")
			self.status = -1
			return
		common.debug("Creating files list", "SystemRecovery")
		allFiles = []
		fileManager = FileManager(self.localFS)
		# go through each of the user selected items and write them to the backup store
		if common.setting('backup_addons'):
			fileManager.addFile("-" + common.path('special://home/addons'))
			fileManager.walkTree(common.path('special://home/addons'))
		fileManager.addFile("-" + common.path('special://home/userdata'))
		if common.setting('backup_addon_data'):
			fileManager.addFile("-" + common.path('special://home/userdata/addon_data'))
			fileManager.walkTree(common.path('special://home/userdata/addon_data'))
		if common.setting('backup_database'):
			fileManager.addFile("-" + common.path('special://home/userdata/Database'))
			fileManager.walkTree(common.path('special://home/userdata/Database'))
		if common.setting("backup_playlists"):
			fileManager.addFile("-" + common.path('special://home/userdata/playlists'))
			fileManager.walkTree(common.path('special://home/userdata/playlists'))
		if common.setting('backup_profiles'):
			fileManager.addFile("-" + common.path('special://home/userdata/profiles'))
			fileManager.walkTree(common.path('special://home/userdata/profiles'))
		if common.setting("backup_thumbnails"):
			fileManager.addFile("-" + common.path('special://home/userdata/Thumbnails'))
			fileManager.walkTree(common.path('special://home/userdata/Thumbnails'))
		if common.setting("backup_config"):
			fileManager.addFile("-" + common.path('special://home/userdata/keymaps'))
			fileManager.walkTree(common.path('special://home/userdata/keymaps'))
			fileManager.addFile("-" + common.path('special://home/userdata/peripheral_data'))
			fileManager.walkTree(common.path('special://home/userdata/peripheral_data'))
			fileManager.addFile('-' + common.path('special://home/userdata/library'))
			fileManager.walkTree(common.path('special://home/userdata/library'))
			# this part is an oddity
			dirs, configFiles = self.localFS.listdir(common.path('special://home/userdata/'))
			for aFile in configFiles:
				if aFile.endswith(".xml"):
					fileManager.addFile(common.path('special://home/userdata/') + aFile)
		# add to array
		allFiles.append({"source":self.localFS.RootPath, "dest":self.remoteFS.RootPath, "files":fileManager.getFiles()})
		orig_base_path = self.remoteFS.RootPath
		# check if there are custom directories
		if common.setting('custom_dir_1_enable') and common.setting('backup_custom_dir_1') is not None and common.setting('backup_custom_dir_1') != '':
			# create a special remote path with hash
			self.localFS.setRootPath(common.setting('backup_custom_dir_1'))
			fileManager.addFile("-custom_" + self._createCRC(self.localFS.RootPath))
			# walk the directory
			fileManager.walkTree(self.localFS.RootPath)
			allFiles.append({"source":self.localFS.RootPath, "dest":self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath),"files":fileManager.getFiles()})
		if common.setting('custom_dir_2_enable') and common.setting('backup_custom_dir_2') is not None and common.setting('backup_custom_dir_2') != '':
			# create a special remote path with hash
			self.localFS.setRootPath(common.setting('backup_custom_dir_2'))
			fileManager.addFile("-custom_" + self._createCRC(self.localFS.RootPath))
			# walk the directory
			fileManager.walkTree(self.localFS.RootPath)
			allFiles.append({"source":self.localFS.RootPath,"dest":self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath),"files":fileManager.getFiles()})
		if common.setting('custom_dir_3_enable') and common.setting('backup_custom_dir_3') is not None and common.setting('backup_custom_dir_3') != '':
			# create a special remote path with hash
			self.localFS.setRootPath(common.setting('backup_custom_dir_3'))
			fileManager.addFile("-custom_" + self._createCRC(self.localFS.RootPath))
			# walk the directory
			fileManager.walkTree(self.localFS.RootPath)
			allFiles.append({"source":self.localFS.RootPath, "dest":self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath),"files":fileManager.getFiles()})
		# backup all the files
		for fileGroup in allFiles:
			self.localFS.setRootPath(fileGroup['source'])
			self.remoteFS.setRootPath(fileGroup['dest'])
			filesCopied = self.backupFiles(fileGroup['files'], self.localFS, self.remoteFS)
			if not filesCopied:
				common.warn("Not all files were copied: %s" %self.localFS.RootPath, "SystemRecovery")
				self.status += 1
		# reset remote and xbmc vfs
		self.localFS.setRootPath("special://home/")
		self.remoteFS.setRootPath(orig_base_path)
		# send the zip file to the real remote vfs
		if common.setting("compress_backups"):
			zip_name = self.remoteFS.RootPath[:-1] + ".zip"
			self.remoteFS.cleanup()
			self.localFS.rename(common.path("special://temp/MCPiBackup.zip"), common.path("special://temp/" + zip_name))
			fileManager.addFile(common.path("special://temp/" + zip_name))
			# set root to data dir home
			self.localFS.setRootPath(common.path("special://temp/"))
			self.remoteFS = self.savedRemoteFS
			fileCopied = self.backupFiles(fileManager.getFiles(),self.localFS, self.remoteFS)
			if not fileCopied:
				# zip archive copy filed, inform the user
				common.warn("The destination may not be writeable: %s" %self.remoteFS.RootPath)
				self.ststus = -1
				return
			# delete the temp zip file
			self.localFS.rmfile(common.path("special://temp/" + zip_name))
		# remove old backups
		self._rotateBackups()


	def restore(self):
		self.status = 0
		# catch for if the restore point is actually a zip file
		if self.restorePoint.split('.')[-1] == 'zip':
			common.debug("Copying zip file: " + self.restorePoint, "SystemRecovery")
			# set root to data dir home
			self.localFS.setRootPath(common.path("special://temp/"))
			if not self.localFS.exists(common.path("special://temp/" + self.restorePoint)):
				# copy just this file from the remote vfs
				zipFile = []
				zipFile.append(self.remoteBasePath + self.restorePoint)
				self.backupFiles(zipFile,self.remoteFS, self.localFS)
			else:
				common.debug("Zip file exists already", "SystemRecovery")
			# extract the zip file
			zip_vfs = ZipFileSystem(common.path("special://temp/"+ self.restorePoint),'r')
			zip_vfs.extract(common.path("special://temp/"))
			zip_vfs.cleanup()
			# set the new remote vfs and fix xbmc path
			self.remoteFS = LocalFileSystem(common.path("special://temp/" + self.restorePoint.split(".")[0] + "/"))
			self.localFS.setRootPath(common.path("special://home/"))
		# for restores remote path must exist
		if not os.path.isdir(self.remoteFS.RootPath):
			common.error("Error: Remote path doesn't exist: %s" %self.remoteFS.RootPath)
			self.status = -1
			return
		# create a validation file for backup rotation
		if not self._checkValidationFile(self.remoteFS.RootPath):
			common.error("Validation file can not be validated, restore process skipped")
			self.status = -1
			return
		common.debug("Creating files list", "SystemRecovery")
		allFiles = []
		fileManager = FileManager(self.remoteFS)
		# go through each of the user selected items and write them to the backup store
		if common.setting("backup_config"):
			# check for the existance of an advancedsettings file
			if self.remoteFS.exists(self.remoteFS.RootPath + "userdata/advancedsettings.xml"):
				fileManager.addFile(self.remoteFS.RootPath + "userdata/advancedsettings.xml")
			fileManager.addFile('-' + self.remoteFS.RootPath + 'userdata/keymaps')
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/keymaps")
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/peripheral_data")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/peripheral_data")
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/library")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/library")
			# this part is an oddity
			dirs,configFiles = self.remoteFS.listdir(self.remoteFS.RootPath + "userdata/")
			for aFile in configFiles:
				if(aFile.endswith(".xml")):
					fileManager.addFile(self.remoteFS.RootPath + "userdata/" + aFile)
		if common.setting('backup_addons'):
			fileManager.addFile('-' + self.remoteFS.RootPath + "addons")
			fileManager.walkTree(self.remoteFS.RootPath + "addons")
		self.localFS.mkdir(common.path('special://home/userdata'))
		if common.setting('backup_addon_data'):
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/addon_data")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/addon_data")
		if common.setting('backup_database'):
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/Database")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/Database")
		if common.setting("backup_playlists"):
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/playlists")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/playlists")
		if common.setting('backup_profiles'):
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/profiles")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/profiles")
		if common.setting("backup_thumbnails"):
			fileManager.addFile('-' + self.remoteFS.RootPath + "userdata/Thumbnails")
			fileManager.walkTree(self.remoteFS.RootPath + "userdata/Thumbnails")
		# add to array
		allFiles.append({"source":self.remoteFS.RootPath,"dest":self.localFS.RootPath,"files":fileManager.getFiles()})
		# check if there are custom directories
		if common.setting('custom_dir_1_enable') and common.setting('backup_custom_dir_1') is not None and common.setting('backup_custom_dir_1') != '':
			self.localFS.setRootPath(common.setting('backup_custom_dir_1'))
			if self.remoteFS.exists(self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath)):
				# index files to restore
				fileManager.walkTree(self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath))
				allFiles.append({"source":self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath),"dest":self.localFS.RootPath,"files":fileManager.getFiles()})
			else:
				self.status += 1
				common.debug("Error: Remote path doesn't exist: %s" %self.remoteFS.RootPath)
		if common.setting('custom_dir_2_enable') and common.setting('backup_custom_dir_2') is not None and common.setting('backup_custom_dir_2') != '':
			self.localFS.setRootPath(common.setting('backup_custom_dir_2'))
			if self.remoteFS.exists(self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath)):
				# index files to restore
				fileManager.walkTree(self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath))
				allFiles.append({"source":self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath),"dest":self.localFS.RootPath,"files":fileManager.getFiles()})
			else:
				self.status += 1
				common.debug("Error: Remote path doesn't exist: %s" %self.remoteFS.RootPath)
		if common.setting('custom_dir_3_enable') and common.setting('backup_custom_dir_3') is not None and common.setting('backup_custom_dir_3') != '':
			self.localFS.setRootPath(common.setting('backup_custom_dir_3'))
			if self.remoteFS.exists(self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath)):
				# index files to restore
				fileManager.walkTree(self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath))
				allFiles.append({"source":self.remoteFS.RootPath + "custom_" + self._createCRC(self.localFS.RootPath),"dest":self.localFS.RootPath,"files":fileManager.getFiles()})
			else:
				self.status += 1
				common.debug("Error: Remote path doesn't exist: %s" %self.remoteFS.RootPath)
		# restore all the files
		for fileGroup in allFiles:
			self.remoteFS.setRootPath(fileGroup['source'])
			self.localFS.setRootPath(fileGroup['dest'])
			self.backupFiles(fileGroup['files'], self.remoteFS, self.localFS)
		if self.restorePoint.split('.')[-1] == 'zip':
			# delete the zip file and the extracted directory
			self.localFS.rmfile(common.path("special://temp/" + self.restorePoint))
			self.localFS.rmdir(self.remoteFS.RootPath)
		if common.setting("backup_config"):
			# update the guisettings information (or what we can from it)
			gui_settings = SettingsManager('special://home/userdata/guisettings.xml')
			gui_settings.run()
		# call update addons to refresh everything
		xbmc.executebuiltin('UpdateLocalAddons')


	def run(self, mode=-1):
		result = True
		if not common.any2bool(xbmc.getInfoLabel("Window(%s).Property(%s)" % (10000, "PluginRecovery.Running"))):
			# set windows setting to true
			window = xbmcgui.Window(10000)
			window.setProperty("PluginRecovery.Running", "true")
			if self.remoteFS.RootPath is not None and self.remoteFS.RootPath != '':
				common.debug("Local directory: " + self.localFS.RootPath + ", Remote directory: " + self.remoteFS.RootPath, "SystemRecovery")
				if mode == self.Backup:
					if common.setting("compress_backups"):
						# delete old temp file
						if self.localFS.exists(common.path('special://temp/MCPiBackup.zip')):
							self.localFS.rmfile(common.path('special://temp/MCPiBackup.zip'))
						# save the remote file system and use the zip vfs
						self.savedRemoteFS = self.remoteFS
						self.remoteFS = ZipFileSystem(common.path("special://temp/MCPiBackup.zip"),"w")
					self.remoteFS.setRootPath(self.remoteFS.RootPath + time.strftime("%Y%m%d%H%M") + "/")
					# run backup process
					self.backup()
					result = self.status >= 0
				elif mode == self.Restore:
					if self.restorePoint.split('.')[-1] != 'zip':
						self.remoteFS.setRootPath(self.remoteFS.RootPath + self.restorePoint + "/")
					# run restore process
					self.restore()
					result = self.status >= 0
				else:
					result = False
				# cleaning locations
				self.localFS.cleanup()
				self.remoteFS.cleanup()
			else:
				result = False
			# reset the window setting
			window.setProperty("PluginRecovery.Running", "")
		else:
			common.warn('Script already running, no additional instance is needed')
			result = False
		return result


	def backupFiles(self, fileList, source, dest):
		result = True
		common.debug("Writing files to '" + dest.RootPath + "', Source is '" + source.RootPath + "'", "SystemRecovery")
		for aFile in fileList:
			common.debug('Writing file: ' + aFile, "SystemRecovery")
			if aFile.startswith("-"):
				dest.mkdir(dest.RootPath + aFile[len(source.RootPath) + 1:])
			else:
				# copy using normal method
				wroteFile = dest.put(aFile,dest.RootPath + aFile[len(source.RootPath):])
				# if result is still true but this file failed
				if not wroteFile and result:
					result = False
		return result


	def _createCRC(self, string):
		# create hash from string
		string = string.lower()		
		bytes = bytearray(string.encode())
		crc = 0xffffffff
		for b in bytes:
			crc ^= b << 24
			for i in range(8):
				if crc & 0x80000000:
					crc = (crc << 1) ^ 0x04C11DB7				
				else:
					crc <<= 1
					crc &= 0xFFFFFFFF
		return '%08x' % crc


	def _rotateBackups(self):
		total_backups = common.setting('backup_rotation')
		if total_backups > 0:
			# get a list of valid backup folders
			dirs = self.listBackups()
			if len(dirs) > total_backups:
				# remove backups to equal total wanted
				remove_num = 0
				# update the progress bar if it is available
				while remove_num < (len(dirs) - total_backups):
					common.debug("Removing backup " + dirs[remove_num][0], "SystemRecovery")
					if dirs[remove_num][0].split('.')[-1] == 'zip':
						# this is a file, remove it that way
						self.remoteFS.rmfile(self.remoteBasePath + dirs[remove_num][0])
					else:
						self.remoteFS.rmdir(self.remoteBasePath + dirs[remove_num][0] + "/")
					remove_num += 1


	def _createValidationFile(self):
		vFile = xbmcvfs.File(common.path(common.AddonProfile() + "backup.bvf"), 'w')
		vFile.write(json.dumps({"name":"Backup Validation File", "version":xbmc.getInfoLabel('System.BuildVersion')}))
		vFile.write("")
		vFile.close()
		return self.remoteFS.put(common.path(common.AddonProfile() + "backup.bvf"), self.remoteFS.RootPath + "backup.bvf")


	def _checkValidationFile(self, path):
		# copy the file and open it
		self.localFS.put(path + "backup.bvf", common.path(common.AddonProfile() + "backup.bvf"))
		vFile = xbmcvfs.File(common.path(common.AddonProfile() + "backup.bvf"), 'r')
		jsonString = vFile.read()
		vFile.close()
		try:
			json_dict = json.loads(jsonString)
			return xbmc.getInfoLabel('System.BuildVersion') == json_dict['version']
		except ValueError:
			return False
