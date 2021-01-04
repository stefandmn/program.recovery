# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import common

if hasattr(sys.modules["__main__"], "xbmc"):
	xbmc = sys.modules["__main__"].xbmc
else:
	import xbmc

if hasattr(sys.modules["__main__"], "xbmcvfs"):
	xbmcvfs = sys.modules["__main__"].xbmcvfs
else:
	import xbmcvfs



class FileSystem:
	RootPath = None


	def __init__(self, rootString):
		self.setRootPath(rootString)


	def setRootPath(self, rootString):
		self.RootPath = rootString
		if self.RootPath is not None:
			# fix slashes
			self.RootPath = self.RootPath.replace("\\", "/")
			# check if trailing slash is included
			if self.RootPath[-1:] != "/":
				self.RootPath += "/"


	def listdir(self, directory):
		return {}


	def mkdir(self, directory):
		return True


	def put(self, source, dest):
		return True


	def getFile(self, source):
		return True


	def rmdir(self, directory):
		return True


	def rmfile(self, aFile):
		return True


	def exists(self, aFile):
		return True


	def rename(self, aFile, newName):
		return True


	def cleanup(self):
		return True



class LocalFileSystem(FileSystem):

	def listdir(self, directory):
		return xbmcvfs.listdir(directory)


	def mkdir(self, directory):
		return xbmcvfs.mkdir(xbmc.translatePath(directory))


	def put(self, source, dest):
		return xbmcvfs.copy(xbmc.translatePath(source), xbmc.translatePath(dest))


	def rmdir(self, directory):
		return xbmcvfs.rmdir(directory,True)


	def rmfile(self, aFile):
		return xbmcvfs.delete(aFile)


	def rename(self, aFile, newName):
		return xbmcvfs.rename(aFile, newName)


	def exists(self, aFile):
		# return xbmcvfs.exists(aFile)
		return os.path.exists(aFile)



class ZipFileSystem(FileSystem):
	zip = None

	def __init__(self, rootString, mode):
		FileSystem.__init__(self, rootString)
		self.RootPath = ""
		self.zip = zipfile.ZipFile(rootString,mode=mode,allowZip64=True)


	def listdir(self,directory):
		return [[],[]]


	def mkdir(self,directory):
		#self.zip.write(directory[len(self.root_path):])
		return False


	def put(self,source,dest):
		aFile = xbmcvfs.File(xbmc.translatePath(source),'r')
		self.zip.writestr(dest.encode('UTF-8', 'replace'), aFile.read(), compress_type=zipfile.ZIP_DEFLATED)
		return True


	def rmdir(self,directory):
		return False


	def exists(self,aFile):
		return False


	def cleanup(self):
		self.zip.close()


	def extract(self,path):
		self.zip.extractall(path)



class FileManager:
	fileArray = []
	not_dir = ['.zip','.xsp','.rar']
	vfs = None


	def __init__(self, vfs):
		self.vfs = vfs


	def walkTree(self, directory):
		if self.vfs.exists(directory):
			dirs,files = self.vfs.listdir(directory)
			# create all the subdirs first
			for aDir in dirs:
				dirPath = xbmc.translatePath(directory + "/" + aDir)
				file_ext = aDir.split('.')[-1]
				self.addFile("-" + dirPath)
				# catch for "non directory" type files
				shouldWalk = True
				for s in file_ext:
					if(s in self.not_dir):
						shouldWalk = False
				if shouldWalk:
					self.walkTree(dirPath)
			# copy all the files
			for aFile in files:
				filePath = xbmc.translatePath(directory + "/" + aFile)
				self.addFile(filePath)


	def addFile(self,filename):
		try:
			filename = filename.decode('UTF-8')
		except UnicodeDecodeError:
			filename = filename.decode('ISO-8859-2')
		# write the full remote path name of this file
		common.trace("Add file: " + filename, "FileManager")
		self.fileArray.append(filename)


	def getFiles(self):
		result = self.fileArray
		self.fileArray = []
		return result


	def size(self):
		return len(self.fileArray)
