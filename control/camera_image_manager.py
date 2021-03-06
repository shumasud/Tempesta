# -*- coding: utf-8 -*-
"""
Created on Wed Jun  1 17:29:20 2016

@author: aurelien.barbotin
"""
import subprocess
import sys
import numpy as np
import os
import datetime
import time
import re

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg
import pyqtgraph.ptime as ptime
from pyqtgraph.parametertree import Parameter, ParameterTree

from tkinter import Tk, filedialog, messagebox
import h5py as hdf
import tifffile as tiff     # http://www.lfd.uci.edu/~gohlke/pythonlibs/#vlfd

import control.guitools as guitools


datapath=u"C:\\Users\\aurelien.barbotin\Documents\Data\DefaultDataFolder"

class ImageManager():
    """class used to acquire and display images with a camera. It creates and handles 4 widgets:
    -self.cameraWidget : handles the camera´s parameter
    -self.viewCtrl : 
    -self.recWidget : to record images
    -self.imageWidget : to display images on screen"""
    def __init__(self,camera,main):
        self.orcaflash=camera
        
        self.main=main
        self.changeParameter(lambda: self.orcaflash.setPropertyValue('trigger_polarity', 2))
        self.changeParameter(lambda: self.orcaflash.setPropertyValue('trigger_active', 2))
        self.shape = (self.orcaflash.getPropertyValue('image_height')[0], self.orcaflash.getPropertyValue('image_width')[0])
        self.latest_image = np.zeros(self.shape)
        self.frameStart = (0, 0)
        
        self.tree = CamParamTree(self.orcaflash)

        # Indicator for loading frame shape from a preset setting 
        # Currently not used.
        self.customFrameLoaded = False
        self.cropLoaded = False

        # Camera binning signals. Defines seperate variables for each parameter and connects the signal
        # emitted when they've been changed to a function that actually changes the parameters on the camera
        # or other appropriate action.
        self.framePar = self.tree.p.param('Image frame')
        self.binPar = self.framePar.param('Binning')
        self.binPar.sigValueChanged.connect(self.setBinning)
        self.FrameMode = self.framePar.param('Mode')
        self.FrameMode.sigValueChanged.connect(self.testfunction)
        self.X0par= self.framePar.param('X0')
        self.Y0par= self.framePar.param('Y0')
        self.Widthpar= self.framePar.param('Width')
        self.Heightpar= self.framePar.param('Height')
        self.applyParam = self.framePar.param('Apply')
        self.NewROIParam = self.framePar.param('New ROI')
        self.AbortROIParam = self.framePar.param('Abort ROI')
        self.applyParam.sigStateChanged.connect(self.applyfcn)  #WARNING: This signal is emitted whenever anything about the status of the parameter changes eg is set writable or not.
        self.NewROIParam.sigStateChanged.connect(self.updateFrame)
        self.AbortROIParam.sigStateChanged.connect(self.AbortROI)


        
        # Exposition signals
        timingsPar = self.tree.p.param('Timings')
        self.EffFRPar = timingsPar.param('Internal frame rate')
        self.expPar = timingsPar.param('Set exposure time')
        self.expPar.sigValueChanged.connect(self.setExposure)
        self.ReadoutPar = timingsPar.param('Readout time')
        self.RealExpPar = timingsPar.param('Real exposure time')
        self.FrameInt = timingsPar.param('Internal frame interval')
        self.RealExpPar.setOpts(decimals = 5)
        self.setExposure()    # Set default values
        
        #Acquisition signals
        acquisParam = self.tree.p.param('Acquisition mode')
        self.trigsourceparam = acquisParam.param('Trigger source')
        self.trigsourceparam.sigValueChanged.connect(self.ChangeTriggerSource)

        # Gain signals
#        self.PreGainPar = self.tree.p.param('Gain').param('Pre-amp gain')
#        updateGain = lambda: self.setGain
#        self.PreGainPar.sigValueChanged.connect(updateGain)
#        self.GainPar = self.tree.p.param('Gain').param('EM gain')
#        self.GainPar.sigValueChanged.connect(updateGain)
#        updateGain()        # Set default values


#        These attributes are the widgets which will be used in the main script
        self.cameraWidget = QtGui.QFrame()        
        self.viewCtrl = QtGui.QWidget()
        self.recWidget = RecordingWidget(self)
        self.imageWidget = pg.GraphicsLayoutWidget()

        # Camera settings widget
        self.cameraWidget.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Raised)
        cameraTitle = QtGui.QLabel('<h2><strong>Camera settings</strong></h2>')
        cameraTitle.setTextFormat(QtCore.Qt.RichText)
        cameraGrid = QtGui.QGridLayout()
        self.cameraWidget.setLayout(cameraGrid)
        cameraGrid.addWidget(cameraTitle, 0, 0)
        cameraGrid.addWidget(self.tree, 1, 0)
        
      # Liveview functionality
        self.liveviewButton = QtGui.QPushButton('LIVEVIEW')
        self.liveviewButton.setStyleSheet("font-size:18px")
        self.liveviewButton.setCheckable(True)
        self.liveviewButton.setSizePolicy(QtGui.QSizePolicy.Preferred,
                                          QtGui.QSizePolicy.Expanding)
        self.liveviewButton.clicked.connect(self.liveview)      #Link button click to funciton liveview
        self.liveviewButton.setEnabled(True)
        self.viewtimer = QtCore.QTimer()
        self.viewtimer.timeout.connect(self.updateView)
        
        
        self.viewCtrlLayout = QtGui.QGridLayout()
        self.viewCtrl.setLayout(self.viewCtrlLayout)
        self.viewCtrlLayout.addWidget(self.liveviewButton, 0, 0, 1, 3)
        
