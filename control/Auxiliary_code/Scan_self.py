# -*- coding: utf-8 -*-
"""
Created on Wed Mar 30 10:32:36 2016

@author: testaRES
"""

try:
    import libnidaqmx
except:
    from control import libnidaqmx
    
import numpy as np
import copy
import time
from numpy import arange
import pyqtgraph as pg
from PyQt4 import QtGui, QtCore




# This class is intended as a widget in the bigger GUI, Thus all the commented parameters etc. It contain an instance
# of stage_scan and pixel_scan which in turn harbour the analog and digital signals respectively.
# The function run is the function that is supposed to start communication with the Nidaq
# through the Scanner object. This object was initially written as a QThread object but is not right now. 
# As seen in the commened lines of run() I also tried running in a QThread created in run().
# The rest of the functions contain mosly GUI related code.

class ScanWidget():
    
    def __init__(self, device, *args, **kwargs):
#        super().__init__(*args, **kwargs)
        self.nidaq = device
        self.aochannels = device.get_analog_output_channels()
        self.dochannels = device.get_digital_output_lines()
        self.saved_signal = np.array([0, 0])
        self.times_run = 0
#        self.widthPar = QtGui.QLineEdit('1')
#        self.widthPar.editingFinished.connect(lambda: self.ScanParameterChanged('width'))
#        self.heightPar = QtGui.QLineEdit('1')
#        self.heightPar.editingFinished.connect(lambda: self.ScanParameterChanged('height'))
#        self.sequence_timePar = QtGui.QLineEdit('0.01') # Seconds
#        self.sequence_timePar.editingFinished.connect(lambda: self.ScanParameterChanged('sequence_time'))
#        self.scan_speedPar = QtGui.QLineEdit('0.5')
#        self.scan_speedPar.editingFinished.connect(lambda: self.ScanParameterChanged('scan_speed'))
#        self.step_sizePar = QtGui.QLineEdit('0.1')
#        self.step_sizePar.editingFinished.connect(lambda: self.ScanParameterChanged('step_size'))
        self.sample_rate = 100000
        
#        self.scan_parameters = {'width': 1, 'height': 1,
#                           'sequence_time': 0.1,
#                           'scan_speed': 0.5,
#                           'step_size': 0.1}

        self.scan_par_values = {'width': 1,
                           'height': 1,
                           'sequence_time': 0.01,
                           'scan_speed': 0.5,
                           'step_size': 0.1}
                           
#        self.start488Par = QtGui.QLineEdit('0')
#        self.start488Par.editingFinished.connect(lambda: self.PixelParameterChanged('start488'))
#        self.start405Par = QtGui.QLineEdit('0')
#        self.start405Par.editingFinished.connect(lambda: self.PixelParameterChanged('start405'))
#        self.start355Par = QtGui.QLineEdit('0')
#        self.start355Par.editingFinished.connect(lambda: self.PixelParameterChanged('start355'))
#        self.startCAMPar = QtGui.QLineEdit('0')
#        self.startCAMPar.editingFinished.connect(lambda: self.PixelParameterChanged('startCAM'))
#        
#        self.end488Par = QtGui.QLineEdit('0')
#        self.end488Par.editingFinished.connect(lambda: self.PixelParameterChanged('end488'))
#        self.end405Par = QtGui.QLineEdit('0.01')
#        self.end405Par.editingFinished.connect(lambda: self.PixelParameterChanged('end405'))
#        self.end355Par = QtGui.QLineEdit('0')
#        self.end355Par.editingFinished.connect(lambda: self.PixelParameterChanged('end355'))
#        self.endCAMPar = QtGui.QLineEdit('0')
#        self.endCAMPar.editingFinished.connect(lambda: self.PixelParameterChanged('endCAM'))

#        self.pixel_parameters = {'start355': 0,
#                                 'start405': 0,
#                                 'start488': 0,
#                                 'startCAM': 0,
#                                 'end488': 0,
#                                 'end405': 0,
#                                 'end355': 0,
#                                 'endCAM': 0}

        
        self.pixel_par_values = {'start355': 0,
                                 'start405': 0,
                                 'start488': 0,
                                 'startCAM': 0,
                                 'end488': 0,
                                 'end405': 0,
                                 'end355': 0,
                                 'endCAM': 0}
        
        self.current_dochannels = {'355': 0, '405': 1, '488': 2, 'CAM': 3}
        self.current_aochannels = {'x': 0, 'y': 1}
