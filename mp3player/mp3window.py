import os
import math
import threading
from collections import OrderedDict, defaultdict
from typing import Dict, List
import random

import vlc
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from PyQt5 import QtWidgets, uic, Qt, QtGui, QtCore

import mp3player.edit_window as edit_window

__all__ = ["MP3Tag", "MP3File", "MP3Table", "MP3Player"]


class MP3Tag(QtWidgets.QTableWidgetItem):
	'''Initializer for MP3Tag class

	It saves the parent class (MP3File class)

	Arguments:

		mp3file {MP3File} -- Wrapper class for wrapping all tags of MP3File
		tagIdentifier {str} -- Tag identifier (from mutagen library)
		text {str} -- Value of the widget item
	'''
	def __init__(self, mp3file, tagIdentifier, text):
		super(QtWidgets.QTableWidgetItem, self).__init__(text)
		self.mp3file = mp3file

	def getMP3File(self):
		'''Getter for mp3file

		Returns:

			MP3File -- parent MP3 file
		'''
		return self.mp3file


class MP3File(object):
	'''Initializer for MP3File class

	Arguments:

		path {str} -- path to MP3 file
	'''
	property_2_name: OrderedDict = OrderedDict({
		"fileName": "Soubor",  # Not tag, just for general usage
		"songName": "Jméno písně",
		"artist": "Umělec",
		"album": "Album",
		"track": "Stopa",
		"year": "Rok",
		"genre": "Žánr",
		"comment": "Komentář",
		"cover": "Obal",
	})
	property_2_tag: OrderedDict = OrderedDict({
		"fileName": "PATH",  # Not tag, just for general usage
		"songName": "TIT2",
		"artist": "TPE1",
		"album": "TALB",
		"track": "TRCK",
		"year": "TDRC",
		"genre": "TCON",
		"comment": "COMM",
		"cover": "APIC",
	})
	tag_2_property: OrderedDict = OrderedDict({
		"PATH": "fileName",  # Not tag, just for general usage
		"TIT2": "songName",
		"TPE1": "artist",
		"TALB": "album",
		"TRCK": "track",
		"TDRC": "year",
		"TCON": "genre",
		"COMM": "comment",
		"APIC": "cover",
	})
	coverExtensions = ["jpg", "jpeg", "gif", "png"]

	def __init__(self, path):
		super(object, self).__init__()

		self.path = path
		self.baseDir = os.path.dirname(self.path)
		self.baseName = os.path.basename(self.path)

		# Create tags and set empty strings as its value
		self.initProperties()

		# Load Tags from file
		self.fillTagsFromFile()

	def loadCoverImageFromFile(self):
		'''Method is loading cover image (QPixmap) to `image` property from file (by path)
		'''
		# Remove image
		self.image = None

		# Reload image from file
		audio = MP3(self.path, ID3=ID3)
		for key in audio.keys():
			for tag in self.tag_2_property:
				if tag in key:
					if tag == "APIC":
						self.loadCoverImageFromBytes(audio.tags.get(key).data)

	def loadCoverImageFromBytes(self, bytes):
		'''Method is loading cover image (QPixmap) from bytes

		Arguments:

			bytes {BytesIO} -- Bytes containing image (loaded from file or from tags data, or whatever)
		'''
		self.imageBytes = bytes
		self.image = QtGui.QPixmap.fromImage(QtGui.QImage.fromData(self.imageBytes))

	def removeCoverImageFromFile(self):
		'''Removes cover image from mp3file
		'''
		audio = MP3(self.path, ID3=ID3)
		keys = list(audio.keys())
		for key in keys:
			if "APIC" in key:
				audio.pop(key, None)
		audio.save(v2_version=4)
		del audio
		self.imageBytes = None
		self.image = None

	def fillTagsFromFile(self):
		'''Fill tags from file

		It's loading tags from mutagen library and saving it to MP3Tag class (which are this class properties accessed by __getattribute__)
		'''
		# Set correct filename (individual because it's not a tag)
		self.fileName.setText(self.baseName)

		# Load whole file
		audio = MP3(self.path, ID3=ID3)

		# Set correctly all tags
		for key in audio.keys():
			for tag in self.tag_2_property:
				if tag in key:
					if tag == "APIC":
						self.loadCoverImageFromBytes(audio.tags.get(key).data)
					else:
						self.__getattribute__(self.tag_2_property[tag]).setText(str(audio.tags[key].text[0]))

		# Set other informations which are not editable using this editor
		self.songLength = int(audio.info.length)
		self.songBitrate = audio.info.bitrate

		del audio

	def saveTagToFile(self, propertyName, propertyValue):
		'''Save individual tag to file using property name and property value

		Arguments:

			propertyName {[type]} -- [description]
			propertyValue {[type]} -- [description]
		'''
		# TODO add validation (And proper raising)
		# If it's fileName, process it differently
		if propertyName == "fileName":
			self.rename(propertyValue)
		# If it's cover image, process it also differently
		elif propertyName == "cover":
			self.saveCover(propertyValue)
		# Other tags can be processed commonly
		else:
			audio = MP3(self.path, ID3=ID3)
			tag = self.property_2_tag[propertyName]

			# If the tag is empty, remove existing tag or don't create an empty tag
			if propertyValue == "":
				if tag in audio:
					audio.pop(tag)
			else:
				audio[tag] = getattr(mutagen.id3, tag)(encoding=3, text=propertyValue)

			# Save it
			audio.save(v2_version=4)
			del audio

		# Finally make sure that the change is also fastforwarded to Text
		self.__getattribute__(propertyName).setText(str(propertyValue))

	def getProperty(self, propertyName):
		"""Get property value by property name (tag value from tag key)

		Arguments:
			propertyName {str} -- Property name

		Returns:
			str -- Property value
		"""
		return self.__getattribute__(propertyName).text()

	def initProperties(self):
		'''Initialization of all tags and images
		'''
		self.imageBytes = None
		self.image = None
		for key in self.property_2_tag:
			self.__setattr__(key, MP3Tag(self, key, ""))
		self.tmpProperties: Dict = defaultdict(str)

	def canRenameFilename(self, newPath):
		'''Check if the new name of the file can be set (check existing files and empty strings)

		Arguments:

			newPath {str} -- New base name of a file

		Returns:

			bool -- True if can be renamed and False if can not
		'''
		return (not os.path.exists(os.path.join(self.baseDir, newPath)) or newPath == self.baseName) and newPath != ""

	def rename(self, newPath):
		'''Rename mp3 file

		Arguments:

			newPath {str} -- New base name of a file
		'''
		if newPath != self.baseName:
			os.renames(os.path.join(self.baseDir, self.baseName), os.path.join(self.baseDir, newPath))
			self.baseName = newPath
			self.path = os.path.join(self.baseDir, self.baseName)

	def hasCover(self):
		'''Method checks if file has a cover

		Returns:

			bool -- True if file has a cover, False if doesn't
		'''
		audio = MP3(self.path, ID3=ID3)
		for key in audio.keys():
			if "APIC" in key:
				return True
		return False

	def saveCover(self, coverPath):
		'''Save cover image to file

		Arguments:

			coverPath {str} -- Path to cover image
		'''
		# Init audio
		audio = MP3(self.path, ID3=ID3)

		# Remove cover images (do not remove cover if there's cover and coverPath is not set properly)
		if coverPath != "" or not self.hasCover():
			keys = list(audio.keys())
			for key in reversed(keys):
				if "APIC" in key:
					audio.pop(key, None)

		# Change mime type and load and save image
		if coverPath != "":
			extension = coverPath.split(".")[-1].lower()
			if extension == "jpg":
				extension = "jpeg"
			mime = "image/" + extension

			with open(coverPath, "rb") as coverFile:
				img = coverFile.read()
				audio['APIC'] = APIC(
					encoding=3,
					mime=mime,
					type=3,
					data=img
				)
				self.loadCoverImageFromBytes(img)
		audio.save(v2_version=4)
		del audio