#        self.viewCtrlLayout.addWidget(self.gridButton, 1, 0)
#        self.viewCtrlLayout.addWidget(self.grid2Button, 1, 1)
#        self.viewCtrlLayout.addWidget(self.crosshairButton, 1, 2)
#        self.viewCtrlLayout.addWidget(self.flipperButton, 2, 0, 1, 3)

        self.fpsBox = QtGui.QLabel()
        self.fpsBox.setText('0 fps')
        self.main.statusBar().addPermanentWidget(self.fpsBox)
        self.tempStatus = QtGui.QLabel()
        self.main.statusBar().addPermanentWidget(self.tempStatus)
        self.temp = QtGui.QLabel()
        self.main.statusBar().addPermanentWidget(self.temp)
        self.cursorPos = QtGui.QLabel()
        self.cursorPos.setText('0, 0')
        self.main.statusBar().addPermanentWidget(self.cursorPos)

        # Image Widget
        self.vb = self.imageWidget.addViewBox(row=1, col=1)
        self.vb.setMouseMode(pg.ViewBox.RectMode)
        self.img = pg.ImageItem()
        self.lut = guitools.cubehelix()
        self.img.setLookupTable(self.lut)
        self.img.translate(-0.5, -0.5)
#        self.img.setPxMode(True)
        self.vb.addItem(self.img)
        self.vb.setAspectLocked(True)
        self.hist = pg.HistogramLUTItem(image=self.img)
#        self.hist.vb.setLimits(yMin=0, yMax=2048)
        self.imageWidget.addItem(self.hist, row=1, col=2)
        self.ROI = guitools.ROI((0, 0), self.vb, (0, 0),
                                        handlePos=(1, 0), handleCenter=(0, 1),
scaleSnap=True, translateSnap=True)
        self.ROI.sigRegionChangeFinished.connect(self.ROIchanged)
        self.ROI.hide()

        # x and y profiles
        xPlot = self.imageWidget.addPlot(row=0, col=1)
        xPlot.hideAxis('left')
        xPlot.hideAxis('bottom')
        self.xProfile = xPlot.plot()
        self.imageWidget.ci.layout.setRowMaximumHeight(0, 40)
        xPlot.setXLink(self.vb)
        yPlot = self.imageWidget.addPlot(row=1, col=0)
        yPlot.hideAxis('left')
        yPlot.hideAxis('bottom')
        self.yProfile = yPlot.plot()
        self.yProfile.rotate(90)
        self.imageWidget.ci.layout.setColumnMaximumWidth(0, 40)
        yPlot.setYLink(self.vb)

        # Initial camera configuration taken from the parameter tree
        self.orcaflash.setPropertyValue('exposure_time', self.expPar.value())
        self.adjustFrame()
        
    def testfunction(self):
        print('In testfunction ie called from frame mode changed signal')
        self.updateFrame()
        
    def applyfcn(self):
        print('Apply pressed')
        self.adjustFrame()

    def mouseMoved(self, pos):
        if self.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.vb.mapSceneToView(pos)
            x, y = int(mousePoint.x()), int(self.shape[1] - mousePoint.y())
            self.cursorPos.setText('{}, {}'.format(x, y))

    def changeParameter(self, function):
        """ This method is used to change those camera properties that need
        the camera to be idle to be able to be adjusted.
        """
        try:
            function()
        except:

            self.liveviewPause()
            function()
            self.liveviewRun()


    def ChangeTriggerSource(self):
        
        if self.trigsourceparam.value() == 'Internal trigger':
            print('Changing to internal trigger')
            self.changeParameter(lambda: self.orcaflash.setPropertyValue('trigger_source', 1))
#            self.RealExpPar.Enable(True)
#            self.EffFRPar.Enable(True)
            
        elif self.trigsourceparam.value() == 'External trigger':
            print('Changing to external trigger')
            self.changeParameter(lambda: self.orcaflash.setPropertyValue('trigger_source', 2))
#            self.RealExpPar.Enable(False)
#            self.EffFRPar.Enable(False)
            
        else:
            pass
        
    def updateLevels(self, image):
        std = np.std(image)
        self.hist.setLevels(np.min(image) - std, np.max(image) + std)

    def setBinning(self):
        
        """Method to change the binning of the captured frame"""

        binning = str(self.binPar.value())

        binstring = binning+'x'+binning
        coded = binstring.encode('ascii')
        

        self.changeParameter(lambda: self.orcaflash.setPropertyValue('binning', coded))


            
        
#    def setNrrows(self):
#        
#        """Method to change the number of rows of the captured frame"""
#        self.changeParameter(lambda: self.orcaflash.setPropertyValue('subarray_vsize', 8))
#
#    def setNrcols(self):
#        
#        """Method to change the number of rows of the captured frame"""
#        self.changeParameter(lambda: self.orcaflash.setPropertyValue('subarray_hsize', self.nrcolPar.value()))

    def setGain(self):
        """ Method to change the pre-amp gain and main gain of the EMCCD
        """
        pass
#        PreAmpGain = self.PreGainPar.value()
#        n = np.where(self.andor.PreAmps == PreAmpGain)[0][0]
#        # The (2 - n) accounts for the difference in order between the options
#        # in the GUI and the camera settings
#        self.andor.preamp = 2 - n
#        self.andor.EM_gain = self.GainPar.value()

    def setExposure(self):
        """ Method to change the exposure time setting
        """
        self.orcaflash.setPropertyValue('exposure_time', self.expPar.value())
        print('Exp time set to:', self.orcaflash.getPropertyValue('exposure_time'))