#        self.XchanPar = QtGui.QComboBox()
#        self.XchanPar.addItems(self.aochannels)
#        self.XchanPar.currentIndexChanged.connect(self.AOchannelsChanged)
#        self.YchanPar = QtGui.QComboBox()
#        self.YchanPar.addItems(self.aochannels)
#        self.YchanPar.currentIndexChanged.connect(self.AOchannelsChanged)
#        self.chan355Par = QtGui.QComboBox()
#        self.chan355Par.addItems(self.dochannels)
#        self.chan405Par = QtGui.QComboBox()
#        self.chan405Par.addItems(self.dochannels)
#        self.chan488Par = QtGui.QComboBox()
#        self.chan488Par.addItems(self.dochannels)
#        self.chanCAMPar = QtGui.QComboBox()
#        self.chanCAMPar.addItems(self.dochannels)
#        self.DOchan_Pars_dict = {'355': self.chan355Par, '405': self.chan405Par, '488': self.chan488Par, 'CAM': self.chanCAMPar}
#        self.chan355Par.currentIndexChanged.connect(lambda: self.DOchannelsChanged('355', self.chan355Par.currentIndex()))
#        self.chan405Par.currentIndexChanged.connect(lambda: self.DOchannelsChanged('405', self.chan405Par.currentIndex()))
#        self.chan488Par.currentIndexChanged.connect(lambda: self.DOchannelsChanged('488', self.chan488Par.currentIndex()))
#        self.chanCAMPar.currentIndexChanged.connect(lambda: self.DOchannelsChanged('CAM', self.chanCAMPar.currentIndex()))
#        self.AOchannelsChanged()
#        for sig in self.current_dochannels:
#            self.DOchan_Pars_dict[sig].setCurrentIndex(self.current_dochannels[sig])
    
        self.stage_scan = StageScan(self.sample_rate)
        self.pixel_cycle = PixelCycle(self.sample_rate)
#        self.graph = GraphFrame(self.pixel_cycle)
        self.update_Scan(['355', '405', '488', 'CAM'])
        
#        self.scanRadio = QtGui.QRadioButton('Scan')
#        self.scanRadio.clicked.connect(lambda: self.setScanMode(True))
#        self.contLaserPulsesRadio = QtGui.QRadioButton('Cont. Laser Pulses')
#        self.contLaserPulsesRadio.clicked.connect(lambda: self.setScanMode(False))
        
