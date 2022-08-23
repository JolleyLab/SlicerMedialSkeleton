import vtk, qt, slicer

from SyntheticSkeletonLib.CustomData import *
from SyntheticSkeletonLib.Constants import *
from SyntheticSkeletonLib.Utils import *
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from dataclasses import astuple
from SyntheticSkeletonLib.Utils import getSortedPointIndices
from pathlib import Path


#
# SyntheticSkeleton
#


class SyntheticSkeleton(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Synthetic Skeleton"
    self.parent.categories = ["Skeletonization"]
    self.parent.dependencies = []
    self.parent.contributors = ["Christian Herz (CHOP), Nicolas Vergnat (PICSL/UPenn), Abdullah Aly (PICSL/UPenn), "
                                "Sijie Tian (PICSL/UPenn), Andras Lasso (PerkLab), Paul Yushkevich (PICSL/UPenn), "
                                "Alison Pouch (PICSL/UPenn), Matt Jolley (CHOP/UPenn)"]
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = """
This module provides functionality for creating a synthetic skeleton which is based on a Voronoi surface.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
"""


#
# SyntheticSkeletonWidget
#

class SyntheticSkeletonWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  @property
  def parameterNode(self):
    if not hasattr(self, "_parameterNode"):
      self._parameterNode = None
    return self._parameterNode

  @parameterNode.setter
  def parameterNode(self, inputParameterNode):
    if self.parameterNode is not None:
      self.removeObserver(self.parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self.parameterNode is not None:
      if self.parameterNode.GetParameterCount() == 0:
        self.logic.setDefaultParameters(self.parameterNode)
      self.addObserver(self.parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self._updatingGUIFromParameterNode = False

  def onReload(self):
    self.cleanup()
    logging.debug(f"Reloading {self. moduleName}")
    reload(packageName='SyntheticSkeletonLib', submoduleNames=['Constants', 'Utils', 'CustomData'])
    ScriptedLoadableModuleWidget.onReload(self)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeAutoSaveTimer()
    self.removeObservers()
    self.deactivateModes()
    self.logic.removeObservers()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    self.initializeUI()

    self.logic = SyntheticSkeletonLogic()

    self.timer = None

    self._selectedPoints = [] # (markupsNode.GetID(), pointIdx)

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    self._observations = []
    self.threeDViewClickObserver = None
    self.endPlacementObserver =  None
    self.placePointsShortcutObserver = None

    self.configureUI()
    self.setupConnections()

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

  def initializeUI(self):
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/SyntheticSkeleton.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    uiWidget.setMRMLScene(slicer.mrmlScene)

  def configureUI(self):
    self.ui.outputModelSelector.enabled = False

    # only use fiducial nodes created in this module
    self.ui.pointLabelSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "ModuleName", self.moduleName)

    self.ui.triangleLabelSelector.setNodeTypeLabel("TriangleLabel", "vtkMRMLScriptedModuleNode")
    self.ui.triangleLabelSelector.baseName = "TriangleLabel"
    self.ui.triangleLabelSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.ui.triangleLabelSelector.addAttribute("vtkMRMLScriptedModuleNode", "Type", "TriangleLabel")

    # set icons
    self.ui.flipNormalsButton.setIcon(qt.QIcon(self.resourcePath("Icons/flip-icon.png")))
    self.ui.assignTriangleButton.setIcon(qt.QIcon(self.resourcePath("Icons/assign-icon.png")))
    self.ui.placeTriangleButton.setIcon(qt.QIcon(self.resourcePath("Icons/add-icon.png")))
    self.ui.deleteTriangleButton.setIcon(qt.QIcon(self.resourcePath("Icons/delete-icon.png")))

    for pointType in TAG_TYPES:
      self.ui.pointTypeCombobox.addItem(pointType)

    tabWidget = self.ui.tabWidget
    tabBar = tabWidget.tabBar()
    tabBar.setTabIcon(1, qt.QIcon(self.resourcePath('Icons/triangulate-icon.png')))
    tabBar.setTabIcon(2, tabWidget.style().standardIcon(qt.QStyle.SP_DialogSaveButton))

    if hasattr(slicer.modules, "skeletontool"):
      w = slicer.modules.skeletontool.createNewWidgetRepresentation()
      tabWidget.widget(0).layout().addWidget(w)
      w.setSizePolicy(qt.QSizePolicy.MinimumExpanding, qt.QSizePolicy.Maximum)
      tabWidget.widget(0).layout().addStretch(1)
      tabBar.setTabIcon(0, qt.QIcon(self.resourcePath('Icons/SyntheticSkeleton.png')))
    else:
      logging.warning("slicer.modules.skeletontool could not be found. The CLI widget will be hidden.")
      self.ui.tabWidget.removeTab(0)

  def setupConnections(self):
    self.ui.outputPathLineEdit.currentPathChanged.connect(self.onOutputDirectoryChanged)
    self.ui.inputModelSelector.currentNodeChanged.connect(self.onInputModelChanged)

    self.ui.pointLabelSelector.currentNodeChanged.connect(self.onPointLabelSelected)
    self.ui.pointTypeCombobox.currentIndexChanged.connect(self.onPointTypeChanged)
    self.ui.pointIndexSpinbox.valueChanged.connect(self.onPointAnatomicalIndexChanged)

    self.ui.triangleLabelSelector.currentNodeChanged.connect(self.onTriangleLabelSelected)
    self.ui.triangleColorPickerButton.colorChanged.connect(self.onTriangleColorChanged)

    self.ui.placeTriangleButton.toggled.connect(self.onPlaceTriangleButtonChecked)
    self.ui.deleteTriangleButton.toggled.connect(
      lambda : self.onDeleteAssignOrFlipTriangleButtonChecked(self.ui.deleteTriangleButton))
    self.ui.assignTriangleButton.toggled.connect(
      lambda : self.onDeleteAssignOrFlipTriangleButtonChecked(self.ui.assignTriangleButton))
    self.ui.flipNormalsButton.toggled.connect(
      lambda : self.onDeleteAssignOrFlipTriangleButtonChecked(self.ui.flipNormalsButton))
    self.ui.skeletonVisibilityCheckbox.toggled.connect(
      lambda t: self.onModelVisibilityToggled(self.ui.inputModelSelector, t))
    self.ui.meshVisibilityCheckbox.toggled.connect(
      lambda t: self.onModelVisibilityToggled(self.ui.outputModelSelector, t))
    self.ui.autoSaveCheckbox.toggled.connect(self.addAutoSaveTimer)

    self.ui.skeletonTransparencySlider.valueChanged.connect(self.onSkeletonTransparencySliderMoved)
    self.ui.meshTransparanceySlider.valueChanged.connect(self.onMeshTransparencySliderMoved)
    self.ui.pointScaleSlider.valueChanged.connect(self.onPointScaleSliderMoved)

    self.ui.subLevelSpinbox.valueChanged.connect(self.onSubdivisionLevelChanged)
    self.ui.solverTypeCombobox.currentIndexChanged.connect(lambda i: self.updateParameterNodeFromGUI())
    self.ui.constantRadiusCheckbox.toggled.connect(lambda t: self.updateParameterNodeFromGUI())
    self.ui.constantRadiusSpinbox.valueChanged.connect(lambda v: self.updateParameterNodeFromGUI())
    self.ui.inflateModelCheckbox.toggled.connect(lambda t: self.updateParameterNodeFromGUI())
    self.ui.inflateRadiusSpinbox.valueChanged.connect(lambda v: self.updateParameterNodeFromGUI())
    self.ui.snapCheckbox.toggled.connect(lambda t: self.updateParameterNodeFromGUI())
    self.ui.inputSkeletonColorPickerButton.colorChanged.connect(self.onInputSkeletonColorChanged)

    self.ui.loadBinaryImageButton.clicked.connect(
      lambda: self.logic.readBinaryImageAndConvertToModel(self.ui.inputImagePathLineEdit.currentPath))

    self.ui.decimationInputModelSelector.currentNodeChanged.connect(self.onDecimationInputModelChanged)
    self.ui.decimationOutputModelSelector.currentNodeChanged.connect(self.onDecimationOutputModelChanged)
    self.ui.decimateButton.clicked.connect(self.onDecimateButtonClicked)
    self.ui.decimModelInpVisibilityCheckbox.toggled.connect(
      lambda t: self.onModelVisibilityToggled(self.ui.decimationInputModelSelector, t))
    self.ui.decimModelOutVisibilityCheckbox.toggled.connect(
      lambda t: self.onModelVisibilityToggled(self.ui.decimationOutputModelSelector, t))

    self.ui.decimationReductionSliderWidget.valueChanged.connect(
      lambda v: self.onDecimationReductionSliderValueChanged())

    self.ui.previewButton.toggled.connect(self.updatePreview)
    self.ui.saveButton.clicked.connect(self.logic.save)

    self.ui.activeScalarCombobox.connect("currentArrayChanged(vtkAbstractArray*)", self.onActiveScalarChanged)

  def onInputSkeletonColorChanged(self, color):
    node = self.ui.inputModelSelector.currentNode()
    if not node:
      return

    def hex2rgb(hex):
      from PIL import ImageColor
      return np.array(ImageColor.getcolor(hex, "RGB")) / 255.0

    dnode = node.GetDisplayNode()
    if not dnode:
      node.CreateDefaultDisplayNodes()
      dnode = node.GetDisplayNode()
    dnode.SetColor(hex2rgb(str(color)))

  def deactivateModes(self):
    for b in [self.ui.placeTriangleButton, self.ui.assignTriangleButton, self.ui.deleteTriangleButton,
              self.ui.flipNormalsButton]:
      if b.checked:
        b.setChecked(False)

    if self.ui.markupsPlaceWidget.placeModeEnabled is True:
      self.ui.markupsPlaceWidget.placeModeEnabled = False
    if self.placePointsShortcutObserver:
      logging.info("removing shortcut observer")
      slicer.util.mainWindow().removeEventFilter(self.placePointsShortcutObserver)
      self.placePointsShortcutObserver = None

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    logging.info("exit")
    self.deactivateModes()
    self.removeAutoSaveTimer()

  def enter(self):
    if slicer.util.toBool(self.parameterNode.GetParameter(PARAM_AUTO_SAVE)) is True:
      self.addAutoSaveTimer()
    self.enableMarkupsPlaceWidget()

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.parameterNode = None

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    if self.parent.isEntered:
      self.initializeParameterNode()

    logging.debug(self.parameterNode.GetParameterNames())

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    if not self.logic:
      # the module was unloaded, ignore initialization request
      return

    self.parameterNode = self.logic.getParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """
    if self.parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    self.ui.inputModelSelector.setCurrentNode(self.parameterNode.GetNodeReference(PARAM_INPUT_MODEL))
    self.ui.pointLabelSelector.setCurrentNode(self.parameterNode.GetNodeReference(PARAM_CURRENT_POINT_LABEL_LIST))
    self.ui.triangleLabelSelector.setCurrentNode(self.parameterNode.GetNodeReference(PARAM_CURRENT_TRIANGLE_LABEL_LIST))
    self.ui.pointScaleSlider.value = float(self.parameterNode.GetParameter(PARAM_POINT_GLYPH_SIZE))
    self.ui.gridTypeCombobox.currentText = self.parameterNode.GetParameter(PARAM_GRID_TYPE)
    self.ui.solverTypeCombobox.currentText = self.parameterNode.GetParameter(PARAM_GRID_MODEL_SOLVER_TYPE)
    self.ui.subLevelSpinbox.value = int(self.parameterNode.GetParameter(PARAM_GRID_MODEL_ATOM_SUBDIVISION_LEVEL))
    self.ui.constantRadiusCheckbox.checked = \
      slicer.util.toBool(self.parameterNode.GetParameter(PARAM_GRID_MODEL_COEFFICIENT_USE_CONSTANT_RADIUS))
    self.ui.constantRadiusSpinbox.value = \
      float(self.parameterNode.GetParameter(PARAM_GRID_MODEL_COEFFICIENT_CONSTANT_RADIUS))
    self.ui.inflateModelCheckbox.checked = slicer.util.toBool(self.parameterNode.GetParameter(PARAM_GRID_MODEL_INFLATE))
    self.ui.inflateRadiusSpinbox.value = float(self.parameterNode.GetParameter(PARAM_GRID_MODEL_INFLATE_RADIUS))
    self.ui.outputPathLineEdit.currentPath = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    self.ui.autoSaveCheckbox.checked = slicer.util.toBool(self.parameterNode.GetParameter(PARAM_AUTO_SAVE))
    self.ui.snapCheckbox.checked = slicer.util.toBool(self.parameterNode.GetParameter(PARAM_SNAP_POINTS_TO_SURFACE))

    inputModel = self.logic.inputModel
    if inputModel is not None:
      self.ui.skeletonVisibilityCheckbox.setChecked(inputModel.GetDisplayVisibility())
      self.ui.skeletonTransparencySlider.setValue(inputModel.GetDisplayNode().GetOpacity())

    outputModel = self.logic.outputModel
    if outputModel is not None:
      self.ui.meshVisibilityCheckbox.setChecked(outputModel.GetDisplayVisibility())
      self.ui.meshTransparanceySlider.setValue(outputModel.GetDisplayNode().GetOpacity())

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self.parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self.parameterNode.StartModify()  # Modify all properties in a single batch
    self.parameterNode.SetNodeReferenceID(PARAM_INPUT_MODEL, self.ui.inputModelSelector.currentNodeID)
    self.parameterNode.SetNodeReferenceID(PARAM_CURRENT_POINT_LABEL_LIST, self.ui.pointLabelSelector.currentNodeID)
    self.parameterNode.SetNodeReferenceID(PARAM_CURRENT_TRIANGLE_LABEL_LIST, self.ui.triangleLabelSelector.currentNodeID)
    self.parameterNode.SetParameter(PARAM_POINT_GLYPH_SIZE, str(self.ui.pointScaleSlider.value))
    self.parameterNode.SetParameter(PARAM_GRID_TYPE, self.ui.gridTypeCombobox.currentText)
    self.parameterNode.SetParameter(PARAM_GRID_MODEL_SOLVER_TYPE, self.ui.solverTypeCombobox.currentText)
    self.parameterNode.SetParameter(PARAM_GRID_MODEL_ATOM_SUBDIVISION_LEVEL, str(self.ui.subLevelSpinbox.value))
    self.parameterNode.SetParameter(
      PARAM_GRID_MODEL_COEFFICIENT_USE_CONSTANT_RADIUS, str(self.ui.constantRadiusCheckbox.checked))
    self.parameterNode.SetParameter(
      PARAM_GRID_MODEL_COEFFICIENT_CONSTANT_RADIUS, str(self.ui.constantRadiusSpinbox.value))
    self.parameterNode.SetParameter(PARAM_GRID_MODEL_INFLATE, str(self.ui.inflateModelCheckbox.checked))
    self.parameterNode.SetParameter(PARAM_GRID_MODEL_INFLATE_RADIUS, str(self.ui.inflateRadiusSpinbox.value))
    self.parameterNode.SetParameter(PARAM_OUTPUT_DIRECTORY, self.ui.outputPathLineEdit.currentPath)
    self.parameterNode.SetParameter(PARAM_AUTO_SAVE, str(self.ui.autoSaveCheckbox.checked))
    if self.ui.activeScalarCombobox.currentText != "":
      self.parameterNode.SetParameter(PARAM_OUTPUT_MODEL_SCALAR_NAME, self.ui.activeScalarCombobox.currentText)
    self.parameterNode.SetParameter(PARAM_SNAP_POINTS_TO_SURFACE, str(self.ui.snapCheckbox.checked))
    self.parameterNode.EndModify(wasModified)

  @whenDoneCall(updateParameterNodeFromGUI)
  def addAutoSaveTimer(self, checked):
    self.removeAutoSaveTimer()
    if checked and not self.timer:
      self.timer = qt.QTimer()
      self.timer.setInterval(60000)
      self.timer.connect('timeout()', self.logic.saveAffixVTKFile)
      self.timer.start()

  def removeAutoSaveTimer(self):
    if self.timer:
      self.timer.stop()
      self.timer.timeout.disconnect()
      self.timer = None

  def onDecimateButtonClicked(self):
    parameters = {"inputModel": self.ui.decimationInputModelSelector.currentNode().GetID(),
                  "outputModel": self.ui.decimationOutputModelSelector.currentNode().GetID(),
                  "reductionFactor": self.ui.decimationReductionSliderWidget.value / 100.0,
                  "boundaryDeletion": True}
    slicer.cli.run(slicer.modules.decimation, None, parameters, wait_for_completion=True)

  def onDecimationInputModelChanged(self, node):
    if node and node is self.ui.decimationOutputModelSelector.currentNode():
      self.ui.decimationOutputModelSelector.setCurrentNode(None)
    self._updateModelDecimationPolygonInfo()
    self._updateDecimationVisibilityCheckboxes()
    self._updateDecimateButtonEnabled()

  def onDecimationOutputModelChanged(self, node):
    if node and not node.GetDisplayNode():
      node.CreateDefaultDisplayNodes()
    if node and node is self.ui.decimationInputModelSelector.currentNode():
      self.ui.decimationOutputModelSelector.setCurrentNode(None)
    self._updateDecimationVisibilityCheckboxes()
    self._updateDecimateButtonEnabled()

  def onDecimationReductionSliderValueChanged(self):
    self._updateModelDecimationPolygonInfo()
    self._updateDecimateButtonEnabled()

  def _updateModelDecimationPolygonInfo(self):
    node = self.ui.decimationInputModelSelector.currentNode()
    if node is not None:
      numPolys = node.GetPolyData().GetNumberOfPolys()
      reduction = self.ui.decimationReductionSliderWidget.value
      self.ui.inputModelNumPolygonsLabel.setText(f"orig.\t{numPolys} Polygons")
      self.ui.outputModelNumPolygonsLabel.setText(f"approx.\t{int(numPolys - numPolys * reduction // 100)} Polygons")
    else:
      self.ui.inputModelNumPolygonsLabel.setText("")
      self.ui.outputModelNumPolygonsLabel.setText("")

  def _updateDecimationVisibilityCheckboxes(self):
    for cb, node in [(self.ui.decimModelInpVisibilityCheckbox, self.ui.decimationInputModelSelector.currentNode()),
                     (self.ui.decimModelOutVisibilityCheckbox, self.ui.decimationOutputModelSelector.currentNode())]:
      wasBlocked = cb.blockSignals(True)
      cb.checked = node is not None and node.GetDisplayVisibility()
      cb.blockSignals(wasBlocked)

  def _updateDecimateButtonEnabled(self):
    self.ui.decimateButton.setEnabled(self.ui.decimationInputModelSelector.currentNode() is not None and
                                      self.ui.decimationOutputModelSelector.currentNode() is not None and
                                      self.ui.decimationReductionSliderWidget.value != 0)

  def onInputModelChanged(self, node):
    buttons = [self.ui.pointLabelsCollapsibleButton, self.ui.triangleLabelsCollapsibleButton]
    if node and not node.GetPolyData().GetPointData().GetArray(SCALAR_RADIUS_NAME):
      slicer.util.errorDisplay("No 'Radius' array found in point data. The selected model may not a Voronoi skeleton.")
      self.ui.inputModelSelector.setCurrentNode(None)
      return
    self.logic.inputModel = node
    outputModel = self.logic.outputModel
    self.ui.outputModelSelector.setCurrentNode(outputModel)
    self.onOutputMeshModified(outputModel)
    if outputModel is not None:
      self.addObserver(outputModel, vtk.vtkCommand.ModifiedEvent, self.onOutputMeshModified)
    else:
      self.removeObservers(self.onOutputMeshModified)

    self.enableWidgets(buttons, node is not None)
    self.updateParameterNodeFromGUI()

  @whenDoneCall(updateParameterNodeFromGUI)
  def onActiveScalarChanged(self, array):
    outModel = self.ui.outputModelSelector.currentNode()
    if outModel is not None:
      configureDisplayNode(outModel, array)
    self.onSubdivisionLevelChanged(self.ui.subLevelSpinbox.value)

  def configureActiveScalarBox(self):
    outputModel = self.logic.outputModel
    wasBlocked = self.ui.activeScalarCombobox.blockSignals(True)
    self.ui.activeScalarCombobox.setDataSet(outputModel.GetPolyData() if outputModel else None)
    self.ui.activeScalarCombobox.blockSignals(wasBlocked)
    if outputModel is not None:
      scalarIndex = \
        self.ui.activeScalarCombobox.findText(self.parameterNode.GetParameter(PARAM_OUTPUT_MODEL_SCALAR_NAME))
      self.ui.activeScalarCombobox.setCurrentIndex(scalarIndex)

  def onOutputMeshModified(self, caller=None, event=None):
    if not self.ui.flipNormalsButton.checked:
      self.configureActiveScalarBox()
    if caller is None:
      self.ui.pointNumberLabel.setText("")
      self.ui.triangleNumberLabel.setText("")
    else:
      self.ui.pointNumberLabel.setText(str(caller.GetPolyData().GetNumberOfPoints()))
      self.ui.triangleNumberLabel.setText(str(caller.GetPolyData().GetNumberOfPolys()))

  @whenDoneCall(updateParameterNodeFromGUI)
  def onPointLabelSelected(self, node):
    self.enableWidgets([self.ui.pointTypeCombobox, self.ui.pointIndexSpinbox], node is not None)

    if not node:
      self.ui.pointTypeCombobox.setCurrentIndex(0)
      self.enableMarkupsPlaceWidget()
      return

    self.logic.addMarkupNodesObserver(node)

    # type index
    typeIndex = node.GetAttribute("TypeIndex")
    if typeIndex:
      self.ui.pointTypeCombobox.setCurrentIndex(int(typeIndex))
    else:
      self.ui.pointTypeCombobox.setCurrentIndex(0)

    # anatomical index
    anatomicalIndex = node.GetAttribute("AnatomicalIndex")
    if anatomicalIndex:
      self.ui.pointIndexSpinbox.setValue(int(anatomicalIndex))
    else:
      self.ui.pointIndexSpinbox.setValue(1)
      self.onPointAnatomicalIndexChanged(1)

  def onPointTypeChanged(self, index):
    pointLabelNode = self.ui.pointLabelSelector.currentNode()
    if not pointLabelNode:
      return

    if index != 0:
      pointLabelNode.SetAttribute("TypeIndex", str(index))
    else:
      pointLabelNode.RemoveAttribute("TypeIndex")
    self.enableMarkupsPlaceWidget()

  def onPointAnatomicalIndexChanged(self, value):
    pointLabelNode = self.ui.pointLabelSelector.currentNode()
    if not pointLabelNode:
      return

    pointLabelNode.SetAttribute("AnatomicalIndex", str(value))
    self.enableMarkupsPlaceWidget()

  def enableMarkupsPlaceWidget(self):
    pointLabelNode = self.ui.pointLabelSelector.currentNode()
    self.ui.markupsPlaceWidget.setEnabled(
      pointLabelNode is not None and \
      pointLabelNode.GetAttribute("TypeIndex") is not None and \
      pointLabelNode.GetAttribute("AnatomicalIndex") is not None
    )
    if self.ui.markupsPlaceWidget.enabled and not self.placePointsShortcutObserver:
      self.placePointsShortcutObserver = \
        KeyboardShortcutObserver(qt.Qt.Key_A, self.ui.markupsPlaceWidget.setPlaceModeEnabled)
      slicer.util.mainWindow().installEventFilter(self.placePointsShortcutObserver)
    else:
      slicer.util.mainWindow().removeEventFilter(self.placePointsShortcutObserver)
      self.placePointsShortcutObserver = None

  def enableWidgets(self, widgets, condition):
    for w in widgets:
      w.setEnabled(condition)

  @whenDoneCall(updateParameterNodeFromGUI)
  def onTriangleLabelSelected(self, node):
    self.ui.placeTriangleButton.setEnabled(node is not None)
    buttons = [self.ui.placeTriangleButton, self.ui.deleteTriangleButton,
               self.ui.assignTriangleButton, self.ui.flipNormalsButton, self.ui.triangleColorPickerButton]
    self.enableWidgets(buttons, node is not None)
    if not node:
      self.deactivateModes()
      return

    for lblIdx, triLabel in enumerate(self.logic.data.vectorLabelInfo):
      if triLabel.mrmlNodeID == node.GetID():
        wasBlocked = self.ui.triangleIndexSpinbox.blockSignals(True)
        self.ui.triangleIndexSpinbox.value = lblIdx + 1
        self.ui.triangleIndexSpinbox.blockSignals(wasBlocked)
        break

    color = node.GetAttribute("Color")
    if color:
      self.ui.triangleColorPickerButton.setColor(qt.QColor(color))
    else:
      color = qt.QColor("#ff0000")
      self.ui.triangleColorPickerButton.setColor(color)
      self.onTriangleColorChanged(color)

  def onTriangleColorChanged(self, color):
    triangleNode = self.ui.triangleLabelSelector.currentNode()
    if not triangleNode:
      return

    triangleNode.SetAttribute("Color", str(color))

  def onModelVisibilityToggled(self, selector, toggled):
    node = selector.currentNode()
    if node:
      node.SetDisplayVisibility(toggled)

  def onSkeletonTransparencySliderMoved(self, value):
    node = self.ui.inputModelSelector.currentNode()
    if node:
      dNode = node.GetDisplayNode()
      dNode.SetOpacity(value)

  def onMeshTransparencySliderMoved(self, value):
    node = self.ui.outputModelSelector.currentNode()
    if node:
      dNode = node.GetDisplayNode()
      dNode.SetOpacity(value)

  def onPointScaleSliderMoved(self, value):
    for mn in self.logic.getAllMarkupNodes():
      mn.GetDisplayNode().SetGlyphScale(value)

  @whenDoneCall(updateParameterNodeFromGUI)
  def onOutputDirectoryChanged(self, path):
    self.ui.saveButton.setEnabled(Path(path).exists())

  def updatePreview(self, checked):
    if checked:
      subdividedModel = self.logic.createSubdivideMesh()
      if subdividedModel:
        if not subdividedModel.GetDisplayNode():
          subdividedModel.CreateDefaultDisplayNodes()

        outputModel = self.logic.outputModel
        if outputModel:
          dispNode = outputModel.GetDisplayNode()
          arrayName = dispNode.GetActiveScalarArray().GetName()
          arr = getArrayByName(subdividedModel.GetPolyData(), arrayName)
          if arr:
            configureDisplayNode(subdividedModel, arr)
    else:
      m = self.parameterNode.GetNodeReference(PARAM_SUBDIVISION_PREVIEW_MODEL)
      if m:
        slicer.mrmlScene.RemoveNode(m)
        self.parameterNode.SetNodeReferenceID(PARAM_SUBDIVISION_PREVIEW_MODEL, "")

  def onSubdivisionLevelChanged(self, value):
    self.updateParameterNodeFromGUI()
    if value > 0 and self.ui.previewButton.checked:
        self.updatePreview(True)
    else:
      self.ui.previewButton.setChecked(False)

  def onPlaceTriangleButtonChecked(self, checked):
    if checked and self.ui.deleteTriangleButton.checked:
      self.ui.deleteTriangleButton.setChecked(False)
    if checked and self.ui.assignTriangleButton.checked:
      self.ui.assignTriangleButton.setChecked(False)

    if checked:
      self.addObserversForTriangleCreation()
    else:
      self.removeObserversForTriangleCreation()

  def addObserversForTriangleCreation(self):
    for markupsNode in self.logic.getAllMarkupNodes():
      dNode = markupsNode.GetDisplayNode()
      self._observations.append([dNode, dNode.AddObserver(dNode.JumpToPointEvent, self.onTrianglePointSelected)])

  def removeObserversForTriangleCreation(self):
    for observedNode, observation in self._observations:
      observedNode.RemoveObserver(observation)
    self.clearSelection()

  def onTrianglePointSelected(self, caller, eventId):
    pointIdx = caller.GetActiveControlPoint()
    markupsNode = caller.GetMarkupsNode()
    selected = markupsNode.GetNthControlPointSelected(pointIdx)
    markupsNode.SetNthControlPointSelected(pointIdx, not selected)
    t = (markupsNode.GetID(), pointIdx)
    if selected is False and t in self._selectedPoints:
      self._selectedPoints.remove(t)
    else:
      self._selectedPoints.append(t)

    if len(self._selectedPoints) > 1:
      m = self.logic.preCheckConstraints(self._selectedPoints)
      if m and confirmOrIgnoreDialog(m):
        self.clearLastSelection()
        return
      else:
        if len(self._selectedPoints) == 3:
          try:
            nextPtIndices = \
              self.logic.attemptToAddTriangle(self._selectedPoints, self.ui.triangleLabelSelector.currentNodeID)
            logging.debug(nextPtIndices)
            if not nextPtIndices:
              self.clearSelection()
            else:
              delete = []
              for selIdx, _ in enumerate(self._selectedPoints):
                if not selIdx in nextPtIndices:
                  delete.append(selIdx)
              for index in sorted(delete, reverse=True):
                mnId, idx = self._selectedPoints[index]
                del self._selectedPoints[index]
                slicer.util.getNode(mnId).SetNthControlPointSelected(idx, True)
          except ValueError as exc:
            slicer.util.warningDisplay(exc, "Violation")
            self.clearLastSelection()

  def clearSelection(self):
    for mnId, idx in self._selectedPoints:
      slicer.util.getNode(mnId).SetNthControlPointSelected(idx, True)
    self._selectedPoints.clear()

  def clearLastSelection(self):
    mnId, idx = self._selectedPoints.pop(-1)
    slicer.util.getNode(mnId).SetNthControlPointSelected(idx, True)

  def checkButtonBlockSignals(self, button, checked):
    wasBlocked = button.blockSignals(True)
    button.checked = checked
    button.blockSignals(wasBlocked)

  def onDeleteAssignOrFlipTriangleButtonChecked(self, button):
    checked = button.checked
    if checked and self.ui.placeTriangleButton.checked:
      self.ui.placeTriangleButton.setChecked(False)

    if checked and button is self.ui.assignTriangleButton:
      self.checkButtonBlockSignals(self.ui.deleteTriangleButton, False)
      self.checkButtonBlockSignals(self.ui.flipNormalsButton, False)

    if checked and button is self.ui.deleteTriangleButton:
      self.checkButtonBlockSignals(self.ui.assignTriangleButton, False)
      self.checkButtonBlockSignals(self.ui.flipNormalsButton, False)

    if checked and button is self.ui.flipNormalsButton:
      self.checkButtonBlockSignals(self.ui.assignTriangleButton, False)
      self.checkButtonBlockSignals(self.ui.deleteTriangleButton, False)

    modelNode = self.logic.outputModel
    dnode = modelNode.GetDisplayNode()
    dnode.EdgeVisibilityOn()
    dnode.SetScalarVisibility(not self.ui.flipNormalsButton.checked)

    self.ui.activeScalarCombobox.setEnabled(not self.ui.flipNormalsButton.checked)

    try:
      pointListNode = slicer.util.getNode("F")  # points will be selected at positions specified by this markups point list node
      pointListNode.RemoveAllMarkups()
    except slicer.util.MRMLNodeNotFoundException:
      pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "F")
    pointListNode.SetDisplayVisibility(False)

    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
    selectionNode.SetActivePlaceNodeID(pointListNode.GetID())

    interactionNode.SwitchToPersistentPlaceMode()
    interactionNode.SetCurrentInteractionMode(interactionNode.Place if checked else interactionNode.Select)

    if checked:
      qt.QApplication.setOverrideCursor(qt.Qt.CrossCursor)

    buttons = [self.ui.assignTriangleButton, self.ui.deleteTriangleButton, self.ui.flipNormalsButton]
    if any(b.checked is True for b in buttons) and self.threeDViewClickObserver is None and self.endPlacementObserver is None:
      # Automatic update each time when a markup point is modified
      self.threeDViewClickObserver = \
        pointListNode.AddObserver(slicer.vtkMRMLMarkupsFiducialNode.PointPositionDefinedEvent, self.onTriangleSelection)

      self.endPlacementObserver = interactionNode.AddObserver(slicer.vtkMRMLInteractionNode.EndPlacementEvent,
                                                              self.onEndTriangleSelectionEvent)
    elif all(b.checked is False for b in buttons) and \
        self.threeDViewClickObserver is not None and \
        self.endPlacementObserver is not None:
      qt.QApplication.setOverrideCursor(qt.Qt.ArrowCursor)
      pointListNode.RemoveObserver(self.threeDViewClickObserver)
      self.threeDViewClickObserver = None
      pointListNode.RemoveObserver(self.endPlacementObserver)
      self.endPlacementObserver = None
      slicer.mrmlScene.RemoveNode(pointListNode)

    self.onOutputMeshModified()

  def onTriangleSelection(self, markupsNode=None, eventid=None):
    for markupPoint in slicer.util.arrayFromMarkupsControlPoints(markupsNode):
      if self.ui.assignTriangleButton.checked:
        self.logic.assignTriangleLabel(markupPoint, self.ui.triangleLabelSelector.currentNodeID)
      elif self.ui.deleteTriangleButton.checked:
        self.logic.attemptTriangleDeletion(markupPoint)
      elif self.ui.flipNormalsButton.checked:
        self.logic.flipTriangleNormal(markupPoint)
    markupsNode.RemoveAllControlPoints()

  def onEndTriangleSelectionEvent(self, caller=None, eventid=None):
    self.ui.assignTriangleButton.setChecked(False)
    self.ui.deleteTriangleButton.setChecked(False)

#
# SyntheticSkeletonLogic
#

class SyntheticSkeletonLogic(VTKObservationMixin, ScriptedLoadableModuleLogic):

  @property
  def parameterNode(self):
    return self.getParameterNode()

  @property
  def inputModel(self):
    mrmlNodeId = self.parameterNode.GetNodeReferenceID(PARAM_INPUT_MODEL)
    if not mrmlNodeId:
      return None
    else:
      return slicer.util.getNode(mrmlNodeId)

  @inputModel.setter
  def inputModel(self, node):
    self.parameterNode.SetNodeReferenceID(PARAM_INPUT_MODEL, "" if node is None else node.GetID())
    self.configurePointLocator(node)

    if node:
      outputModel = node.GetNodeReference(PARAM_OUTPUT_MODEL)
      if not outputModel:  # create new output model
        outputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", f"{node.GetName()}_syn_skeleton")
        node.SetNodeReferenceID(PARAM_OUTPUT_MODEL, outputModel.GetID())
      polydata = node.GetPolyData()
      customInfo = CustomInformation(polydata)
      customInfo.readCustomData()
      if customInfo.hasCustomData() is not None and len(list(self.getAllMarkupNodes())) == 0:
        self.readCustomInformation(customInfo)

  @property
  def outputModel(self):
    inputModel = self.inputModel
    return inputModel.GetNodeReference(PARAM_OUTPUT_MODEL) if inputModel else None

  def __init__(self):
    VTKObservationMixin.__init__(self)
    ScriptedLoadableModuleLogic.__init__(self)

    self.locator = None
    self.data = CustomInformation()
    self.pointArray = dict()
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.addSceneObservers()

  def addSceneObservers(self):
    self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)
    self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAboutToBeRemovedEvent, self.onNodeRemoved)

  def onSceneStartClose(self, caller, event):
    self.removeObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)
    self.removeObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAboutToBeRemovedEvent, self.onNodeRemoved)
    self.locator = None
    self.data = CustomInformation()
    self.pointArray = dict()

  def onSceneEndClose(self, caller, event):
    self.addSceneObservers()

  def __del__(self):
    pass

  def resetData(self):
    self.data = CustomInformation(self.inputModel.GetPolyData() if self.inputModel else None)

  def createParameterNode(self):
    parameterNode = ScriptedLoadableModuleLogic.createParameterNode(self)
    self.setDefaultParameters(parameterNode)
    return parameterNode

  def setDefaultParameters(self, parameterNode):
    for paramName, paramDefaultValue in PARAM_DEFAULTS.items():
      if not parameterNode.GetParameter(paramName):
        parameterNode.SetParameter(paramName, str(paramDefaultValue))

  def updateOutputMesh(self):
    triangles = vtk.vtkCellArray()

    meshPoly = vtk.vtkPolyData()
    meshPoints = vtk.vtkPoints()
    meshPoly.SetPoints(meshPoints)

    for pt in self.data.vectorTagPoints:
      meshPoints.InsertNextPoint(astuple(pt.pos))

    radiusArray = vtk.vtkFloatArray()
    radiusArray.SetName(SCALAR_RADIUS_NAME)
    for pt in self.data.vectorTagPoints:
      radiusArray.InsertNextValue(pt.radius)
    meshPoly.GetPointData().AddArray(radiusArray)

    labelArray = vtk.vtkFloatArray()
    labelArray.SetName(SCALAR_POINT_ANATOMICAL_INDEX_NAME)
    for pt in self.data.vectorTagPoints:
      labelArray.InsertNextValue(pt.typeIndex)
    meshPoly.GetPointData().AddArray(labelArray)

    colorsArray = vtk.vtkUnsignedCharArray()
    colorsArray.SetNumberOfComponents(3)
    colorsArray.SetName(SCALAR_TRIANGLE_COLOR_NAME)

    for tri in self.data.vectorTagTriangles:
      triPtIds = self.data.triPtIds(tri)
      triangle = vtk.vtkTriangle()
      triangle.GetPointIds().SetId(0, triPtIds[0])
      triangle.GetPointIds().SetId(1, triPtIds[1])
      triangle.GetPointIds().SetId(2, triPtIds[2])
      triangles.InsertNextCell(triangle)

      color = qt.QColor(tri.label.labelColor)
      colorsArray.InsertNextTuple3(color.red(), color.green(), color.blue())

    fltArray8 = vtk.vtkFloatArray()
    fltArray8.SetName(SCALAR_TRIANGLE_ANATOMICAL_INDEX_NAME)
    for ti in self.data.vectorTagTriangles:
      fltArray8.InsertNextValue(self.data.vectorLabelInfo.index(ti.label) + 1)
    meshPoly.GetCellData().AddArray(fltArray8)

    meshPoly.GetCellData().SetScalars(colorsArray)
    meshPoly.SetPoints(meshPoints)
    meshPoly.SetPolys(triangles)

    self.outputModel.SetAndObservePolyData(meshPoly)

  def configurePointLocator(self, node):
    if node:
      self.locator = vtk.vtkKdTreePointLocator()
      self.locator.SetDataSet(node.GetPolyData())
      self.locator.BuildLocator()
    else:
      self.locator = None

  def getAllMarkupNodes(self):
    return filter(lambda node: node.GetAttribute('ModuleName') == self.moduleName,
                  slicer.util.getNodesByClass('vtkMRMLMarkupsNode'))

  def getAllTriangleNodes(self):
    return filter(lambda node: node.GetAttribute('ModuleName') == self.moduleName and
                               node.GetAttribute('Type') == "TriangleLabel",
                  slicer.util.getNodesByClass('vtkMRMLScriptedModuleNode'))

  def addMarkupNodesObserver(self, markupsNode):
    self.addObserver(markupsNode, markupsNode.PointPositionDefinedEvent, self.onPointAdded)
    self.addObserver(markupsNode, markupsNode.PointStartInteractionEvent, self.onPointInteractionStarted)
    self.addObserver(markupsNode, markupsNode.PointEndInteractionEvent, self.onPointInteractionEnded)
    self.addObserver(markupsNode, markupsNode.PointRemovedEvent, self.onPointRemoved)

  def onDataModified(self):
    self.updateOutputMesh()

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onNodeAdded(self, caller, event, node):
    logging.debug(f"onNodeAdded {node.GetID()}")
    if isinstance(node, slicer.vtkMRMLScriptedModuleNode) and \
        node.GetAttribute('ModuleName') == self.moduleName and node.GetAttribute('Type') == "TriangleLabel":
        self.onTriangleLabelAdded(node)
    elif isinstance(node, slicer.vtkMRMLMarkupsFiducialNode) and node.GetAttribute('ModuleName') == self.moduleName:
        self.onPointLabelAdded(node)

  def onTriangleLabelAdded(self, node):
    color = node.GetAttribute("Color")
    color = qt.QColor(color) if color else qt.QColor(DEFAULT_TRIANGLE_COLOR)
    self.data.vectorLabelInfo.append(
      LabelTriangle(labelName=node.GetName(), labelColor=str(color), mrmlNodeID=node.GetID())
    )
    # logging.debug(self.data.vectorLabelInfo)
    self.addObserver(node, vtk.vtkCommand.ModifiedEvent, self.onTriangleModified)

  def onPointLabelAdded(self, node):
    dnode = node.GetDisplayNode()
    if not dnode:
      node.CreateDefaultDisplayNodes()
      dnode = node.GetDisplayNode()
    dnode.SetTextScale(0)
    dnode.SetColor(DEFAULT_POINT_COLOR)
    dnode.SetActiveColor(DEFAULT_POINT_COLOR)
    dnode.SetPointLabelsVisibility(False)
    dnode.SetPropertiesLabelVisibility(False)
    dnode.SetGlyphScale(float(self.getParameterNode().GetParameter(PARAM_POINT_GLYPH_SIZE)))
    color = dnode.GetSelectedColor()
    anatomicalIndex = node.GetAttribute("AnatomicalIndex")
    ti = TagInfo(
      tagName=node.GetName(),
      tagType=int(node.GetAttribute("TypeIndex") if node.GetAttribute("TypeIndex") else -1),
      tagIndex=int(anatomicalIndex) if anatomicalIndex else "",
      tagColor=Color(color[0] * 255, color[1] * 255, color[2] * 255),
      mrmlNodeID=node.GetID()
    )
    self.data.vectorTagInfo.append(ti)
    self.addObserver(node, vtk.vtkCommand.ModifiedEvent, self.onMarkupsNodeModified)

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onNodeRemoved(self, caller, event, node):
    logging.debug(f"onNodeRemoved {node.GetID()}")
    if isinstance(node, slicer.vtkMRMLScriptedModuleNode) and \
        node.GetAttribute('ModuleName') == self.moduleName and node.GetAttribute('Type') == "TriangleLabel":
        self.onTriangleLabelRemoved(node)
    elif isinstance(node, slicer.vtkMRMLMarkupsFiducialNode) and node.GetAttribute('ModuleName') == self.moduleName:
      self.onPointLabelRemoved(node)

  def onTriangleLabelRemoved(self, node):
    delete = []

    for lblIdx, triLabel in enumerate(self.data.vectorLabelInfo):
      if triLabel.mrmlNodeID == node.GetID():
        for triIdx, tri in enumerate(self.data.vectorTagTriangles):
          if tri.label == triLabel:
            delete.append(triIdx)
        del self.data.vectorLabelInfo[lblIdx]
        break

    for triIdx in sorted(delete, reverse=True):
      del self.data.vectorTagTriangles[triIdx]

    self.removeObserver(node, vtk.vtkCommand.ModifiedEvent, self.onTriangleModified)
    self.generateEdges()
    self.onDataModified()

  def onPointLabelRemoved(self, node):
    for idx in reversed(range(node.GetNumberOfControlPoints())):
      self.onPointRemoved(node, "PointRemovedEvent", idx, callModified=False)
    self.removeObserver(node, vtk.vtkCommand.ModifiedEvent, self.onMarkupsNodeModified)

    for idx, ti in enumerate(self.data.vectorTagInfo):
      if ti.mrmlNodeID == node.GetID():
        del self.data.vectorTagInfo[idx]
        break

    self.generateEdges()
    self.onDataModified()

  def onTriangleModified(self, caller, event):
    for tl in self.data.vectorLabelInfo:
      if caller.GetID() == tl.mrmlNodeID:
        tl.labelName = caller.GetName()
        tl.labelColor = caller.GetAttribute("Color")
        # logging.debug(self.data.vectorLabelInfo)
        break
    self.onDataModified()

  def onMarkupsNodeModified(self, node, event):
    for ti in self.data.vectorTagInfo:
      if node.GetID() == ti.mrmlNodeID:
        dnode = node.GetDisplayNode()
        color = dnode.GetSelectedColor()
        ti.tagName = node.GetName()
        ti.tagType = int(node.GetAttribute("TypeIndex") if node.GetAttribute("TypeIndex") else -1)
        ti.tagIndex = int(node.GetAttribute("AnatomicalIndex"))
        ti.tagColor = Color(color[0] * 255, color[1] * 255, color[2] * 255)
        # logging.debug(self.data.vectorTagInfo)
        break
    self.onDataModified()

  def readCustomInformation(self, customInfo: CustomInformation):
    self.resetData()
    markupNodes = []
    for ti in customInfo.vectorTagInfo:
      n = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", ti.tagName)
      n.SetAttribute("TypeIndex", str(ti.tagType))
      n.SetAttribute("AnatomicalIndex", str(ti.tagIndex))
      n.SetAttribute("ModuleName", self.moduleName)
      dNode = n.GetDisplayNode()
      dNode.SetSelectedColor([ti.tagColor.r / 255.0, ti.tagColor.g / 255.0, ti.tagColor.b / 255.0])
      markupNodes.append(n)
      self.onNodeAdded(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, n)
      self.addMarkupNodesObserver(n)

    for p in customInfo.vectorTagPoints:
      pos = p.pos
      mn = markupNodes[customInfo.vectorTagInfo.index(p.tag)]
      mn.AddControlPoint(vtk.vtkVector3d(pos.x, pos.y, pos.z))

    for tl in customInfo.vectorLabelInfo:
      n = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode", tl.labelName)
      n.SetAttribute("ModuleName", self.moduleName)
      n.SetAttribute("Color", tl.labelColor)
      n.SetAttribute("Type", "TriangleLabel")
      self.onNodeAdded(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, n)

    self.data.vectorTagTriangles = []
    for srcTri in customInfo.vectorTagTriangles:
      triIds = customInfo.triPtIds(srcTri)
      tri = TagTriangle(
        p1=self.data.vectorTagPoints[triIds[0]],
        p2=self.data.vectorTagPoints[triIds[1]],
        p3=self.data.vectorTagPoints[triIds[2]],
        label=self.data.vectorLabelInfo[customInfo.vectorLabelInfo.index(srcTri.label)]
      )
      self.data.vectorTagTriangles.append(tri)

    self.generateEdges()

    for uniqueId, edge in self.data.vectorTagEdges.items():
      assert uniqueId == pairNumber(edge.ptId1, edge.ptId2)

    self.onDataModified()

  def getClosestVertexAndRadius(self, pos):
    assert self.locator is not None
    vertexIdx = self.locator.FindClosestPoint(pos)
    poly = self.locator.GetDataSet()
    radiusArray = poly.GetPointData().GetArray(SCALAR_RADIUS_NAME)
    return vertexIdx, radiusArray.GetValue(vertexIdx)

  def onPointAdded(self, caller, event):
    logging.debug("Point Added")
    pointIdx = caller.GetNumberOfControlPoints()-1
    pos = caller.GetNthControlPointPosition(pointIdx)
    vertIdx, radius = self.getClosestVertexAndRadius(pos)
    poly = self.inputModel.GetPolyData()
    if slicer.util.toBool(self.parameterNode.GetParameter(PARAM_SNAP_POINTS_TO_SURFACE)):
      caller.SetNthControlPointPosition(pointIdx, poly.GetPoints().GetPoint(vertIdx))

    pt = TagPoint(
      pos=Point(*pos),
      radius=radius,
      tag=self.data.getTagInfo(caller),
      seq=vertIdx
    )
    logging.debug(f"New: {pt}")
    self.data.vectorTagPoints.append(pt)
    self.pointArray[(caller.GetID(), pointIdx)] = len(self.data.vectorTagPoints) - 1

    self.onDataModified()

  def onPointInteractionStarted(self, caller, event):
    self.addObserver(caller, caller.PointModifiedEvent, self.onPointModified)

  @vtk.calldata_type(vtk.VTK_INT)
  def onPointModified(self, caller, event, pointIdx):
    # logging.debug(f"modified event {caller.GetID}, {pointIdx}, {self.pointArray[(caller.GetID(), pointIdx)]}")

    pointIdx = caller.GetDisplayNode().GetActiveControlPoint()
    pos = caller.GetNthControlPointPosition(pointIdx)
    pt = self.data.vectorTagPoints[self.pointArray[(caller.GetID(), pointIdx)]]
    pt.pos = Point(*pos)
    self.updateOutputMesh()

  def onPointInteractionEnded(self, caller, event):
    self.removeObserver(caller, caller.PointModifiedEvent, self.onPointModified)
    pointIdx = caller.GetDisplayNode().GetActiveControlPoint()
    pos = caller.GetNthControlPointPosition(pointIdx)
    vertIdx, radius = self.getClosestVertexAndRadius(pos)
    poly = self.locator.GetDataSet()
    if slicer.util.toBool(self.parameterNode.GetParameter(PARAM_SNAP_POINTS_TO_SURFACE)):
      caller.SetNthControlPointPosition(pointIdx, poly.GetPoints().GetPoint(vertIdx))
    pos = caller.GetNthControlPointPosition(pointIdx)

    pt = self.data.vectorTagPoints[self.pointArray[(caller.GetID(), pointIdx)]]
    pt.pos = Point(*pos)
    pt.radius = radius
    pt.seq = vertIdx

    self.onDataModified()

  @vtk.calldata_type(vtk.VTK_INT)
  def onPointRemoved(self, caller, event, localPointIdx, callModified=True):
    logging.debug(f"onPointRemoved: {caller.GetID()}, idx: {localPointIdx}")
    try:
      globPIdx = self.pointArray[(caller.GetID(), localPointIdx)]
    except KeyError:
      logging.debug("could not find point in global array")
      return

    # delete triangles
    delete = []
    pt = self.data.vectorTagPoints[globPIdx]
    for triIdx, tri in enumerate(self.data.vectorTagTriangles):
      if pt in tri.points:
        delete.append(triIdx)
    for index in sorted(delete, reverse=True):
      del self.data.vectorTagTriangles[index]

    del self.data.vectorTagPoints[globPIdx]
    del self.pointArray[(caller.GetID(), localPointIdx)]

    # updating global array including global index and their local index if from the same markups list
    newDict = dict()
    for key, val in self.pointArray.items():
      mnId, idx = key
      if val > globPIdx:
        val = val - 1
      if mnId == caller.GetID() and idx > localPointIdx:
        newDict[(mnId, idx-1)] = val
      else:
        newDict[key] =  val
    self.pointArray = newDict

    if callModified:
      self.generateEdges()
      self.onDataModified()

  def generateEdges(self):
    self.data.vectorTagEdges = OrderedDict()
    for tri in self.data.vectorTagTriangles:
      self.checkEdgeConstraints(self.data.triPtIds(tri))

  def preCheckConstraints(self, points):
    types = [TAG_TYPES[int(slicer.util.getNode(mn).GetAttribute("TypeIndex"))] for mn, pIdx in points]

    if len(types) == 2 and all(t == EDGE_POINT for t in types):
      return self.checkEdgePoints(points, 0, 1)

    if len(types) == 3:
      if all(t == EDGE_POINT for t in types):
        return f"Cannot use three points of type '{EDGE_POINT}' to create triangle"
      else: # not all are edge points
        indices = [i for i, x in enumerate(types) if x == EDGE_POINT]
        if len(indices) == 2:
          return self.checkEdgePoints(points, indices[0], indices[1])
    return ""

  def checkEdgePoints(self, points, ptIdx1, ptIdx2):
    m = ""
    if points[ptIdx1][0] != points[ptIdx2][0]: # different point lists
      return f"Cannot use edge points from different lists"

    node = slicer.util.getNode(points[ptIdx1][0])
    sortedIndices = getSortedPointIndices(slicer.util.arrayFromMarkupsControlPoints(node))
    for ix, idx in enumerate(sortedIndices):
      node.SetNthMarkupLabel(idx, f"{ix}")
    pt1Idx = sortedIndices.index(points[ptIdx1][1])
    pt2Idx = sortedIndices.index(points[ptIdx2][1])
    nControlPoints = node.GetNumberOfControlPoints()
    # taking care of case if first and last idx was selected (which are neighbors)
    if not sorted([pt1Idx, pt2Idx]) == [0, nControlPoints - 1] and abs(pt1Idx - pt2Idx) != 1:
      m = "Violation: Only directly neighboring edge points can be connected."
    return m

  def attemptToAddTriangle(self, selectedPoints, triLabelId):
    for lblIdx, triLabel in enumerate(self.data.vectorLabelInfo):
      if triLabel.mrmlNodeID == triLabelId:
        triPtIds = [self.pointArray[i] for i in selectedPoints]
        tri = self.createTriangle(triPtIds, triLabel)
        self.onDataModified()
        nextTriPtIds = self.getNextTriPt(tri)
        logging.debug(f"after {triPtIds}")
        logging.debug(f"Next PT ids {nextTriPtIds}")
        return [triPtIds.index(ptId) for ptId in nextTriPtIds]
    raise ValueError("No valid triangle label found")

  def isValidEdge(self, ptId1, ptId2):
    edgeId12 = pairNumber(ptId1, ptId2)
    edgeId21 = pairNumber(ptId1, ptId2)
    if edgeId12 in self.data.vectorTagEdges.keys():
      edge = self.data.vectorTagEdges[edgeId12]
    elif edgeId21 in self.data.vectorTagEdges.keys():
      edge = self.data.vectorTagEdges[edgeId21]
    else:
      cons = self.data.getEdgeConstraint(self.data.vectorTagPoints[ptId1], self.data.vectorTagPoints[ptId2])
      edge = TagEdge(
        ptId1=ptId1,
        ptId2=ptId2,
        seq=0,
        numEdge=0,
        constrain=cons
      )

    if edge.numEdge >= edge.constrain:
      return False
    return True

  def getNextTriPt(self, tri):
    triPtIds = self.data.triPtIds(tri)
    if self.isValidEdge(triPtIds[1], triPtIds[2]):
      return [triPtIds[1], triPtIds[2]]
    elif self.isValidEdge(triPtIds[0], triPtIds[1]):
      return [triPtIds[0], triPtIds[1]]
    elif self.isValidEdge(triPtIds[0], triPtIds[2]):
      return [triPtIds[0], triPtIds[2]]
    else:
      return []

  def createTriangle(self, triPtIds, label):
    logging.debug(f"ID {triPtIds}")

    # CurvePointOrder
    logging.debug(triPtIds)
    triPtIds = self.checkNormal(triPtIds.copy())
    logging.debug(triPtIds)
    m = self.checkEdgeConstraints(triPtIds)
    if m:
      raise ValueError(m)

    vectorTagPoints = self.data.vectorTagPoints

    # Store the new triangle
    tri = TagTriangle(
      p1=vectorTagPoints[triPtIds[0]],
      p2=vectorTagPoints[triPtIds[1]],
      p3=vectorTagPoints[triPtIds[2]],
      label=label
    )

    self.data.vectorTagTriangles.append(tri)
    return tri

  def checkEdgeConstraints(self, triPtIds):
    edge1 = self.getOrCreateEdge(triPtIds[0], triPtIds[1])
    if edge1.numEdge >= edge1.constrain:
      return f"Edge number 1 already has {edge1.numEdge} connection(s) and can only have {edge1.constrain} connection(s) maximum."
    edge2 = self.getOrCreateEdge(triPtIds[1], triPtIds[2])
    if edge2.numEdge >= edge2.constrain:
      return f"Edge number 2 already has {edge2.numEdge} connection(s) and can only have {edge2.constrain} connection(s) maximum."
    edge3 = self.getOrCreateEdge(triPtIds[2], triPtIds[0])
    if edge3.numEdge >= edge3.constrain:
      return f"Edge number 3 already has {edge3.numEdge} connection(s) and can only have {edge3.constrain} connection(s) maximum."

    edge1.increaseNumEdges()
    edge2.increaseNumEdges()
    edge3.increaseNumEdges()

    return ""

  def getOrCreateEdge(self, ptId1, ptId2):
    edgeId = pairNumber(ptId1, ptId2)
    try:
      edge = self.data.vectorTagEdges[edgeId]
    except KeyError:
      vectorTagPoints = self.data.vectorTagPoints
      cons = self.data.getEdgeConstraint(vectorTagPoints[ptId1], vectorTagPoints[ptId2])
      edge = TagEdge(
        ptId1=ptId1,
        ptId2=ptId2,
        seq=0,
        numEdge=0,
        constrain=cons
      )
      self.data.vectorTagEdges[edgeId] = edge
    return edge

  def assignTriangleLabel(self, pos, triLabelId: str):
    if not self.outputModel:
      return
    poly = self.outputModel.GetPolyData()

    for lblIdx, triLabel in enumerate(self.data.vectorLabelInfo):
      if triLabel.mrmlNodeID == triLabelId:
        for triIdx, tri in enumerate(self.data.vectorTagTriangles):
          if poly.GetCell(triIdx).PointInTriangle(pos, astuple(tri.p1.pos), astuple(tri.p2.pos), astuple(tri.p3.pos), 0.1):
            tri.label = triLabel
            self.onDataModified()
            break
        break
    return "No valid triangle label found"

  def attemptTriangleDeletion(self, pos):
    if not self.outputModel:
      return
    poly = self.outputModel.GetPolyData()

    for triIdx, tri in enumerate(self.data.vectorTagTriangles):
      if poly.GetCell(triIdx).PointInTriangle(pos, astuple(tri.p1.pos), astuple(tri.p2.pos), astuple(tri.p3.pos), 0.1):
        del self.data.vectorTagTriangles[triIdx]
        break
    self.generateEdges()
    self.onDataModified()

  def flipTriangleNormal(self, pos):
    if not self.outputModel:
      return
    poly = self.outputModel.GetPolyData()

    for triIdx, tri in enumerate(self.data.vectorTagTriangles):
      if poly.GetCell(triIdx).PointInTriangle(pos, astuple(tri.p1.pos), astuple(tri.p2.pos), astuple(tri.p3.pos), 0.1):
        # flip the 2nd and 3rd vertices
        tempPos = tri.p2
        tri.p2 = tri.p3
        tri.p3 = tempPos
        break
    self.onDataModified()

  def deletePointIdxRelatedEdges(self, globPIdx):
    delete = [key for key, ed in self.data.vectorTagEdges.items() if any(pId == globPIdx for pId in ed.edgPtIds)]
    for key in delete:
      del self.data.vectorTagEdges[key]

  def checkNormal(self, triPtIds):
    id1, id2, id3 = triPtIds

    normalGenerator = vtk.vtkPolyDataNormals()
    surface = slicer.util.getNode(self.getParameterNode().GetNodeReferenceID(PARAM_INPUT_MODEL))
    normalGenerator.SetInputData(surface.GetPolyData())
    normalGenerator.Update()
    normalPolyData = normalGenerator.GetOutput()
    normalDataFloat = normalPolyData.GetPointData().GetArray("Normals")

    vectorTagPoints = self.data.vectorTagPoints

    if normalDataFloat:
      normal1 = [0, 0, 0]
      normalDataFloat.GetTypedTuple(vectorTagPoints[id1].seq, normal1)
      normal2 = [0, 0, 0]
      normalDataFloat.GetTypedTuple(vectorTagPoints[id2].seq, normal2)
      normal3 = [0, 0, 0]
      normalDataFloat.GetTypedTuple(vectorTagPoints[id2].seq, normal3)

      import numpy as np

      normalAverage = np.array([
        (normal1[0] + normal2[0] + normal3[0]) / 3.0,
        (normal1[1] + normal2[1] + normal3[1]) / 3.0,
        (normal1[2] + normal2[2] + normal3[2]) / 3.0
      ])

      d1 = np.array([
        vectorTagPoints[id2].pos.x - vectorTagPoints[id1].pos.x,
        vectorTagPoints[id2].pos.y - vectorTagPoints[id1].pos.y,
        vectorTagPoints[id2].pos.z - vectorTagPoints[id1].pos.z
      ])

      d2 = np.array([
        vectorTagPoints[id3].pos.x - vectorTagPoints[id2].pos.x,
        vectorTagPoints[id3].pos.y - vectorTagPoints[id2].pos.y,
        vectorTagPoints[id3].pos.z - vectorTagPoints[id2].pos.z
      ])

      result = [0.0, 0.0, 0.0]
      vtk.vtkMath.Cross(d1, d2, result)
      vtk.vtkMath.Normalize(result)
      vtk.vtkMath.Normalize(normalAverage)

      cos = vtk.vtkMath.Dot(result, normalAverage)

      if cos < 0: # need to swap
        tempid = triPtIds[1]
        triPtIds[1] = triPtIds[2]
        triPtIds[2] = tempid

    return triPtIds

  def save(self):
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    logging.info(f"Saving to directory: {outputDirectory}")
    self.saveTriangulatedMesh()
    self.saveAffixVTKFile("")
    self.saveCMRepFile()
    subdividedModel = self.createSubdivideMesh()
    if subdividedModel:
      slicer.util.saveNode(subdividedModel, str(Path(outputDirectory) / f"{subdividedModel.GetName()}.vtk"))
      slicer.mrmlScene.RemoveNode(subdividedModel)

    if slicer.util.toBool(self.parameterNode.GetParameter(PARAM_GRID_MODEL_INFLATE)) is True:
      inflatedModel = self.createInflatedModel()
      slicer.util.saveNode(inflatedModel, str(Path(outputDirectory) / f"{inflatedModel.GetName()}.vtk"))
      slicer.mrmlScene.RemoveNode(inflatedModel)

  def saveAffixVTKFile(self, suffix="Temp"):
    if self.inputModel is None:
      return

    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    writer = CustomInformationWriter(self.data)
    out = f"{outputDirectory}/{self.inputModel.GetName()}{suffix}Affix.vtk"
    logging.info(f"Saving file {out}")
    writer.writeCustomDataToFile(out)

  def saveTriangulatedMesh(self):
    outputModel = self.outputModel
    if outputModel is None:
      return
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    slicer.util.saveNode(outputModel, str(Path(outputDirectory) / f"{outputModel.GetName()}.vtk"))

  def saveCMRepFile(self):
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    modelName = self.outputModel.GetName()
    outFile = Path(outputDirectory) / f"{modelName}.cmrep"

    attrs = OrderedDict({
      "Grid.Type": self.parameterNode.GetParameter(PARAM_GRID_TYPE),
      "Grid.Model.SolverType": self.parameterNode.GetParameter(PARAM_GRID_MODEL_SOLVER_TYPE),
      "Grid.Model.Atom.SubdivisionLevel": self.parameterNode.GetParameter(PARAM_GRID_MODEL_ATOM_SUBDIVISION_LEVEL),
      "Grid.Model.Coefficient.FileName": f"{modelName}.vtk",
      "Grid.Model.Coefficient.FileType": "VTK",
      "Grid.Model.nLabels": len(self.data.vectorLabelInfo)
    })

    if self.parameterNode.GetParameter(PARAM_GRID_MODEL_SOLVER_TYPE) == "PDE":
      attrs["Grid.Model.Coefficient.ConstantRho"] = \
        self.parameterNode.GetParameter(PARAM_GRID_MODEL_COEFFICIENT_CONSTANT_RHO)

    if slicer.util.toBool(self.parameterNode.GetParameter(PARAM_GRID_MODEL_COEFFICIENT_USE_CONSTANT_RADIUS)) is True:
      attrs["Grid.Model.Coefficient.ConstantRadius"] = \
        self.parameterNode.GetParameter(PARAM_GRID_MODEL_COEFFICIENT_CONSTANT_RADIUS)

    with open(outFile, "w") as f:
      for key, value in attrs.items():
        f.write(f"{key} = {value}\n")

  def createInflatedModel(self):
    try:
      outputModel = self.parameterNode.GetNodeReference(PARAM_INFLATED_MODEL)
      if not outputModel:
        outputModel = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
        self.parameterNode.SetNodeReferenceID(PARAM_INFLATED_MODEL, outputModel.GetID())
      outputModel.SetName(f"{self.inputModel.GetName()}_Inflated")
      params = {
        'inputSurface': self.outputModel.GetID(),
        'outputSurface': outputModel.GetID(),
        'rad': float(self.parameterNode.GetParameter(PARAM_GRID_MODEL_INFLATE_RADIUS))
      }
      slicer.cli.run(slicer.modules.inflatemedialmodel, None, params, wait_for_completion=True)
      return outputModel
    except Exception as exc:
      logging.debug(exc)
      return None

  def createSubdivideMesh(self):
    numberOfSubdivisions = int(self.parameterNode.GetParameter(PARAM_GRID_MODEL_ATOM_SUBDIVISION_LEVEL))

    if not numberOfSubdivisions > 0 or self.outputModel is None:
      return None

    # clean
    cleanPoly = vtk.vtkCleanPolyData()
    cleanPoly.SetInputData(self.outputModel.GetPolyData())

    # subdivide
    subdivisionFilter = vtk.vtkLoopSubdivisionFilter()
    subdivisionFilter.SetNumberOfSubdivisions(numberOfSubdivisions)
    subdivisionFilter.SetInputConnection(cleanPoly.GetOutputPort())
    subdivisionFilter.Update()
    subdivisionOutput = subdivisionFilter.GetOutput()

    # clean radius array if exists
    pointdata = subdivisionOutput.GetPointData()
    if pointdata.GetArray(SCALAR_RADIUS_NAME):
      pointdata.RemoveArray(SCALAR_RADIUS_NAME)

    fltArray1 = vtk.vtkFloatArray()
    fltArray1.SetName(SCALAR_RADIUS_NAME)

    pos = [0.0, 0.0, 0.0]
    for i in range(subdivisionOutput.GetNumberOfPoints()):
      subdivisionOutput.GetPoint(i, pos)
      _, radius = self.getClosestVertexAndRadius(pos)
      fltArray1.InsertNextValue(radius)

    pointdata.AddArray(fltArray1)

    outputModel = self.parameterNode.GetNodeReference(PARAM_SUBDIVISION_PREVIEW_MODEL)
    if not outputModel:
      outputModel = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
      self.parameterNode.SetNodeReferenceID(PARAM_SUBDIVISION_PREVIEW_MODEL, outputModel.GetID())
    outputModel.SetName(f"{self.inputModel.GetName()}_Subdivide")
    outputModel.SetAndObservePolyData(subdivisionOutput)
    return outputModel

  def readBinaryImageAndConvertToModel(self, path):
    segNode = None
    try:
      segNode = slicer.util.loadSegmentation(path)
      segmentationsLogic = slicer.modules.segmentations.logic()
      segmentationsLogic.ExportVisibleSegmentsToModels(segNode, 0)
    except RuntimeError as exc:
      slicer.util.errorDisplay(exc, "RuntimeError")
    finally:
      if segNode:
        slicer.mrmlScene.RemoveNode(segNode)


class KeyboardShortcutObserver(qt.QObject):

  def __init__(self, key, callback):
    super(KeyboardShortcutObserver, self).__init__()
    self.key = key
    self.modeCallback = callback

  def eventFilter(self, obj, event):
    if type(event) == qt.QKeyEvent and event.key() == self.key and not event.isAutoRepeat():
      # print(event)
      if event.type() == qt.QKeyEvent.KeyPress:
        self.modeCallback(True)
        logging.debug("KeyPress event")
      elif event.type() == qt.QKeyEvent.KeyRelease:
        self.modeCallback(False)
        logging.debug("KeyRelease event")
      return True

#
# SyntheticSkeletonTest
#


class SyntheticSkeletonTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear()

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SyntheticSkeleton1()

  def test_SyntheticSkeleton1(self):

    self.delayDisplay('Test passed')