#        self.andor.frame_transfer_mode = self.FTMPar.value()
#        hhRatesArr = np.array([item.magnitude for item in self.andor.HRRates])
#        n_hrr = np.where(hhRatesArr == self.HRRatePar.value().magnitude)[0][0]
#        # The (3 - n) accounts for the difference in order between the options
#        # in the GUI and the camera settings
#        self.andor.horiz_shift_speed = 3 - n_hrr
#
#        n_vss = np.where(np.array([item.magnitude
#                                  for item in self.andor.vertSpeeds])
#                         == self.vertShiftSpeedPar.value().magnitude)[0][0]
#        self.andor.vert_shift_speed = n_vss
#
#        n_vsa = np.where(np.array(self.andor.vertAmps) ==
#                         self.vertShiftAmpPar.value())[0][0]
#        self.andor.set_vert_clock(n_vsa)
#
        self.updateTimings()
        
    def cropOrca(self, hpos, vpos, hsize, vsize):
        """Method to crop the fram read out by Orcaflash """
#       Round to closest "divisable by 4" value.
        self.orcaflash.setPropertyValue('subarray_vpos', 0)
        self.orcaflash.setPropertyValue('subarray_hpos', 0)
        self.orcaflash.setPropertyValue('subarray_vsize', 2048)
        self.orcaflash.setPropertyValue('subarray_hsize', 2048)

 
        vpos = int(4*np.ceil(vpos/4))
        hpos = int(4*np.ceil(hpos/4))
        vsize = int(min(2048 - vpos, 4*np.ceil(vsize/4)))
        hsize = int(min(2048 - hpos, 4*np.ceil(hsize/4)))

        self.orcaflash.setPropertyValue('subarray_vsize', vsize)
        self.orcaflash.setPropertyValue('subarray_hsize', hsize)
        self.orcaflash.setPropertyValue('subarray_vpos', vpos)
        self.orcaflash.setPropertyValue('subarray_hpos', hpos)
        
        self.frameStart = (hpos, vpos) # Should be only place where self.frameStart is changed
        self.shape = (hsize, vsize)     # Only place self.shape is changed
        
        print('orca has been cropped to: ', vpos, hpos, vsize, hsize)

    def adjustFrame(self):
        """ Method to change the area of the sensor to be used and adjust the
        image widget accordingly. It needs a previous change in self.shape
        and self.frameStart)
        """
        binning = self.binPar.value()

        self.changeParameter(lambda: self.cropOrca(binning*self.X0par.value(), binning*self.Y0par.value(), binning*self.Widthpar.value(), self.Heightpar.value()))

        self.updateTimings()
        self.recWidget.filesizeupdate()
        self.ROI.hide()

    def updateFrame(self):
        """ Method to change the image frame size and position in the sensor
        """
        print('Update frame called')
        frameParam = self.tree.p.param('Image frame')
        if frameParam.param('Mode').value() == 'Custom':
            self.X0par.setWritable(True)
            self.Y0par.setWritable(True)
            self.Widthpar.setWritable(True)
            self.Heightpar.setWritable(True)

#            if not(self.customFrameLoaded):
            ROIsize = (int(0.2 * self.vb.viewRect().width()), int(0.2 * self.vb.viewRect().height()))
            ROIcenter = (int(self.vb.viewRect().center().x()), int(self.vb.viewRect().center().y()))
            ROIpos = (ROIcenter[0] - 0.5*ROIsize[0], ROIcenter[1] - 0.5*ROIsize[1])
            
#            try:
            self.ROI.setPos(ROIpos)
            self.ROI.setSize(ROIsize)
            self.ROI.show()

                
            self.ROIchanged()
            
        else:
            self.X0par.setWritable(False)
            self.Y0par.setWritable(False)
            self.Widthpar.setWritable(False)
            self.Heightpar.setWritable(False)

            
            if frameParam.param('Mode').value() == 'Full Widefield':
                self.X0par.setValue(600)
                self.Y0par.setValue(600)
                self.Widthpar.setValue(900)
                self.Heightpar.setValue(900)
                self.adjustFrame()

                self.ROI.hide()


            elif frameParam.param('Mode').value() == 'Full chip':
                print('Full chip')
                self.X0par.setValue(0)
                self.Y0par.setValue(0)
                self.Widthpar.setValue(2048)
                self.Heightpar.setValue(2048)
                self.adjustFrame()

                self.ROI.hide()
                
            elif frameParam.param('Mode').value() == 'Minimal line':
                print('Full chip')
                self.X0par.setValue(0)
                self.Y0par.setValue(1020)
                self.Widthpar.setValue(2048)
                self.Heightpar.setValue(8)
                self.adjustFrame()

                self.ROI.hide()




#        else:
#            pass
#            side = int(frameParam.param('Mode').value().split('x')[0])
#            self.shape = (side, side)
#            start = int(0.5*(self.andor.detector_shape[0] - side) + 1)
#            self.frameStart = (start, start)
#
#            self.changeParameter(self.adjustFrame)
##            self.applyParam.disable()

    def ROIchanged(self):

        self.X0par.setValue(self.frameStart[0] + int(self.ROI.pos()[0]))
        self.Y0par.setValue(self.frameStart[1] + int(self.ROI.pos()[1]))

        self.Widthpar.setValue(int(self.ROI.size()[0])) # [0] is Width
        self.Heightpar.setValue(int(self.ROI.size()[1])) # [1] is Height
        
        
    def AbortROI(self):
        
        self.ROI.hide()
        
        self.X0par.setValue(self.frameStart[0])
        self.Y0par.setValue(self.frameStart[1])

        self.Widthpar.setValue(self.shape[0]) # [0] is Width
        self.Heightpar.setValue(self.shape[1]) # [1] is Height    

    def updateTimings(self):
        """ Update the real exposition and accumulation times in the parameter
        tree.
        """
#        timings = self.orcaflash.getPropertyValue('exposure_time') 
#        self.t_exp_real, self.t_acc_real, self.t_kin_real = timings
        self.RealExpPar.setValue(self.orcaflash.getPropertyValue('exposure_time')[0])
        self.FrameInt.setValue(self.orcaflash.getPropertyValue('internal_frame_interval')[0])
        self.ReadoutPar.setValue(self.orcaflash.getPropertyValue('timing_readout_time')[0])
        self.EffFRPar.setValue(self.orcaflash.getPropertyValue('internal_frame_rate')[0])