#        self.ScanButton = QtGui.QPushButton('Scan')
#        self.ScanButton.clicked.connect(self.PrepAndRun)
#        
#        grid = QtGui.QGridLayout()
#        self.setLayout(grid)
##        grid.setRowMaximumHeight(0, 20)
##        grid.setRowMamimumHeight(1, 20)
#        grid.addWidget(QtGui.QLabel('X channel'), 0, 4)
#        grid.addWidget(self.XchanPar, 0, 5)
#        grid.addWidget(QtGui.QLabel('Width:'), 0, 0, 2, 1)
#        grid.addWidget(self.widthPar, 0, 1, 2, 1)
#        grid.addWidget(QtGui.QLabel('Height:'), 0, 2, 2, 1)
#        grid.addWidget(self.heightPar, 0, 3, 2, 1)
#        grid.addWidget(QtGui.QLabel('Y channel'), 1, 4)
#        grid.addWidget(self.YchanPar, 1, 5)
#        grid.addWidget(QtGui.QLabel('Sequence Time:'),3, 0)
#        grid.addWidget(self.sequence_timePar, 3, 1)
#        grid.addWidget(QtGui.QLabel('Scan speed:'), 3, 2)
#        grid.addWidget(self.scan_speedPar, 3, 3)
#        grid.addWidget(QtGui.QLabel('Step size:'), 3, 4)
#        grid.addWidget(self.step_sizePar, 3, 5)
#        grid.addWidget(QtGui.QLabel('Start:'), 5, 1)
#        grid.addWidget(QtGui.QLabel('End:'), 5, 2)
#        grid.addWidget(QtGui.QLabel('355:'), 6, 0)
#        grid.addWidget(self.start355Par, 6, 1)
#        grid.addWidget(self.end355Par, 6, 2)
#        grid.addWidget(self.chan355Par, 6, 3)
#        grid.addWidget(self.scanRadio, 6, 5)
#        grid.addWidget(QtGui.QLabel('405:'), 7, 0)
#        grid.addWidget(self.start405Par, 7, 1)
#        grid.addWidget(self.end405Par, 7, 2)
#        grid.addWidget(self.chan405Par, 7, 3)
#        grid.addWidget(self.contLaserPulsesRadio, 7, 5)
#        grid.addWidget(QtGui.QLabel('488:'), 8, 0)
#        grid.addWidget(self.start488Par, 8, 1)
#        grid.addWidget(self.end488Par, 8, 2)
#        grid.addWidget(self.chan488Par, 8, 3)
#        grid.addWidget(QtGui.QLabel('CAM:'), 9, 0)
#        grid.addWidget(self.startCAMPar, 9, 1)
#        grid.addWidget(self.endCAMPar, 9, 2)
#        grid.addWidget(self.chanCAMPar, 9, 3)
#        grid.addWidget(self.graph, 10, 0, 1, 6)
#        grid.addWidget(self.ScanButton, 11, 3)
        
    @property
    def scanMode(self):
        return self._scanMode

    @scanMode.setter
    def scanMode(self, value):
        self.EnableScanPars(value)
        
    def EnableScanPars(self, value):
        self.widthPar.setEnabled(value)
        self.heightPar.setEnabled(value)
        self.sequence_timePar.setEnabled(value)
        self.scan_speedPar.setEnabled(value)
        self.step_sizePar.setEnabled(value)
        if value:
            self.ScanButton.setText('Scan')
        else:
            self.ScanButton.setText('Run')
        
    def setScanMode(self, value):
        self.scanMode = value        
        
    def AOchannelsChanged (self):
        
        Xchan = self.XchanPar.currentIndex()
        Ychan = self.YchanPar.currentIndex()
        if Xchan == Ychan:
            Ychan = (Ychan + 1)%4
            self.YchanPar.setCurrentIndex(Ychan)
        self.current_aochannels['x'] = Xchan
        self.current_aochannels['y'] = Ychan
        
    def DOchannelsChanged(self, sig, new_index):
        
        for i in self.current_dochannels:
            if i != sig and new_index == self.current_dochannels[i]:
                self.DOchan_Pars_dict[sig].setCurrentIndex(self.current_dochannels[sig])
        
        self.current_dochannels[sig] = self.DOchan_Pars_dict[sig].currentIndex()
        

        
    def ScanParameterChanged(self, parameter):
        self.scan_par_values[parameter] = float(self.scan_parameters[parameter].text())
        if parameter == 'sequence_time' or parameter == 'scan_speed':
            self.update_Scan(['355', '405', '488', 'CAM'])
            self.graph.update(['355', '405', '488', 'CAM'])
        
    def PixelParameterChanged(self, parameter):
        self.pixel_par_values[parameter] = float(self.pixel_parameters[parameter].text())
        device = parameter[-3]+parameter[-2]+parameter[-1]
        self.update_Scan([device])
        self.graph.update([device])
        

    
    def PrepAndRun(self):
        self.scanner = Scanner(self.nidaq, self.stage_scan, self.pixel_cycle, self.current_aochannels, self.current_dochannels, self)
#        self.ScanButton.setEnabled(0)
#        self.ScanButton.setText('Running')
#        self.scanner.doneSignal.connect(self.ScanDone)
        self.scanner.run()
#        self.ScanDone()
#        self.scanningThread = QtCore.QThread()
#        self.scanner.moveToThread(self.scanningThread)
#        self.scanningThread.started.connect(self.scanner.run)
#        self.scanningThread.start()
        
        
    def ScanDone(self):
        self.ScanButton.setText('Scan')        
        self.ScanButton.setEnabled(1)
#        self.scanningThread.quit
#        del self.scanningThread
        
        
    def update_Scan(self, devices):
        self.stage_scan.update(self.scan_par_values)
        self.pixel_cycle.update(devices, self.pixel_par_values, self.stage_scan.step_samples)        
        
# This class was intended as a QThread to not intefere with the rest of the widgets in the GUI. 

