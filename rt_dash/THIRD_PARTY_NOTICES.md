# Third-Party Notices

## Smart Home Dataset

The bundled trace-source snapshot derives from the Smart Home Dataset distributed through Mendeley Data. The manuscript cites Version 1, DOI `10.17632/zgsw84b2ff.1`. The repository states CC BY 4.0. Source attribution and the snapshot digest are recorded in `DATA_AVAILABILITY.md` and `data/SOURCE_DATA_PROVENANCE.md`.

## Python dependencies

The archive does not redistribute Python packages. Reproduction installs NumPy, pandas, Matplotlib, SciPy, tabulate, and pytest from their respective distributions. Exact versions are recorded in `environment/requirements-lock.txt`; each distribution retains its own license.

## FreeRTOS

The archive does not redistribute the FreeRTOS kernel source. `rtos/` and `firmware/` contain RT-DASH project-specific integration sources, configuration, named-target startup and linker files, and build artifacts. The archived firmware images were compiled and linked against FreeRTOS Kernel V11.1.0. To rebuild a firmware target, obtain that compatible upstream version from the official FreeRTOS distribution and place it at `rtos/FreeRTOS/` as expected by the target Makefiles.

The firmware images contain portions of FreeRTOS Kernel V11.1.0 distributed under the MIT License:

Copyright (C) 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

FreeRTOS: <https://www.freertos.org/>  
Kernel source: <https://github.com/FreeRTOS/FreeRTOS-Kernel>

## Toolchain

CMake and C++ compilers are build tools rather than redistributed components. Their recorded versions identify the original environment; they are not incorporated into this archive.