#        RealExpPar.setValue(self.orcaflash.getPropertyValue('exposure_time')[0])
#        RealAccPar.setValue(self.orcaflash.getPropertyValue('accumulation_time')[0])
#        EffFRPar.setValue(1 / self.orcaflash.getPropertyValue('accumulation_time')[0])

    # This is the function triggered by the liveview shortcut
    def liveviewKey(self):

        if self.liveviewButton.isChecked():
            self.liveviewStop()
            self.liveviewButton.setChecked(False)

        else:
            self.liveviewStart(True)
            self.liveviewButton.setChecked(True)

    # This is the function triggered by pressing the liveview button
    def liveview(self):
        """ Image live view when not recording
        """
        if self.liveviewButton.isChecked():
            self.liveviewStart()

        else:
            self.liveviewStop()
            
# Threading below  is done in this way since making LVThread a QThread resulted in QTimer
# not functioning in the thread. Image is now also saved as latest_image in 
# TormentaGUI class since setting image in GUI from thread resultet in 
# issues when interacting with the viewbox from GUI. Maybe due to 
# simultaious manipulation of viewbox from GUI and thread. 

    def liveviewStart(self):

#        self.orcaflash.startAcquisition()
#        time.sleep(0.3)
#        time.sleep(np.max((5 * self.t_exp_real.magnitude, 1)))
        self.updateFrame()
        self.vb.scene().sigMouseMoved.connect(self.mouseMoved)
        self.recWidget.readyToRecord = True
        self.lvworker = LVWorker(self, self.orcaflash)
        self.lvthread = QtCore.QThread()
        self.lvworker.moveToThread(self.lvthread)
        self.lvthread.started.connect(self.lvworker.run)
        self.lvthread.start()
        self.viewtimer.start(30)
        self.liveviewRun()
#        self.liveviewStarts.emit()
#
#        idle = 'Camera is idle, waiting for instructions.'
#        if self.andor.status != idle:
#            self.andor.abort_acquisition()
#
#        self.andor.acquisition_mode = 'Run till abort'
#        self.andor.shutter(0, 1, 0, 0, 0)
#
#        self.andor.start_acquisition()
#        time.sleep(np.max((5 * self.t_exp_real.magnitude, 1)))
#        self.recWidget.readyToRecord = True
#        self.recWidget.recButton.setEnabled(True)
#
#        # Initial image
#        rawframes = self.orcaflash.getFrames()
#        firstframe = rawframes[0][-1].getData() #return A numpy array that contains the camera data. "Circular" indexing makes [-1] return the latest frame
#        self.image = np.reshape(firstframe, (self.orcaflash.frame_y, self.orcaflash.frame_x), order='C')
#        print(self.frame)
#        print(type(self.frame))
#        self.img.setImage(self.image, autoLevels=False, lut=self.lut) #Autolevels = True gives a stange numpy (?) warning
#        image = np.transpose(self.andor.most_recent_image16(self.shape))
#        self.img.setImage(image, autoLevels=False, lut=self.lut)
#        if update:
#            self.updateLevels(image)
#        self.viewtimer.start(0)
#        while self.liveviewButton.isChecked():
#            self.updateView()

#        self.moleculeWidget.enableBox.setEnabled(True)
#        self.gridButton.setEnabled(True)
#        self.grid2Button.setEnabled(True)
#        self.crosshairButton.setEnabled(True)

    def liveviewStop(self):
        self.lvworker.stop()
        self.lvthread.terminate()
        self.viewtimer.stop()
        self.recWidget.readyToRecord = False

        # Turn off camera, close shutter
        self.orcaflash.stopAcquisition()
        self.img.setImage(np.zeros(self.shape), autoLevels=False)
        del self.lvthread

#        self.liveviewEnds.emit()

#    def updateinThread(self):
#        
#        self.recordingThread = QtCore.QThread()
#        self.worker.moveToThread(self.recordingThread)
#        self.recordingThread.started.connect(self.worker.start)
#        self.recordingThread.start()
#        
#        self.updateThread = QtCore.QThread()
#        self.

    def liveviewRun(self):
#        self.lvworker.reset() # Needed if parameter is changed during liveview since that causes camera to start writing to buffer place zero again.
        self.orcaflash.startAcquisition()
#        time.sleep(0.3)
#        self.viewtimer.start(0)
#        self.lvthread.run()
#        self.lvthread.start()
    
    def liveviewPause(self):
        
#        self.lvworker.stop()
#        self.viewtimer.stop()
        self.orcaflash.stopAcquisition()

    def updateView(self):
        """ Image update while in Liveview mode
        """
        rawframes = self.orcaflash.getFrames()
        
        firstframe = rawframes[0][-1].getData() #"Circular indexing" makes [-1] return the latest frame
        self.latest_image=np.reshape(firstframe,self.shape)
        self.img.setImage(self.latest_image, autoLevels=False, autoDownsample = False) 



    def fpsMath(self):
        now = ptime.time()
        dt = now - self.lastTime
        self.lastTime = now
        if self.fps is None:
            self.fps = 1.0/dt
        else:
            s = np.clip(dt * 3., 0, 1)
            self.fps = self.fps * (1 - s) + (1.0/dt) * s
        self.fpsBox.setText('{} fps'.format(int(self.fps)))
        
