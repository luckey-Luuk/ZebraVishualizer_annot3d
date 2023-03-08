from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QCoreApplication, QEvent, QSize, QMetaObject, Qt, SLOT, Slot
from PySide2.QtGui import QBitmap, QColor, QCursor, QIcon, QImage, QKeySequence, QPainter, QPalette, QPixmap, QResizeEvent, QColor
from PySide2.QtWidgets import QApplication, QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDial, QDockWidget, QDoubleSpinBox, QFileDialog, QFontComboBox, QGraphicsGridLayout, QGraphicsOpacityEffect, QHBoxLayout, QInputDialog, QLCDNumber, QLabel, QLineEdit, QMainWindow, QMenu, QProgressBar, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStatusBar, QTimeEdit, QToolBar, QGridLayout, QVBoxLayout, QWidget, QAction, QShortcut


from traits.api import HasTraits, Instance, on_trait_change, Range
from traitsui.api import View, Item
from mayavi.core.ui.api import MayaviScene, MlabSceneModel, SceneEditor
from mayavi import mlab

import mayavi
import numpy as np
import os
from PIL import Image, ImageQt
from AnnotationSpace3D import AnnotationSpace3D
import random
import sys
import matplotlib.pyplot as plt
from helpers import read_tiff, apply_contrast, apply_brightness, disk, extract_max_value, create_image_dict
import asyncio
from openpyxl import Workbook, load_workbook


COLORS = {
    '#ff0000': [255, 0, 0, 255],
    '#35e3e3': [53, 227, 227, 255],
    '#5ebb49': [94, 187, 73, 255],
    '#ffd035': [255, 208, 53, 255],
}

ERASER_COLOR_RGBA = [255, 255, 255, 255]
INIT_COLOR_RGBA = COLORS['#ff0000']

p = 'xy' # xy initially, yz, xz
current_slide = {'xy': 0, 'xz': 0, 'yz': 0}
annot3D = -1
w, h, d = 500, 500, 25
eraser_on = False
brush_size = 5
eraser_size = 5
global_contrast = 1
global_brightness = 20
global_annot_opacity = 0.8
global_zoom = 0.0

def get_filled_pixmap(pixmap_file):
    pixmap = QPixmap(pixmap_file)
    mask = pixmap.createMaskFromColor(QColor('black'), Qt.MaskOutColor)
    pixmap.fill((QColor('white')))
    pixmap.setMask(mask)
    return pixmap


