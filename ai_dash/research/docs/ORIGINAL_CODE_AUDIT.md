# Original Project Code Audit

This audit describes the source exactly as supplied. It is not a criticism of the research objective; it explains why a validated replacement core was necessary.

## Build and portability

1. `Makefile` directory rules use Windows `if not exist` syntax under `/bin/sh`; a fresh Linux build terminates before compilation.
2. The selected FreeRTOS PC port includes `windows.h`, so it cannot compile with the documented Linux `gcc` toolchain.
3. The target name is a Windows `.exe`, but no MinGW or native Windows build contract is included.
4. Exact FreeRTOS version, board/host port, compiler, tick rate, heap size, and timer source are not frozen.
5. Two library files are zero bytes and cannot provide prediction/security functionality.

## Scheduler

1. The task type has no release, period, relative/absolute deadline, or WCET field capable of implementing EDF/RMS semantics.
2. EDF and RMS comparators both use generic priority rather than deadline or period.
3. `Scheduler::areResourcesAvailable` constructs a new empty `Resource` object for every check. Because it has no capacities, normal admission fails.
4. `checkResourceUtilization` is a stub returning `true`.
5. `calculateUtilization` sums CPU requirement rather than `C/T` or measured busy fraction.
6. `executeTask` sleeps for a constant 100 ms independent of task data.
7. There is no job-release model, preemptive execution model, deadline check, or mode state.

## Event manager and concurrency

1. `handleCriticalEvent` holds `eventMutex` and calls `adjustTasksAfterCriticalEvent`, which tries to lock the same non-recursive mutex. This can self-deadlock.
2. Normal-task priority is decremented without a lower-bound check and may violate task validation.
3. `executeAllTasks` transfers tasks to the scheduler but never calls scheduler execution.
4. Logging occurs while the event mutex is held, increasing lock duration and lock-order risk.
5. Recovery, stale-job handling, and starvation bounds are not implemented.

## Logger

`setLogLevel` acquires the logger mutex and then calls `log`, which acquires the same mutex. This is another self-deadlock path unless the implementation is changed to log outside the lock or use an internal unlocked writer.

## Resource manager

1. Allocation is not guaranteed to be transactional across all resource dimensions.
2. A failure after partially updating counters can leak capacity.
3. Callback/logging work may occur while holding a resource lock.
4. The custom FreeRTOS allocation/deallocation source uses independent static counters, so deallocation does not necessarily modify the allocation state.
5. One path holds a standard C++ mutex while delaying, which is unsafe for real-time latency.

## Dataset loading

1. The processed CSV has 36 columns, while `main.cpp` requires at least 37.
2. Field indices are shifted: the first token is a sensor state, not a timestamp/task ID.
3. As supplied, the loader can skip the entire processed dataset as malformed.
4. The project does not preserve the mapping from activity/sensor state to computation time, period, or deadline.

## Preprocessing

1. Input/output paths are hard-coded to a local Windows drive.
2. Random priority boosts and resource annotations have no seed.
3. The raw `leisure` activity is omitted from the activity mapping, producing missing values.
4. Synthetic resource columns are not measured data.
5. Duplicate timestamps and large gaps are not governed by a documented policy.
6. Exact reproduction of the supplied processed file is impossible from the script alone.

## Python simulation

1. It iterates records sequentially, immediately allocates and releases resources, and has no scheduler ready queue.
2. Critical handling only checks a priority value and does not cause mode control or preemption.
3. ARIMA is attempted on the full resource series without a controlled time-series protocol.
4. LSTM uses a random train/test split on temporal windows, allowing temporal leakage.
5. The target `CPU` also appears among input features, creating target leakage in the supplied call.
6. No deadline, response-time, preemption, recovery, or mode-transition metrics are computed.

## Tests

The supplied tests target APIs from earlier commits and do not compile against the final source. They therefore cannot establish correctness of the archived implementation.

## Corrective action

The original files were preserved. A new validated reference implementation was added rather than silently modifying evidence and presenting it as the historical implementation.