class RecordingWidget(QtGui.QFrame):

    def __init__(self, main, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.main = main
        self.dataname = 'data'      # In case I need a QLineEdit for this
        try:
            startdir = datapath+u"\\%s"
            newfolderpath =  startdir % time.strftime('%Y-%m-%d')
            if not os.path.exists(newfolderpath):
                os.mkdir(newfolderpath)
        except:
            startdir = u'C:\\Users\TestaRES\Documents\Data\DefaultDataFolder\%s'
            newfolderpath =  startdir % time.strftime('%Y-%m-%d')
            if not os.path.exists(newfolderpath):
                os.mkdir(newfolderpath)

            
        self.initialDir = newfolderpath
        
        self.filesizewar = QtGui.QMessageBox()
        self.filesizewar.setText("File size is very big!")
        self.filesizewar.setInformativeText("Are you sure you want to continue?")
        self.filesizewar.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        
        # Title
        recTitle = QtGui.QLabel('<h2><strong>Recording</strong></h2>')
        recTitle.setTextFormat(QtCore.Qt.RichText)
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Raised)
        
        # Folder and filename fields
        self.folderEdit = QtGui.QLineEdit(self.initialDir)
        openFolderButton = QtGui.QPushButton('Open')
        openFolderButton.clicked.connect(self.openFolder)
        loadFolderButton = QtGui.QPushButton('Load...')
        loadFolderButton.clicked.connect(self.loadFolder)
        self.specifyfile = QtGui.QCheckBox('Specify file name')
        self.specifyfile.clicked.connect(self.specFile)
        self.filenameEdit = QtGui.QLineEdit('Current_time')

        # Snap and recording buttons
        self.snapTIFFButton = QtGui.QPushButton('Snap')
        self.snapTIFFButton.setStyleSheet("font-size:16px")
        self.snapTIFFButton.setSizePolicy(QtGui.QSizePolicy.Preferred,
                                          QtGui.QSizePolicy.Expanding)
        self.snapTIFFButton.clicked.connect(self.snapTIFF)
        self.recButton = QtGui.QPushButton('REC')
        self.recButton.setStyleSheet("font-size:16px")
        self.recButton.setCheckable(True)
        self.recButton.setSizePolicy(QtGui.QSizePolicy.Preferred,
                                     QtGui.QSizePolicy.Expanding)
        self.recButton.clicked.connect(self.startRecording)

        # Number of frames and measurement timing
        self.specifyFrames = QtGui.QRadioButton('Nr of frames')
        self.specifyFrames.clicked.connect(self.specFrames)
        self.specifyTime = QtGui.QRadioButton('Time to rec (sec)')
        self.specifyTime.clicked.connect(self.specTime) 
        self.timeToRec = QtGui.QLineEdit('1')
        self.timeToRec.setFixedWidth(45)
        self.timeToRec.textChanged.connect(self.filesizeupdate)
        self.currentTime = QtGui.QLabel('0 /')
        self.currentTime.setAlignment((QtCore.Qt.AlignRight |
                                        QtCore.Qt.AlignVCenter))
        self.currentFrame = QtGui.QLabel('0 /')
        self.currentFrame.setAlignment((QtCore.Qt.AlignRight |
                                        QtCore.Qt.AlignVCenter))
        self.currentFrame.setFixedWidth(45)
        self.numExpositionsEdit = QtGui.QLineEdit('100')
        self.numExpositionsEdit.setFixedWidth(45)
        self.tRemaining = QtGui.QLabel()
        self.tRemaining.setAlignment((QtCore.Qt.AlignCenter |
                                      QtCore.Qt.AlignVCenter))
        self.numExpositionsEdit.textChanged.connect(self.filesizeupdate)
#        self.updateRemaining()

        self.progressBar = QtGui.QProgressBar()
        self.progressBar.setTextVisible(False)
        
        self.filesizeBar = QtGui.QProgressBar()
        self.filesizeBar.setTextVisible(False)
        self.filesizeBar.setRange(0, 2000000000)

        # Layout
        buttonWidget = QtGui.QWidget()
        buttonGrid = QtGui.QGridLayout()
        buttonWidget.setLayout(buttonGrid)
        buttonGrid.addWidget(self.snapTIFFButton, 0, 0)
#        buttonGrid.addWidget(self.snapHDFButton, 0, 1)
        buttonWidget.setSizePolicy(QtGui.QSizePolicy.Preferred,
                                   QtGui.QSizePolicy.Expanding)
        buttonGrid.addWidget(self.recButton, 0, 2)

        recGrid = QtGui.QGridLayout()
        self.setLayout(recGrid)

# Graphically adding the labels and fields etc to the gui. Four numbers specify row, column, rowspan
# and columnspan.
        recGrid.addWidget(recTitle, 0, 0, 1, 3)
        recGrid.addWidget(QtGui.QLabel('Folder'), 2, 0)
        recGrid.addWidget(loadFolderButton, 1, 5)
        recGrid.addWidget(openFolderButton, 1, 4)
        recGrid.addWidget(self.folderEdit, 2, 1, 1, 5)
        recGrid.addWidget(self.specifyfile, 3, 0, 1, 5)
        recGrid.addWidget(self.filenameEdit, 3, 2, 1, 4)
        recGrid.addWidget(self.specifyFrames, 4, 0, 1, 5)
        recGrid.addWidget(self.currentFrame, 4, 1)
        recGrid.addWidget(self.numExpositionsEdit, 4, 2)
        recGrid.addWidget(QtGui.QLabel('File size'), 4, 3, 1, 2)
        recGrid.addWidget(self.filesizeBar, 4, 4, 1, 2)
        recGrid.addWidget(self.specifyTime, 5, 0, 1, 5)
        recGrid.addWidget(self.currentTime, 5, 1)
        recGrid.addWidget(self.timeToRec, 5, 2)
        recGrid.addWidget(self.tRemaining, 5, 3, 1, 2)
        recGrid.addWidget(self.progressBar, 5, 4, 1, 2)
        recGrid.addWidget(buttonWidget, 6, 0, 1, 0)

        recGrid.setColumnMinimumWidth(0, 70)
        recGrid.setRowMinimumHeight(6, 40)

