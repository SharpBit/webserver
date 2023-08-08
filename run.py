from core import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(port=app.config.PORT, debug=app.config.DEBUG_MODE)