def get_circle_cursor(brush_size, color_rgba):
    x, y = (brush_size*2+1, brush_size*2+1)
    circle_img = np.zeros((x, y, 4))
    rr, cc = disk(center=(x//2, y//2), radius=brush_size, shape=(x, y))
    circle_img[rr, cc] = color_rgba
    image = np.require(circle_img, np.uint8, 'C')
    qimg = QImage(image.data, y, x, 4 * y , QImage.Format_RGBA8888)
    return QCursor(QPixmap(qimg))



class Visualization(HasTraits):
    scene = Instance(MlabSceneModel, ())

    @on_trait_change('scene.activated')
    

    def update_plot(self):

        self.image_dictionary=create_image_dict()
        self.current_image_number=0
        self.current_point_index=0

        self.amount_of_points=20
        self.colour_array=[(1,0,0),(1,1,0),(0,0,1),(0.95,0.5,0.2),(0.55,0.1,0.7),(0.3,1,1),(1,0.75,0.8),(0.65,0.4,0.15),(1,1,0.8),(0.5,0,0),(0.65,1,0.75),(0.5,0.5,0),(1,1,1),(0.05,0.05,0.05),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]
        self.point_location_data=[[[None]*3 for i in range(self.amount_of_points)]for j in range(len(self.image_dictionary))] #information of point locations in every time step

        self.mayavi_dots=[None for i in range(self.amount_of_points)]#location for mayavi to store individual dots


        self.figure = mlab.gcf(engine=self.scene.engine)#nodig voor de picker functie

        global annot3D
        npimages = annot3D.get_npimages()
        #print(npimages)
        npspace = annot3D.get_npspace()
        self.npspace_sf = mlab.pipeline.scalar_field(npspace) # scalar field to update later
        self.volume = mlab.pipeline.volume(mlab.pipeline.scalar_field(npimages),color=(0,1,0))

        self.figure.on_mouse_pick(self.picker_callback)


        #bg_original._volume_property.set_color('greens')
        segmask = mlab.pipeline.iso_surface(self.npspace_sf, color=(1.0, 0.0, 0.0))
        self.scene.background = (0.1, 0.1, 0.1)  
        #print('test')
         #self.scene.scene.disable_render = False

    def draw_point(self,new_x,new_y,new_z):#updates point data and draws updated point
        #update point data
        self.point_location_data[self.current_image_number][self.current_point_index]=[new_x,new_y,new_z]
        #draw new point
        if self.mayavi_dots[self.current_point_index] is not None:
            self.mayavi_dots[self.current_point_index].remove()
            self.mayavi_dots[self.current_point_index]=None
        self.mayavi_dots[self.current_point_index]=mlab.points3d(new_x,new_y,new_z,color=self.colour_array[self.current_point_index],scale_factor=10)

    def delete_point(self):
        #update point data
        self.point_location_data[self.current_image_number][self.current_point_index]=[None,None,None]
        #delete point
        if self.mayavi_dots[self.current_point_index] is not None:
            self.mayavi_dots[self.current_point_index].remove()
            self.mayavi_dots[self.current_point_index]=None

    def redraw_all_points(self): #redraws all points, used to update points for the next timestep
        for i in range(self.amount_of_points):
            if self.mayavi_dots[i] is not None:
                self.mayavi_dots[i].remove()
                self.mayavi_dots[i]=None

            if self.point_location_data[self.current_image_number][i][0] is not None: #check if x cordinate is not no to see if a point needs to be placed
                self.mayavi_dots[i]=mlab.points3d(self.point_location_data[self.current_image_number][i][0],self.point_location_data[self.current_image_number][i][1],self.point_location_data[self.current_image_number][i][2],color=self.colour_array[i],scale_factor=10)

    def add_value_to_point(self,added_value):
        old_value=self.point_location_data[self.current_image_number][self.current_point_index]
        if old_value[0] is not None:#check if value exists 
            self.draw_point(old_value[0]+added_value[0],old_value[1]+added_value[1],old_value[2]+added_value[2])

    

    def update_volume(self,next_or_previous='next'):
        if next_or_previous=="next":
            if self.current_image_number==len(self.image_dictionary)-1:
                return
            self.current_image_number+=1
        elif next_or_previous=="previous":
            if self.current_image_number==0:
                return
            self.current_image_number-=1
        elif isinstance(next_or_previous,int):
            if len(self.image_dictionary)-1<next_or_previous:
                self.current_image_number=len(self.image_dictionary)-1
            else:
                self.current_image_number=next_or_previous
        window.load_source_file('data/'+self.image_dictionary[self.current_image_number])
        npimages = annot3D.get_npimages()
        self.volume.remove()
        self.volume = mlab.pipeline.volume(mlab.pipeline.scalar_field(npimages),color=(0,1,0))
        self.redraw_all_points()

    def picker_callback(self,picker):
        #print(dir(picker))
        cordinates=picker.pick_position
        self.draw_point(cordinates[0],cordinates[1],cordinates[2])

    def save_data(self,file_name="test_file"):
        point_data_list=[] #meant to put in data from point_location_data that is not None, later used for export to excel
        for i in range(len(self.image_dictionary)):
            for j in range(self.amount_of_points):
                if self.point_location_data[i][j][0] is not None:
                    point_data_list.append([i,j,self.point_location_data[i][j][0],self.point_location_data[i][j][1],self.point_location_data[i][j][2]])


        book=Workbook()
        sheet=book.active
        sheet.append(["timestep","dot","x","y","z"])
        for row in point_data_list:
            sheet.append(row)
        for row in sheet.values:
            print(row)
        book.save(file_name+'.xlsx')


    def load_data(self,file_name="test_file.xlsx"):
        book=load_workbook(filename=file_name)
        sheet=book.active
        for row in sheet.values:
            if type(row[0])==int: #done to skip the first row that doesn't give data
                self.point_location_data[row[0]][row[1]]=[row[2],row[3],row[4]]
        self.redraw_all_points()


    


    def update_annot(self): # update the scalar field and visualization auto updates
        npspace = annot3D.get_npspace()
        self.npspace_sf.mlab_source.trait_set(scalars=npspace) 

    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False), resizable=True )



class MayaviQWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.visualization = Visualization()

        self.ui = self.visualization.edit_traits(parent=self, kind='subpanel').control
        layout.addWidget(self.ui)
        self.ui.setParent(self)
    
    def update_annot(self):
        self.visualization.update_annot()



class QPaletteButton(QPushButton):
    def __init__(self, color):
        super().__init__()
        self.setFixedSize(QSize(24,24))
        self.color = color
        self.setStyleSheet("background-color: %s;" % color)


