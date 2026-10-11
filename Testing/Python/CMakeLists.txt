set(SLICERDDSURFER_TEST_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

# Match CTest coverage to Python unittest discovery. Configured GUI/science
# smoke scripts are run separately by scripts/slicer_acceptance.py.
file(GLOB SLICERDDSURFER_UNIT_TESTS CONFIGURE_DEPENDS
  "${SLICERDDSURFER_TEST_SOURCE_DIR}/test_*.py")
foreach(TEST_SCRIPT IN LISTS SLICERDDSURFER_UNIT_TESTS)
  slicer_add_python_unittest(SCRIPT "${TEST_SCRIPT}")
endforeach()
