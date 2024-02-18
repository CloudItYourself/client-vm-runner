from ciy_backend_libraries.general.logging import initialize_logger

from internal_controller import LOGGER_NAME
from internal_controller.connection.vm_manager_connection import ConnectionHandler


def main():
    initialize_logger(LOGGER_NAME)
    initializer = ConnectionHandler(39019)
    initializer.run()


if __name__ == '__main__':
    main()
