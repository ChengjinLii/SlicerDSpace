#-----------------------------------------------------------------------------
set(MODULE_NAME SlicerDDSurfer)

#-----------------------------------------------------------------------------
file(GLOB_RECURSE SHARED_PYTHON_SCRIPTS "shared/*.py")
file(GLOB_RECURSE SURFACE_PYTHON_SCRIPTS "surface/*.py")
file(GLOB_RECURSE PARCELLATION_PYTHON_SCRIPTS "parcellation/*.py")
list(FILTER PARCELLATION_PYTHON_SCRIPTS EXCLUDE REGEX "/tests/")
file(GLOB_RECURSE SEGMENTATION_PYTHON_SCRIPTS "segmentation/*.py")
file(GLOB_RECURSE MICROSTRUCTURE_PYTHON_SCRIPTS "microstructure/*.py")
file(GLOB_RECURSE TRACTOGRAPHY_PYTHON_SCRIPTS "tractography/*.py")
file(GLOB_RECURSE CONNECTOME_PYTHON_SCRIPTS "connectome/*.py")

file(GLOB_RECURSE PARCELLATION_WEIGHT_FILES "parcellation/weights/*.pkl")
file(GLOB_RECURSE SEGMENTATION_WEIGHT_FILES "segmentation/weights/*.pt")

set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  workflow_catalog.py
  ${SHARED_PYTHON_SCRIPTS}
  ${SURFACE_PYTHON_SCRIPTS}
  ${PARCELLATION_PYTHON_SCRIPTS}
  ${SEGMENTATION_PYTHON_SCRIPTS}
  ${MICROSTRUCTURE_PYTHON_SCRIPTS}
  ${TRACTOGRAPHY_PYTHON_SCRIPTS}
  ${CONNECTOME_PYTHON_SCRIPTS}
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  Resources/Data/100HCP-population-mean-T2.nii.gz
  Resources/Data/template/100307-FA.nii.gz
  Resources/Data/template/hcp_hemi-left_init_160k.obj
  Resources/Data/template/hcp_hemi-right_init_160k.obj
  Resources/Data/ckpts/hcp/DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt
  Resources/Data/ckpts/hcp/DDCSR_white_rh_Full_DualStream_no_b0_Cascaded.pt
  Resources/Data/ckpts/hcp/DDCSR_pial_lh_Full_DualStream_no_b0_Cascaded.pt
  Resources/Data/ckpts/hcp/DDCSR_pial_rh_Full_DualStream_no_b0_Cascaded.pt
  parcellation/conversion/data/FreeSurferColorLUT.txt
  ${PARCELLATION_WEIGHT_FILES}
  ${SEGMENTATION_WEIGHT_FILES}
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
