import vtk, qt, slicer

from SyntheticSkeletonLib.CustomData import *
from SyntheticSkeletonLib.Constants import *
from SyntheticSkeletonLib.Utils import *
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from pathlib import Path
from SyntheticSkeletonLib.SyntheticSkeletonSubjectHierarchyPlugin import SyntheticSkeletonSubjectHierarchyPlugin


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
  def syntheticSkeletonModel(self):
    return self.logic.syntheticSkeletonModel

  @syntheticSkeletonModel.setter
  def syntheticSkeletonModel(self, node):
    self.logic.syntheticSkeletonModel = node

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
        self.logic.setDefaultParameters(self._parameterNode)
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
    self.shortcuts = []

  def onReload(self):
    self.cleanup()
    logging.debug(f"Reloading {self. moduleName}")
    reload(packageName='SyntheticSkeletonLib', submoduleNames=['SkeletonModel', 'Constants', 'Utils', 'CustomData'])
    ScriptedLoadableModuleWidget.onReload(self)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()
    self.deactivateModes()
    self.removeShortcutKeys()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    self.initializeUI()
    self.logic = SyntheticSkeletonLogic()

    self._selectedPoints = [] # (markupsNode.GetID(), pointID)

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    self._observations = []
    self.threeDViewClickObserver = None
    self.endPlacementObserver =  None

    self.configureUI()
    self.setupConnections()

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()
    self.installShortcutKeys()

    scriptedPlugin = slicer.qSlicerSubjectHierarchyScriptedPlugin(None)
    scriptedPlugin.setPythonSource(SyntheticSkeletonSubjectHierarchyPlugin.filePath)

  def initializeUI(self):
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/SyntheticSkeleton.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    uiWidget.setMRMLScene(slicer.mrmlScene)

  def configureUI(self):
    self.ui.outputModelSelector.enabled = False

    self.ui.syntheticSkeletonNodeSelector.setNodeTypeLabel(self.moduleName, "vtkMRMLScriptedModuleNode")
    self.ui.syntheticSkeletonNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.ui.syntheticSkeletonNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "Type", self.moduleName+"Node")
    self.ui.syntheticSkeletonNodeSelector.setMRMLScene(slicer.mrmlScene)

    # only use fiducial nodes created in this module
    self.ui.pointLabelSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "ModuleName", self.moduleName)

    self.ui.triangleLabelSelector.setNodeTypeLabel("TriangleLabel", "vtkMRMLScriptedModuleNode")
    self.ui.triangleLabelSelector.baseName = "TriangleLabel"
    self.ui.triangleLabelSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.ui.triangleLabelSelector.addAttribute("vtkMRMLScriptedModuleNode", "Type", "TriangleLabel")

    # set icons
    self.ui.placeTriangleButton.setIcon(qt.QIcon(self.resourcePath("Icons/add-icon.png")))
    self.ui.deleteTriangleButton.setIcon(qt.QIcon(self.resourcePath("Icons/delete-icon.png")))
    self.ui.assignTriangleButton.setIcon(qt.QIcon(self.resourcePath("Icons/assign-icon.png")))
    self.ui.flipNormalsButton.setIcon(qt.QIcon(self.resourcePath("Icons/flip-icon.png")))

    for pointType in TAG_TYPES:
      self.ui.pointTypeCombobox.addItem(pointType)

    tabWidget = self.ui.tabWidget
    tabBar = tabWidget.tabBar()
    tabBar.setTabIcon(0, qt.QIcon(self.resourcePath('Icons/SyntheticSkeleton.png')))
    tabBar.setTabIcon(1, qt.QIcon(self.resourcePath('Icons/triangulate-icon.png')))
    tabBar.setTabIcon(2, tabWidget.style().standardIcon(qt.QStyle.SP_DialogSaveButton))

    if hasattr(slicer.modules, "skeletontool"):
      w = slicer.modules.skeletontool.createNewWidgetRepresentation()
      tabWidget.widget(0).layout().addWidget(w)
      w.setSizePolicy(qt.QSizePolicy.MinimumExpanding, qt.QSizePolicy.Maximum)
      tabWidget.widget(0).layout().addStretch(1)
    else:
      logging.warning("slicer.modules.skeletontool could not be found. The CLI widget will be hidden.")

  def setupConnections(self):
    self.ui.syntheticSkeletonNodeSelector.currentNodeChanged.connect(self.onSyntheticSkeletonNodeSelected)
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

    self.ui.skeletonTransparencySlider.valueChanged.connect(self.onSkeletonTransparencySliderMoved)
    self.ui.meshTransparanceySlider.valueChanged.connect(self.onMeshTransparencySliderMoved)
    self.ui.pointScaleSlider.valueChanged.connect(self.onPointScaleSliderMoved)

    self.ui.subLevelSpinbox.valueChanged.connect(self.onSubdivisionLevelChanged)
    self.ui.solverTypeCombobox.currentIndexChanged.connect(lambda i: self.updateParameterNodeFromGUI())
    self.ui.constantRadiusCheckbox.toggled.connect(lambda t: self.updateParameterNodeFromGUI())
    self.ui.constantRadiusSpinbox.valueChanged.connect(lambda v: self.updateParameterNodeFromGUI())
    self.ui.inflateModelCheckbox.toggled.connect(lambda t: self.updateParameterNodeFromGUI())
    self.ui.inflateRadiusSpinbox.valueChanged.connect(lambda v: self.updateParameterNodeFromGUI())
    self.ui.snapCheckbox.toggled.connect(self.onSnapCheckboxToggled)
    self.ui.inputSkeletonColorPickerButton.colorChanged.connect(self.onInputSkeletonColorChanged)
    self.ui.coordinateSystemCombobox.activated.connect(lambda i: self.updateParameterNodeFromGUI())

    self.ui.loadBinaryImageButton.clicked.connect(
      lambda: readBinaryImageAndConvertToModel(self.ui.inputImagePathLineEdit.currentPath))

    self.ui.loadModelButton.clicked.connect(
      lambda: loadModel(self.ui.inputModelPathLineEdit.currentPath,
                        self.ui.inputCoordinateSystemCombobox.currentText))

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

    self.ui.pointLabelSelector.nodeAddedByUser.connect(self.onPointLabelAdded)
    self.ui.triangleLabelSelector.nodeAddedByUser.connect(self.onTriangleLabelAdded)

    # self.ui.pointLabelSelector.nodeAboutToBeRemoved.connect(self.onPointLabelRemoved)
    # self.ui.triangleLabelSelector.nodeAboutToBeRemoved.connect(self.onTriangleLabelRemoved)

    self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAboutToBeRemovedEvent, self.onNodeRemoved)

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onNodeRemoved(self, caller, event, node):
    logging.debug(f"onNodeRemoved {node.GetID()}")
    if isinstance(node, slicer.vtkMRMLScriptedModuleNode) and \
        node.GetAttribute('ModuleName') == self.moduleName and node.GetAttribute('Type') == "TriangleLabel" and \
        node.GetAttribute('SyntheticSkeleton') == self.ui.syntheticSkeletonNodeSelector.currentNodeID:
        self.onTriangleLabelRemoved(node)
    elif isinstance(node, slicer.vtkMRMLMarkupsFiducialNode) and node.GetAttribute('ModuleName') == self.moduleName and \
        node.GetAttribute('SyntheticSkeleton') == self.ui.syntheticSkeletonNodeSelector.currentNodeID:
      self.onPointLabelRemoved(node)

  def onPointLabelAdded(self, node):
    self.syntheticSkeletonModel.addPointLabel(node)

  def onTriangleLabelAdded(self, node):
    self.syntheticSkeletonModel.addTriangleLabel(node)

  def onPointLabelRemoved(self, node):
    self.syntheticSkeletonModel.removePointLabel(node)

  def onTriangleLabelRemoved(self, node):
    self.syntheticSkeletonModel.removeTriangleLabel(node)

  def onSnapCheckboxToggled(self, toggled):
    markupsNode = self.ui.pointLabelSelector.currentNode()
    if markupsNode is not None:
      markupsNode.SetAttribute(ATTR_TO_SURFACE, str(toggled))
      if toggled is True:
        for ptIdx in range(markupsNode.GetNumberOfControlPoints()):
          self.syntheticSkeletonModel.updatePoint(markupsNode, ptIdx)

  def onInputSkeletonColorChanged(self, color):
    node = self.ui.inputModelSelector.currentNode()
    if not node:
      return

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

  def enter(self):
    self.installShortcutKeys()

  def exit(self):
    self.removeShortcutKeys()
    self.deactivateModes()

  def installShortcutKeys(self):
    logging.debug('installShortcutKeys')
    self.removeShortcutKeys()
    keysAndCallbacks = (
      (qt.Qt.Key_A, self.onAssignTriangleKeyEvent),
      (qt.Qt.Key_S, self.onPlacePointsKeyEvent),
      (qt.Qt.Key_D, self.onDeleteTriangleKeyEvent),
      (qt.Qt.Key_F, self.onFlipTriangleKeyEvent),
      )
    for key, callback in keysAndCallbacks:
      observer = KeyboardShortcutObserver(key, callback)
      slicer.util.mainWindow().installEventFilter(observer)
      self.shortcuts.append(observer)

  def removeShortcutKeys(self):
    logging.debug('removeShortcutKeys')
    for shortcut in self.shortcuts:
      slicer.util.mainWindow().removeEventFilter(shortcut)
    self.shortcuts = []

  def onPlacePointsKeyEvent(self, pressed):
    if self.ui.markupsPlaceWidget.enabled:
      self.ui.markupsPlaceWidget.setPlaceModeEnabled(pressed)
    else:
      self.ui.markupsPlaceWidget.setPlaceModeEnabled(False)

  def onAssignTriangleKeyEvent(self, pressed):
    self.onTriangleKeyEvent(self.ui.assignTriangleButton, pressed)

  def onDeleteTriangleKeyEvent(self, pressed):
    self.onTriangleKeyEvent(self.ui.deleteTriangleButton, pressed)

  def onFlipTriangleKeyEvent(self, pressed):
    self.onTriangleKeyEvent(self.ui.flipNormalsButton, pressed)

  def onTriangleKeyEvent(self, button, pressed):
    if self.ui.triangleLabelSelector.currentNode() is not None:
      button.setChecked(pressed)
    else:
      button.setChecked(False)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.deactivateModes()
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
    self.ui.syntheticSkeletonNodeSelector.setCurrentNode(self.parameterNode.GetNodeReference(PARAM_SYNTHETIC_SKELETON))
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

    inputModel = self.syntheticSkeletonModel.getInputModelNode() if self.syntheticSkeletonModel else None
    if inputModel is not None:
      self.ui.skeletonVisibilityCheckbox.setChecked(inputModel.GetDisplayVisibility())
      self.ui.skeletonTransparencySlider.setValue(inputModel.GetDisplayNode().GetOpacity())

    outputModel = self.syntheticSkeletonModel.getOutputModelNode() if self.syntheticSkeletonModel else None
    if outputModel is not None:
      self.ui.meshVisibilityCheckbox.setChecked(outputModel.GetDisplayVisibility())
      if outputModel.GetDisplayNode():
        self.ui.meshTransparanceySlider.setValue(outputModel.GetDisplayNode().GetOpacity())

    coordinateSystem = self.parameterNode.GetParameter(PARAM_OUTPUT_MODEL_COORDINATE_SYSTEM)
    self.ui.coordinateSystemCombobox.setCurrentIndex(self.ui.coordinateSystemCombobox.findText(coordinateSystem))

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
    self.parameterNode.SetNodeReferenceID(PARAM_SYNTHETIC_SKELETON, self.ui.syntheticSkeletonNodeSelector.currentNodeID)
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
    if self.ui.activeScalarCombobox.currentText != "":
      self.parameterNode.SetParameter(PARAM_OUTPUT_MODEL_SCALAR_NAME, self.ui.activeScalarCombobox.currentText)
    self.parameterNode.SetParameter(PARAM_OUTPUT_MODEL_COORDINATE_SYSTEM, self.ui.coordinateSystemCombobox.currentText)
    self.parameterNode.EndModify(wasModified)

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

  def onSyntheticSkeletonNodeSelected(self, node):
    logging.debug("Selected synthetic skeleton node: {0}".format(node.GetName() if node else "None"))
    self.setSyntheticSkeletonNode(node)
    self.enableWidgets([self.ui.inputModelSelector], node is not None)
    self.enableWidgets([self.ui.pointLabelsCollapsibleButton, self.ui.triangleLabelsCollapsibleButton],
                       self.ui.inputModelSelector.currentNode() is not None)
    if node is not None:
      self.ui.triangleLabelSelector.addAttribute("vtkMRMLScriptedModuleNode", "SyntheticSkeleton", node.GetID())
      self.ui.pointLabelSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "SyntheticSkeleton", node.GetID())
    else:
      self.ui.triangleLabelSelector.removeAttribute("vtkMRMLScriptedModuleNode", "SyntheticSkeleton")
      self.ui.pointLabelSelector.removeAttribute("vtkMRMLMarkupsFiducialNode", "SyntheticSkeleton")

  def setSyntheticSkeletonNode(self, node):
    if self.syntheticSkeletonModel and self.syntheticSkeletonModel.getSyntheticSkeletonNode() == node:
      return

    self.ui.pointLabelSelector.setCurrentNode(None)
    self.ui.triangleLabelSelector.setCurrentNode(None)

    import SyntheticSkeletonLib
    self.syntheticSkeletonModel = SyntheticSkeletonLib.getSyntheticSkeletonModel(node)

    blockedUpdate(self.ui.inputModelSelector,
                  self.syntheticSkeletonModel.getInputModelNode() if self.syntheticSkeletonModel else None)
    self.updateInputModelColorPicker()
    self.setAndObserveOutputModel()

  def setAndObserveOutputModel(self):
    outputModel = self.syntheticSkeletonModel.getOutputModelNode() if self.syntheticSkeletonModel else None
    blockedUpdate(self.ui.outputModelSelector,
                  self.syntheticSkeletonModel.getOutputModelNode() if self.syntheticSkeletonModel else None)
    if outputModel is not None:
      self.onOutputMeshModified(outputModel)
      self.addObserver(outputModel, vtk.vtkCommand.ModifiedEvent, self.onOutputMeshModified)
    else:
      self.removeObservers(self.onOutputMeshModified)
      self.updateMeshInformation()

  def onInputModelChanged(self, node):
    if node and not node.GetPolyData().GetPointData().GetArray(SCALAR_RADIUS_NAME):
      slicer.util.errorDisplay("No 'Radius' array found in point data. "
                               "The selected model may not be a Voronoi skeleton.")
      self.ui.inputModelSelector.setCurrentNode(None)
      return

    if self.syntheticSkeletonModel:
      self.syntheticSkeletonModel.setInputModelNode(node)

    self.updateInputModelColorPicker()
    self.setAndObserveOutputModel()

    self.enableWidgets([self.ui.pointLabelsCollapsibleButton, self.ui.triangleLabelsCollapsibleButton],
                       node is not None)
    self.updateParameterNodeFromGUI()

  def updateInputModelColorPicker(self):
    node = self.ui.inputModelSelector.currentNode()
    if node is None:
      return
    color = node.GetDisplayNode().GetColor()
    wasBlocked = self.ui.inputSkeletonColorPickerButton.blockSignals(True)
    self.ui.inputSkeletonColorPickerButton.setColor(qt.QColor(color[0] * 255, color[1] * 255, color[2] * 255))
    self.ui.inputSkeletonColorPickerButton.blockSignals(wasBlocked)

  @whenDoneCall(updateParameterNodeFromGUI)
  def onActiveScalarChanged(self, array):
    outModel = self.ui.outputModelSelector.currentNode()
    if outModel is not None:
      configureDisplayNode(outModel, array)
    self.onSubdivisionLevelChanged(self.ui.subLevelSpinbox.value)

  def configureActiveScalarBox(self):
    outputModel = self.ui.outputModelSelector.currentNode()
    wasBlocked = self.ui.activeScalarCombobox.blockSignals(True)
    self.ui.activeScalarCombobox.setDataSet(outputModel.GetPolyData() if outputModel else None)
    self.ui.activeScalarCombobox.blockSignals(wasBlocked)
    if outputModel is not None and self.parameterNode is not None:
      scalarIndex = \
        self.ui.activeScalarCombobox.findText(self.parameterNode.GetParameter(PARAM_OUTPUT_MODEL_SCALAR_NAME))
      self.ui.activeScalarCombobox.setCurrentIndex(scalarIndex)

  def onOutputMeshModified(self, caller=None, event=None):
    if not self.ui.flipNormalsButton.checked:
      self.configureActiveScalarBox()
    self.updateMeshInformation()

  def updateMeshInformation(self):
    node = self.ui.outputModelSelector.currentNode()
    if node is None or node.GetPolyData() is None:
      self.ui.pointNumberLabel.setText("")
      self.ui.triangleNumberLabel.setText("")
    else:
      self.ui.pointNumberLabel.setText(str(node.GetPolyData().GetNumberOfPoints()))
      self.ui.triangleNumberLabel.setText(str(node.GetPolyData().GetNumberOfPolys()))

  @whenDoneCall(updateParameterNodeFromGUI)
  def onPointLabelSelected(self, node):
    logging.debug("onPointLabelSelected")
    self.enableWidgets([self.ui.pointTypeCombobox, self.ui.pointIndexSpinbox, self.ui.snapCheckbox],
                       node is not None)

    if not node:
      self.ui.pointTypeCombobox.setCurrentIndex(0)
      self.enableMarkupsPlaceWidget()
      return

    # type index
    typeIndex = node.GetAttribute(ATTR_TYPE_INDEX)
    if typeIndex:
      self.ui.pointTypeCombobox.setCurrentIndex(int(typeIndex))
    else:
      self.ui.pointTypeCombobox.setCurrentIndex(0)

    # anatomical index
    anatomicalIndex = node.GetAttribute(ATTR_ANATOMICAL_INDEX)
    if anatomicalIndex:
      self.ui.pointIndexSpinbox.setValue(int(anatomicalIndex))
    else:
      self.ui.pointIndexSpinbox.setValue(1)
      self.onPointAnatomicalIndexChanged(1)

    # snapping
    snapToSurface = node.GetAttribute(ATTR_TO_SURFACE)
    if snapToSurface is not None:
      wasBlocked = self.ui.snapCheckbox.blockSignals(True)
      self.ui.snapCheckbox.checked = slicer.util.toBool(snapToSurface)
      self.ui.snapCheckbox.blockSignals(wasBlocked)
    else:
      if not self.ui.snapCheckbox.checked:
        self.ui.snapCheckbox.checked = True
      else:
        self.onSnapCheckboxToggled(True)
    self.enableMarkupsPlaceWidget()

  def onPointTypeChanged(self, index):
    logging.debug("onPointTypeChanged")
    pointLabelNode = self.ui.pointLabelSelector.currentNode()
    if not pointLabelNode:
      return

    if index != 0:
      pointLabelNode.SetAttribute(ATTR_TYPE_INDEX, str(index))
    else:
      pointLabelNode.RemoveAttribute(ATTR_TYPE_INDEX)
    self.enableMarkupsPlaceWidget()

  def onPointAnatomicalIndexChanged(self, value):
    logging.debug("onPointAnatomicalIndexChanged")
    pointLabelNode = self.ui.pointLabelSelector.currentNode()
    if not pointLabelNode:
      return

    pointLabelNode.SetAttribute(ATTR_ANATOMICAL_INDEX, str(value))
    self.enableMarkupsPlaceWidget()

  def enableMarkupsPlaceWidget(self):
    pointLabelNode = self.ui.pointLabelSelector.currentNode()
    self.ui.markupsPlaceWidget.setEnabled(
      pointLabelNode is not None and \
      pointLabelNode.GetAttribute(ATTR_TYPE_INDEX) is not None and \
      pointLabelNode.GetAttribute(ATTR_ANATOMICAL_INDEX) is not None
    )

  def enableWidgets(self, widgets, condition):
    for w in widgets:
      w.setEnabled(condition)

  @whenDoneCall(updateParameterNodeFromGUI)
  def onTriangleLabelSelected(self, node):
    logging.debug("onTriangleLabelSelected")
    self.ui.placeTriangleButton.setEnabled(node is not None)
    buttons = [self.ui.placeTriangleButton, self.ui.deleteTriangleButton,
               self.ui.assignTriangleButton, self.ui.flipNormalsButton, self.ui.triangleColorPickerButton]
    self.enableWidgets(buttons, node is not None)
    if not node:
      self.deactivateModes()
      return

    for lblIdx, triLabel in enumerate(self.syntheticSkeletonModel.triangleLabels):
      if triLabel.scriptedNode is node:
        wasBlocked = self.ui.triangleIndexSpinbox.blockSignals(True)
        self.ui.triangleIndexSpinbox.value = lblIdx + 1
        self.ui.triangleIndexSpinbox.blockSignals(wasBlocked)
        break

    color = node.GetAttribute(ATTR_COLOR)
    if color:
      self.ui.triangleColorPickerButton.setColor(qt.QColor(color))
    else:
      color = qt.QColor("#ff0000")
      self.ui.triangleColorPickerButton.setColor(color)
      self.onTriangleColorChanged(color)

  def onTriangleColorChanged(self, color):
    logging.debug("onTriangleColorChanged")
    triangleNode = self.ui.triangleLabelSelector.currentNode()
    if not triangleNode:
      return

    triangleNode.SetAttribute(ATTR_COLOR, str(color))

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
    if self.syntheticSkeletonModel:
      self.syntheticSkeletonModel.setGlyphScale(value)

  @whenDoneCall(updateParameterNodeFromGUI)
  def onOutputDirectoryChanged(self, path):
    self.ui.saveButton.setEnabled(Path(path).exists())

  def updatePreview(self, checked):
    if checked:
      subdividedModel = self.logic.createSubdivideMesh()
      if subdividedModel:
        if not subdividedModel.GetDisplayNode():
          subdividedModel.CreateDefaultDisplayNodes()

        outputModel = self.syntheticSkeletonModel.getOutputModelNode()
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
    if checked and self.ui.flipNormalsButton.checked:
      self.ui.flipNormalsButton.setChecked(False)

    if checked:
      self.addObserverForPlacingTriangles()
    else:
      self.removeObserverForPlacingTriangles()

  def addObserverForPlacingTriangles(self):
    for markupsNode in self.logic.getAllMarkupNodes():
      dNode = markupsNode.GetDisplayNode()
      self._observations.append([dNode, dNode.AddObserver(dNode.JumpToPointEvent, self.onTrianglePointSelected)])

  def removeObserverForPlacingTriangles(self):
    for observedNode, observation in self._observations:
      observedNode.RemoveObserver(observation)
    self.clearSelection()

  def onTrianglePointSelected(self, caller, eventId):
    pointIdx = caller.GetActiveControlPoint()
    markupsNode = caller.GetMarkupsNode()
    selected = markupsNode.GetNthControlPointSelected(pointIdx)
    markupsNode.SetNthControlPointSelected(pointIdx, not selected)
    t = (markupsNode.GetID(), markupsNode.GetNthControlPointID(pointIdx))
    if selected is False and t in self._selectedPoints:
      self._selectedPoints.remove(t)
    else:
      self._selectedPoints.append(t)

    if len(self._selectedPoints) > 1:
      m = preCheckConstraints(self._selectedPoints)
      if m and confirmOrIgnoreDialog(m):
        self.clearLastSelection()
        return
      else:
        if len(self._selectedPoints) == 3:
          try:
            nextPtIndices = \
              self.syntheticSkeletonModel.attemptToAddTriangle(self._selectedPoints,
                                                               self.ui.triangleLabelSelector.currentNode())
            logging.debug(nextPtIndices)
            if not nextPtIndices:
              self.clearSelection()
            else:
              delete = []
              for selIdx, _ in enumerate(self._selectedPoints):
                if not selIdx in nextPtIndices:
                  delete.append(selIdx)
              for index in sorted(delete, reverse=True):
                mnId, ptId = self._selectedPoints[index]
                del self._selectedPoints[index]
                mn = slicer.util.getNode(mnId)
                pIdx = mn.GetNthControlPointIndexByID(ptId)
                mn.SetNthControlPointSelected(pIdx, True)
          except ValueError as exc:
            slicer.util.warningDisplay(exc, "Violation")
            self.clearLastSelection()

  def clearSelection(self):
    for mnId, ptId in self._selectedPoints:
      mn = slicer.util.getNode(mnId)
      ptIdx = mn.GetNthControlPointIndexByID(ptId)
      mn.SetNthControlPointSelected(ptIdx, True)
    self._selectedPoints.clear()

  def clearLastSelection(self):
    mnId, ptId = self._selectedPoints.pop(-1)
    mn = slicer.util.getNode(mnId)
    ptIdx = mn.GetNthControlPointIndexByID(ptId)
    slicer.util.getNode(mnId).SetNthControlPointSelected(ptIdx, True)

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

    modelNode = self.syntheticSkeletonModel.getOutputModelNode()
    dnode = modelNode.GetDisplayNode()
    dnode.EdgeVisibilityOn()
    dnode.SetScalarVisibility(not self.ui.flipNormalsButton.checked)

    self.ui.activeScalarCombobox.setEnabled(not self.ui.flipNormalsButton.checked)

    self.observeTriangleSelection(checked)

    self.onOutputMeshModified()

  def observeTriangleSelection(self, checked):
    try:
      pointListNode = slicer.util.getNode("F")  # points selected at position specified by this markups point list node
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
    if any(b.checked is True for b in
           buttons) and self.threeDViewClickObserver is None and self.endPlacementObserver is None:
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

  def onTriangleSelection(self, markupsNode=None, eventid=None):
    for pos in slicer.util.arrayFromMarkupsControlPoints(markupsNode):
      if self.ui.assignTriangleButton.checked:
        self.syntheticSkeletonModel.assignTriangleLabel(pos, self.ui.triangleLabelSelector.currentNode())
      elif self.ui.deleteTriangleButton.checked:
        self.syntheticSkeletonModel.removeTriangle(pos)
      elif self.ui.flipNormalsButton.checked:
        self.syntheticSkeletonModel.flipTriangleNormal(pos)
    markupsNode.RemoveAllControlPoints()

  def onEndTriangleSelectionEvent(self, caller=None, eventid=None):
    self.ui.assignTriangleButton.setChecked(False)
    self.ui.deleteTriangleButton.setChecked(False)