# Initial condition of fields and checkboxes.
        self.writable = True
        self.readyToRecord = False
        self.filenameEdit.setEnabled(False)
        self.specTime()
        self.filesizeupdate()

    @property
    def readyToRecord(self):
        return self._readyToRecord

    @readyToRecord.setter
    def readyToRecord(self, value):
        self.snapTIFFButton.setEnabled(value)
#        self.snapHDFButton.setEnabled(value)
        self.recButton.setEnabled(value)
        self._readyToRecord = value

    @property
    def writable(self):
        return self._writable

# Setter for the writable property. If Nr of frame is checked only the frames field is
# set active and vice versa.

    @writable.setter
    def writable(self, value):
        if value:
            if self.specifyFrames.isChecked():
                self.specFrames()
            else:
                self.specTime()
        else:
            self.numExpositionsEdit.setEnabled(False)
            self.timeToRec.setEnabled(False)
#        self.folderEdit.setEnabled(value)
#        self.filenameEdit.setEnabled(value)
        self._writable = value

    def specFile(self):
        
        if self.specifyfile.checkState():
            self.filenameEdit.setEnabled(True)
            self.filenameEdit.setText('Filename')
        else:
            self.filenameEdit.setEnabled(False)
            self.filenameEdit.setText('Current time')

# Functions for changing between choosing frames or time when recording.
            
    def specFrames(self):
        
        self.numExpositionsEdit.setEnabled(True)
        self.timeToRec.setEnabled(False)
        self.filesizeupdate()
    
    def specTime(self):
        self.numExpositionsEdit.setEnabled(False)
        self.timeToRec.setEnabled(True)
        self.specifyTime.setChecked(True)
        self.filesizeupdate()
            
# For updating the appriximated file size of and eventual recording. Called when frame dimensions
# or frames to record is changed.            
            
    def filesizeupdate(self):
        if self.specifyFrames.isChecked():
            frames = int(self.numExpositionsEdit.text())
        else:
            frames = int(self.timeToRec.text()) / self.main.RealExpPar.value()

        self.filesize = 2 * frames * self.main.shape[0] * self.main.shape[1]
        self.filesizeBar.setValue(min(2000000000, self.filesize)) #Percentage of 2 GB
        self.filesizeBar.setFormat(str(self.filesize/1000))

    def n(self):
        text = self.numExpositionsEdit.text()
        if text == '':
            return 0
        else:
            return int(text)

# Function that returns the time to record in order to record the correct number of frames.
            
    def getRecTime(self):
        
        if self.specifyFrames.isChecked():
            time = int(self.numExpositionsEdit.text()) * self.main.RealExpPar.value()
            return time
        else:
            return int(self.timeToRec.text())

    def openFolder(self, path):
        if sys.platform == 'darwin':
            subprocess.check_call(['open', '', self.folderEdit.text()])
        elif sys.platform == 'linux':
            subprocess.check_call(['gnome-open', '', self.folderEdit.text()])
        elif sys.platform == 'win32':
            os.startfile(self.folderEdit.text())

    def loadFolder(self):
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(parent=root,
                                             initialdir=self.initialDir)
            root.destroy()
            if folder != '':
                self.folderEdit.setText(folder)
        except OSError:
            pass

    # Attributes saving
    def getAttrs(self):
        self.main.AbortROI()
        attrs = self.main.tree.attrs()
        attrs.extend([('Date', time.strftime("%Y-%m-%d")),
                      ('Saved at', time.strftime("%H:%M:%S")),
                      ('NA', 1.42)])
        for laserControl in self.main.laserWidgets.controls:
            name = re.sub('<[^<]+?>', '', laserControl.name.text())
            attrs.append((name, laserControl.laser.power))
        return attrs

    def snapHDF(self):

        folder = self.folderEdit.text()
        if os.path.exists(folder):

#            image = self.main.andor.most_recent_image16(self.main.shape)
            image = self.main.image

            name = os.path.join(folder, self.getFileName())
            savename = guitools.getUniqueName(name + '.hdf5')
            store_file = hdf.File(savename)
            store_file.create_dataset(name=self.dataname, data=image)
            for item in self.getAttrs():
                if item[1] is not None:
                    store_file[self.dataname].attrs[item[0]] = item[1]
            store_file.close()

        else:
            self.folderWarning()
            
    def getFileName(self):
        
        if self.specifyfile.checkState():
            filename = self.filenameEdit.text()
            
        else:
            filename = time.strftime('%Hh%Mm%Ss')
            
        return filename
        
    def snapTIFF(self):
        folder = self.folderEdit.text()
        if os.path.exists(folder):

#            image = self.main.andor.most_recent_image16(self.main.shape)
            time.sleep(0.01)
            savename = (os.path.join(folder, self.getFileName()) +
                        '_snap.tiff')
            savename = guitools.getUniqueName(savename)
#            tiff.imsave(savename, np.flipud(image.astype(np.uint16)),
#                        description=self.dataname, software='Tormenta')
            tiff.imsave(savename, self.main.latest_image.astype(np.uint16),
                        description=self.dataname, software='Tormenta')
            guitools.attrsToTxt(os.path.splitext(savename)[0], self.getAttrs())

        else:
            self.folderWarning()

    def folderWarning(self):
        root = Tk()
        root.withdraw()
        messagebox.showwarning(title='Warning', message="Folder doesn't exist")
        root.destroy()

    def updateGUI(self):

        eSecs = self.worker.timerecorded
        nframe = int(self.worker.timerecorded / self.main.RealExpPar.value())
        rSecs = self.getRecTime() - eSecs
        rText = '{}'.format(datetime.timedelta(seconds=max(0, rSecs)))
        self.tRemaining.setText(rText)
        self.currentFrame.setText(str(nframe) + ' /')
        self.currentTime.setText(str(int(eSecs)) + ' /')
        self.progressBar.setValue(100*(1 - rSecs / (eSecs + rSecs)))
#        self.main.img.setImage(self.worker.liveImage, autoLevels=False)