class Label(QLabel):

    def __init__(self):
        super(Label, self).__init__()
        self.pixmap_width: int = 1
        self.pixmapHeight: int = 1

    def setPixmap(self, pm: QPixmap) -> None:
        self.pixmap_width = pm.width()
        self.pixmapHeight = pm.height()

        self.updateMargins()
        super(Label, self).setPixmap(pm)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        self.updateMargins()
        super(Label, self).resizeEvent(a0)

    def updateMargins(self):
        if self.pixmap() is None:
            return
        pixmapWidth = self.pixmap().width()
        pixmapHeight = self.pixmap().height()
        if pixmapWidth <= 0 or pixmapHeight <= 0:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        if w * pixmapHeight > h * pixmapWidth:
            m = int((w - (pixmapWidth * h / pixmapHeight)) / 2)
            self.setContentsMargins(m, 0, m, 0)
        else:
            m = int((h - (pixmapHeight * w / pixmapWidth)) / 2)
            self.setContentsMargins(0, m, 0, m)


class Canvas(QWidget):

    def __init__(self, image, plane):
        super().__init__()
        global current_slide, annot3D, COLORS
        self.dx, self.dy = image.shape
        self.p = plane # plane

        self.l = QGridLayout()

        self.bg = QLabel()
        # self.bg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.bg.setScaledContents(True)
        # self.bg.setMinimumSize(QSize(0,0))
        # self.bg.setMaximumSize(QSize(16777215, 16777215))

        self.annot = QLabel()
        # self.annot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.annot.setScaledContents(True)
        # self.annot.setMinimumSize(QSize(0,0))
        # self.annot.setMaximumSize(QSize(16777215, 16777215))
        # self.annot.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)


        image = np.require(image, np.short, 'C')   
        qimg = QImage(image.data, self.dy, self.dx, 2 * self.dy , QImage.Format_Grayscale16)
        self.bg.setPixmap(QPixmap(qimg))

        image = np.zeros((self.dx, self.dy, 4))
        image = np.require(image, np.uint8, 'C') 
        qimg = QImage(image.data, self.dy, self.dx, 4 * self.dy , QImage.Format_RGBA8888)
        self.annot.setPixmap(QPixmap(qimg))

        self.opacity_effect = QGraphicsOpacityEffect() 
        self.opacity_effect.setOpacity(0.5) 
        self.annot.setGraphicsEffect(self.opacity_effect)

        # self.bg.resize(self.bg.pixmap().size())
        # self.annot.resize(self.annot.pixmap().size())

        self.l.addWidget(self.bg, 0, 0, Qt.AlignLeft | Qt.AlignTop)
        self.l.addWidget(self.annot, 0, 0, Qt.AlignLeft | Qt.AlignTop)
        
        self.setLayout(self.l)

        self.pen_color_rgba = INIT_COLOR_RGBA
        
        self.update_cursor()


    def update_cursor(self):
        if eraser_on:
            self.setCursor(get_circle_cursor(eraser_size, ERASER_COLOR_RGBA))
        else:
            self.setCursor(get_circle_cursor(brush_size, self.pen_color_rgba))


    def update_annot_opacity(self):
        self.opacity_effect.setOpacity(global_annot_opacity) 


    def set_pen_color(self, c):
        self.pen_color_rgba = COLORS[c]
        self.update_cursor()


    def mouseMoveEvent(self, e):   
        global current_slide, annot3D    
        x = e.x()-10
        y = e.y()-10
        
        d = current_slide[self.p]

        if (eraser_on): 
            annot3D.draw(self.p, d, x, y, eraser_size, 0, [0,0,0,0])
        else:
            annot3D.draw(self.p, d, x, y, brush_size, 1, self.pen_color_rgba)

        self.change_annot(annot3D.get_slice(self.p, d))
        self.annot.update()


    def mousePressEvent(self, e):
        annot3D.save_history(self.p, current_slide[self.p]) # save history after every line stroke
        

    def change_bg(self, image):
        image = np.require(image, np.short, 'C')        
        qimg = QImage(image.data, self.dy, self.dx, 2 * self.dy , QImage.Format_Grayscale16)
        qpixmap = QPixmap(qimg)
        # w = int(self.dx*(1+global_zoom))
        # h = int(self.dy*(1+global_zoom))
        # qpixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.bg.setPixmap(qpixmap)
        self.bg.update()


    def change_annot(self, image):
        annot = np.require(image, np.uint8, 'C') 
        qimg = QImage(annot.data, self.dy, self.dx, 4 * self.dy , QImage.Format_RGBA8888)
        qpixmap = QPixmap(qimg)
        # self.annot.resize((1+global_zoom)*self.annot.pixmap().size())
        self.annot.setPixmap(qpixmap)
        self.annot.update()





