# sharpbit.dev
A [website](https://sharpbit.dev/) made with Python and Sanic. It uses Bootstrap in the front-end.

### Deployment
#### Running without Docker
1. Populate the `.env` file with the necessary information as outlined in `.env.example`.
2. Install the requirements by running `pip install -r requirements.txt`.
3. Run the server with `python run.py`. The server should be up and running at `localhost:PORT`.

#### Deploy with Docker
1. Populate the `.env` file with the necessary information as outlined in `.env.example`.
2. Build and start the container in detached mode using `docker-compose up -d`.
3. Optionally, check the docker container list using `docker ps`.

#### Update with changes
1. Update the local repo with `git pull`.
2. Restart the container with `docker restart <container_id>`.
3. Optionally, check the logs with `docker logs <container_id>`.

#### Kill the server
1. Run `docker kill <container_id>`.
