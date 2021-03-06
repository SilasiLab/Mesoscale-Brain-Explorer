#!/usr/bin/env python3

import pickle
import types
import uuid

import matplotlib
import numpy as np
import pyqtgraph as pg
import pyqtgraph.functions as fn
from pyqtgraph.Qt import QtCore, QtGui

from .custom_pyqtgraph_items import QMenuCustom, ImageExporterCustom
from .roi import RectROIcustom, PolyLineROIcustom
from pyqtgraph.exporters.ImageExporter import ImageExporter

__all__= ['ImageAnalysisViewBox', 'ViewMode', 'MultiRoiViewBox']

class UnsupportedRoiTypeError(Exception):
  pass

# class ImageAnalysisViewBox(pg.ViewBox):
#     """
#     Custom ViewBox used to over-ride the context menu. I don't want the full context menu,
#     just a view all and an export. Export does not call a dialog, just prompts user for filename.
#     """
#     def __init__(self, parent=None, border=None, lockAspect=False, enableMouse=True, invertY=False, enableMenu=True, name=None):
#         pg.ViewBox.__init__(self, parent, border, lockAspect, enableMouse, invertY, enableMenu, name)
#
#         self.menu = None # Override pyqtgraph ViewBoxMenu
#         self.menu = self.getMenu(None)
#
#     def raiseContextMenu(self, ev):
#         if not self.menuEnabled(): return
#         menu = self.getMenu(ev)
#         pos  = ev.screenPos()
#         menu.popup(QtCore.QPoint(pos.x(), pos.y()))
#
#     def export(self):
#         #self.exp = ImageExporterCustom(self)
#         self.
#         self.exp = ImageExporter(self)
#         self.exp.export()
#
#     def getMenu(self, event):
#         if self.menu is None:
#             self.menu        = QMenuCustom()
#             self.viewAll     = QtGui.QAction("View All", self.menu)
#             self.exportImage = QtGui.QAction("Export image", self.menu)
#             self.viewAll.triggered[()].connect(self.autoRange)
#             self.exportImage.triggered[()].connect(self.export)
#             self.menu.addAction(self.viewAll)
#             self.menu.addAction(self.exportImage)
#         return self.menu
 
class ViewMode():
    def __init__(self, id, cmap):
        self.id   = id
        self.cmap = cmap
        self.getLookupTable()
    def getLookupTable(self):        
        lut = [ [ int(255*val) for val in self.cmap(i)[:3] ] for i in range(256) ]
        lut = np.array(lut,dtype=np.ubyte)
        self.lut = lut     