class Scanner():
#    doneSignal = QtCore.pyqtSignal()
    def __init__(self, device, stage_scan, pixel_cycle, current_aochannels, current_dochannels, main, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nidaq = device
        self.stage_scan = stage_scan
        self.pixel_cycle = pixel_cycle
        self.current_aochannels = current_aochannels  # Dict containing channel numbers to be written to for each signal
        self.current_dochannels = current_dochannels  # Dict containing channel numbers to be written to for each device
        self.samples_in_scan = len(self.stage_scan.sig_dict['x_sig'])
        self.main = main
        
    def run(self):
        
#        self.nidaq.reset()
        
        aotask = libnidaqmx.AnalogOutputTask('aotask')
        dotask = libnidaqmx.DigitalOutputTask('dotask')  


        full_ao_signal = []
        final_samps = []
        temp_aochannels = copy.copy(self.current_aochannels)
        min_ao = -10
        max_ao = 10
           
        # Following loop creates the voltage channels in smallest to largest order and places signals in same order.
        
        for i in range(0,2):
            dim = min(temp_aochannels, key = temp_aochannels.get)   # dim = dimension ('x' or 'y') containing smallest channel nr. 
            chanstring = 'Dev1/ao%s'%temp_aochannels[dim]
            aotask.create_voltage_channel(phys_channel = chanstring, channel_name = 'chan%s'%dim, min_val = min_ao, max_val = max_ao)
            temp_aochannels.pop(dim)
            signal = self.stage_scan.sig_dict[dim+'_sig']
            if i == 1 and len(full_ao_signal) != len(signal):
                print('Length of signals are not equal (printed from RunScan()')
            full_ao_signal = np.append(full_ao_signal, signal)
            final_samps = np.append(final_samps, signal[-1])

        
        # Same as above but for the digital signals/devices        
        
        full_do_signal = []
        temp_dochannels = copy.copy(self.current_dochannels)
        for i in range(0,4):
            dev = min(temp_dochannels, key = temp_dochannels.get)
            chanstring = 'Dev1/port0/line%s'%temp_dochannels[dev]
            dotask.create_channel(lines = chanstring, name = 'chan%s'%dev)
            temp_dochannels.pop(dev)
            signal = self.pixel_cycle.sig_dict[dev+'sig']
            if len(full_ao_signal)%len(signal) != 0 and len(full_do_signal)%len(signal) != 0:
                print('Signal lengths does not match (printed from run)')
            full_do_signal = np.append(full_do_signal, signal)
        
        
        aotask.configure_timing_sample_clock(rate = self.stage_scan.sample_rate,
                                             sample_mode = 'finite',
                                             samples_per_channel = self.samples_in_scan)
                        
        dotask.configure_timing_sample_clock(source = r'ao/SampleClock', 
                                             rate = self.pixel_cycle.sample_rate, 
                                             sample_mode = 'finite', 
                                             samples_per_channel = self.samples_in_scan)
                        

        
     
        # Following is to create ramps back to zero for the analog channels during one second.     
     
        return_ramps = np.array([])
        for i in range(0,2):
            ramp_and_k = make_ramp(final_samps[i], 0, self.stage_scan.sample_rate)
            return_ramps = np.append(return_ramps, ramp_and_k[0]) 
            
        print(np.ones(1)) # This line alone fixes the problem...
        
        dotask.write(full_do_signal, layout = 'group_by_channel', auto_start = False)
        aotask.write(full_ao_signal, layout = 'group_by_channel', auto_start = False)

        dotask.start()
        aotask.start()
        aotask.wait_until_done() ##Need to wait for task to finish, otherwise aotask will be deleted 
        aotask.stop()
        
        aotask.configure_timing_sample_clock(rate = self.stage_scan.sample_rate,
                                                 sample_mode = 'finite',
                                                 samples_per_channel = self.stage_scan.sample_rate)
                                                 
                              
                                             
        aotask.write(return_ramps, layout = 'group_by_channel', auto_start = False)
        aotask.start()
        aotask.wait_until_done()


        aotask.clear()          ## when function is finished and task aborted
        dotask.clear()        

#        self.doneSignal.emit()
#
        
# Following class containg the analog signals in sig_dict. The update function takes the parameter_values
# and updates the signals accordingly
        
class StageScan():
    
    def __init__(self, sample_rate):
        self.sig_dict = {'x_sig': [], 'y_sig': []}
        self.sample_rate = sample_rate
        self.corr_step_size = None
        self.step_samples = None
        
        # Update signals according to parameters.
        # Note that rounding floats to ints may cause actual scan to differ slighly from expected scan. 
        # Maybe either limit input parameters to numbers that "fit each other" or find other solution, eg step size has to
        # be width divided by an integer.
        # Maybe not a problem ???
    def update(self, par_values):
        
        # Create signals
        start_x = 0
        size = par_values['width']
        sequence_samples = np.round(self.sample_rate * par_values['sequence_time']) #WARNING: Correct for units of the time, now seconds!!!!
        steps = int(np.ceil(size / par_values['step_size']))
        self.corr_step_size = size/steps # Step size compatible with width
        self.step_samples = int(np.ceil(sequence_samples / par_values['scan_speed']))
        row_samples = steps * self.step_samples
        
        
        ramp_and_k = make_ramp(start_x, size, row_samples) # ramp_and_k contains [ramp, k]
        k = ramp_and_k[1]
        ltr_ramp = ramp_and_k[0]
        rtl_ramp = ltr_ramp[::-1]  # rtl_ramp contains only ramp, no k since same k = -k
        gradual_k = make_ramp(k, -k, self.step_samples)
        turn_rtl = np.cumsum(gradual_k[0])
        turn_ltr = -turn_rtl
        max_turn = np.max(turn_rtl)
        adjustor = 1 - self.step_samples%2
        
        first_part =  max_turn - turn_rtl[range(int(np.ceil(self.step_samples/2)), self.step_samples)] # Create first and last part by flipping and turnign the turn_rtl array
        last_part = max_turn + turn_rtl[range(0, int(np.floor(self.step_samples/2) - adjustor + 1))]
        y_ramp_smooth = np.append(first_part, last_part)
        y_ramp_smooth = (self.corr_step_size/(2*max_turn)) * y_ramp_smooth        # adjust scale and offset of ramp

        turn_rtl = ltr_ramp[-1] + turn_rtl;

        x_sig = []
        y_sig = []
        new_value = 0
        for i in range(0,steps):
            if i%2==0:               
                x_sig = np.concatenate((x_sig, ltr_ramp, turn_rtl))
            else:
                x_sig = np.concatenate((x_sig, rtl_ramp, turn_ltr))
            y_sig = np.concatenate((y_sig, new_value*np.ones(row_samples), new_value+y_ramp_smooth))
            new_value = new_value + self.corr_step_size
            
        i = i + 1
        if i%2 == 0:
            x_sig = np.concatenate((x_sig, ltr_ramp))
        else:
            x_sig = np.concatenate((x_sig, rtl_ramp))  
        y_sig = np.concatenate((y_sig, new_value*np.ones(row_samples)))

        # Assign x_sig
        self.sig_dict['x_sig'] = x_sig
        # Assign y_sig
        self.sig_dict['y_sig'] = y_sig

        
# The follwing class contains the digital signals for the pixel cycle. The update function takes a parameter_values
# dict and updates the signal accordingly.         
        
class PixelCycle():
    
    def __init__(self, sample_rate):
        self.sig_dict = {'355sig': [], '405sig': [], '488sig': [], 'CAMsig': []}
        self.sample_rate = sample_rate
      
        
    def update(self, devices, par_values, cycle_samples):
        for device in devices:
            signal = np.zeros(cycle_samples)
            start_name = 'start'+device
            end_name = 'end'+device
            start_pos = par_values[start_name] * self.sample_rate
            start_pos = int(min(start_pos, cycle_samples - 1))
            end_pos = par_values[end_name] * self.sample_rate
            end_pos = int(min(end_pos, cycle_samples - 1))
            signal[range(start_pos, end_pos)] = 1
            self.sig_dict[device+'sig'] = signal
        


        
#class GraphFrame(pg.GraphicsWindow):
#    """Class is child of pg.GraphicsWindow and creats the plot that plots the preview of the pulses. 
#    Fcn update() updates the plot of "device" with signal "signal"  """
#
#    def __init__(self, pixel_cycle, *args, **kwargs):
#
#        super().__init__(*args, **kwargs)
#        
#        self.pixel_cycle = pixel_cycle
#        self.plot = self.addPlot(row=1, col=0)
#        self.plot.showGrid(x=False, y=False)
#        self.plot_sig_dict = {'355': self.plot.plot(pen=pg.mkPen(97, 0, 97)), 
#                              '405': self.plot.plot(pen=pg.mkPen(73, 0, 188)), 
#                              '488': self.plot.plot(pen=pg.mkPen(0, 247, 255)), 
#                              'CAM': self.plot.plot(pen='w')}
#        
#    def update(self, devices):
#        
#        for device in devices:
#            signal = self.pixel_cycle.sig_dict[device+'sig']
#            self.plot_sig_dict[device].setData(signal)      
        
        
        
def make_ramp(start, end, samples):

    ramp = []
    k  = (end - start) / (samples - 1)
    for i in range(0, samples):
        ramp.append(start + k * i)
        
    return np.array([ramp, k])
    
    
    
    
    
    
    
if __name__ == '__main__':
    ScanWid = ScanWidget(libnidaqmx.Device('Dev1'))
#    ScanWid.update_Scan()
