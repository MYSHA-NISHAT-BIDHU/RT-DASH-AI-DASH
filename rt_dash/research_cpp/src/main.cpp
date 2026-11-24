#include "rtdash/Scheduler.hpp"

#include <iostream>
#include <vector>

int main() {
    using namespace rtdash;
    TaskSpec display{"display", 20, 50, 100, Criticality::Low, true, 0.25};
    TaskSpec alarm{"alarm", 80, 180, 0, Criticality::High, false, 1.0};
    std::vector<Job> ready;
    ready.emplace_back(display, 0, 0);
    ready.emplace_back(alarm, 0, 10);

    Scheduler scheduler(Policy::RTDASH);
    const auto index = scheduler.select(ready, Mode::Critical);
    const auto reduced = scheduler.applyCriticalModeService(ready, 0, 50, 0.10);
    std::cout << "selected=" << ready[index].task.id << " reduced_ms=" << reduced << "\n";
    return ready[index].task.id == "alarm" ? 0 : 1;
}
