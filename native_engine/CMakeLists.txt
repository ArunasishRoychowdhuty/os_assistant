cmake_minimum_required(VERSION 3.20)
project(os_assistant_native_engine LANGUAGES CXX)

add_library(os_assistant_native_engine SHARED native_engine.cpp)
set_target_properties(os_assistant_native_engine PROPERTIES PREFIX "")
target_compile_features(os_assistant_native_engine PRIVATE cxx_std_17)
target_compile_definitions(os_assistant_native_engine PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)

if(MSVC)
  target_compile_options(os_assistant_native_engine PRIVATE /W4 /permissive-)
else()
  target_compile_options(os_assistant_native_engine PRIVATE -Wall -Wextra)
endif()