# This funciton is called when "Rec" button is pressed. 

    def startRecording(self):
        if self.recButton.isChecked():  
            ret = QtGui.QMessageBox.Yes
            if self.filesize > 1500000000:  # Checks if estimated file size is dangourusly large, > 1,5GB-.
                ret = self.filesizewar.exec_()
                
            folder = self.folderEdit.text()
            if os.path.exists(folder) and ret == QtGui.QMessageBox.Yes:
                
                self.writable = False # Sets Recording widget to not be writable during recording.
                self.readyToRecord = False
                self.recButton.setEnabled(True)
                self.recButton.setText('STOP')
                self.main.tree.writable = False # Sets camera parameters to not be writable during recording.
                self.main.liveviewButton.setEnabled(False)
#                self.main.liveviewStop() # Stops liveview from updating

                self.savename = (os.path.join(folder, self.getFileName()) + '_rec.hdf5') # Sets name for final output file
                self.savename = guitools.getUniqueName(self.savename) # If same  filename exists it is appended by (1) or (2) etc.
                self.startTime = ptime.time() # Saves the time when started to calculate remaining time.

                self.worker = RecWorker(self.main.orcaflash, self.getRecTime(), self.main.shape, self.main.lvworker,  #Creates an instance of RecWorker class.
                                        self.main.RealExpPar, self.savename,
                                        self.dataname, self.getAttrs())
                self.worker.updateSignal.connect(self.updateGUI)    # Connects the updatesignal that is continously emitted from recworker to updateGUI function.
                self.worker.doneSignal.connect(self.endRecording) # Connects the donesignal emitted from recworker to endrecording function.
                self.recordingThread = QtCore.QThread() # Creates a new thread
                self.worker.moveToThread(self.recordingThread) # moves the worker object to this thread. 
                self.recordingThread.started.connect(self.worker.start)
                self.recordingThread.start()

            else:
                self.recButton.setChecked(False)
                self.folderWarning()

        else:
            self.worker.pressed = False

# Function called when recording finishes to reset relevent parameters.

    def endRecording(self):

        self.recordingThread.terminate() 

        converterFunction = lambda: guitools.TiffConverterThread(self.savename)
        self.main.exportlastAction.triggered.connect(converterFunction)
        self.main.exportlastAction.setEnabled(True)

        self.writable = True
        self.readyToRecord = True
        self.recButton.setText('REC')
        self.recButton.setChecked(False)
        self.main.tree.writable = True
        self.main.orcaflash.startAcquisition()
        self.main.liveviewButton.setEnabled(True)
#        self.main.liveviewStart()
        self.progressBar.setValue(0)
        self.currentTime.setText('0 /')
        self.currentFrame.setText('0 /')


