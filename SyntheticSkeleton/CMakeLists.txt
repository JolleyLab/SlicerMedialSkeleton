#-----------------------------------------------------------------------------
set(MODULE_NAME SyntheticSkeleton)
string(TOUPPER ${MODULE_NAME} MODULE_NAME_UPPER)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  SyntheticSkeletonLib/__init__
  SyntheticSkeletonLib/Constants
  SyntheticSkeletonLib/CustomData
  SyntheticSkeletonLib/SkeletonModel
  SyntheticSkeletonLib/Utils
  SyntheticSkeletonLib/SyntheticSkeletonSubjectHierarchyPlugin
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  Resources/Icons/add-icon.png
  Resources/Icons/delete-icon.png
  Resources/Icons/assign-icon.png
  Resources/Icons/flip-icon.png
  Resources/Icons/triangulate-icon.png
  Resources/Icons/triangle-icon.png
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)

  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)

  # Additional build-time testing
  add_subdirectory(Testing)
endif()
