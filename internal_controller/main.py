from internal_controller.connection.vm_manager_connection import ConnectionHandler


def main():
    initializer = ConnectionHandler(39019)
    initializer.run()


if __name__ == '__main__':
    main()
