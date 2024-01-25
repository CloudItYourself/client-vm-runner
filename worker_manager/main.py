import asyncio
import logging
import sys
from ciy_backend_libraries.general.logging import initialize_logger
from utilities.machine_identification import get_machine_unique_id
from worker_manager import LOGGER_NAME
from worker_manager.configuration.configuration_manager import ConfigurationManager
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms
from worker_manager.monitoring.metrics_distribution import MetricsDistribution


async def maintenance_loop(internal_vm_comms: InternalControllerComms, metrics_reporter: MetricsDistribution):
    while True:
        if internal_vm_comms.should_terminate:
            logging.getLogger(LOGGER_NAME).critical("VM Error: terminating")
            internal_vm_comms.terminate()
            sys.exit(-1)
        if metrics_reporter.should_terminate():
            logging.getLogger(LOGGER_NAME).critical("Metrics report error: terminating")
            internal_vm_comms.terminate()
            sys.exit(-1)
        await asyncio.sleep(5)


def main():
    config = ConfigurationManager()
    event_loop = asyncio.new_event_loop()
    initialize_logger(LOGGER_NAME)
    internal_vm_comms = InternalControllerComms(core_count=config.config.cpu_limit,
                                                memory_size=config.config.memory_limit,
                                                image_location=config.config.vm_image_location,
                                                qemu_installation_location=config.config.qemu_installation_location)

    machine_details = get_machine_unique_id()
    metrics_handler = MetricsDistribution(config.config.server_url, machine_details, internal_vm_comms)
    event_loop.run_until_complete(internal_vm_comms.wait_for_full_vm_connection())
    event_loop.create_task(metrics_handler.periodically_publish_details())
    event_loop.run_until_complete(maintenance_loop(internal_vm_comms, metrics_handler))


if __name__ == '__main__':
    main()
