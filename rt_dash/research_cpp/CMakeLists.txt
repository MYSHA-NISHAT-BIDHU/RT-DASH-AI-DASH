cmake_minimum_required(VERSION 3.16)
project(rt_dash_reference LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(rtdash src/Scheduler.cpp src/ResourceManager.cpp)
target_include_directories(rtdash PUBLIC include)
target_compile_options(rtdash PRIVATE -Wall -Wextra -Wpedantic)

add_executable(rtdash_demo src/main.cpp)
target_link_libraries(rtdash_demo PRIVATE rtdash)


add_executable(rtdash_host_simulation src/host_simulation.cpp)
target_link_libraries(rtdash_host_simulation PRIVATE rtdash)

add_executable(rtdash_tests tests/test_scheduler.cpp)
target_link_libraries(rtdash_tests PRIVATE rtdash)

enable_testing()
add_test(NAME rtdash_tests COMMAND rtdash_tests)