class MP3Table(QtWidgets.QTableWidget):
	'''Custom QTableWidget wrapping mp3 file

	Arguments:

		QtWidgets {QTableWidget} -- Base class

	Returns:

		MP3Table -- instance of MP3Table
	'''
	HEADER_CHECK_EMPTY = "[_]"
	HEADER_CHECK_CHECKED = "[X]"

	def __init__(self, *args):
		'''Initializer of MP3Table
		'''
		super(QtWidgets.QTableWidget, self).__init__(*args)

	def setup(self, mainWindow):
		'''Setup function for connecting parent widgets with child widgets

		Arguments:

			mainWindow {QtWidgets.QMainWindow} -- Main window of whole application
		'''
		# Init
		self.mainWindow = mainWindow
		self.createHeaders()

		# Handlers
		self.horizontalHeader().sectionClicked.connect(self.handleHeaderClicked)
		self.cellClicked.connect(self.handleCellClick)

		# Properties
		self.lastSelectedRow = None
		self.lastOrderedColumn = None
		self.lastOrder = None
		self.checkedRows: List = list()

	def isEmpty(self):
		'''Checks if table is empty

		Returns:

			bool -- True if empty, False if not
		'''
		return self.rowCount() == 0

	def checkedRowsCount(self):
		'''Number of checked rows in this table

		Returns:

			int -- Number of checked rows
		'''
		return len(self.checkedRows)

	def getMP3File(self, row):
		'''Get mp3 file wrapper from this table

		Arguments:

			row {int} -- Row to get a mp3 file

		Returns:

			MP3File -- MP3File
		'''
		return self.item(row, 1).mp3file

	def getSelectedRowFromRanges(self):
		'''Get selected row of TableWdiget using selected ranges

		Returns:

			int -- Row index
		'''
		rows = [i.topRow() for i in self.selectedRanges() if i.rightColumn() - i.leftColumn() > 0]
		if len(rows) == 1:
			return rows[0]
		else:
			return None

	def activateRow(self, row):
		'''Activate row of MP3Player

		Arguments:

			row {int} -- Row which should be activated
		'''
		self.lastSelectedRow = row
		self.mainWindow.setMediaFileFromRow(self.lastSelectedRow)

	def handleCellClick(self, row, col):
		'''Handle cell click in the QTableWidget

		Arguments:

			row {int} -- Row of the clicked cell
			col {int} -- Column of the clicked cell
		'''
		# If tag was clicked
		if col > 0:
			selectedRow = self.getSelectedRowFromRanges()
			if selectedRow is not None:
				self.activateRow(selectedRow)
		# If checkbox was clicked
		if col == 0:
			self.toggleRowCheckBox(row)

	def setRangeSelectionByRow(self, row=None):
		'''Set RangeSelected according to the single row given (if not given set it by actual selected row)

		Keyword Arguments:

			row {int} -- Row index which range should be selected (default: {None})
		'''
		row = self.lastSelectedRow if row is None else row
		self.setRangeSelected(QtWidgets.QTableWidgetSelectionRange(0, 0, self.rowCount() - 1, self.columnCount() - 1), False)
		if row is not None:
			self.setRangeSelected(QtWidgets.QTableWidgetSelectionRange(row, 0, row, self.columnCount() - 1), True)

	def activateNextRow(self, deterministic=True):
		'''Activate next row (mp3file)

		Keyword Arguments:

			deterministic {bool} -- Whether to shuffle or not (default: {True})
		'''
		# If MP3 player is not empty
		if not self.isEmpty():
			if self.lastSelectedRow is None:
				self.lastSelectedRow = 0 if deterministic else random.randint(0, self.rowCount() - 1)
			else:
				self.lastSelectedRow = (self.lastSelectedRow + 1) % self.rowCount() if deterministic else (self.lastSelectedRow + random.randint(0, self.rowCount() - 1)) % self.rowCount()

			self.mainWindow.setMediaFileFromRow(self.lastSelectedRow)

	def activatePreviousRow(self, deterministic=True):
		'''Activate previous row (mp3file)

		Keyword Arguments:

			deterministic {bool} -- Whether to shuffle or not (default: {True})
		'''
		# If MP3 player is not empty
		if not self.isEmpty():
			if self.lastSelectedRow is None:
				self.lastSelectedRow = 0 if deterministic else random.randint(0, self.rowCount() - 1)
			else:
				self.lastSelectedRow = (self.lastSelectedRow - 1) % self.rowCount() if deterministic else (self.lastSelectedRow + random.randint(0, self.rowCount() - 1)) % self.rowCount()

			self.mainWindow.setMediaFileFromRow(self.lastSelectedRow)

	def getCheckBox(self, row):
		'''Get Checkbox by row

		Arguments:

			row {int} -- Checkbox's row which we should get

		Returns:

			QtWidgets.QTableWidgetItem -- Checkbox
		'''
		return self.item(row, 0)

	def unCheckRow(self, row):
		'''Uncheck row

		Arguments:

			row {int} -- Which row should be unchecked
		'''
		item = self.getCheckBox(row)
		if item in self.checkedRows:
			self.checkedRows.remove(item)
		item.setCheckState(Qt.Qt.Unchecked)

		self.updateCheckHeader()
		self.mainWindow.updateFilesCheckedLabel()

	def checkRow(self, row):
		'''Check row

		Arguments:

			row {int} -- Which row should be checked
		'''
		item = self.getCheckBox(row)
		if item not in self.checkedRows:
			self.checkedRows.append(item)
		item.setCheckState(Qt.Qt.Checked)

		self.updateCheckHeader()
		self.mainWindow.updateFilesCheckedLabel()

	def toggleRowCheckBox(self, row):
		'''Toggle check on the item specified by row

		Arguments:

			row {int} -- Checkbox's row
		'''
		item = self.getCheckBox(row)
		if item not in self.checkedRows:
			self.checkRow(row)
		else:
			self.unCheckRow(row)

	def checkAllRows(self):
		'''Check all rows
		'''
		for i in range(self.rowCount()):
			self.checkRow(i)

	def unCheckAllRows(self):
		'''Uncheck all rowy
		'''
		for i in range(self.rowCount()):
			self.unCheckRow(i)

	def getCheckedMP3Files(self):
		'''Get all checked mp3 files

		Returns:

			List[MP3File] -- List of MP3File
		'''
		mp3files = [self.getMP3File(i.row()) for i in self.checkedRows]
		return mp3files

	def removeCheckedMP3Files(self):
		'''Remove checked mp3 files (checked rows)
		'''
		for item in sorted(self.checkedRows, key=lambda x: x.row(), reverse=True):
			self.removeMP3(item.row())

	def removeMP3(self, row):
		'''Remove mp3 file (row from table)

		Arguments:

			row {int} -- Row index
		'''
		# Check if the row is in the table
		if row < self.rowCount():
			self.unCheckRow(row)
			self.removeRow(row)

			# If the table will be empty
			if self.isEmpty():
				self.lastSelectedRow = None
				self.mainWindow.setMediaFileFromRow(self.lastSelectedRow)

			# If removed row was before selected row decrease index
			elif self.lastSelectedRow is not None and self.lastSelectedRow > row:
				self.lastSelectedRow -= 1

			# If removed row was selected row decrease index and reload media file
			elif self.lastSelectedRow is not None and self.lastSelectedRow == row:
				self.lastSelectedRow -= 1
				self.mainWindow.setMediaFileFromRow(self.lastSelectedRow)

	def updateCheckHeader(self):
		'''Update checkbox header
		'''
		if self.checkedRowsCount() == self.rowCount():
			self.horizontalHeaderItem(0).setText(self.HEADER_CHECK_CHECKED)
		else:
			self.horizontalHeaderItem(0).setText(self.HEADER_CHECK_EMPTY)

	def createHeaders(self):
		'''Create headers of table
		'''
		header_labels = [self.HEADER_CHECK_EMPTY] + [j for (i, j) in MP3File.property_2_name.items() if i != "cover"]
		self.setColumnCount(len(header_labels))
		self.setHorizontalHeaderLabels(header_labels)
		self.setFocusPolicy(Qt.Qt.NoFocus)
		self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
		self.setColumnWidth(0, 20)

	def addMP3(self, mp3file):
		'''Add MP3 file to table

		Arguments:

			mp3file {MP3File} -- MP3File object which should be inserted to table
		'''
		# Get current number of rows and insert new row
		rowCount = self.rowCount()
		self.insertRow(rowCount)

		# Create checkbox item and insert it
		checkBoxHeader = QtWidgets.QTableWidgetItem()
		checkBoxHeader.setFlags(Qt.Qt.ItemIsUserCheckable | Qt.Qt.ItemIsEnabled)
		checkBoxHeader.setCheckState(Qt.Qt.Unchecked)
		checkBoxHeader.setTextAlignment(Qt.Qt.AlignCenter)
		self.setItem(rowCount, 0, checkBoxHeader)

		# insert all other tags to table
		for idx, key in enumerate(mp3file.property_2_tag):
			if key != "cover":
				self.setItem(rowCount, idx + 1, mp3file.__getattribute__(key))

	def reorderItemsByLastOrder(self):
		'''Reorder items in the table again by using last order
		'''
		if self.lastOrderedColumn is None or self.lastOrder is None:
			self.horizontalHeader().setSortIndicatorShown(False)
		else:
			self.horizontalHeader().setSortIndicatorShown(True)
			self.horizontalHeader().setSortIndicator(self.lastOrderedColumn, self.lastOrder)
			self.sortItems(self.lastOrderedColumn, order=self.lastOrder)

	def sortItems(self, column, order=Qt.Qt.AscendingOrder):
		'''Overriden method of sortItems for saving last ordered column and order type, also for managing select range and index of actual media

		Arguments:

			column {int} -- Column by which it should be order

		Keyword Arguments:

			order {Qt.Qt.QOrder} -- Order type (default: {Qt.Qt.AscendingOrder})
		'''
		self.lastOrderedColumn = column
		self.lastOrder = order

		super().sortItems(column, order=order)

		row = self.getSelectedRowFromRanges()
		if row is not None:
			self.lastSelectedRow = row

	def handleHeaderClicked(self, column):
		'''Handle header clicked (checkbox vs. sorting)

		Arguments:

			column {int} -- Header index clicked
		'''
		# If checkbox is clicked
		if column == 0:
			if self.checkedRowsCount() == self.rowCount():
				self.unCheckAllRows()
			else:
				self.checkAllRows()
			self.reorderItemsByLastOrder()
		else:
			self.horizontalHeader().setSortIndicatorShown(True)
			if self.horizontalHeader().sortIndicatorOrder() == Qt.Qt.AscendingOrder:
				self.horizontalHeader().setSortIndicator(column, Qt.Qt.AscendingOrder)
				self.sortItems(column, order=Qt.Qt.AscendingOrder)
			else:
				self.horizontalHeader().setSortIndicator(column, Qt.Qt.DescendingOrder)
				self.sortItems(column, order=Qt.Qt.DescendingOrder)