class MultiRoiViewBox(pg.ViewBox):
    sigROIchanged = QtCore.Signal(object)
    clicked = QtCore.pyqtSignal(float, float)
    hovering = QtCore.pyqtSignal(float, float)
    roi_placed = QtCore.pyqtSignal(PolyLineROIcustom)


    def __init__(self, parent=None, border=None, lockAspect=False,
                 enableMouse=True, invertY=False, enableMenu=True, name=None):
        pg.ViewBox.__init__(self, parent, border, lockAspect,
                            enableMouse, invertY, enableMenu, name)

        self.crosshair_visible = True
        self.rois = []
        self.currentROIindex = None
        self.img      = None
        self.menu     = None # Override pyqtgraph ViewBoxMenu 
        self.menu     = self.getMenu(None)       
        self.NORMAL   = ViewMode(0, matplotlib.cm.gray)
        self.DEXA     = ViewMode(1, matplotlib.cm.jet)
        self.viewMode = self.NORMAL
        self.drawROImode = False
        self.drawingROI  = None
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.hLine = pg.InfiniteLine(angle=0, movable=False)

        self.mouseclickeventCount = 0

        l = QtGui.QGraphicsGridLayout()
        l.setHorizontalSpacing(0)
        l.setVerticalSpacing(0)
        xScale = pg.AxisItem(orientation='bottom', linkView=self)
        l.addItem(xScale, 1, 1)
        yScale = pg.AxisItem(orientation='left', linkView=self)
        l.addItem(yScale, 0, 0)
        xScale.setLabel(text="<span style='color: #ff0000; font-weight: bold'>X</span> <i>Axis</i>", units="s")
        yScale.setLabel('Y Axis', units='V')

    def getContextMenus(self, ev):
        return None
        
    def raiseContextMenu(self, ev):
        if not self.menuEnabled(): return
        menu = self.getMenu(ev)
        pos  = ev.screenPos()
        menu.popup(QtCore.QPoint(pos.x(), pos.y()))
        
    def export(self):
        #self.exp = ImageExporterCustom(self)
        self.exp = ImageExporter(self)
        self.exp.export()

    def mouseClickEvent(self, ev):
        if self.drawROImode:
            ev.accept()
            #print('mouseClickEvent->drawPolygonRoi')
            self.drawPolygonRoi(ev)            
        elif ev.button() == QtCore.Qt.RightButton and self.menuEnabled():
            ev.accept()
            self.raiseContextMenu(ev)
        elif ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            pos = self.mapToItem(self.img, ev.pos())
            self.clicked.emit(pos.x(), pos.y())
        # if self.mouseclickeventCount <= 1:
        #     proxy = pg.SignalProxy(self.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        #     self.scene().sigMouseMoved.connect(self.mouseMoved)

    def mouseMoved(self, ev):
        #pos = ev ## using signal proxy turns original arguments into a tuple (or not...)
        if self.sceneBoundingRect().contains(ev) and not self.drawROImode:
            mousePoint = self.mapSceneToView(ev)
            index = int(mousePoint.x())
            #if index > 0 and index < len(data1):
            #    label.setText("<span style='font-size: 12pt'>x=%0.1f,   <span style='color: red'>y1=%0.1f</span>,   <span style='color: green'>y2=%0.1f</span>" % (mousePoint.x(), data1[index], data2[index]))
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())

            #pos = self.mapToItem(self.img, ev.pos())
        mousePoint = self.mapSceneToView(ev)
        # print(str(mousePoint.x())+","+str(mousePoint.y()))
        self.hovering.emit(mousePoint.x(), mousePoint.y())

    def addPolyRoiRequest(self):
        """Function to add a Polygon ROI"""
        #print('addPolyRoiRequest')
        self.drawROImode = True
        for roi in self.rois:        
           roi.setActive(False)           

    def endPolyRoiRequest(self):
        self.drawROImode = False  # Deactivate drawing mode
        self.drawingROI  = None   # No roi being drawn, so set to None
        for r in self.rois:
            r.setActive(True)

    def addPolyLineROI(self, handlePositions, name):
        roi = PolyLineROIcustom(handlePositions=handlePositions, removable=True)
        roi.setName(name)
        self.addItem(roi)                      # Add roi to viewbox
        self.rois.append(roi)                  # Add to list of rois
        self.selectROI(roi)
        self.setCurrentROIindex(roi)
        roi.translatable = True
        #roi.setAcceptedMouseButtons(QtCore.Qt.LeftButton or QtCore.Qt.RightButton)
        roi.setActive(True)      
        for seg in roi.segments:
            seg.setSelectable(True)
        for h in roi.handles:
            h['item'].setSelectable(True)
        # Setup signals
        roi.sigClicked.connect(self.selectROI)
        roi.sigRegionChanged.connect(self.roiChanged)
        roi.sigRemoveRequested.connect(self.removeROI)
        roi.sigCopyRequested.connect(self.copyROI)
        roi.sigSaveRequested.connect(self.saveROI)            
        return roi

    def drawPolygonRoi(self, ev):
        "Function to draw a polygon ROI"
        roi = self.drawingROI
        pos = self.mapSceneToView(ev.scenePos())
        
        if ev.button() == QtCore.Qt.LeftButton:
            if roi is None:
                roi = PolyLineROIcustom(removable = False)
                # roi.setName('ROI-%i'% self.getROIid()) # Do this before self.selectROIs(roi)
                self.drawingROI = roi                  
                roi.addFreeHandle(pos)
                roi.addFreeHandle(pos)
                self.addItem(roi)                      # Add roi to viewbox
                self.rois.append(roi)                  # Add to list of rois
                self.selectROI(roi)
                self.sortROIs()  
                self.setCurrentROIindex(roi)                
                roi.translatable = False 
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.connect(h.movePoint)
            else:
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.disconnect()           
                roi.addFreeHandle(pos)
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.connect(h.movePoint)                
            # Add a segment between the handles
            roi.addSegment(roi.handles[-2]['item'],roi.handles[-1]['item'])
            # Set segment and handles to non-selectable
            seg = roi.segments[-1]
            seg.setSelectable(False)
            for h in seg.handles:
                h['item'].setSelectable(False)
                
        elif (ev.button() == QtCore.Qt.MiddleButton) or \
             (ev.button() == QtCore.Qt.RightButton and (roi==None or len(roi.segments)<3)):
            if roi!=None:
                # Remove handle and disconnect from scene
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.disconnect()
                roi.removeHandle(h)
                # Removed roi from viewbox
                self.removeItem(roi)
                self.rois.pop(self.currentROIindex)
                self.setCurrentROIindex(None)
            # Exit ROI drawing mode
            self.endPolyRoiRequest()

        elif ev.button() == QtCore.Qt.RightButton:
            # Remove last handle
            h = roi.handles[-1]['item']
            h.scene().sigMouseMoved.disconnect()  
            roi.removeHandle(h)
            # Add segment to close ROI
            roi.addSegment(roi.handles[-1]['item'], roi.handles[0]['item'])
            # Setup signals
            roi.sigClicked.connect(self.selectROI)
            roi.sigRegionChanged.connect(self.roiChanged)
            roi.sigRemoveRequested.connect(self.removeROI)
            roi.sigCopyRequested.connect(self.copyROI)
            roi.sigSaveRequested.connect(self.saveROI)
            # Re-activate mouse clicks for all roi, segments and handles
            roi.removable   = True
            roi.translatable = True  
            for seg in roi.segments:
                seg.setSelectable(True)
            for h in roi.handles:
                h['item'].setSelectable(True)
            # Exit ROI drawing mode
            self.endPolyRoiRequest()
            self.roi_placed.emit(roi)

    def autoDrawPolygonRoi(self, name, pos=QtCore.QPointF(0, 0), finished=False):
        "Function to draw a polygon ROI"
        roi = self.drawingROI

        if not finished:
            if roi is None:
                roi = PolyLineROIcustom(removable=False)
                roi.setName(name)  # Do this before self.selectROIs(roi)
                self.drawingROI = roi
                roi.addFreeHandle(pos)
                roi.addFreeHandle(pos)
                self.addItem(roi)  # Add roi to viewbox
                self.rois.append(roi)  # Add to list of rois
                self.selectROI(roi)
                self.sortROIs()
                self.setCurrentROIindex(roi)
                roi.translatable = False
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.connect(h.movePoint)
            else:
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.disconnect()
                roi.addFreeHandle(pos)
                h = roi.handles[-1]['item']
                h.scene().sigMouseMoved.connect(h.movePoint)
                # Add a segment between the handles
            roi.addSegment(roi.handles[-2]['item'], roi.handles[-1]['item'])
            # Set segment and handles to non-selectable
            seg = roi.segments[-1]
            seg.setSelectable(False)
            for h in seg.handles:
                h['item'].setSelectable(False)

        elif finished:
            # Remove last handle
            h = roi.handles[-1]['item']
            h.scene().sigMouseMoved.disconnect()
            roi.removeHandle(h)
            # Add segment to close ROI
            roi.addSegment(roi.handles[-1]['item'], roi.handles[0]['item'])
            # Setup signals
            roi.sigClicked.connect(self.selectROI)
            roi.sigRegionChanged.connect(self.roiChanged)
            roi.sigRemoveRequested.connect(self.removeROI)
            roi.sigCopyRequested.connect(self.copyROI)
            roi.sigSaveRequested.connect(self.saveROI)
            # Re-activate mouse clicks for all roi, segments and handles
            roi.removable = True
            roi.translatable = True
            for seg in roi.segments:
                seg.setSelectable(True)
            for h in roi.handles:
                h['item'].setSelectable(True)
            # Exit ROI drawing mode
            self.endPolyRoiRequest()

    # def getMenu(self, event):
    #     super().getMenu(event)
    #     if self.menu is None:
    #         self.menu = QtGui.QMenu()
    #
    #         # self.loadROIAct  = QActionCustom("Load ROI", self.menu)
    #         self.viewAll = QtGui.QAction("View All", self.menu)
    #         self.exportImage = QtGui.QAction("Export image", self.menu)
    #
    #         self.viewAll.triggered[()].connect(self.autoRange)
    #         self.exportImage.triggered[()].connect(self.export)
    #
    #         self.menu.addAction(self.viewAll)
    #         self.menu.addAction(self.exportImage)
    #         # Update action event. This enables passing of the event to the fuction connected to the
    #     # action i.e.  event will be passed to self.addRoiRequest when a Rectangular ROI is clicked
    #     # self.addROIRectAct.updateEvent(event)
    #     # self.addROIPolyAct.updateEvent(event)
    #     return self.menu

    def getMenu(self, event):
        if self.menu is None:
            self.menu          = QtGui.QMenu()
            # Submenu to add ROIs
            self.submenu       = QtGui.QMenu("Add ROI",self.menu)
            #self.addROIRectAct = QActionCustom("Rectangular",  self.submenu)
            self.addROIRectAct = QtGui.QAction("Rectangular",  self.submenu)
            #self.addROIPolyAct = QActionCustom("Polygon",  self.submenu)
            self.addROIPolyAct = QtGui.QAction("Polygon",  self.submenu)
            #self.addROIRectAct.clickEvent.connect(self.addRoiRequest)
            self.addROIRectAct.triggered.connect(self.addROI)
            #self.addROIPolyAct.clickEvent.connect(self.addPolyRoiRequest)
            self.addROIPolyAct.triggered.connect(self.addPolyRoiRequest)
            self.submenu.addAction(self.addROIRectAct)
            self.submenu.addAction(self.addROIPolyAct)

            self.removeAllROIAct  = QtGui.QAction("Remove all ROIs", self.menu)
            self.loadROIAct  = QtGui.QAction("Load ROI", self.menu)
            self.dexaMode    = QtGui.QAction("DEXA mode", self.menu)
            self.viewAll     = QtGui.QAction("View All", self.menu)
            self.exportImage = QtGui.QAction("Export image", self.menu)
            self.crosshair_toggle = QtGui.QAction("Show crosshair", self.menu)

            #self.loadROIAct.clickEvent.connect(self.loadROI)
            self.removeAllROIAct.triggered[()].connect(self.removeROI)
            self.loadROIAct.triggered[()].connect(self.loadROI)
            self.crosshair_toggle.toggled.connect(self.toggleCrosshair)
            # self.dexaMode.toggled.connect(self.toggleViewMode)
            self.viewAll.triggered[()].connect(self.autoRange)
            self.exportImage.triggered[()].connect(self.export)

            self.menu.addAction(self.crosshair_toggle)
            self.menu.addAction(self.viewAll)
            # self.menu.addAction(self.dexaMode)
            self.menu.addAction(self.exportImage)
            # self.menu.addSeparator()
            # self.menu.addMenu(self.submenu)
            self.menu.addAction(self.loadROIAct)
            self.crosshair_toggle.setCheckable(True)
            self.crosshair_toggle.setChecked(True)
            self.dexaMode.setCheckable(True)
        # Update action event. This enables passing of the event to the fuction connected to the
        # action i.e.  event will be passed to self.addRoiRequest when a Rectangular ROI is clicked
        #self.addROIRectAct.updateEvent(event)
        #self.addROIPolyAct.updateEvent(event)
        return self.menu
        
    def setCurrentROIindex(self, roi=None):
        """ Use this function to change currentROIindex value to ensure a signal is emitted"""
        if roi==None: self.currentROIindex = None
        else:         self.currentROIindex = self.rois.index(roi)
        self.sigROIchanged.emit(roi)  

    def roiChanged(self, roi):
        self.sigROIchanged.emit(roi) 

    def getCurrentROIindex(self):
        return self.currentROIindex    
    
    def selectROI(self, roi):
        """ Selection control of ROIs """
        # If no ROI is currently selected (currentROIindex is None), select roi
        if self.currentROIindex == None:
            roi.setSelected(True)
            self.setCurrentROIindex(roi)
        # If an ROI is already selected...
        else:
            roiSelected = self.rois[self.currentROIindex]
            roiSelected.setSelected(False) 
            # If a different roi is already selected, then select roi 
            if self.currentROIindex != self.rois.index(roi):
                self.setCurrentROIindex(roi)
                roi.setSelected(True)
            # If roi is already selected, then unselect
            else: 
                self.setCurrentROIindex(None)
        
    def addRoiRequest(self, ev):
        """ Function to addROI at an event screen position """
        # Get position
        pos  = self.mapSceneToView(ev.scenePos())        
        xpos = pos.x()
        ypos = pos.y()
        # Shift down by size
        xr,yr = self.viewRange()
        xsize  = 0.25*(xr[1]-xr[0])
        ysize  = 0.25*(yr[1]-yr[0])
        xysize = min(xsize,ysize)
        if xysize==0: xysize=100       
        ypos -= xysize
        # Create ROI
        xypos = (xpos, ypos)
        self.addROI(pos=xypos)
        
    def addROI(self, name, pos=None, size=None, angle=0.0):
        """ Add an ROI to the ViewBox """
        if name is None:
            raise ValueError('ROIs must have names. A nameless ROI was loaded')
        xr, yr = self.viewRange()
        if pos is None:
            posx = xr[0]+0.05*(xr[1]-xr[0])
            posy = yr[0]+0.05*(yr[1]-yr[0])
            pos = [posx, posy]
        if size is None:
            xsize = 0.25*(xr[1]-xr[0])
            ysize = 0.25*(yr[1]-yr[0])
            xysize = min(xsize, ysize)
            if xysize == 0: xysize = 100
            size = [xysize, xysize]
        roi = RectROIcustom(pos, size, angle, removable=True, pen=(255, 0, 0))
        roi.setName(name)
        # Setup signals
        #roi.setName('ROI-%i' % self.getROIid())
        roi.sigClicked.connect(self.selectROI)
        roi.sigRegionChanged.connect(self.roiChanged)
        roi.sigRemoveRequested.connect(self.removeROI)
        roi.sigCopyRequested.connect(self.copyROI)
        roi.sigSaveRequested.connect(self.saveROI)
        # Keep track of rois
        self.addItem(roi)
        self.rois.append(roi)
        self.selectROI(roi)
        self.sortROIs()  
        self.setCurrentROIindex(roi)
        return roi

    def sortROIs(self):
        """ Sort self.rois by roi name and adjust self.currentROIindex as necessary """
        if len(self.rois) == 0: return
        if self.currentROIindex == None:
            self.rois.sort()  
        else:
            roiCurrent = self.rois[self.currentROIindex]
            #self.rois.sort()
            self.currentROIindex = self.rois.index(roiCurrent)
    
    def getROIid(self):
        """ Get available and unique number for ROI name """
        if not self.rois:
            return 1
        parseable_rois = [roi for roi in self.rois if '-' in roi.name]
        nums = [(roi.name.split('-')[-1]) for roi in parseable_rois if roi.name != None ]
        nid  = 1
        if len(nums)>0:
            while(True):
                if nid not in nums: break
                nid+=1
        return nid

    def copyROI(self, roi_selected):
        """ Copy current ROI. Offset from original for visibility """
        if self.currentROIindex!=None:
            osFract = 0.05              
            roi     = self.rois[self.currentROIindex]
            assert(roi==roi_selected)
            # For rectangular ROI, offset by a fraction of the rotated size
            if type(roi)==RectROIcustom: 
                roiState = roi.getState()
                pos      = roiState['pos']
                size     = roiState['size']
                angle    = roiState['angle']
                dx, dy    = np.array(size)*osFract
                ang      = np.radians(angle)
                cosa     = np.cos(ang)
                sina     = np.sin(ang)
                dxt      = dx*cosa - dy*sina
                dyt      = dx*sina + dy*cosa
                offset   = QtCore.QPointF(dxt, dyt)
                self.addROI(pos+offset, size, angle)
            # For a polyline ROI, offset by a fraction of the bounding rectangle
            if type(roi)==PolyLineROIcustom:                             
                br        = roi.shape().boundingRect()
                size      = np.array([br.width(), br.height()])
                osx,osy   = size * osFract
                offset    = QtCore.QPointF(osx, osy)
                hps       = [i[-1] for i in roi.getSceneHandlePositions(index=None)]                
                hpsOffset = [self.mapSceneToView(hp)+offset for hp in hps]
                name = str(uuid.uuid4())
                self.addPolyLineROI(hpsOffset, name)
                roi_copy = [r for r in self.rois if r.name == name]
                assert(len(roi_copy) == 1)
                roi_copy = roi_copy[0]
                self.roi_placed.emit(roi_copy)

    def saveROI(self, fileName=''):
        """ Save the highlighted ROI to file """
        if self.currentROIindex!=None:
            roi = self.rois[self.currentROIindex]
            if roi == fileName:
                self.roi_placed.emit(roi)
                return
            if not fileName:
              fileName = QtGui.QFileDialog.getSaveFileName(None, self.tr("Save ROI"), QtCore.QDir.currentPath(), self.tr("ROI (*.roi)"))
              # Fix for PyQt/PySide compatibility. PyQt returns a QString, whereas PySide returns a tuple (first entry is filename as string)        
              if isinstance(fileName, types.TupleType): fileName = fileName[0]
              if hasattr(QtCore, 'QString') and isinstance(fileName, QtCore.QString): fileName = str(fileName)
            if not fileName == '':
                if type(roi) == RectROIcustom:
                    roiState = roi.saveState()
                    roiState['type'] = 'RectROIcustom'
                    roiState['name'] = roi.name
                elif type(roi)==PolyLineROIcustom: 
                    roiState = {}
                    hps   = [self.mapSceneToView(i[-1]) for i in roi.getSceneHandlePositions(index=None)]                                                      
                    hps   = [[hp.x(), hp.y()] for hp in hps]
                    roiState['type'] = 'PolyLineROIcustom'
                    roiState['handlePositions'] = hps
                    roiState['name'] = roi.name
                pickle.dump(roiState, open(fileName, "wb"))

    def addRoi(self, roipath, roiname, roimode='static'):
      roistate = pickle.load(open(roipath, 'rb'))
      if roistate['type'] == 'RectROIcustom':
        roi = self.addROI(roistate['pos'], roistate['size'], roistate['angle'])
      elif roistate['type'] == 'PolyLineROIcustom':
        roi = self.addPolyLineROI(roistate['handlePositions'], roistate['name'])
      else:
        raise UnsupportedRoiTypeError()
      roi.setName(roiname)
      self.selectROI(roi)

    def getRoi(self, roiname):
      rois = [roi for roi in self.rois if roi.name == roiname]
      assert(len(rois) == 1)
      return rois[0]
  
    def removeRoi(self, roiname):
      rois = [roi for roi in self.rois if roi.name == roiname]
      if not rois:
        return  
      assert(len(rois) == 1)
      roi = rois[0]
      self.rois.remove(roi)
      self.removeItem(roi)
                          
    def loadROI(self, fileNames = None):
        """ Load a previously saved ROI from file """
        if fileNames == None:
            fileNames = QtGui.QFileDialog.getOpenFileNames(None, self.tr("Load ROI"),
                                                           QtCore.QDir.currentPath(),
                                                           self.tr("ROI (*.roi)"))
        if hasattr(QtCore, 'QStringList') and \
                isinstance(fileNames, QtCore.QStringList): fileNames = [str(i) for i in fileNames]
        if len(fileNames) > 0:
            for fileName in fileNames:
                if fileName != '':
                    roiState = pickle.load(open(fileName, "rb"))
                    if roiState['type'] == 'RectROIcustom':
                        self.addROI(roiState['name'], roiState['pos'], roiState['size'], roiState['angle'])
                    elif roiState['type'] == 'PolyLineROIcustom':
                        self.addPolyLineROI(roiState['handlePositions'], roiState['name'])

    def removeROI(self):
        """ Delete the highlighted ROI """
        if self.currentROIindex!=None:
            roi = self.rois[self.currentROIindex]
            self.rois.pop(self.currentROIindex)
            self.removeItem(roi)  
            self.setCurrentROIindex(None)

    def toggleCrosshair(self, isChecked):
        if hasattr(self, 'vLine') and hasattr(self, 'hLine'):
            if isChecked:
                self.vLine.setVisible(True)
                self.hLine.setVisible(True)
            else:
                self.vLine.setVisible(False)
                self.hLine.setVisible(False)

    def toggleViewMode(self, isChecked):
        """ Toggles between NORMAL (Black/White) and DEXA mode (colour) """
        if isChecked: viewMode = self.DEXA
        else:         viewMode = self.NORMAL
        self.setViewMode(viewMode)
        
    def setViewMode(self,viewMode):
        self.viewMode = viewMode
        self.updateView()

    def updateView(self):
        self.background.setBrush(fn.mkBrush(self.viewMode.lut[0]))
        self.background.show()  
        if    self.img==None: return
        # todo: validate safe removal of line
        #else: self.img.setLookupTable(self.viewMode.lut)
 
    def update_rect(self, x1, y1, x2, y2):
      if not self.img:
        return
      self.img.setRect(QtCore.QRectF(x1, y1, x2, y2))
       
    def showImage(self, arr, min=None, max=None):
        arr = arr.astype("float64")
        if arr is None:
            self.img = None
            return
        if self.img==None:
            if min and max:
                self.img = pg.ImageItem(arr, levels=(min, max), autoLevels=False)
            else:
                self.img = pg.ImageItem(arr, autoRange=False, autoLevels=False)
            self.addItem(self.img)
        # Add/readd crosshair
        if self.crosshair_visible:
          self.addItem(self.vLine, ignoreBounds=True)
          self.addItem(self.hLine, ignoreBounds=True)
        proxy = pg.SignalProxy(self.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        self.scene().sigMouseMoved.connect(self.mouseMoved)
        if min and max:
            self.img.setImage(arr, levels=(min, max))
        else:
            self.img.setImage(arr)
        self.updateView()





