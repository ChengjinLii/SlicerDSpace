#-----------------------------------------------------------------------------
set(MODULE_NAME SlicerDDSurfer)

#-----------------------------------------------------------------------------
file(GLOB_RECURSE DDPARCEL_PYTHON_SCRIPTS "ddparcpipeline/*.py")
list(FILTER DDPARCEL_PYTHON_SCRIPTS EXCLUDE REGEX "/tests/")

file(GLOB_RECURSE DDPARCEL_WEIGHT_FILES "ddparcpipeline/weights/*.pkl")
file(GLOB_RECURSE DDSEG_PYTHON_SCRIPTS "ddsegpipeline/src/ddseg/*.py")
file(GLOB_RECURSE DDSEG_WEIGHT_FILES "ddsegpipeline/weights/*.pt")

set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  ddsurferpipeline/__init__.py
  ddsurferpipeline/preprocessing.py
  ddsurferpipeline/prediction.py
  ddsurferpipeline/postprocessing.py
  ddsurferpipeline/models/__init__.py
  ddsurferpipeline/models/cmunext_3d.py
  ddsurferpipeline/models/d_lka_attention.py
  ddsurferpipeline/models/dsc_volume_reg.py
  ddsurferpipeline/networks/__init__.py
  ddsurferpipeline/networks/tanet.py
  ddsurferpipeline/sculpting/__init__.py
  ddsurferpipeline/sculpting/surface_sculptor.py
  ${DDPARCEL_PYTHON_SCRIPTS}
  ${DDSEG_PYTHON_SCRIPTS}
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
  ${DDPARCEL_WEIGHT_FILES}
  ${DDSEG_WEIGHT_FILES}
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