class MP3Player(QtWidgets.QMainWindow):
	'''QMainWindow containing mp3 player

	Arguments:

		QtWidgets {QMainWindow} -- Base class

	Raises:

		TypeError -- [description]
		TypeError -- [description]
		FileExistsError -- [description]
		FileNotFoundError -- [description]
		FileNotFoundError -- [description]
		NameError -- [description]

	Returns:

		[type] -- [description]
	'''
	# Play state
	PLAYING = 0
	STOPPED = 1
	PAUSED = 2

	# Shuffle state
	SHUFFLE = 0
	UNSHUFFLE = 1

	# Mute state
	MUTE = 0
	UNMUTE = 1

	def __init__(self):
		'''Initializer
		'''
		super(QtWidgets.QMainWindow, self).__init__()

		# Load UI
		uiFile = "ui/main_window.ui"
		with open(uiFile) as f:
			uic.loadUi(f, self)

		# Init all properties
		self.propertyInit()

		# Connect all signals to handlers
		self.setupHandlers()

		# Setup custom widgets
		self.setupCustomWidgets()

	def setupCustomWidgets(self):
		'''Setup custom widgets (linking parent object to them)
		'''
		self.tableWidget.setup(self)
		self.timeSlider.setup(self)
		self.volumeSlider.setup(self)
		self.tagDialog.setup(self, MP3File.property_2_name, MP3File.property_2_tag)
		self.editWindow.setup(self, MP3File.property_2_name, MP3File.property_2_tag, MP3File.coverExtensions)

	def propertyInit(self):
		'''Property initializer
		'''
		# Player states
		self.playState = self.STOPPED
		self.shuffleState = self.UNSHUFFLE
		self.muteState = self.UNMUTE

		# MP3file
		self.mp3file = None

		# VLC player
		self.media = None
		self.vlcInstance = vlc.Instance()
		self.vlcPlayer = self.vlcInstance.media_player_new()
		self.vlcPlayer.audio_set_volume(100)

		# Init sliders
		self.volume = 100
		self.previousVolume = 100
		self.currentSeconds = 0
		self.songLength = 0
		self.updateVolume(100)
		self.updateTimes(self.currentSeconds, self.songLength)

		# Dialogs and other managed windows
		self.tagDialog = edit_window.TagDialog(self)
		self.editWindow = edit_window.EditWindow(self)

		self.timer = QtCore.QTimer(self)
		self.timer.setSingleShot(False)
		self.timer.timeout.connect(self.updatingPlayerState)
		self.timer.start(200)

	def setupHandlers(self):
		'''Setup handlers to the signals and shortcuts also
		'''
		self.openFileButton.clicked.connect(self.handleOpenFileButton)
		self.chooseImageButton.clicked.connect(self.handleChooseImageButton)
		self.removeFileButton.clicked.connect(self.handleRemoveFileButton)
		self.deleteCoverButton.clicked.connect(self.handleDeleteCoverButton)
		self.guessTagButton.clicked.connect(self.handleGuessTagButton)
		self.guessNameButton.clicked.connect(self.handleGuessNameButton)
		self.saveChangesButton.clicked.connect(self.handleSaveChangesButton)
		self.groupEditButton.clicked.connect(self.handleGroupEditButton)
		self.playButton.clicked.connect(self.handlePlayButton)
		self.stopButton.clicked.connect(self.handleStopButton)
		self.nextButton.clicked.connect(self.handleNextButton)
		self.previousButton.clicked.connect(self.handlePreviousButton)
		self.shuffleButton.clicked.connect(self.handleShuffleButton)
		self.muteButton.clicked.connect(self.handleMuteButton)
		QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self).activated.connect(self.handleSelectAll)
		QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self).activated.connect(self.handleUnSelectAll)
		QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+O"), self).activated.connect(self.handleOpenFileButton)
		QtWidgets.QShortcut(Qt.Qt.Key_Delete, self, self.handleRemoveFileButton)
		QtWidgets.QShortcut(Qt.Qt.Key_Right, self, self.nextSong)
		QtWidgets.QShortcut(Qt.Qt.Key_Left, self, self.previousSong)
		QtWidgets.QShortcut(Qt.Qt.Key_Down, self, self.nextSong)
		QtWidgets.QShortcut(Qt.Qt.Key_Up, self, self.previousSong)
		QtWidgets.QShortcut(Qt.Qt.Key_Space, self, self.togglePlayPause)
		QtWidgets.QShortcut(Qt.Qt.Key_Escape, self, self.focusOut)

	def isPlaying(self):
		'''If mp3 player should be playing

		Returns:

			bool -- True if playing, False if not
		'''
		return self.playState == self.PLAYING

	def isStopped(self):
		'''If mp3 player should be stopped

		Returns:

			bool -- True if stopped, False if not
		'''
		return self.playState == self.STOPPED

	def isPaused(self):
		'''If mp3 player should be paused

		Returns:

			bool -- True if paused, False if not
		'''
		return self.playState == self.PAUSED

	def isShuffleOn(self):
		'''If shuffle is turned on

		Returns:

			bool -- True if yes, False if no
		'''
		return self.shuffleState == self.SHUFFLE

	def isMuted(self):
		'''If volume is muted

		Returns:

			bool -- True if yes, False if no
		'''
		return self.muteState == self.MUTE

	def focusOut(self):
		'''Focus out (for example from line edits)
		'''
		self.setFocus(Qt.Qt.OtherFocusReason)

	def closeEvent(self, event):
		'''If the window is closing, just memorize it happend

		Arguments:

			event {[type]} -- [description]
		'''
		self.closed = True
		event.accept()

	def setEnabled(self, enabled):
		"""Set enabled (pause the music if another modal window have appeared)

		Arguments:
			enabled {bool} -- True/False
		"""
		if not enabled and self.isPlaying():
			self.pause()
		super().setEnabled(enabled)

	def show(self, *args, **kwargs):
		'''Override show method for memorizing that self.closed
		'''
		# Window state
		self.closed = False
		# self.updatingPlayerState()

		super().show(*args, **kwargs)

	def handleSelectAll(self):
		'''Handle select all
		'''
		self.tableWidget.checkAllRows()

	def handleUnSelectAll(self):
		'''Handle unselect all
		'''
		self.tableWidget.unCheckAllRows()

	def clearLineEdits(self):
		'''Clear line edits
		'''
		self.labelImage.hide()
		for key in MP3File.property_2_name:
			self.__getattribute__(key + "Line").setText("")

	def fillLineEdits(self, mp3file=None):
		'''Fill line edits from mp3 file

		Arguments:

			mp3file {MP3File} -- MP3File
		'''
		mp3file = self.mp3file if mp3file is None else mp3file
		if mp3file is not None:
			for key in mp3file.property_2_tag:
				self.__getattribute__(key + "Line").setText(mp3file.__getattribute__(key).text())

	def redrawCoverImage(self):
		'''Redraw cover image
		'''
		if self.mp3file is not None and self.mp3file.image is not None:
			img = self.mp3file.image
			if (img.width() / img.height()) > (self.labelImage.width() / self.labelImage.height()):
				img = img.scaledToWidth(self.labelImage.width())
			else:
				img = img.scaledToHeight(self.labelImage.height())
			self.labelImage.setPixmap(img)
			self.labelImage.show()
		else:
			self.labelImage.hide()

	def setMediaFileFromRow(self, row):
		'''Set media file from row from tableWidget

		Arguments:

			row {int} -- Row index
		'''
		if row is None:
			self.mp3file = None
		else:
			self.mp3file = self.tableWidget.getMP3File(row)

		self.setMediaFileFromMP3File(self.mp3file)
		self.tableWidget.setRangeSelectionByRow(row)

	def setMediaFileFromMP3File(self, mp3file):
		'''Reload MP3File and if player should be playing, play

		Arguments:

			mp3file {MP3File} -- MP3File to be played
		'''
		if mp3file is not None:
			# Load media file to vlc media and if it should be playing and it is not, hit play
			self.media = self.vlcInstance.media_new(mp3file.path)
			self.vlcPlayer.set_media(self.media)
			if self.isPlaying() and not self.vlcPlayer.is_playing():
				self.vlcPlayer.play()

			# Update correct informations
			self.songBitRateLabel.setText(str(self.mp3file.songBitrate))
			self.updateTimes(currentSeconds=0, songLength=self.mp3file.songLength)

			# Fill the tags into the lineEdits and reload CoverImage
			self.fillLineEdits(self.mp3file)
			self.mp3file.loadCoverImageFromFile()
			self.redrawCoverImage()
		else:
			# If there's no file, we should definitely stop and clear media file
			self.stop()
			self.media = None

			# Remove informations and set times to zeros
			self.songBitRateLabel.setText("N/A")
			self.updateTimes(currentSeconds=0, songLength=0)

			# Clear tags and reload cover image (it will be empty)
			self.clearLineEdits()
			self.redrawCoverImage()

	def updatingPlayerState(self):
		'''Update mp3 player state periodically
		'''
		if self.isPlaying() and self.vlcPlayer.get_time() >= self.songLength * 1000:
			self.nextSong()
			# threading.Timer(0.2, self.updatingPlayerState).start()

		if self.isPlaying() or self.isPaused():
			songTime = int(self.vlcPlayer.get_time() * 0.001)
			self.updateTimes(currentSeconds=songTime)

		# if not self.closed:
			# threading.Timer(0.2, self.updatingPlayerState).start()

	def handleChooseImageButton(self):
		'''Handle choose image button, select path and redraw cover image
		'''
		if self.mp3file is None:
			QtWidgets.QMessageBox.warning(self, "Není načtený soubor", "Nebyl načten žádný hudební soubor, nelze vložit obrázek.")
		else:
			path = QtWidgets.QFileDialog.getOpenFileName(self, "Select image cover", filter="images ({})".format(" ".join(["*." + i for i in MP3File.coverExtensions])))[0]
			if path != "":
				self.coverLine.setText(path)
				with open(self.coverLine.text(), "rb") as coverFile:
					self.mp3file.loadCoverImageFromBytes(coverFile.read())
				self.redrawCoverImage()

	def handleOpenFileButton(self):
		'''Handle open file button, create mp3 file and add it to table
		'''
		paths = QtWidgets.QFileDialog.getOpenFileNames(self, "Select MP3 files", filter="mp3(*.mp3)")[0]
		for path in paths:
			mp3file = MP3File(path)
			self.tableWidget.addMP3(mp3file)

	def convertSecsToString(self, secs, hours_digits=0, long_format=False):
		'''Convert seconds to human readable format

		Arguments:

			secs {int} -- Seconds

		Keyword Arguments:

			hours_digits {int} -- How many hour digits to zfill (default: {0})
			long_format {bool} -- If long format is triggered (default: {False})

		Returns:

			str -- string time format
		'''
		hours = secs // 3600
		mins = (secs % 3600) // 60
		secs = secs % 60

		if not long_format:
			if hours_digits == 0 and hours == 0:
				return "{}:{}".format(str(mins).zfill(2), str(secs).zfill(2))
			elif hours_digits == 0 and hours > 0:
				return "{}:{}:{}".format(str(hours), str(mins).zfill(2), str(secs).zfill(2))
			hours_digits = int(math.ceil(math.log10(hours)))
			return "{}:{}:{}".format(str(hours).zfill(hours_digits), str(mins).zfill(2), str(secs).zfill(2))
		else:
			if hours_digits == 0 and hours == 0:
				return "{} mins {} secs".format(str(mins), str(secs))
			elif hours_digits == 0 and hours > 0:
				return "{} hours {} mins {} secs".format(str(hours), str(mins), str(secs))
			hours_digits = int(math.ceil(math.log10(hours)))
			return "{} hours {} mins {} secs".format(str(hours), str(mins), str(secs))

	def updateFilesCheckedLabel(self):
		'''Update how many files are checked
		'''
		self.filesPickedLabel.setText(str(self.tableWidget.checkedRowsCount()))

	def updateTimeFromSlider(self):
		'''Update current time progress of song from slider
		'''
		self.songTimeLabel.setText(self.convertSecsToString(self.timeSlider.maximum()))
		self.songCurrentTimeLabel.setText(self.convertSecsToString(self.timeSlider.sliderPosition()))
		self.songLengthStrLabel.setText(self.convertSecsToString(self.timeSlider.maximum(), long_format=True))
		self.updateTimes(int(self.timeSlider.sliderPosition()), int(self.timeSlider.maximum()), recurse=False)

	def updateTimes(self, currentSeconds=None, songLength=None, recurse=True):
		'''Update song times, it triggers changes of sliders if recurse is set to true

		Keyword Arguments:

			currentSeconds {int} -- Current seconds progress of song (default: {None})
			songLength {int} -- Song length (default: {None})
			recurse {bool} -- If it should trigger change of slider (default: {True})

		Raises:

			TypeError -- [description]
			TypeError -- [description]
		'''

		if currentSeconds is not None and not isinstance(currentSeconds, int):
			raise TypeError("currentSeconds must be integer")

		if songLength is not None and not isinstance(songLength, int):
			raise TypeError("songLength must be integer")

		if currentSeconds is not None and self.currentSeconds != currentSeconds:
			self.currentSeconds = currentSeconds

		if songLength is not None and self.songLength != songLength:
			self.songLength = songLength

		self.songCurrentTimeLabel.setText(self.convertSecsToString(self.currentSeconds))
		self.songTimeLabel.setText(self.convertSecsToString(self.songLength))
		self.songLengthStrLabel.setText(self.convertSecsToString(self.songLength, long_format=True))
		if recurse:
			self.timeSlider.setSliderPosition(self.currentSeconds)
			self.timeSlider.setMaximum(self.songLength)

		if int(self.vlcPlayer.get_time() * 0.001) != self.currentSeconds:
			self.vlcPlayer.set_time(self.currentSeconds * 1000)

	def updateVolumeFromSlider(self):
		'''Update volume from actual slider position
		'''
		self.updateVolume(int(self.volumeSlider.sliderPosition()), recurse=False)

	def updateVolume(self, volume, recurse=True):
		'''Update volume of the player

		Arguments:

			volume {int} -- Volume value

		Keyword Arguments:

			recurse {bool} -- If it should trigger change of slider (default: {True})
		'''

		self.volume = volume
		if self.volume > 0:
			self.muteState = self.UNMUTE
			self.muteButton.setIcon(QtGui.QIcon("ui/icon/unmute.png"))
			self.muteButton.setToolTip("Mute")
		else:
			self.muteState = self.MUTE
			self.muteButton.setIcon(QtGui.QIcon("ui/icon/mute.png"))
			self.muteButton.setToolTip("UnMute")

		if recurse:
			self.volumeSlider.setSliderPosition(self.volume)

		self.vlcPlayer.audio_set_volume(self.volume)

	def mute(self):
		'''Mute player
		'''
		self.previousVolume = self.volume
		self.volume = 0
		self.updateVolume(0)

	def unmute(self):
		'''Unmute player
		'''
		self.volume, self.previousVolume = self.previousVolume, self.volume
		self.updateVolume(self.volume)

	def togglePlayPause(self):
		'''Toggle play or pause
		'''
		if self.isPlaying():
			self.pause()
		else:
			self.play()

	def play(self):
		'''Play the song
		'''
		self.playState = self.PLAYING
		self.playButton.setIcon(QtGui.QIcon("ui/icon/pause.png"))
		self.playButton.setToolTip("Pause")

		self.vlcPlayer.play()

	def stop(self):
		'''Stop the song
		'''
		self.playState = self.STOPPED
		self.playButton.setIcon(QtGui.QIcon("ui/icon/play.png"))
		self.stopButton.setToolTip("Stop")

		self.updateTimes(currentSeconds=0)
		self.vlcPlayer.stop()

	def pause(self):
		'''Pause the song
		'''
		self.playState = self.PAUSED
		self.playButton.setIcon(QtGui.QIcon("ui/icon/play.png"))
		self.playButton.setToolTip("Play")

		self.vlcPlayer.pause()

	def nextSong(self):
		'''Play next song
		'''
		self.tableWidget.activateNextRow(self.shuffleState == self.UNSHUFFLE)

	def previousSong(self):
		'''Play previous song
		'''
		self.tableWidget.activatePreviousRow(self.shuffleState == self.UNSHUFFLE)

	def shuffle(self):
		'''Set shuffle on
		'''
		self.shuffleState = self.SHUFFLE
		self.shuffleButton.setIcon(QtGui.QIcon("ui/icon/unshuffle.png"))
		self.shuffleButton.setToolTip("Switch shuffle off")

	def unshuffle(self):
		'''Set shuffle off
		'''
		self.shuffleState = self.UNSHUFFLE
		self.shuffleButton.setIcon(QtGui.QIcon("ui/icon/shuffle.png"))
		self.shuffleButton.setToolTip("Switch shuffle on")

	def handleRemoveFileButton(self):
		'''Handle remove file button
		'''
		filesCount = self.tableWidget.checkedRowsCount()
		if filesCount > 0:
			if filesCount == 1:
				filesInflected = "vybraný {} soubor".format(filesCount)
			elif filesCount < 5:
				filesInflected = "vybrané {} soubory".format(filesCount)
			else:
				filesInflected = "vybraných {} souborů".format(filesCount)
			msg = "Opravdu chcete odstranit {}?".format(filesInflected)
			reply = QtWidgets.QMessageBox.question(self, 'Message', msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

			if reply == QtWidgets.QMessageBox.Yes:
				self.tableWidget.removeCheckedMP3Files()
		else:
			QtWidgets.QMessageBox.warning(self, "Nevybrané žádné soubory", "Nebyly vybrány žádné soubory pro odstranění.")

		if self.tableWidget.rowCount() == 0 or self.isPlaying():
			self.stop()

	def saveTags(self):
		'''Save tags from lineEdits

		Raises:

			FileExistsError -- Cannot rename file
			FileNotFoundError -- Cover file wasn't found
			NameError -- Image is in wrong format
		'''
		# Check tricky parts
		if not self.mp3file.canRenameFilename(self.fileNameLine.text()):
			raise FileExistsError("Cannot rename file because file already exists!")
		if self.coverLine.text() != "" and not os.path.exists(self.coverLine.text()):
			raise FileNotFoundError("The album image doesnt exists!")
		if self.coverLine.text() != "" and self.coverLine.text().split(".")[-1] not in MP3File.coverExtensions:
			raise NameError("Image is in wrong format")

		# Rename file if needed
		self.mp3file.saveTagToFile("fileName", self.fileNameLine.text())

		# Set album name
		self.mp3file.saveTagToFile("cover", self.coverLine.text())

		# Save all other tags
		if self.mp3file is not None:
			for key, value in self.mp3file.property_2_tag.items():
				if value not in ["APIC", "PATH"]:
					self.mp3file.saveTagToFile(key, self.__getattribute__(key + "Line").text())

	def handleSaveChangesButton(self):
		'''Handle save changes button
		'''
		if self.mp3file is not None:
			try:
				self.saveTags()
				self.redrawCoverImage()
			except FileExistsError:
				QtWidgets.QMessageBox.warning(self, "NNelze přejmenovat soubor", "Nelze přejmenovat soubor, soubor již existuje, nebo byl zadán prázdný řetězec.")
			except FileNotFoundError:
				QtWidgets.QMessageBox.warning(self, "Obrázek alba nenalazen", "Obrázek alba neexistuje.")
			except NameError:
				QtWidgets.QMessageBox.warning(self, "Špatný formát obrázku", "Špatný formát vstupního obrázku alba.")
			except Exception:
				QtWidgets.QMessageBox.warning(self, "Nelze uložit data", "Vyskytla se chyba při ukládání")
			QtWidgets.QMessageBox.information(self, "Uložení proběhlo úspěšně", "Uloženi informací o souboru proběhlo úspěšně.")
		else:
			QtWidgets.QMessageBox.warning(self, "Není načtený soubor", "Nebyl načten žádný hudební soubor, nelze uložit změny.")

	def handleDeleteCoverButton(self):
		'''Handle delete cover album button
		'''
		if self.mp3file is not None and self.mp3file.image is not None:
			msg = "Opravdu chcete odstranit fotku alba?"
			reply = QtWidgets.QMessageBox.question(self, 'Message', msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

			if reply == QtWidgets.QMessageBox.Yes:
				self.mp3file.removeCoverImageFromFile()
				self.coverLine.setText("")
				self.redrawCoverImage()
		else:
			QtWidgets.QMessageBox.warning(self, "Fotka alba neexistuje", "Fotku alba nelze odstranit, protože neexistuje.")

	def handleGuessTagButton(self):
		'''Handle guess tags button
		'''
		if self.tableWidget.checkedRowsCount() > 0:
			self.editWindow.exec(self.tableWidget.getCheckedMP3Files(), None, True, False)
		else:
			QtWidgets.QMessageBox.warning(self, "Nevybrané žádné soubory", "Nebyly vybrány žádné soubory pro odhad tagů.")

	def handleGuessNameButton(self):
		'''Handle guess name button
		'''
		if self.tableWidget.checkedRowsCount() > 0:
			self.editWindow.exec(self.tableWidget.getCheckedMP3Files(), None, False, True)
		else:
			QtWidgets.QMessageBox.warning(self, "Nevybrané žádné soubory", "Nebyly vybrány žádné soubory pro odhad názvu souboru.")

	def handleGroupEditButton(self):
		'''Handle group edit button
		'''
		if self.tableWidget.checkedRowsCount() > 0:
			if self.tagDialog.exec() > 0:
				self.editWindow.exec(self.tableWidget.getCheckedMP3Files(), self.tagDialog.getChoosedProperty(), False)
		else:
			QtWidgets.QMessageBox.warning(self, "Nevybrané žádné soubory", "Nebyly vybrány žádné soubory pro hromadné úpravy.")

	def handlePlayButton(self):
		'''Handle play button
		'''
		if self.isPlaying():
			self.pause()

		elif self.isPaused() or self.isStopped():
			self.play()

	def handleStopButton(self):
		'''Handle stop button
		'''
		self.stop()

	def handleNextButton(self):
		'''Handle next song button
		'''
		self.nextSong()

	def handlePreviousButton(self):
		'''Handle previous song button
		'''
		self.previousSong()

	def handleShuffleButton(self):
		'''Handle shuffle button
		'''
		if self.isShuffleOn():
			self.unshuffle()

		elif not self.isShuffleOn():
			self.shuffle()

	def handleMuteButton(self):
		'''Handle mute button
		'''
		if self.isMuted():
			self.unmute()

		elif not self.isMuted():
			self.mute()