class MainWindow(QMainWindow):
    c = {'xy': 0, 'xz': 0, 'yz': 0}
    
    dims = (500, 500, 25) # w, h, d
    slides={}
    plane_depth = {}
    slide_annotations = {}
    num_slides = 0
    npimages = -1


    def load_source_file(self, filename):
        global COLORS, p, current_slide, annot3D

        self.slides['xy'], self.slides['xz'], self.slides['yz'] = read_tiff(filename)



        self.npimages = self.slides['xy']
        
        w = self.npimages[0].shape[0]
        h = self.npimages[0].shape[1]
        d = self.npimages.shape[0]

        annot3D = AnnotationSpace3D(self.npimages, (d, w, h), INIT_COLOR_RGBA)

        self.plane_depth = {
            'xy': d,
            'xz': w,
            'yz': h
        }

        self.dims = (w, h, d)
        #print(self.dims)

        self.num_slides = self.plane_depth[p]

        self.slide_annotations = {
            'xy': [] * d, 
            'xz': [] * w, 
            'yz': [] * h
        }


    def __init__(self):
        super().__init__()
        
    # INIT ANNOT LOAD UP
        temp_dict=create_image_dict() #creates a dict so it can load the first file, there might be a beter way to load the first file since this dict is only used once
        #self.load_source_file('data/src.tiff')
        #self.load_source_file('data/test.tif')
        self.load_source_file('data/'+temp_dict[0]) #load the first image in the dict
        #self.load_source_file('data/test2.tif')

        if len(sys.argv) == 2:
            global annot3D
            print("Set server URL to", sys.argv[1])
            annot3D.set_server_url(sys.argv[1])

        #for p in ['xy', 'xz', 'yz']:
        #    self.c[p] = Canvas(image=self.slides[p][0], plane=p)
            

        w = QWidget()
        
        l = QHBoxLayout()
        w.setLayout(l)


    # COLOR PALETTE
        # palette_layout = QGridLayout()
        # i, j = 1, 1
        # for c in COLORS:
        #     b = QPaletteButton(c)
        #     b.pressed.connect(lambda c=c : self.set_canvas_pen_color(c))
        #     palette_layout.addWidget(b, i, j)
        #     j += 1
        #     if j > 2:
        #         j = 1
        #         i += 1

        # l.addLayout(palette_layout)

    # CANVAS LAYOUT
        canvas_layout = QGridLayout()
        #self.slide_label = QLabel('xy: 1')
        #self.slide_label.setFixedWidth(40)
        #canvas_layout.addWidget(self.slide_label,0,1)


    # TOOLBAR, STATUSBAR, MENU
        self.setup_bar_actions()

    # SLIDERS
        self.setup_sliders()

    # MAYAVI RENDER VIEW
        self.rdock = QDockWidget("Render View", self) # render dock
        self.rdock.setFeatures(self.rdock.features() & ~QDockWidget.DockWidgetClosable) # unclosable
        self.rdock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        container = QWidget(self.rdock)
        self.mayavi_widget = MayaviQWidget(container)
        self.rdock.setWidget(self.mayavi_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.rdock)
    
    # GENERAL WINDOW PROPS
        self.setWindowTitle("Cell Annotation")
        self.setCentralWidget(w)

        def create_button(self,text,width,update=[0,0,0]): #function to create standard button
            self.button=QPushButton(text)
            self.button.setFixedWidth(width)
            self.button.clicked.connect(lambda: self.mayavi_widget.visualization.add_value_to_point(update))
            return self.button    

        self.delete_button=QPushButton('delete point')
        self.delete_button.setFixedWidth(110)
        self.delete_button.clicked.connect(lambda: self.mayavi_widget.visualization.delete_point())
        canvas_layout.addWidget(self.delete_button,3,0)

        self.save_button=QPushButton('save data')
        self.save_button.setFixedWidth(100)
        self.save_button.clicked.connect(lambda: self.mayavi_widget.visualization.save_data())
        canvas_layout.addWidget(self.save_button,3,1)

        self.load_button=QPushButton('load data')
        self.load_button.setFixedWidth(100)
        self.load_button.clicked.connect(lambda: self.mayavi_widget.visualization.load_data())
        canvas_layout.addWidget(self.load_button,3,2)

        self.x_label = QLabel('X')
        self.y_label = QLabel('Y')
        self.z_label = QLabel('Z')
        self.slide_label = QLabel('slide 1') #number of current slide modified when switching
        canvas_layout.addWidget(self.x_label,0,0)
        canvas_layout.addWidget(self.y_label,1,0)
        canvas_layout.addWidget(self.z_label,2,0)
        canvas_layout.addWidget(self.slide_label,4,2)

        canvas_layout.addWidget(create_button(self,'-5',50,[-5,0,0]),0,1) #create x-5 button
        canvas_layout.addWidget(create_button(self,'-1',50,[-1,0,0]),0,2) #create x-1 button
        canvas_layout.addWidget(create_button(self,'+1',50,[1,0,0]),0,3) #create x+1 button
        canvas_layout.addWidget(create_button(self,'+5',50,[5,0,0]),0,4) #create x+5 button

        canvas_layout.addWidget(create_button(self,'-5',50,[0,-5,0]),1,1) #create y-5 button
        canvas_layout.addWidget(create_button(self,'-1',50,[0,-1,0]),1,2) #create y-1 button
        canvas_layout.addWidget(create_button(self,'+1',50,[0,1,0]),1,3) #create y+1 button
        canvas_layout.addWidget(create_button(self,'+5',50,[0,5,0]),1,4) #create y+5 button

        canvas_layout.addWidget(create_button(self,'-5',50,[0,0,-5]),2,1) #create z-5 button
        canvas_layout.addWidget(create_button(self,'-1',50,[0,0,-1]),2,2) #create z-1 button
        canvas_layout.addWidget(create_button(self,'+1',50,[0,0,1]),2,3) #create z+1 button
        canvas_layout.addWidget(create_button(self,'+5',50,[0,0,5]),2,4) #create z+5 button

        def change_selected_point(new_point):
            new_point=new_point.split(" ")[1] #split the string and take the number
            self.mayavi_widget.visualization.current_point_index=int(new_point)-1 #-1 becouse index starts at 0

        point_amount=20 #amount of points in pointlist
        point_list=[]   #list for the selectable points in the combobox
        for i in range(point_amount):
            point_list.append("point "+str(i+1))

        selection_box=QComboBox()
        selection_box.addItems(point_list)
        
        selection_box.currentIndexChanged.connect(lambda: change_selected_point(selection_box.currentText()))
        
        #selection_box.setFixedWidth(50)
        #v_box.addWidget(selection_box)
        canvas_layout.addWidget(selection_box,4,0)
        


        # self.scrollAreaXY = QScrollArea()
        # self.scrollAreaXY.setWidget(self.c['xy'])
        # self.scrollAreaXY.setWidgetResizable(True)
        # self.scrollAreaXY.setMinimumSize(self.dims[0], self.dims[1])

        # self.scrollAreaXZ = QScrollArea()
        # self.scrollAreaXZ.setWidget(self.c['xz'])
        # self.scrollAreaXZ.setWidgetResizable(True)
        # self.scrollAreaXZ.setMinimumSize(self.dims[2], self.dims[1])

        # self.scrollAreaYZ = QScrollArea()
        # self.scrollAreaYZ.setWidget(self.c['yz'])
        # self.scrollAreaYZ.setWidgetResizable(True)
        # self.scrollAreaYZ.setMinimumSize(self.dims[1], self.dims[2])

        # canvas_layout.addWidget(self.scrollAreaXY,2,2, stretch=1)
        # canvas_layout.addWidget(self.scrollAreaXZ,1,2, stretch=0)
        # canvas_layout.addWidget(self.scrollAreaYZ,2,1, stretch=0)

        #canvas_layout.addWidget(self.c['xy'],2,2)
        #canvas_layout.addWidget(self.c['xz'],1,2)
        #canvas_layout.addWidget(self.c['yz'],2,1)

        #canvas_layout.addWidget(QColor("red"),2,2)
        l.addLayout(canvas_layout)

        

    


    def setup_bar_actions(self):
        self.statusBar()
        
        exitAction = QAction(QIcon(get_filled_pixmap('graphics/delete.png')), 'Exit', self)
        exitAction.setShortcut(QKeySequence.Quit) # Ctrl+Q
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        loadAnnotAction = QAction(QIcon(get_filled_pixmap('graphics/load.png')), 'Load annotations', self)
        loadAnnotAction.setShortcut(QKeySequence.Open) # Ctrl+O
        loadAnnotAction.setStatusTip('Load new annotations file')
        loadAnnotAction.triggered.connect(self.load_annot_dialog)

        mergeAnnotAction = QAction(QIcon(get_filled_pixmap('graphics/load.png')), 'Merge annotations', self)
        mergeAnnotAction.setShortcut('Ctrl+M')
        mergeAnnotAction.setStatusTip('Merge multiple annotations')
        mergeAnnotAction.triggered.connect(self.merge_annot_dialog)

        loadWeightsAction = QAction(QIcon(get_filled_pixmap('graphics/merge.png')), 'Load model weights', self)
        loadWeightsAction.setShortcut('Ctrl+W')
        loadWeightsAction.setStatusTip('Load model weights')
        loadWeightsAction.triggered.connect(self.load_weights_dialog)

        saveAnnotAction = QAction(QIcon(get_filled_pixmap('graphics/save.png')), 'Save annotations', self)
        saveAnnotAction.setShortcut(QKeySequence.Save) # Ctrl+S
        saveAnnotAction.setStatusTip('Save annotations file')
        saveAnnotAction.triggered.connect(self.save_annots_dialog)

        exportAction = QAction(QIcon(get_filled_pixmap('graphics/render.png')), 'Export dataset', self)
        exportAction.setShortcut('Ctrl+E')
        exportAction.setStatusTip('Export source and annotations as dataset directory')
        exportAction.triggered.connect(self.export_dialog)

        selectEraserAction = QAction(QIcon(get_filled_pixmap('graphics/eraser.png')), 'Toggle Eraser', self)
        selectEraserAction.setShortcut('E')
        selectEraserAction.setStatusTip('Toggle eraser')
        selectEraserAction.setCheckable(True)
        selectEraserAction.triggered.connect(self.toggle_eraser)

        self.xyAction = QAction('xy', self)
        self.xyAction.setShortcut('1')
        self.xyAction.setStatusTip('Switch to xy plane')
        self.xyAction.setCheckable(True)
        self.xyAction.triggered.connect(lambda: self.switch_plane('xy'))

        self.xzAction = QAction('xz', self)
        self.xzAction.setShortcut('2')
        self.xzAction.setStatusTip('Switch to xz plane')
        self.xzAction.setCheckable(True)
        self.xzAction.triggered.connect(lambda: self.switch_plane('xz'))

        self.yzAction = QAction('yz', self)
        self.yzAction.setShortcut('3')
        self.yzAction.setStatusTip('Switch to yz plane')
        self.yzAction.setCheckable(True)
        self.yzAction.triggered.connect(lambda: self.switch_plane('yz'))

        gotoAction = QAction('goto', self)
        gotoAction.setShortcut(QKeySequence.Find)
        gotoAction.setStatusTip('Go to specific slide on selected plane')
        gotoAction.triggered.connect(self.goto_slide)

        ChangeVolumeNextAction = QAction('>', self)
        ChangeVolumeNextAction.setShortcut(QKeySequence.Find)
        ChangeVolumeNextAction.setStatusTip('Go to another volume rendering')
        ChangeVolumeNextAction.triggered.connect(self.change_volume_model_next)

        ChangeVolumePreviusAction = QAction('<', self)
        ChangeVolumePreviusAction.setShortcut(QKeySequence.Find)
        ChangeVolumePreviusAction.setStatusTip('Go to another volume rendering')
        ChangeVolumePreviusAction.triggered.connect(self.change_volume_model_previous)
        

    # HIDDEN HOTKEY ACTIONS
        slideLeftAction = QAction('Left', self)
        slideLeftAction.setShortcut('Left')
        slideLeftAction.setStatusTip('Slide left')
        slideLeftAction.triggered.connect(self.slide_left)

        slideRightAction = QAction('Right', self)
        slideRightAction.setShortcut('Right')
        slideRightAction.setStatusTip('Slide right')
        slideRightAction.triggered.connect(self.slide_right)

        undoAction = QAction('Undo', self)
        undoAction.setShortcut(QKeySequence.Undo)
        undoAction.setStatusTip('Undo last annotation')
        undoAction.triggered.connect(self.undo)

        renderAction = QAction('Render', self)
        renderAction.setShortcut('R')
        renderAction.setStatusTip('Update annotation render')
        renderAction.triggered.connect(self.render)

        predictAction = QAction('Predict Current', self)
        predictAction.setShortcut('P')
        predictAction.setStatusTip('Predict for current slide')
        predictAction.triggered.connect(lambda: self.predict_slide(num_slides=None))

        predict5Action = QAction('Predict Current', self)
        predict5Action.setShortcut('Ctrl+P')
        predict5Action.setStatusTip('Predict for current 5 slides')
        predict5Action.triggered.connect(lambda: self.predict_slide(num_slides=5))

        self.addAction(slideLeftAction)
        self.addAction(slideRightAction)
        self.addAction(undoAction)
        self.addAction(renderAction)
        self.addAction(predictAction)
        self.addAction(predict5Action)
        
    
    # adding menubar actions 
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(loadAnnotAction)
        fileMenu.addAction(saveAnnotAction)
        fileMenu.addAction(mergeAnnotAction)
        fileMenu.addAction(loadWeightsAction)
        fileMenu.addAction(exportAction)
        fileMenu.addAction(exitAction)

    # adding toolbar actions
        self.toolbar = self.addToolBar('Main')
        self.toolbar.addActions([self.xyAction, self.xzAction, self.yzAction, gotoAction, selectEraserAction,ChangeVolumePreviusAction,ChangeVolumeNextAction])



    def setup_sliders(self):
        # create
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setValue(global_brightness)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(30)
        self.brightness_slider.valueChanged.connect(self.change_brightness)

        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setValue(global_contrast)
        self.contrast_slider.setMinimum(1)
        self.contrast_slider.setMaximum(15)
        self.contrast_slider.valueChanged.connect(self.change_contrast)

        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setValue(brush_size)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(15)
        self.brush_size_slider.valueChanged.connect(self.change_brush_size)

        self.eraser_size_slider = QSlider(Qt.Horizontal)
        self.eraser_size_slider.setValue(eraser_size)
        self.eraser_size_slider.setMinimum(1)
        self.eraser_size_slider.setMaximum(15)
        self.eraser_size_slider.valueChanged.connect(self.change_eraser_size)

        self.annot_opacity_slider = QSlider(Qt.Horizontal)
        self.annot_opacity_slider.setValue(int(global_annot_opacity*10))
        self.annot_opacity_slider.setSingleStep(2) # 0.1 * scaled later
        self.annot_opacity_slider.setMinimum(2)
        self.annot_opacity_slider.setMaximum(10)
        self.annot_opacity_slider.valueChanged.connect(self.change_annot_opacity)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setValue(int(global_zoom*10))
        self.zoom_slider.setSingleStep(2) # 0.1 * scaled later
        self.zoom_slider.setMinimum(0)
        self.zoom_slider.setMaximum(10)
        self.zoom_slider.valueChanged.connect(self.change_zoom)

        # add to toolbar
        self.toolbar.addSeparator()
        self.toolbar.setStyleSheet("QToolBar{spacing:10px;}")
        self.toolbar.addWidget(QLabel('Brightness'))
        self.toolbar.addWidget(self.brightness_slider)
        self.toolbar.addWidget(QLabel('Contrast'))
        self.toolbar.addWidget(self.contrast_slider)
        self.toolbar.addWidget(QLabel('Brush Size'))
        self.toolbar.addWidget(self.brush_size_slider)
        self.toolbar.addWidget(QLabel('Eraser Size'))
        self.toolbar.addWidget(self.eraser_size_slider)
        self.toolbar.addWidget(QLabel('Annotation Opacity'))
        self.toolbar.addWidget(self.annot_opacity_slider)
        # self.toolbar.addWidget(QLabel('Zoom'))
        # self.toolbar.addWidget(self.zoom_slider)
    
    def merge_annot_dialog(self):
        fnames_list, _ = QFileDialog.getOpenFileNames(self, 'Select multiple annotation files to merge and load', '.')

        global annot3D, current_slide
        if len(fnames_list) > 0:
            annot3D.mergeload(fnames_list)


    def load_weights_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Load model weights (hfd5)', '.')
        global annot3D
        if fname:
            annot3D.load_model_weights(fname)

    def load_annot_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Load annotations file', '.',filter="*.xlsx")

        #global annot3D, current_slide
        if fname:
            window.mayavi_widget.visualization.load_data(fname)
            #annot3D.load(fname)
            #for p in ['xy', 'xz', 'yz']:
            #    self.c[p].change_annot(annot3D.get_slice(p, current_slide[p]))

    def save_annots_dialog(self):
        fname, _ = QFileDialog.getSaveFileName(self, 'Save annotations file', '.')
        #global annot3D
        if fname:
            print(fname)
            print(_)
            window.mayavi_widget.visualization.save_data(fname) 
        #    annot3D.save(os.path.join(fname))    


    def export_dialog(self):
        fname, _ = QFileDialog.getSaveFileName(self, 'Export dataset directory (src and annot)', '.') # here fname is folder/dir name
        global annot3D
        print(fname)
        if fname:
            annot3D.export(fname, 'xz')

    def update_slide_number(self): #used to change slide number display
        slide_number=self.mayavi_widget.visualization.current_image_number
        text="slide "+str(slide_number+1)
        self.slide_label.setText(text)

    def goto_slide(self):
        global p, annot3D

        cs, ok = QInputDialog.getText(self, "Go to slide", "Go to slide on plane "+p)
        if ok and cs.isnumeric(): # current slide cs must be a number
            cs = int(cs)-1
            if cs < 0: # slide out of range
                return
        window.mayavi_widget.visualization.update_volume(cs)
        self.update_slide_number()



    def update_canvas_cursors(self):
        self.c['xy'].update_cursor()
        self.c['xz'].update_cursor()
        self.c['yz'].update_cursor()


    def change_zoom(self):
        global global_zoom, annot3D
        global_zoom = self.zoom_slider.value()
        #for p in ['xy', 'xz', 'yz']:
        #    self.c[p].change_annot(annot3D.get_slice(p, current_slide[p]))


    def toggle_eraser(self):
        global eraser_on
        eraser_on = not eraser_on
        self.update_canvas_cursors()


    def change_brush_size(self):
        global brush_size 
        brush_size = self.brush_size_slider.value()
        self.update_canvas_cursors()


    def change_eraser_size(self):
        #window.mayavi_widget.visualization.update_volume()
        global eraser_size 
        eraser_size = self.eraser_size_slider.value()
        self.update_canvas_cursors()


    def change_annot_opacity(self):
        global global_annot_opacity 
        global_annot_opacity = self.annot_opacity_slider.value() * 0.1
        self.c['xy'].update_annot_opacity()
        self.c['xz'].update_annot_opacity()
        self.c['yz'].update_annot_opacity()


    def change_brightness(self):
        global global_brightness
        global_brightness = self.brightness_slider.value()



    def change_contrast(self):
        global global_contrast
        global_contrast = self.contrast_slider.value()
    

    def switch_plane(self, plane):
        global p, current_slide
        p = plane
        if p == 'xy':
            self.xzAction.setChecked(False)
            self.yzAction.setChecked(False)
        elif p == 'xz':
            self.xyAction.setChecked(False)
            self.yzAction.setChecked(False)
        elif p == 'yz':
            self.xyAction.setChecked(False)
            self.xzAction.setChecked(False)
        
        self.num_slides = self.plane_depth[p]
        self.change_slide(0)
        


    def render(self):
        self.mayavi_widget.update_annot()

    
    # def focus_plane(self, curr_p):
    #     for p in ['xy', 'xz', 'yz']:
    #         if p == curr_p:
    #             self.c[p].focus(True)
    #             self.c[p].hide(False)
    #         else:
    #             self.c[p].focus(False)
    #             self.c[p].hide(True)

    # def reset_focus(self):
    #     for p in ['xy', 'xz', 'yz']:
    #         self.c[p].focus(False)
    #         self.c[p].hide(False)


    def predict_slide(self, num_slides=None):
        global annot3D, p, current_slide

        if p == 'xz': # model predictions work only for the plane it is trained on
            if num_slides is None: # not specified
                num_slides = 1

            for i in range(num_slides):
                if current_slide[p]+i >= self.dims[0]: # does not exceed slide range
                    break

                annot3D.model_predict(p, current_slide[p]+i)
                self.c[p].change_annot(annot3D.get_slice(p, current_slide[p]+i))


    def slide_left(self):
        global current_slide, p
        if (current_slide[p] > 0):
            self.change_slide(-1)


    def slide_right(self):
        global current_slide, p
        if (current_slide[p] < self.num_slides-1):
            self.change_slide(1)


    def change_slide(self, step):
        global current_slide, p, annot3D, slides
        
        current_slide[p] += step
        cs = current_slide[p]

        self.slide_label.setText(p + ': ' + str(cs+1))

        self.c[p].change_bg(self.slides[p][cs])
        self.c[p].change_annot(annot3D.get_slice(p, cs))


    def clear(self):
        global annot3D, p, current_slide
        annot3D.clear_slice(p, current_slide[p])
        self.c[p].change_annot(annot3D.get_slice(p, current_slide[p]))


    def undo(self):
        global annot3D, current_slide
        annot3D.undo_history()
        for p in ['xy', 'xz', 'yz']:
            self.c[p].change_annot(annot3D.get_slice(p, current_slide[p]))


    def set_canvas_pen_color(self, c):
        self.c['xy'].set_pen_color(c)
        self.c['xz'].set_pen_color(c)
        self.c['yz'].set_pen_color(c)

    def change_volume_model_next(self):
        window.mayavi_widget.visualization.update_volume('next')
        #self.slide_label.setText('test')
        self.update_slide_number()

    def change_volume_model_previous(self):
        window.mayavi_widget.visualization.update_volume('previous')
        self.update_slide_number()


        


if __name__ == "__main__":
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()


    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.black)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