#
# SyntheticSkeletonLogic
#

class SyntheticSkeletonLogic(ScriptedLoadableModuleLogic):

  @property
  def parameterNode(self):
    return self.getParameterNode()

  @property
  def syntheticSkeletonModel(self):
    return self._syntheticSkeletonModel

  @syntheticSkeletonModel.setter
  def syntheticSkeletonModel(self, node):
    self._syntheticSkeletonModel = node

  @property
  def inputModel(self):
    return self._syntheticSkeletonModel.getInputModelNode() if self._syntheticSkeletonModel else None

  @property
  def outputModel(self):
    return self._syntheticSkeletonModel.getOutputModelNode() if self._syntheticSkeletonModel else None

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    self._syntheticSkeletonModel = None

  def createParameterNode(self):
    parameterNode = ScriptedLoadableModuleLogic.createParameterNode(self)
    self.setDefaultParameters(parameterNode)
    return parameterNode

  def setDefaultParameters(self, parameterNode):
    for paramName, paramDefaultValue in PARAM_DEFAULTS.items():
      if not parameterNode.GetParameter(paramName):
        parameterNode.SetParameter(paramName, str(paramDefaultValue))

  def getAllMarkupNodes(self):
    if not self.syntheticSkeletonModel:
      return []
    return [pointLabel.markupsNode for pointLabel in self.syntheticSkeletonModel.pointLabels]

  def save(self):
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    logging.debug(f"Saving to directory: {outputDirectory}")

    coordinateSystem = self.parameterNode.GetParameter(PARAM_OUTPUT_MODEL_COORDINATE_SYSTEM)
    coordinateSystemIndex = slicer.vtkMRMLModelStorageNode.GetCoordinateSystemFromString(coordinateSystem)
    useRAS = coordinateSystemIndex == slicer.vtkMRMLModelStorageNode.CoordinateSystemRAS

    self.saveTriangulatedMesh(useRAS)
    self.saveAffixVTKFile()
    self.saveCMRepFile()
    subdividedModel = self.createSubdivideMesh()

    if subdividedModel:
      saveModel(subdividedModel, str(Path(outputDirectory) / f"{subdividedModel.GetName()}.vtk"), useRAS=useRAS)
      slicer.mrmlScene.RemoveNode(subdividedModel)

    if slicer.util.toBool(self.parameterNode.GetParameter(PARAM_GRID_MODEL_INFLATE)) is True:
      inflatedModel = self.createInflatedModel()
      saveModel(inflatedModel, str(Path(outputDirectory) / f"{inflatedModel.GetName()}.vtk"), useRAS=useRAS)
      slicer.mrmlScene.RemoveNode(inflatedModel)

  def saveAffixVTKFile(self):
    if self.inputModel is None:
      return

    from CustomData import CustomInformationWriter
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    writer = CustomInformationWriter(self.syntheticSkeletonModel)
    out = f"{outputDirectory}/{self.inputModel.GetName()}Affix.vtk"
    logging.debug(f"Saving file {out}")
    writer.writeCustomDataToFile(out)

  def saveTriangulatedMesh(self, useRAS):
    outputModel = self.outputModel
    if outputModel is None:
      return
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    saveModel(outputModel, str(Path(outputDirectory) / f"{outputModel.GetName()}.vtk"), useRAS=useRAS)

  def saveCMRepFile(self):
    outputDirectory = self.parameterNode.GetParameter(PARAM_OUTPUT_DIRECTORY)
    modelName = self.outputModel.GetName()
    outFile = Path(outputDirectory) / f"{modelName}.cmrep"

    from collections import OrderedDict
    attrs = OrderedDict({
      "Grid.Type": self.parameterNode.GetParameter(PARAM_GRID_TYPE),
      "Grid.Model.SolverType": self.parameterNode.GetParameter(PARAM_GRID_MODEL_SOLVER_TYPE),
      "Grid.Model.Atom.SubdivisionLevel": self.parameterNode.GetParameter(PARAM_GRID_MODEL_ATOM_SUBDIVISION_LEVEL),
      "Grid.Model.Coefficient.FileName": f"{modelName}.vtk",
      "Grid.Model.Coefficient.FileType": "VTK",
      "Grid.Model.nLabels": len(self.syntheticSkeletonModel.triangleLabels)
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
      _, radius = self.syntheticSkeletonModel.getClosestVertexAndRadius(pos)
      fltArray1.InsertNextValue(radius)

    pointdata.AddArray(fltArray1)

    outputModel = self.parameterNode.GetNodeReference(PARAM_SUBDIVISION_PREVIEW_MODEL)
    if not outputModel:
      outputModel = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
      self.parameterNode.SetNodeReferenceID(PARAM_SUBDIVISION_PREVIEW_MODEL, outputModel.GetID())
    outputModel.SetName(f"{self.inputModel.GetName()}_Subdivide")
    outputModel.SetAndObservePolyData(subdivisionOutput)
    return outputModel


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