class RecWorker(QtCore.QObject):

    updateSignal = QtCore.pyqtSignal()
    doneSignal = QtCore.pyqtSignal()

    def __init__(self, orcaflash, timetorec, shape, lvworker, t_exp, savename, dataname, attrs,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orcaflash = orcaflash
        self.timetorec = timetorec
        self.shape = shape # Shape of one frame
        self.lvworker = lvworker
        self.t_exp = t_exp
        self.savename = savename
        self.dataname = dataname
        self.attrs = attrs
        self.pressed = True
        
    def start(self):
        self.orcaflash.stopAcquisition()
        for k in range(0, 1):
            print('Round :', k)
            self.timerecorded = 0
            self.orcaflash.startAcquisition()
            time.sleep(0.1)
            print('self.lvworker.f_count = ', self.lvworker.f_count)
            last_f = self.lvworker.f_count
            if last_f == None:
                start_f = 0 
                print('f_count was None so set to : ', start_f)
            else:
                start_f = last_f + 1 # index of first frame is one more then provious frame.
                
            self.starttime = time.time()
            print('start_f = ',start_f)        
    #        f_count = 0
            while self.timerecorded < self.timetorec and self.pressed:
                self.timerecorded = time.time() - self.starttime
    #            f_count = f_count + np.size(self.orcaflash.newFrames()) # In original driver, new_Frames waited for 
                # new frame before returning value which could cause a freeze here when if aquisition stops before 
                # recording was finished ie in external trigger mode. This has now been commented out from driver.
    #            self.liveImage = self.orcaflash.hcam_data[f_count-1].getData()
    #            self.liveImage = np.reshape(self.liveImage, (self.orcaflash.frame_x, self.orcaflash.frame_y), order='F')
                time.sleep(0.1)
                self.updateSignal.emit()
                
    #        frames = self.orcaflash.getFrames()
            self.orcaflash.stopAcquisition()   # To avoid overwriting buffer while saving recording
            end_f = self.lvworker.f_count # 
            if end_f == None:
                end_f = -1
                
            if end_f >= start_f - 1:
                f_range = range(start_f, end_f + 1)
            else:
                buffer_size = self.orcaflash.number_image_buffers
                f_range = np.append(range(start_f, buffer_size), range(0, end_f + 1))
                
            print('Start_f = :', start_f)
            print('End_f = :', end_f)
            f_count = len(f_range)
            data = [];
            for i in f_range:
                data.append(self.orcaflash.hcam_data[i].getData())
    
            datashape = (f_count, self.shape[1], self.shape[0])     # Adapted for ImageJ data read shape
    
    #        f_count = len(frames[0])
    #        for i in range(0, f_count):
    #            data.append(frames[0][i].getData())
#            self.savename = (r'E:\Andreas\Noise\GainNoise\Noise\Sixteenth\%s.hdf5' % k)
            print('Savename = ', self.savename)
            self.store_file = hdf.File(self.savename, "w")
            self.store_file.create_dataset(name=self.dataname, shape=datashape, maxshape=datashape, dtype=np.uint16)
            dataset = self.store_file[self.dataname]
    
                
            reshapeddata = np.reshape(data, datashape, order='C')
            dataset[...] = reshapeddata
            
            # Saving parameters
            for item in self.attrs:
                if item[1] is not None:
                    dataset.attrs[item[0]] = item[1]
         
            self.store_file.close()
        self.doneSignal.emit()
        
class CamParamTree(ParameterTree):
    """ Making the ParameterTree for configuration of the camera during imaging
    """

    def __init__(self, orcaflash, *args, **kwargs):
        super().__init__(*args, **kwargs)

        BinTip = ("Sets binning mode. Binning mode specifies if and how many \n"
                    "pixels are to be read out and interpreted as a single pixel value.")
                    

        # Parameter tree for the camera configuration
        params = [{'name': 'Camera', 'type': 'str',
                   'value': orcaflash.camera_id},
                  {'name': 'Image frame', 'type': 'group', 'children': [
                      {'name': 'Binning', 'type': 'list', 
                                  'values': [1, 2, 4], 'tip': BinTip},
{'name': 'Mode', 'type': 'list', 'values': ['Full Widefield', 'Full chip', 'Minimal line', 'Custom']},
{'name': 'X0', 'type': 'int', 'value': 0, 'limits': (0, 2044)},
{'name': 'Y0', 'type': 'int', 'value': 0, 'limits': (0, 2044)},
{'name': 'Width', 'type': 'int', 'value': 2048, 'limits': (1, 2048)},
{'name': 'Height', 'type': 'int', 'value': 2048, 'limits': (1, 2048)}, 
                                  {'name': 'Apply', 'type': 'action'},
{'name': 'New ROI', 'type': 'action'}, {'name': 'Abort ROI', 'type': 'action', 'align': 'right'}]},
                  {'name': 'Timings', 'type': 'group', 'children': [
                      {'name': 'Set exposure time', 'type': 'float',
                       'value': 0.03, 'limits': (0,
                                                9999),
                       'siPrefix': True, 'suffix': 's'},
                      {'name': 'Real exposure time', 'type': 'float',
                       'value': 0, 'readonly': True, 'siPrefix': True,
                       'suffix': ' s'},
                      {'name': 'Internal frame interval', 'type': 'float',
                       'value': 0, 'readonly': True, 'siPrefix': True,
                       'suffix': ' s'},
                      {'name': 'Readout time', 'type': 'float',
                       'value': 0, 'readonly': True, 'siPrefix': True,
                       'suffix': 's'},
                      {'name': 'Internal frame rate', 'type': 'float',
                       'value': 0, 'readonly': True, 'siPrefix': False,
                       'suffix': ' fps'}]}, 
                       {'name': 'Acquisition mode', 'type': 'group', 'children': [
                      {'name': 'Trigger source', 'type': 'list',
                       'values': ['Internal trigger', 'External trigger'],
                       'siPrefix': True, 'suffix': 's'}]}]

        self.p = Parameter.create(name='params', type='group', children=params)
        self.setParameters(self.p, showTop=False)
        self._writable = True

    def enableCropMode(self):
        value = self.frameTransferParam.value()
        if value:
            self.cropModeEnableParam.setWritable(True)
        else:
            self.cropModeEnableParam.setValue(False)
            self.cropModeEnableParam.setWritable(False)

    @property
    def writable(self):
        return self._writable

    @writable.setter
    def writable(self, value):
        """
        property to set basically the whole parameters tree as writable
        (value=True) or not writable (value=False)
        useful to set it as not writable during recording
        """
        self._writable = value
        framePar = self.p.param('Image frame')
        framePar.param('Binning').setWritable(value)
        framePar.param('Mode').setWritable(value)
        framePar.param('X0').setWritable(value)
        framePar.param('Y0').setWritable(value)
        framePar.param('Width').setWritable(value)
        framePar.param('Height').setWritable(value)
#       WARNING: If Apply and New ROI button are included here they will emit status changed signal
        # and their respective functions will be called... -> problems.
        
        timingPar = self.p.param('Timings')
        timingPar.param('Set exposure time').setWritable(value)

    def attrs(self):
        attrs = []
        for ParName in self.p.getValues():
            print(ParName)
            Par = self.p.param(str(ParName))
            if not(Par.hasChildren()):
                attrs.append((str(ParName), Par.value()))
            else:
                for sParName in Par.getValues():
                    sPar = Par.param(str(sParName))
                    if sPar.type() != 'action':
                        if not(sPar.hasChildren()):
                            attrs.append((str(sParName), sPar.value()))
                        else:
                            for ssParName in sPar.getValues():
                                ssPar = sPar.param(str(ssParName))
                                attrs.append((str(ssParName), ssPar.value()))
        return attrs
        
class LVWorker(QtCore.QObject):
    
    def __init__(self, main, orcaflash, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main = main
        self.orcaflash = orcaflash
        self.running = False
        self.f_count = None
        
    def run(self):
        
        self.vtimer = QtCore.QTimer()
        self.vtimer.timeout.connect(self.update)
        self.running = True
        self.f_count = None # Should maybe be f_ind
        self.vtimer.start(30)
        print('f_count when startd = ',self.f_count)
        
    def update(self):

        if self.running:
            self.f_count = self.orcaflash.newFrames()[-1]

            print('f_count in LVWorker:', self.f_count)
            frame = self.orcaflash.hcam_data[self.f_count].getData()
#                rawframes = self.orcaflash.getFrames()
#                firstframe = rawframes[0][-1].getData() #return A numpy array that contains the camera data. "Circular" indexing makes [-1] return the latest frame
            self.image = np.reshape(frame, (self.orcaflash.frame_x, self.orcaflash.frame_y), 'F')
            self.main.latest_image = self.image

        
    def stop(self):
        if self.running:
#            self.vtimer.stop()
            self.running = False
            print('Acquisition stopped')
        else:
            print('Cannot stop when not running (from LVThread)')
            
    def reset(self):
        self.f_count = None
        print('LVworker reset, f_count = ', self.f_count)